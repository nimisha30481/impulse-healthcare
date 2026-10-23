import { useEffect, useRef, useState, type InputHTMLAttributes } from "react";
import clsx from "clsx";
import { CalendarDays } from "lucide-react";
import { Input } from "./primitives";

type Base = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type" | "min" | "max">;

const toText = (iso: string) => (iso ? iso.split("-").reverse().join("/") : "");

function validIso(iso: string) {
  const d = new Date(`${iso}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === iso;
}

/** Date field that always reads DD/MM/YYYY (the browser's own date box follows the browser's
 *  language, e.g. MM/DD/YYYY in US-English Chrome). Value in and out is ISO "YYYY-MM-DD". */
export function DateInput({ value, onChange, min, max, className, ...rest }: Base & {
  value: string; onChange: (iso: string) => void; min?: string; max?: string;
}) {
  const [text, setText] = useState(toText(value));
  const picker = useRef<HTMLInputElement>(null);
  useEffect(() => setText(toText(value)), [value]);

  const typed = (raw: string) => {
    const d = raw.replace(/\D/g, "").slice(0, 8);
    setText([d.slice(0, 2), d.slice(2, 4), d.slice(4)].filter(Boolean).join("/"));
    if (d.length === 0) onChange("");
    if (d.length === 8) {
      const iso = `${d.slice(4)}-${d.slice(2, 4)}-${d.slice(0, 2)}`;
      if (validIso(iso) && (!min || iso >= min) && (!max || iso <= max)) onChange(iso);
    }
  };

  return (
    <div className="relative">
      <Input {...rest} inputMode="numeric" placeholder="DD/MM/YYYY" maxLength={10} value={text}
        onChange={(e) => typed(e.target.value)} onBlur={() => setText(toText(value))} className={clsx("pr-11", className)} />
      <button type="button" aria-label="Open calendar" tabIndex={-1}
        onClick={() => { try { picker.current?.showPicker(); } catch { picker.current?.focus(); } }}
        className="absolute right-1.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-ink-3 hover:bg-surface-2 hover:text-ink">
        <CalendarDays className="h-4 w-4" />
      </button>
      <input ref={picker} type="date" tabIndex={-1} aria-hidden value={value} min={min} max={max}
        onChange={(e) => onChange(e.target.value)}
        className="pointer-events-none absolute bottom-0 right-0 h-px w-px opacity-0" />
    </div>
  );
}

/** Date (DD/MM/YYYY) + time. Value in and out is "YYYY-MM-DDTHH:MM", or "" when empty. */
export function DateTimeInput({ value, onChange, ...rest }: Base & { value: string; onChange: (v: string) => void }) {
  const [date, time] = value ? value.split("T") : ["", ""];
  return (
    <div className="grid grid-cols-[1fr_auto] gap-2">
      <DateInput {...rest} value={date} onChange={(d) => onChange(d ? `${d}T${time || "09:00"}` : "")} />
      <Input type="time" aria-label="Time" value={time?.slice(0, 5) ?? ""} className="w-32"
        onChange={(e) => date && onChange(`${date}T${e.target.value}`)} />
    </div>
  );
}
