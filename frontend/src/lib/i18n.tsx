import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { startTranslator } from "./translator";

/**
 * Interface language for the whole website. Interface text is translated (including text that
 * isn't wired through t(), via the DOM translator in translator.ts). Clinical content written by
 * doctors (dosage instructions, notes) is never machine-translated.
 */
export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "ta", label: "தமிழ்" },
  { code: "te", label: "తెలుగు" },
];

const en = {
  "nav.dashboard": "Dashboard",
  "nav.medicines": "My Medicines",
  "nav.records": "Medical Records",
  "nav.appointments": "Appointments",
  "nav.careTeam": "Care Team",
  "nav.reports": "Reports",
  "nav.notifications": "Notifications",
  "nav.settings": "Settings",
  "nav.help": "Help & Support",
  "nav.directory": "Find Care",
  "nav.messages": "Messages",
  "nav.signOut": "Sign out",
  "common.emergency": "Emergency",
  "common.today": "Today",
  "dose.markTaken": "Log dosage",
  "dose.snooze": "Snooze",
  "dose.cantTake": "I can't take it",
  "dose.details": "View details",
  "greeting.morning": "Good morning",
  "greeting.afternoon": "Good afternoon",
  "greeting.evening": "Good evening",
};
type Key = keyof typeof en;

const STORAGE_KEY = "dosewise-lang";
const storedLang = () => { try { return localStorage.getItem(STORAGE_KEY) ?? "en"; } catch { return "en"; } };

interface Ctx { lang: string; setLang: (l: string) => void }
const LangCtx = createContext<Ctx>({ lang: "en", setLang: () => {} });

/** userLang: the signed-in user's saved preference (wins); onPersist saves a change to their account. */
export function I18nProvider({ userLang, onPersist, children }: { userLang?: string; onPersist?: (l: string) => void; children: ReactNode }) {
  const [lang, setLangState] = useState(userLang ?? storedLang());
  useEffect(() => { if (userLang) setLangState(userLang); }, [userLang]);
  useEffect(() => {
    document.documentElement.lang = lang;
    return startTranslator(lang);
  }, [lang]);
  const setLang = useCallback((l: string) => {
    setLangState(l);
    try { localStorage.setItem(STORAGE_KEY, l); } catch { /* storage unavailable */ }
    onPersist?.(l);
  }, [onPersist]);
  return <LangCtx.Provider value={{ lang, setLang }}>{children}</LangCtx.Provider>;
}

export const useLanguage = () => useContext(LangCtx);
export const useLang = () => useContext(LangCtx).lang;

/** Keys render in English; the translator swaps them for the selected language. */
export function useT() {
  return (key: Key) => en[key];
}
