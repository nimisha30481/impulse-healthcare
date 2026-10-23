import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import {
  AlarmClock, BadgeCheck, Ban, CheckCircle2, CircleDashed, CircleHelp, Clock, FileScan, HelpCircle,
  MinusCircle, PauseCircle, UserRound, XCircle,
} from "lucide-react";
import { motion } from "framer-motion";
import { Badge, type Tone } from "./primitives";
import type { DoseStatus } from "@/lib/types";

/** Medication status is never conveyed by colour alone: every pill has an icon and words. */
const DOSE: Record<DoseStatus, { label: string; tone: Tone; icon: ReactNode }> = {
  upcoming: { label: "Upcoming", tone: "neutral", icon: <Clock className="h-3.5 w-3.5" /> },
  due: { label: "Due now", tone: "primary", icon: <AlarmClock className="h-3.5 w-3.5" /> },
  taken_reported: { label: "Reported taken", tone: "ok", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  missed_reported: { label: "Reported missed", tone: "danger", icon: <XCircle className="h-3.5 w-3.5" /> },
  snoozed: { label: "Snoozed", tone: "info", icon: <PauseCircle className="h-3.5 w-3.5" /> },
  skipped: { label: "Skipped", tone: "warn", icon: <MinusCircle className="h-3.5 w-3.5" /> },
  unconfirmed: { label: "Unconfirmed", tone: "warn", icon: <CircleHelp className="h-3.5 w-3.5" /> },
  awaiting_confirmation: { label: "Awaiting your reply", tone: "warn", icon: <CircleDashed className="h-3.5 w-3.5" /> },
  cancelled: { label: "Cancelled (prescription changed)", tone: "neutral", icon: <Ban className="h-3.5 w-3.5" /> },
};

export function DoseStatusPill({ status }: { status: DoseStatus }) {
  const s = DOSE[status] ?? DOSE.upcoming;
  return <Badge tone={s.tone} icon={s.icon}>{s.label}</Badge>;
}

const RX: Record<string, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  pending_verification: { label: "Pending verification", tone: "warn" },
  scheduled: { label: "Scheduled", tone: "info" },
  active: { label: "Active", tone: "ok" },
  on_hold: { label: "On hold", tone: "warn" },
  completed: { label: "Completed", tone: "neutral" },
  discontinued: { label: "Discontinued", tone: "danger" },
  superseded: { label: "Superseded", tone: "neutral" },
};

export function RxStatus({ status }: { status: string }) {
  const s = RX[status] ?? { label: status, tone: "neutral" as Tone };
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

const PROV: Record<string, { label: string; tone: Tone; icon: ReactNode }> = {
  clinician_verified: { label: "Clinician verified", tone: "ok", icon: <BadgeCheck className="h-3.5 w-3.5" /> },
  imported: { label: "Imported", tone: "info", icon: <HelpCircle className="h-3.5 w-3.5" /> },
  ocr_extracted: { label: "OCR — unverified", tone: "warn", icon: <FileScan className="h-3.5 w-3.5" /> },
  patient_reported: { label: "Patient reported", tone: "primary", icon: <UserRound className="h-3.5 w-3.5" /> },
  demo: { label: "Demo data", tone: "neutral", icon: <CircleDashed className="h-3.5 w-3.5" /> },
};

export function Provenance({ value }: { value: string }) {
  const p = PROV[value] ?? { label: value, tone: "neutral" as Tone, icon: null };
  return <Badge tone={p.tone} icon={p.icon}>{p.label}</Badge>;
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: string; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <motion.header initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="mb-1 text-sm font-medium text-primary">{eyebrow}</div>}
        <h1 className="text-2xl font-extrabold text-ink sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 text-[15px] text-ink-3">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </motion.header>
  );
}

export function SectionTitle({ title, action, icon }: { title: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <h2 className="flex items-center gap-2 text-base font-bold text-ink">{icon}{title}</h2>
      {action}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: {
  tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void; label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto rounded-xl bg-surface-2 p-1">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={clsx("relative whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors",
            value === t.id ? "text-ink" : "text-ink-3 hover:text-ink")}>
          {value === t.id && <motion.span layoutId={`tab-${label}`} className="absolute inset-0 rounded-lg bg-surface shadow-card" transition={{ duration: 0.2 }} />}
          <span className="relative">{t.label}{t.count != null && <span className="ml-1.5 text-ink-3">{t.count}</span>}</span>
        </button>
      ))}
    </div>
  );
}

export function StatCard({ label, value, hint, icon, tone = "primary" }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode; tone?: "primary" | "ok" | "warn" | "danger" | "info" }) {
  const t = { primary: "bg-primary-soft text-primary", ok: "bg-ok-soft text-ok", warn: "bg-warn-soft text-warn", danger: "bg-danger-soft text-danger", info: "bg-info-soft text-info" }[tone];
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-ink-3">{label}</span>
        {icon && <span className={clsx("grid h-8 w-8 place-items-center rounded-lg", t)}>{icon}</span>}
      </div>
      <div className="mt-2 font-display text-2xl font-extrabold text-ink">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-3">{hint}</div>}
    </div>
  );
}

export function DemoTag() {
  return <Badge tone="neutral" icon={<CircleDashed className="h-3 w-3" />}>DEMO</Badge>;
}

export function LinkCard({ to, children, className }: { to: string; children: ReactNode; className?: string }) {
  return (
    <Link to={to} className={clsx("card block p-4 transition-all hover:-translate-y-0.5 hover:shadow-lift", className)}>
      {children}
    </Link>
  );
}
