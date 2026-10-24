const TZ = "Asia/Kolkata";

export function fmtTime(iso: string, tz = TZ) {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", timeZone: tz });
}

/** DD/MM/YYYY everywhere (Indian convention), whatever the browser's language. */
export function fmtDate(iso: string | Date, opts: Intl.DateTimeFormatOptions = {}, tz = TZ) {
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: tz, ...opts });
}

export function fmtDateTime(iso: string, tz = TZ) {
  return `${fmtDate(iso, { weekday: "short" }, tz)} · ${fmtTime(iso, tz)}`;
}

export function fmtRelative(iso: string) {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

export function initials(name: string) {
  return name
    .replace(/^Dr\.?\s+/i, "")
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

export function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function greetingKey(): "greeting.morning" | "greeting.afternoon" | "greeting.evening" {
  const h = Number(new Date().toLocaleString("en-IN", { hour: "numeric", hour12: false, timeZone: TZ }));
  return h < 12 ? "greeting.morning" : h < 17 ? "greeting.afternoon" : "greeting.evening";
}

export function pct(n: number | null | undefined) {
  return n == null ? "—" : `${Math.round(n * 100)}%`;
}

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Age, sex, height, weight and BMI in one line; missing parts are left out. */
export function bodySummary(b: { age?: number | null; sex?: string | null; height_cm?: number | null; weight_kg?: number | null;
  bmi?: number | null; bmi_category?: string | null }): string {
  return [b.age != null ? `${b.age} y` : null, b.sex, b.height_cm ? `${b.height_cm} cm` : null, b.weight_kg ? `${b.weight_kg} kg` : null,
    b.bmi ? `BMI ${b.bmi}${b.bmi_category ? ` (${b.bmi_category})` : ""}` : null].filter(Boolean).join(" · ");
}
