import { createContext, useContext, type ReactNode } from "react";

/**
 * Interface-text localisation. Clinical content (dosage instructions, doctor notes) is NEVER
 * machine-translated: it is always shown exactly as the clinician wrote it.
 * Non-English strings below are a starter set awaiting professional review; anything missing
 * falls back to English.
 */
export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "kn", label: "ಕನ್ನಡ (Kannada)" },
  { code: "hi", label: "हिन्दी (Hindi)" },
  { code: "te", label: "తెలుగు (Telugu)" },
  { code: "ta", label: "தமிழ் (Tamil)" },
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
  "dose.markTaken": "Mark as taken",
  "dose.snooze": "Snooze",
  "dose.cantTake": "I can't take it",
  "dose.details": "View details",
  "greeting.morning": "Good morning",
  "greeting.afternoon": "Good afternoon",
  "greeting.evening": "Good evening",
};
type Key = keyof typeof en;

const dict: Record<string, Partial<Record<Key, string>>> = {
  en,
  hi: {
    "nav.dashboard": "डैशबोर्ड", "nav.medicines": "मेरी दवाइयाँ", "nav.records": "मेडिकल रिकॉर्ड",
    "nav.appointments": "अपॉइंटमेंट", "nav.careTeam": "देखभाल टीम", "nav.reports": "रिपोर्ट",
    "nav.notifications": "सूचनाएँ", "nav.settings": "सेटिंग्स", "nav.help": "सहायता", "nav.signOut": "साइन आउट",
    "common.emergency": "आपातकाल", "common.today": "आज", "dose.markTaken": "ले ली", "dose.snooze": "बाद में याद दिलाएँ",
    "greeting.morning": "सुप्रभात",
  },
  kn: {
    "nav.dashboard": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", "nav.medicines": "ನನ್ನ ಔಷಧಿಗಳು", "nav.records": "ವೈದ್ಯಕೀಯ ದಾಖಲೆಗಳು",
    "nav.appointments": "ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್‌ಗಳು", "nav.settings": "ಸೆಟ್ಟಿಂಗ್‌ಗಳು", "nav.signOut": "ಸೈನ್ ಔಟ್",
    "common.emergency": "ತುರ್ತು", "common.today": "ಇಂದು",
  },
  te: {
    "nav.dashboard": "డాష్‌బోర్డ్", "nav.medicines": "నా మందులు", "nav.records": "వైద్య రికార్డులు",
    "nav.appointments": "అపాయింట్‌మెంట్లు", "nav.settings": "సెట్టింగ్‌లు", "nav.signOut": "సైన్ అవుట్",
    "common.emergency": "అత్యవసరం", "common.today": "ఈ రోజు",
  },
  ta: {
    "nav.dashboard": "டாஷ்போர்டு", "nav.medicines": "என் மருந்துகள்", "nav.records": "மருத்துவ பதிவுகள்",
    "nav.appointments": "சந்திப்புகள்", "nav.settings": "அமைப்புகள்", "nav.signOut": "வெளியேறு",
    "common.emergency": "அவசரம்", "common.today": "இன்று",
  },
};

const Ctx = createContext<string>("en");

export function I18nProvider({ lang, children }: { lang: string; children: ReactNode }) {
  return <Ctx.Provider value={lang}>{children}</Ctx.Provider>;
}

export function useT() {
  const lang = useContext(Ctx);
  return (key: Key) => dict[lang]?.[key] ?? en[key];
}

export function useLang() {
  return useContext(Ctx);
}
