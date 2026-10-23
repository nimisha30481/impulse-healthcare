import { Languages } from "lucide-react";
import clsx from "clsx";
import { LANGUAGES, useLanguage } from "@/lib/i18n";

export function LanguageSelect({ compact, className }: { compact?: boolean; className?: string }) {
  const { lang, setLang } = useLanguage();
  return (
    <label className={clsx("relative inline-flex items-center", className)} data-no-translate>
      <Languages className="pointer-events-none absolute left-2.5 h-4 w-4 text-ink-3" aria-hidden />
      <span className="sr-only">Language</span>
      <select value={lang} onChange={(e) => setLang(e.target.value)}
        className={clsx("h-10 appearance-none rounded-xl border border-line bg-surface pl-8 pr-3 text-sm font-semibold text-ink hover:bg-surface-2",
          compact ? "w-[112px]" : "w-full")}>
        {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
      </select>
    </label>
  );
}
