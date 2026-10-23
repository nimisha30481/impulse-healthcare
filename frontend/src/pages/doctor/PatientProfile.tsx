import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, ClipboardPlus, FilePlus2, MessageSquare, Pause, Pencil, Play, Plus, Send, StopCircle } from "lucide-react";
import { Avatar, Badge, Button, Checkbox, Field, Input, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { RxStatus, StatCard, Tabs } from "@/components/ui/domain";
import { Timeline } from "@/pages/patient/Records";
import { AdherenceCard } from "@/features/adherence/AdherenceCard";
import { PrescriptionForm, DiscontinueForm } from "@/features/prescriptions/PrescriptionForm";
import { InteractionPanel } from "@/features/prescriptions/InteractionPanel";
import { BriefView } from "@/features/briefs/BriefView";
import { DoseLog } from "@/features/access/AccessComponents";
import { MessageThread } from "@/pages/shared/Messages";
import { api, errorMessage } from "@/lib/api";
import { fmtDate, fmtDateTime, titleCase } from "@/lib/format";
import type { MedItem } from "@/lib/types";

type Tab = "summary" | "history" | "prescriptions" | "adherence" | "communication" | "brief";

export default function DoctorPatientProfile() {
  const { patientId } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "summary";
  const setTab = (t: Tab) => setParams({ tab: t }, { replace: true });
  const q = useQuery({ queryKey: ["doctor-patient", patientId], queryFn: () => api.get(`/api/doctor/patients/${patientId}`) });
  const [rxOpen, setRxOpen] = useState<{ item?: MedItem | null } | null>(null);
  const [stop, setStop] = useState<MedItem | null>(null);
  const [brief, setBrief] = useState<any>(null);
  const qc = useQueryClient();
  const toast = useToast();

  const genBrief = useMutation({ mutationFn: () => api.post(`/api/doctor/patients/${patientId}/brief`, {}), onSuccess: (b) => { setBrief(b); setTab("brief"); }, onError: (e) => toast("danger", errorMessage(e)) });
  const status = useMutation({
    mutationFn: ({ item, s }: { item: MedItem; s: string }) => api.post(`/api/doctor/prescription-items/${item.id}/status`, { status: s, reason: s === "on_hold" ? "Held by prescriber" : s === "active" ? "Resumed by prescriber" : "Course completed", expected_lock_version: item.lock_version }),
    onSuccess: () => { toast("ok", "Status updated."); qc.invalidateQueries({ queryKey: ["doctor-patient"] }); }, onError: (e) => toast("danger", errorMessage(e)),
  });
  const refill = useMutation({ mutationFn: ({ id, approve }: { id: string; approve: boolean }) => api.post(`/api/doctor/refills/${id}`, { approve, note: approve ? "Approved" : "Please book a review first" }),
    onSuccess: () => { toast("ok", "Refill decision sent."); qc.invalidateQueries({ queryKey: ["doctor-patient"] }); } });
  const correction = useMutation({ mutationFn: ({ id, accept }: { id: string; accept: boolean }) => api.post(`/api/doctor/corrections/${id}`, { accept, note: accept ? "Correction accepted" : "Record is accurate as documented" }),
    onSuccess: () => { toast("ok", "Decision recorded; original kept in history."); qc.invalidateQueries({ queryKey: ["doctor-patient"] }); } });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96" />;
  const d = q.data;
  const p = d.patient;
  const active = d.prescriptions.filter((m: MedItem) => ["active", "on_hold", "scheduled"].includes(m.status));
  const age = p.dob ? Math.floor((Date.now() - new Date(p.dob).getTime()) / 3.156e10) : null;

  return (
    <div className="space-y-5">
      <Link to="/doctor/patients" className="inline-flex items-center gap-1 text-sm font-semibold text-ink-3 hover:text-ink"><ArrowLeft className="h-4 w-4" />Patients</Link>
      <div className="card flex flex-wrap items-center gap-4 p-5">
        <Avatar name={p.name} color={p.avatar_color} size={56} />
        <div className="flex-1">
          <h1 className="text-2xl font-extrabold">{p.name}</h1>
          <p className="text-sm text-ink-3">{p.mrn} · {age != null ? `${age} y` : "Age unknown"} · {p.sex ?? "Sex not recorded"} · Blood group {p.blood_group ?? "unknown"}</p>
          {d.access === "break_glass" && <Badge tone="danger" className="mt-1">Emergency access — read only, logged</Badge>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => genBrief.mutate()} loading={genBrief.isPending} icon={<BookOpen className="h-4 w-4" />}>Generate clinical brief</Button>
          {d.access !== "break_glass" && <Button onClick={() => setRxOpen({})} icon={<Plus className="h-4 w-4" />}>New prescription</Button>}
        </div>
      </div>
      <Tabs label="Patient sections" value={tab} onChange={setTab} tabs={[
        { id: "summary", label: "Summary" }, { id: "history", label: "Medical history" }, { id: "prescriptions", label: "Prescriptions", count: active.length },
        { id: "adherence", label: "Adherence" }, { id: "communication", label: "Communication" }, { id: "brief", label: "Clinical brief" }]} />

      {tab === "summary" && (
        <div className="grid gap-5 lg:grid-cols-2">
          <section className="card p-5">
            <h2 className="font-bold">Current medications</h2>
            <ul className="mt-3 space-y-2 text-sm">{active.map((m: MedItem) => <li key={m.id} className="flex justify-between gap-2"><span><b>{m.current.generic_name}</b> {m.current.strength} — {m.current.dose_amount} {m.current.dose_unit} {m.current.frequency_label}</span><RxStatus status={m.status} /></li>)}
              {active.length === 0 && <li className="text-ink-3">None.</li>}</ul>
          </section>
          <section className="card p-5">
            <h2 className="font-bold">Allergies</h2>
            <p className="mt-1 text-sm text-ink-2">Status: <b>{titleCase(p.allergy_status)}</b>. See the brief or history for details and provenance.</p>
            <h2 className="mt-4 font-bold">Outstanding follow-ups</h2>
            <ul className="mt-2 space-y-1 text-sm">{d.follow_ups.filter((f: any) => f.status === "open").map((f: any) => <li key={f.id}>{f.title} <span className="text-ink-3">{f.due_date && `· ${fmtDate(f.due_date)}`} {f.kind === "follow_up" && (f.appointment_id ? "· booked" : "· not booked")}</span></li>)}</ul>
          </section>
          <section className="card p-5 lg:col-span-2">
            <h2 className="font-bold">Recent encounters</h2>
            <ul className="mt-3 divide-y divide-line text-sm">{d.recent_encounters.map((r: any) => <li key={r.id} className="flex justify-between gap-2 py-2"><span><b>{r.title}</b> {r.summary && <span className="text-ink-3">— {r.summary}</span>}</span><span className="shrink-0 text-ink-3">{fmtDate(r.occurred_at)}</span></li>)}</ul>
          </section>
          {(d.refills.length > 0 || d.corrections.length > 0) && (
            <section className="card p-5 lg:col-span-2">
              <h2 className="font-bold">Requests</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {d.refills.map((r: any) => <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-surface-2 p-3">
                  <span>Refill: <b>{d.prescriptions.find((m: MedItem) => m.id === r.item_id)?.current.generic_name}</b> {r.note && `— ${r.note}`}</span>
                  <span className="flex gap-2"><Button size="sm" onClick={() => refill.mutate({ id: r.id, approve: true })}>Approve</Button><Button size="sm" variant="outline" onClick={() => refill.mutate({ id: r.id, approve: false })}>Decline</Button></span></li>)}
                {d.corrections.map((c: any) => <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-surface-2 p-3">
                  <span>Correction request: {c.description}</span>
                  <span className="flex gap-2"><Button size="sm" onClick={() => correction.mutate({ id: c.id, accept: true })}>Accept & amend</Button><Button size="sm" variant="outline" onClick={() => correction.mutate({ id: c.id, accept: false })}>Decline</Button></span></li>)}
              </ul>
            </section>
          )}
        </div>
      )}
      {tab === "history" && <Timeline patientId={p.id} />}
      {tab === "prescriptions" && (
        <div className="space-y-3">
          {d.prescriptions.map((m: MedItem) => (
            <div key={m.id} className="card p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-bold">{m.current.generic_name} {m.current.strength}</p><RxStatus status={m.status} />
                <Badge>v{m.current.version_no}</Badge>
                {m.pending_change && <Badge tone="info">v{m.pending_change.version_no} from {fmtDateTime(m.pending_change.effective_from)}</Badge>}
                <span className="ml-auto text-xs text-ink-3">{m.prescriber?.name ?? "External"} · {m.source.replace("_", " ")}</span>
              </div>
              <p className="mt-1 text-sm text-ink-2">{m.current.dose_amount} {m.current.dose_unit} · {m.current.route} · {m.current.frequency_label} · {m.current.schedule?.times_of_day?.join(", ")} · {fmtDate(m.current.start_date)} → {m.current.end_date ? fmtDate(m.current.end_date) : "ongoing"}</p>
              {d.access !== "break_glass" && ["active", "on_hold", "scheduled"].includes(m.status) && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" icon={<Pencil className="h-4 w-4" />} onClick={async () => setRxOpen({ item: await api.get(`/api/doctor/prescription-items/${m.id}`) })}>Edit</Button>
                  {m.status === "active" && <Button size="sm" variant="outline" icon={<Pause className="h-4 w-4" />} onClick={() => status.mutate({ item: m, s: "on_hold" })}>Hold</Button>}
                  {m.status === "on_hold" && <Button size="sm" variant="outline" icon={<Play className="h-4 w-4" />} onClick={() => status.mutate({ item: m, s: "active" })}>Resume</Button>}
                  <Button size="sm" variant="ghost" className="text-danger" icon={<StopCircle className="h-4 w-4" />} onClick={() => setStop(m)}>Discontinue</Button>
                </div>
              )}
            </div>
          ))}
          {d.assessments.length > 0 && <><h2 className="pt-4 font-bold">Recent safety checks</h2>{d.assessments.map((a: any) => <InteractionPanel key={a.id} a={a} />)}</>}
        </div>
      )}
      {tab === "adherence" && (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-4">
            <StatCard label="Scheduled (30d)" value={d.adherence.month.scheduled} />
            <StatCard label="Patient-reported taken" value={d.adherence.month.taken_reported} tone="ok" />
            <StatCard label="Reported missed" value={d.adherence.month.missed_reported} tone="danger" />
            <StatCard label="Unconfirmed (no data)" value={d.adherence.month.unconfirmed} tone="warn" hint="Lack of data — not proof of non-adherence" />
          </div>
          <DoseLog patientId={p.id} />
          <AdherenceCard patientId={p.id} />
          <section className="card p-5">
            <h2 className="font-bold">Patient-reported barriers</h2>
            <ul className="mt-2 space-y-1 text-sm">{d.adherence.barriers.map((b: any, i: number) => <li key={i}>{fmtDateTime(b.at)} — <b>{titleCase(b.reason ?? "other")}</b>{b.note && `: ${b.note}`}</li>)}
              {d.adherence.barriers.length === 0 && <li className="text-ink-3">None reported.</li>}</ul>
          </section>
        </div>
      )}
      {tab === "communication" && <Communication patientId={p.id} patientUserId={p.user_id} careTeam={d.care_team} />}
      {tab === "brief" && (brief ? <BriefView brief={brief} patientId={p.id} /> : (
        <Notice tone="info" title="No brief generated in this session">Generate a brief to see a source-linked summary. <button className="link" onClick={() => genBrief.mutate()}>Generate now</button></Notice>
      ))}

      {rxOpen && <PrescriptionForm patientId={p.id} item={rxOpen.item} open onClose={() => setRxOpen(null)} />}
      {stop && <DiscontinueForm item={stop} open onClose={() => setStop(null)} />}
    </div>
  );
}

