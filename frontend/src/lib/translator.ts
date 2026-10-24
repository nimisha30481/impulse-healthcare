/**
 * Whole-site interface translation. Watches the DOM and replaces text nodes (and placeholder /
 * aria-label / title attributes) with their translation:
 *  1. the hand-checked dictionary in translations.ts, then
 *  2. for any other interface text, a translation fetched once from /api/i18n/translate (Amazon
 *     Bedrock, cached on the server and in this browser), so every word on the page follows the
 *     selected language.
 * Names, medicines, numbers, dates and IDs are left as written (the server prompt keeps proper nouns;
 * strings without letters are never sent). Anything inside [data-no-translate] is skipped.
 */
import { DICTIONARY, LANG_INDEX } from "./translations";

const ATTRS = ["placeholder", "aria-label", "title"] as const;
const SKIP = new Set(["SCRIPT", "STYLE", "CODE", "PRE", "TEXTAREA", "OPTION"]);
const originalText = new WeakMap<Text, string>();
const originalAttr = new WeakMap<Element, Record<string, string>>();

// remote translations: lang -> English text -> translation
const remote: Record<string, Record<string, string>> = {};
const CACHE_PREFIX = "dosewise-i18n-";
const NOT_TEXT = /^(?:[\d\s.,:;/+\-–—()%#₹$@|·•*×]+|[\w.+-]+@[\w-]+\.[\w.]+|https?:\/\/\S+|DW-[A-Z0-9]+)$/;

function remoteFor(lang: string): Record<string, string> {
  if (!remote[lang]) {
    try { remote[lang] = JSON.parse(localStorage.getItem(CACHE_PREFIX + lang) ?? "{}"); } catch { remote[lang] = {}; }
  }
  return remote[lang];
}

function lookup(s: string, idx: number, lang: string): string | undefined {
  const key = s.trim();
  if (!key) return undefined;
  const t = DICTIONARY[key]?.[idx] ?? remoteFor(lang)[key];
  return t ? s.replace(key, t) : undefined;
}

function skipped(el: Element | null): boolean {
  for (let e = el; e; e = e.parentElement) {
    if (SKIP.has(e.tagName) || e.hasAttribute("data-no-translate")) return true;
  }
  return false;
}

/** True when `value` is one of our translations of `original` (in any language). */
function isTranslationOf(value: string, original: string): boolean {
  return Object.entries(LANG_INDEX).some(([lang, i]) => lookup(original, i, lang) === value);
}

/** The English text behind `current`: the saved original if `current` is still our translation of
 *  it; otherwise React has rendered new text, which becomes the new original. */
function originalOf(current: string, known: string | undefined): string {
  return known !== undefined && (current === known || isTranslationOf(current, known)) ? known : current;
}

// ---- batching of strings the dictionary doesn't know ----
let pending = new Set<string>();
let timer: number | undefined;
const asked: Record<string, Set<string>> = {};

function want(text: string, lang: string) {
  const key = text.trim();
  if (key.length < 2 || key.length > 800 || !/[A-Za-z]/.test(key) || NOT_TEXT.test(key)) return;
  const done = (asked[lang] ??= new Set());
  if (done.has(key) || remoteFor(lang)[key]) return;
  done.add(key);
  pending.add(key);
  window.clearTimeout(timer);
  timer = window.setTimeout(() => flush(lang), 120);
}

async function flush(lang: string) {
  const batch = [...pending];
  pending = new Set();
  for (let i = 0; i < batch.length; i += 60) {
    const texts = batch.slice(i, i + 60);
    try {
      const r = await fetch("/api/i18n/translate", {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lang, texts }),
      });
      if (!r.ok) throw new Error(String(r.status));
      const { translations } = await r.json();
      Object.assign(remoteFor(lang), translations);
      try { localStorage.setItem(CACHE_PREFIX + lang, JSON.stringify(remoteFor(lang))); } catch { /* storage full */ }
    } catch {
      // server restarting or busy: forget these so the next page change asks again
      texts.forEach((t) => asked[lang]?.delete(t));
      window.setTimeout(() => { if (activeLang === lang) walk(document.body, activeIdx, lang); }, 5000);
    }
  }
  if (activeLang === lang) walk(document.body, activeIdx, lang);
}

function translateText(node: Text, idx: number, lang: string) {
  if (skipped(node.parentElement)) return;
  const current = node.nodeValue ?? "";
  const original = originalOf(current, originalText.get(node));
  const target = idx < 0 ? original : lookup(original, idx, lang);
  if (target === undefined) {
    if (idx >= 0) want(original, lang);
    return;
  }
  originalText.set(node, original);
  if (current !== target) node.nodeValue = target;
}

function translateAttrs(el: Element, idx: number, lang: string) {
  if (skipped(el)) return;
  const saved = originalAttr.get(el) ?? {};
  for (const a of ATTRS) {
    const v = el.getAttribute(a);
    if (v == null) continue;
    const orig = originalOf(v, saved[a]);
    const target = idx < 0 ? orig : lookup(orig, idx, lang);
    if (target === undefined) {
      if (idx >= 0) want(orig, lang);
      continue;
    }
    saved[a] = orig;
    if (v !== target) el.setAttribute(a, target);
  }
  originalAttr.set(el, saved);
}

function walk(root: Node, idx: number, lang: string) {
  if (root.nodeType === Node.TEXT_NODE) return translateText(root as Text, idx, lang);
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  const el = root as Element;
  translateAttrs(el, idx, lang);
  const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    if (n.nodeType === Node.TEXT_NODE) translateText(n as Text, idx, lang);
    else translateAttrs(n as Element, idx, lang);
  }
}

let activeLang = "en";
let activeIdx = -1;

/** Starts translating for `lang`; returns a cleanup function. "en" restores the originals. */
export function startTranslator(lang: string): () => void {
  const idx = lang === "en" ? -1 : (LANG_INDEX as Record<string, number>)[lang] ?? -1;
  activeLang = idx < 0 ? "en" : lang;
  activeIdx = idx;
  walk(document.body, idx, lang);
  if (idx < 0) return () => {};
  let busy = false;
  const obs = new MutationObserver((muts) => {
    if (busy) return;
    busy = true;
    for (const m of muts) {
      if (m.type === "characterData") translateText(m.target as Text, idx, lang);
      else if (m.type === "attributes") translateAttrs(m.target as Element, idx, lang);
      else m.addedNodes.forEach((n) => walk(n, idx, lang));
    }
    obs.takeRecords();
    busy = false;
  });
  obs.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...ATTRS] });
  return () => { obs.disconnect(); if (activeLang === lang) { activeLang = "en"; activeIdx = -1; } };
}
