/**
 * Whole-site interface translation. Watches the DOM and replaces text nodes (and placeholder /
 * aria-label / title attributes) whose full trimmed text matches an entry in the dictionary.
 * Only exact interface strings are translated, so medicine names, doses, doctors' notes and other
 * user content are left exactly as written. Anything inside [data-no-translate] is skipped.
 */
import { DICTIONARY, LANG_INDEX } from "./translations";

const ATTRS = ["placeholder", "aria-label", "title"] as const;
const SKIP = new Set(["SCRIPT", "STYLE", "CODE", "PRE", "TEXTAREA", "OPTION"]);
const originalText = new WeakMap<Text, string>();
const originalAttr = new WeakMap<Element, Record<string, string>>();

function lookup(s: string, idx: number): string | undefined {
  const key = s.trim();
  const row = key && DICTIONARY[key];
  if (!row) return undefined;
  const t = row[idx];
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
  return Object.values(LANG_INDEX).some((i) => lookup(original, i) === value);
}

/** The English text behind `current`: the saved original if `current` is still our translation of
 *  it; otherwise React has rendered new text, which becomes the new original. */
function originalOf(current: string, known: string | undefined): string {
  return known !== undefined && (current === known || isTranslationOf(current, known)) ? known : current;
}

function translateText(node: Text, idx: number) {
  if (skipped(node.parentElement)) return;
  const current = node.nodeValue ?? "";
  const original = originalOf(current, originalText.get(node));
  const target = idx < 0 ? original : lookup(original, idx);
  if (target === undefined) return;
  originalText.set(node, original);
  if (current !== target) node.nodeValue = target;
}

function translateAttrs(el: Element, idx: number) {
  if (skipped(el)) return;
  const saved = originalAttr.get(el) ?? {};
  for (const a of ATTRS) {
    const v = el.getAttribute(a);
    if (v == null) continue;
    const orig = originalOf(v, saved[a]);
    const target = idx < 0 ? orig : lookup(orig, idx);
    if (target === undefined) continue;
    saved[a] = orig;
    if (v !== target) el.setAttribute(a, target);
  }
  originalAttr.set(el, saved);
}

function walk(root: Node, idx: number) {
  if (root.nodeType === Node.TEXT_NODE) return translateText(root as Text, idx);
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  const el = root as Element;
  translateAttrs(el, idx);
  const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    if (n.nodeType === Node.TEXT_NODE) translateText(n as Text, idx);
    else translateAttrs(n as Element, idx);
  }
}

/** Starts translating for `lang`; returns a cleanup function. "en" restores the originals. */
export function startTranslator(lang: string): () => void {
  const idx = lang === "en" ? -1 : (LANG_INDEX as Record<string, number>)[lang] ?? -1;
  walk(document.body, idx);
  if (idx < 0) return () => {};
  let busy = false;
  const obs = new MutationObserver((muts) => {
    if (busy) return;
    busy = true;
    for (const m of muts) {
      if (m.type === "characterData") translateText(m.target as Text, idx);
      else if (m.type === "attributes") translateAttrs(m.target as Element, idx);
      else m.addedNodes.forEach((n) => walk(n, idx));
    }
    obs.takeRecords();
    busy = false;
  });
  obs.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...ATTRS] });
  return () => obs.disconnect();
}