function Communication({ patientId, patientUserId, careTeam }: { patientId: string; patientUserId: string; careTeam: any[] }) {
  const [open, setOpen] = useState<"instruction" | "follow_up" | null>(null);
  const [f, setF] = useState<any>({ audience: "patient", title: "", description: "", priority: "normal", requires_ack: false, due_date: "", timeframe: "", appointment_request: true });
  const [note, setNote] = useState("");
  const [kind, setKind] = useState("consultation_note");
  const qc = useQueryClient();
  const toast = useToast();
  const create = useMutation({
    mutationFn: () => api.post("/api/doctor/instructions", { ...f, kind: open, patient_id: patientId, due_date: f.due_date || null, timeframe: f.timeframe || null }),
    onSuccess: (r) => { toast("ok", r.delivery_status === "no_recipient" ? "Saved, but no authorised recipient for that audience." : "Sent."); setOpen(null); qc.invalidateQueries({ queryKey: ["doctor-patient"] }); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  const send = useMutation({
    mutationFn: () => api.post(`/api/patients/${patientId}/messages`, { recipient_id: patientUserId, body: note, kind }),
    onSuccess: () => { toast("ok", kind === "consultation_note" ? "Consultation note recorded on the timeline." : "Sent."); setNote(""); qc.invalidateQueries({ queryKey: ["messages"] }); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="card space-y-3 p-5">
        <h2 className="font-bold">Send to the patient</h2>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setOpen("instruction")} icon={<ClipboardPlus className="h-4 w-4" />}>Instruction</Button>
          <Button variant="outline" onClick={() => setOpen("follow_up")} icon={<FilePlus2 className="h-4 w-4" />}>Follow-up recommendation</Button>
        </div>
        <Select aria-label="Note type" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="consultation_note">Consultation note (added to timeline)</option><option value="follow_up_note">Follow-up note</option>
          <option value="report_request">Request updated reports</option><option value="appointment_reminder">Appointment reminder</option><option value="message">Message</option>
        </Select>
        <Textarea aria-label="Note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Write a note…" />
        <Button onClick={() => send.mutate()} disabled={!note.trim()} loading={send.isPending} icon={<Send className="h-4 w-4" />}>Send</Button>
        <p className="text-xs text-ink-3">Every item is timestamped with your name. Care team: {careTeam.map((c) => c.name).join(", ") || "patient only"}.</p>
      </section>
      <section className="card p-5"><h2 className="mb-3 flex items-center gap-2 font-bold"><MessageSquare className="h-5 w-5 text-primary" />Conversation</h2><MessageThread patientId={patientId} /></section>
      <Modal open={!!open} onClose={() => setOpen(null)} title={open === "follow_up" ? "Follow-up recommendation" : "New instruction"} size="lg"
        footer={<><Button variant="outline" onClick={() => setOpen(null)}>Cancel</Button><Button onClick={() => create.mutate()} disabled={f.title.length < 3 || f.description.length < 3} loading={create.isPending}>Send</Button></>}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Audience">{(p) => <Select {...p} value={f.audience} onChange={(e) => setF({ ...f, audience: e.target.value })}><option value="patient">Patient</option><option value="caregiver">Caregiver (if authorised)</option><option value="both">Both</option></Select>}</Field>
          <Field label="Priority">{(p) => <Select {...p} value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></Select>}</Field>
          <div className="sm:col-span-2"><Field label="Title" required>{(p) => <Input {...p} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />}</Field></div>
          <div className="sm:col-span-2"><Field label="Description" required>{(p) => <Textarea {...p} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />}</Field></div>
          {open === "follow_up" ? <>
            <Field label="Recommended by date">{(p) => <Input {...p} type="date" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} />}</Field>
            <Field label="or timeframe">{(p) => <Input {...p} placeholder="e.g. in 3 months" value={f.timeframe} onChange={(e) => setF({ ...f, timeframe: e.target.value })} />}</Field>
            <Checkbox checked={f.appointment_request} onChange={(v) => setF({ ...f, appointment_request: v })} label="Ask the patient to book an appointment" description="Shown as 'recommended — not booked' until they book." />
          </> : <>
            <Field label="Expires on">{(p) => <Input {...p} type="date" value={f.expires_on ?? ""} onChange={(e) => setF({ ...f, expires_on: e.target.value || null })} />}</Field>
            <Checkbox checked={f.requires_ack} onChange={(v) => setF({ ...f, requires_ack: v })} label="Require acknowledgement" />
          </>}
        </div>
      </Modal>
    </div>
  );
}
