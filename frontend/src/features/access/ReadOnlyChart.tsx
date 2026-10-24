import { Activity, AlertTriangle, CheckCircle2, Clock, FileText, Phone, Pill, Printer, XCircle } from "lucide-react";
import { Badge, Button } from "@/components/ui/primitives";
import { Notice } from "@/components/ui/feedback";
import { Provenance } from "@/components/ui/domain";
import { fmtDate, fmtDateTime, pct, titleCase, bodySummary } from "@/lib/format";

const DOSE_STATE: Record<string, { label: string; tone: any; icon: any }> = {
  taken: { label: "Taken", tone: "ok", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  late: { label: "Taken late", tone: "warn", icon: <Clock className="h-3.5 w-3.5" /> },
  missed: { label: "Missed", tone: "danger", icon: <XCircle className="h-3.5 w-3.5" /> },
  not_logged: { label: "Not logged", tone: "neutral", icon: <Clock className="h-3.5 w-3.5" /> },
  pending: { label: "Due / upcoming", tone: "info", icon: <Clock className="h-3.5 w-3.5" /> },
};

export function DoseStateBadge({ state }: { state: string }) {
  const s = DOSE_STATE[state] ?? DOSE_STATE.pending;
  return <Badge tone={s.tone} icon={s.icon}>{s.label}</Badge>;
}

/** Read-only clinical chart shown to guest doctors (no editing controls anywhere). */
export function ReadOnlyChart({ data, onNewSearch, secondsLeft }: { data: any; onNewSearch: () => void; secondsLeft?: number }) {
  const p = data.patient;
  return (
    <div className="space-y-5 print:space-y-3">
      <div className="card flex flex-wrap items-center gap-3 border-primary/30 bg-primary-soft/40 p-4">
        <Badge tone="primary">Read-only guest session</Badge>
        <p className="flex-1 text-sm text-ink-2">Opened with Access ID <b className="font-mono">{data.session.access_id}</b> by {data.session.viewer} · {fmtDateTime(data.generated_at)}</p>
        <div className="flex gap-2 print:hidden">
          <Button size="sm" variant="outline" onClick={() => window.print()} icon={<Printer className="h-4 w-4" />}>Print chart</Button>
          {secondsLeft != null && (
            <Badge tone={secondsLeft < 120 ? "danger" : "warn"} icon={<Clock className="h-3.5 w-3.5" />}>
              Closes in {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}
            </Badge>
          )}
          <Button size="sm" onClick={onNewSearch}>End session</Button>
        </div>
      </div>

      <div className="card grid gap-4 p-5 lg:grid-cols-[1.4fr_1fr_1fr_1.2fr]">
        <div>
          <h2 className="text-2xl font-extrabold">{p.name}</h2>
          <p className="text-sm text-ink-3">{p.dob ? `DOB ${fmtDate(p.dob)}` : "DOB not recorded"} · {bodySummary(p) || "Sex not recorded"}{p.phone && ` · ${p.phone}`}</p>
        </div>
        <div className="rounded-xl border border-line p-3 text-center"><p className="text-xs text-ink-3">Blood group</p><p className="font-display text-xl font-extrabold text-danger">{p.blood_group ?? "Unknown"}</p></div>
        <div className="rounded-xl border border-danger/30 bg-danger-soft/40 p-3 text-center">
          <p className="text-xs text-ink-3">Allergies</p>
          <p className="font-bold text-danger">{data.allergies.length ? data.allergies.map((a: any) => a.substance).join(", ") : data.allergy_status === "none_known" ? "None known" : "Unknown — not recorded"}</p>
        </div>
        <div className="rounded-xl border border-line p-3"><p className="text-xs text-ink-3">Emergency contact</p>
          {p.emergency_contact.name ? <p className="flex items-center gap-1.5 text-sm font-semibold"><Phone className="h-3.5 w-3.5 text-ok" />{p.emergency_contact.name}{p.emergency_contact.phone && `: ${p.emergency_contact.phone}`}</p> : <p className="text-sm">Not recorded</p>}</div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card flex items-center gap-3 p-4"><Activity className="h-5 w-5 text-primary" /><div><p className="font-display text-2xl font-extrabold">{pct(data.adherence.reported_rate)}</p><p className="text-xs text-ink-3">30-day reported adherence</p></div></div>
        <div className="card flex items-center gap-3 p-4"><Pill className="h-5 w-5 text-primary" /><div><p className="font-display text-2xl font-extrabold">{data.active_medications.length}</p><p className="text-xs text-ink-3">Active prescriptions</p></div></div>
        <div className="card flex items-center gap-3 p-4"><CheckCircle2 className="h-5 w-5 text-ok" /><div><p className="font-display text-2xl font-extrabold">{data.adherence.taken_reported} doses</p><p className="text-xs text-ink-3">Logged as taken (30 days)</p></div></div>
      </div>

      <section className="card overflow-x-auto p-5">
        <h3 className="flex items-center gap-2 font-bold"><Pill className="h-4 w-4 text-primary" />Active medications & dosing schedule</h3>
        {data.active_medications.length === 0 ? <p className="mt-2 text-sm text-ink-3">No active medications recorded in DoseWISE.</p> : (
          <table className="mt-3 w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs uppercase text-ink-3"><tr><th className="py-2">Medication</th><th>Generic</th><th>Dose</th><th>Frequency</th><th>Instructions</th><th>Prescribed</th></tr></thead>
            <tbody>{data.active_medications.map((m: any, i: number) => (
              <tr key={i} className="border-t border-line align-top"><td className="py-2 font-semibold text-primary">{m.name} {m.strength}</td><td>{m.generic_name}</td>
                <td><Badge tone="info">{m.dose}</Badge></td><td>{m.frequency}{m.times.length > 0 && <span className="block text-xs text-ink-3">{m.times.join(", ")}</span>}</td>
                <td className="text-ink-2">{m.instructions ?? "—"}</td><td>{fmtDate(m.prescribed)}</td></tr>))}</tbody>
          </table>
        )}
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card p-5">
          <h3 className="font-bold">Recent dose history</h3>
          <ul className="mt-3 space-y-2">{data.dose_history.map((d: any) => (
            <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line px-3 py-2 text-sm">
              <span><b>{d.medication}</b> <span className="text-ink-3">{d.dose}</span></span>
              <span className="flex items-center gap-2 text-xs text-ink-3">{fmtDateTime(d.scheduled_at)}<DoseStateBadge state={d.state} /></span>
            </li>))}
            {data.dose_history.length === 0 && <li className="text-sm text-ink-3">No doses recorded yet.</li>}</ul>
        </section>
        <section className="card p-5">
          <h3 className="flex items-center gap-2 font-bold"><FileText className="h-4 w-4 text-primary" />Conditions, consultations & reports</h3>
          {data.conditions.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{data.conditions.map((c: any) => <Badge key={c.name}>{c.name}{c.code && ` (${c.code})`}</Badge>)}</div>}
          <ul className="mt-3 space-y-2">{data.records.map((r: any, i: number) => (
            <li key={i} className="rounded-xl border border-line px-3 py-2 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2"><b>{r.title}</b><span className="text-xs text-ink-3">{fmtDate(r.date)}</span></div>
              <p className="text-ink-2">{titleCase(r.type)}{r.summary && ` — ${r.summary}`}</p><Provenance value={r.provenance} />
            </li>))}</ul>
        </section>
      </div>
      <Notice tone="warn" icon={<AlertTriangle className="h-[18px] w-[18px]" />}>{data.notice} This view is logged and the patient has been notified.</Notice>
    </div>
  );
}
