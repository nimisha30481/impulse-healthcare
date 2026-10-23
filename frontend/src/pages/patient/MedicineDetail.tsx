import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, CalendarClock, ExternalLink, HelpCircle, History, Pill, RefreshCw, ShieldAlert, Utensils } from "lucide-react";
import type { ReactNode } from "react";
import { Badge, Button, Skeleton, Textarea } from "@/components/ui/primitives";
import { ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader, RxStatus } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, fmtDateTime, titleCase, WEEKDAYS } from "@/lib/format";
import type { MedItem } from "@/lib/types";

function Block({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="card p-5">
      <h2 className="flex items-center gap-2 text-base font-bold"><span className="text-primary">{icon}</span>{title}</h2>
      <div className="mt-3 text-[15px] text-ink-2">{children}</div>
    </section>
  );
}

export function MedicineDetailView({ patientId, itemId, back }: { patientId: string; itemId: string; back: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["medication", itemId], queryFn: () => api.get<MedItem>(`/api/patients/${patientId}/medications/${itemId}`) });
  const [refillOpen, setRefillOpen] = useState(false);
  const [note, setNote] = useState("");
  const refill = useMutation({
    mutationFn: () => api.post(`/api/patients/${patientId}/refills`, { item_id: itemId, note }),
    onSuccess: (r) => { toast("ok", r.note); setRefillOpen(false); qc.invalidateQueries({ queryKey: ["refills"] }); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <div className="space-y-4"><Skeleton className="h-12 w-1/2" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;
  const m = q.data;
  const v = m.current;
  const s = v.schedule;
  const days = s?.days_of_week?.length ? s.days_of_week.map((d) => WEEKDAYS[d]).join(", ") : s?.interval_days && s.interval_days > 1 ? `every ${s.interval_days} days` : "every day";

  return (
    <div className="space-y-5">
      <Link to={back} className="inline-flex items-center gap-1 text-sm font-semibold text-ink-3 hover:text-ink"><ArrowLeft className="h-4 w-4" />Back</Link>
      <PageHeader title={`${v.generic_name} ${v.strength}`} subtitle={v.brand_name ? `Brand: ${v.brand_name}` : undefined}
        eyebrow={<RxStatus status={m.status} />}
        actions={["active", "on_hold"].includes(m.status) ? <Button variant="outline" icon={<RefreshCw className="h-4 w-4" />} onClick={() => setRefillOpen(true)}>Request refill</Button> : undefined} />

      {m.pending_change && <Notice tone="info" title="A change is scheduled">From {fmtDateTime(m.pending_change.effective_from)}: {m.pending_change.dose_amount} {m.pending_change.dose_unit}, {m.pending_change.frequency_label}. Reason: {m.pending_change.change_reason}</Notice>}
      {m.discontinue && <Notice tone="warn" title={`Discontinued ${fmtDate(m.discontinue.effective)}`}>{m.discontinue.reason}{m.discontinue.instructions && <><br />Instructions: {m.discontinue.instructions}</>}</Notice>}
      {m.hold_reason && <Notice tone="warn" title="On hold">{m.hold_reason}</Notice>}

      <section className="card p-5">
        <h2 className="text-base font-bold">Medication overview</h2>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-4">
          {[["Generic name", v.generic_name], ["Brand", v.brand_name ?? "—"], ["Strength", v.strength], ["Form", titleCase(v.dosage_form)],
            ["Dose", `${v.dose_amount} ${v.dose_unit}`], ["Route", titleCase(v.route)], ["Frequency", v.frequency_label],
            ["Timing", s?.times_of_day?.join(", ") || (v.is_prn ? "As needed" : "—")], ["Start date", fmtDate(v.start_date)],
            ["End date", v.end_date ? fmtDate(v.end_date) : "Ongoing"], ["Prescriber", m.prescriber?.name ?? "External provider"],
            ["Prescription status", titleCase(m.status)]].map(([k, val]) => (
            <div key={k}><dt className="text-ink-3">{k}</dt><dd className="font-semibold text-ink">{val}</dd></div>
          ))}
        </dl>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Block icon={<BookOpen className="h-5 w-5" />} title="What is this medicine?">
          {m.education?.available ? <p>{m.education.content.simple}</p> : (
            <>
              <p>Reliable, reviewed information for this medicine isn't connected to DoseWISE yet, so we don't show a description here.</p>
              <a className="link mt-2 inline-flex items-center gap-1" href={`https://medlineplus.gov/druginfo/meds.html`} target="_blank" rel="noreferrer">
                Look it up on MedlinePlus (U.S. National Library of Medicine) <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </>
          )}
        </Block>
        <Block icon={<HelpCircle className="h-5 w-5" />} title="Why am I taking it?">
          {v.indication ? <p>Your prescription records the reason as: <b className="text-ink">{v.indication}</b>.</p> :
            <p>The reason wasn't recorded on this prescription. Ask your doctor — DoseWISE never guesses a diagnosis from a medicine name.</p>}
        </Block>
        <Block icon={<CalendarClock className="h-5 w-5" />} title="When should I take it?">
          {v.is_prn ? <p>Only when needed, as your doctor explained.</p> : <p><b className="text-ink">{s?.times_of_day?.join(", ")}</b>, {days}{s?.timezone ? ` (${s.timezone})` : ""}.</p>}
          {v.food_instructions && <p className="mt-2 flex items-center gap-1.5"><Utensils className="h-4 w-4" />{v.food_instructions}</p>}
        </Block>
        <Block icon={<Pill className="h-5 w-5" />} title="How should I take it?">
          <p>{v.dose_amount} {v.dose_unit}, {v.route}.</p>
          {v.special_instructions && <p className="mt-2">{v.special_instructions}</p>}
        </Block>
        <Block icon={<ShieldAlert className="h-5 w-5" />} title="Precautions">
          <p>Verified information about side effects, warnings, food interactions and storage isn't available yet. Your pharmacist's leaflet is the best source.</p>
          <p className="mt-3 font-semibold text-ink">If you miss a dose</p>
          <p>{v.missed_dose_guidance ?? "Your doctor hasn't added missed-dose guidance for this medicine. Don't double the next dose — ask your doctor or pharmacist."}</p>
          {m.interaction && (
            <Notice tone={m.interaction.drug_drug_state === "assessed" ? "info" : "warn"} title="Interaction check">{m.interaction.patient_message}</Notice>
          )}
        </Block>
      </div>

      <section className="card p-5">
        <h2 className="flex items-center gap-2 text-base font-bold"><History className="h-5 w-5 text-primary" />Prescription history</h2>
        <ol className="mt-4 space-y-4 border-l-2 border-line pl-5">
          {m.versions?.map((ver) => (
            <li key={ver.id} className="relative">
              <span className="absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-surface bg-primary" />
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold">Version {ver.version_no}</p>
                <Badge tone={ver.status === "current" ? "ok" : ver.status === "scheduled" ? "info" : "neutral"}>{titleCase(ver.status)}</Badge>
                <span className="text-xs text-ink-3">{fmtDateTime(ver.created_at)} · {ver.author?.name ?? "Prescriber"}</span>
              </div>
              <p className="mt-1 text-sm text-ink-2">{ver.dose_amount} {ver.dose_unit} · {ver.route} · {ver.frequency_label} · {ver.schedule?.times_of_day?.join(", ")}</p>
              {ver.change_reason && <p className="text-sm text-ink-3">Reason: {ver.change_reason}</p>}
            </li>
          ))}
        </ol>
      </section>

      {m.events && m.events.length > 0 && (
        <section className="card p-5">
          <h2 className="text-base font-bold">Recent dose activity</h2>
          <ul className="mt-3 divide-y divide-line text-sm">
            {m.events.slice(0, 15).map((e) => (
              <li key={e.id} className="flex justify-between gap-3 py-2">
                <span>{titleCase(e.kind)}{e.reason ? ` — ${titleCase(e.reason)}` : ""}</span>
                <span className="text-ink-3">{fmtDateTime(e.at)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Modal open={refillOpen} onClose={() => setRefillOpen(false)} title="Request a refill" size="sm"
        footer={<><Button variant="outline" onClick={() => setRefillOpen(false)}>Cancel</Button><Button onClick={() => refill.mutate()} loading={refill.isPending}>Send request</Button></>}>
        <p className="text-sm text-ink-2">Your doctor will review this. Refills are never approved automatically.</p>
        <Textarea className="mt-3" aria-label="Note for your doctor" placeholder="Optional note" value={note} onChange={(e) => setNote(e.target.value)} />
      </Modal>
    </div>
  );
}

export default function MedicineDetail() {
  const { itemId } = useParams();
  const { user } = useAuth();
  return <MedicineDetailView patientId={user!.patient_id!} itemId={itemId!} back="/patient/medicines" />;
}
