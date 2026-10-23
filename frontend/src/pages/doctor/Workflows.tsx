/** Smaller doctor pages: Prescriptions hub, Adherence alerts, Clinical briefs, Follow-ups, Verification. */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, BadgeCheck, BookOpen, CheckCircle2, ClipboardList, FileText, Pill, Plus, XCircle } from "lucide-react";
import { Avatar, Badge, Button, Field, Input, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { BriefView } from "@/features/briefs/BriefView";
import { PrescriptionForm } from "@/features/prescriptions/PrescriptionForm";
import { api, errorMessage } from "@/lib/api";
import { fmtDate, fmtDateTime } from "@/lib/format";

export function PrescriptionsHub() {
  const pts = useQuery({ queryKey: ["doctor-patients", "", ""], queryFn: () => api.get("/api/doctor/patients") });
  const [pid, setPid] = useState("");
  const [open, setOpen] = useState(false);
  return (
    <>
      <PageHeader title="Prescriptions" subtitle="Create prescriptions for authorised patients. Edit or discontinue from a patient's profile." />
      <section className="card max-w-2xl p-5">
        <h2 className="font-bold">New prescription</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <Select aria-label="Patient" className="flex-1" value={pid} onChange={(e) => setPid(e.target.value)}>
            <option value="">Choose a patient…</option>
            {pts.data?.map((p: any) => <option key={p.id} value={p.id}>{p.name} ({p.mrn})</option>)}
          </Select>
          <Button disabled={!pid} onClick={() => setOpen(true)} icon={<Plus className="h-4 w-4" />}>Start</Button>
        </div>
      </section>
      <h2 className="mb-3 mt-8 font-bold">Patients with active treatment</h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {pts.data?.filter((p: any) => p.flags.active_treatment).map((p: any) => (
          <li key={p.id}><Link to={`/doctor/patients/${p.id}?tab=prescriptions`} className="card flex items-center gap-3 p-4 hover:shadow-lift">
            <Avatar name={p.name} color={p.avatar_color} size={36} /><span className="flex-1 font-semibold">{p.name}</span><Pill className="h-4 w-4 text-primary" />
          </Link></li>
        ))}
      </ul>
      {open && pid && <PrescriptionForm patientId={pid} open onClose={() => setOpen(false)} />}
    </>
  );
}

export function AdherenceAlertsPage() {
  const q = useQuery({ queryKey: ["doctor-dashboard"], queryFn: () => api.get("/api/doctor/dashboard") });
  if (q.isError) return <ErrorState error={q.error} />;
  return (
    <>
      <PageHeader title="Adherence Alerts" subtitle="Patients whose recent doses are unconfirmed after reminders, follow-ups and check-ins." />
      <Notice tone="info">Unconfirmed means no response was received — it is a lack of data, not proof that doses were missed.</Notice>
      <div className="mt-5">
        {q.isLoading ? <Skeleton className="h-40" /> : q.data.adherence_alerts.length === 0 ? <EmptyState icon={<Activity className="h-6 w-6" />} title="No open adherence alerts" /> : (
          <ul className="space-y-2">{q.data.adherence_alerts.map((a: any) => (
            <li key={a.patient_id}><Link to={`/doctor/patients/${a.patient_id}?tab=adherence`} className="card flex flex-wrap items-center gap-3 p-4 hover:shadow-lift">
              <Avatar name={a.patient_name} size={36} />
              <div className="flex-1"><p className="font-semibold">{a.patient_name}</p><p className="text-xs text-ink-3">Since {fmtDateTime(a.since)}</p></div>
              <Badge tone="warn">{a.consecutive_unconfirmed} consecutive unconfirmed</Badge><Badge tone="info">Escalation stage {a.stage}</Badge>
            </Link></li>))}</ul>
        )}
      </div>
    </>
  );
}

export function BriefsPage() {
  const { briefId } = useParams();
  const nav = useNavigate();
  const list = useQuery({ queryKey: ["briefs"], queryFn: () => api.get("/api/doctor/briefs") });
  const one = useQuery({ queryKey: ["brief", briefId], queryFn: () => api.get(`/api/doctor/briefs/${briefId}`), enabled: !!briefId });
  return (
    <>
      <PageHeader title="Clinical Briefs" subtitle="Automatically assembled, source-linked summaries for new consultations. Generate one from a patient profile." />
      {briefId ? (one.data ? <><Button variant="ghost" size="sm" onClick={() => nav("/doctor/briefs")}>← All briefs</Button><div className="mt-3"><BriefView brief={one.data} patientId={one.data.patient_id} /></div></> : <Skeleton className="h-64" />) :
        list.isLoading ? <Skeleton className="h-40" /> : list.data.length === 0 ? <EmptyState icon={<BookOpen className="h-6 w-6" />} title="No briefs yet" body="Open a patient and choose 'Generate clinical brief'." /> : (
          <ul className="space-y-2">{list.data.map((b: any) => (
            <li key={b.id}><Link to={`/doctor/briefs/${b.id}`} className="card flex flex-wrap items-center gap-3 p-4 hover:shadow-lift">
              <BookOpen className="h-5 w-5 text-primary" /><span className="flex-1 font-semibold">{b.patient_name}</span>
              <span className="text-xs text-ink-3">{fmtDateTime(b.created_at)}</span>
              {b.missing > 0 && <Badge tone="warn">{b.missing} missing</Badge>}{b.conflicts > 0 && <Badge tone="danger">{b.conflicts} conflicts</Badge>}
            </Link></li>))}</ul>
        )}
    </>
  );
}

export function FollowUpsPage() {
  const [status, setStatus] = useState("open");
  const q = useQuery({ queryKey: ["follow-ups", status], queryFn: () => api.get(`/api/doctor/follow-ups?status=${status}`) });
  const qc = useQueryClient();
  const toast = useToast();
  const done = useMutation({ mutationFn: (id: string) => api.post(`/api/doctor/follow-ups/${id}/complete`), onSuccess: () => { toast("ok", "Marked complete."); qc.invalidateQueries({ queryKey: ["follow-ups"] }); } });
  return (
    <>
      <PageHeader title="Follow-ups" subtitle="Recommended follow-ups you created, and whether patients have booked them."
        actions={<Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="open">Open</option><option value="completed">Completed</option></Select>} />
      {q.isLoading ? <Skeleton className="h-40" /> : q.data.length === 0 ? <EmptyState icon={<ClipboardList className="h-6 w-6" />} title="Nothing here" /> : (
        <ul className="space-y-2">{q.data.map((f: any) => (
          <li key={f.id} className="card flex flex-wrap items-center gap-3 p-4">
            <div className="flex-1"><Link to={`/doctor/patients/${f.patient_id}`} className="font-semibold hover:underline">{f.patient_name}</Link><p className="text-sm text-ink-2">{f.title}</p>
              <p className="text-xs text-ink-3">{f.due_date ? `Recommended by ${fmtDate(f.due_date)}` : f.timeframe}</p></div>
            {f.kind === "follow_up" ? (f.appointment_id ? <Badge tone="ok">Booked</Badge> : <Badge tone="warn">Recommended — not booked</Badge>) : <Badge>Instruction</Badge>}
            {f.requires_ack && <Badge tone={f.acknowledged_at ? "ok" : "neutral"}>{f.acknowledged_at ? "Acknowledged" : "Awaiting acknowledgement"}</Badge>}
            {f.status === "open" && <Button size="sm" variant="outline" onClick={() => done.mutate(f.id)}>Complete</Button>}
          </li>))}</ul>
      )}
    </>
  );
}

const FORMS = ["tablet", "capsule", "syrup", "suspension", "injection", "inhaler", "drops", "cream", "ointment", "patch", "powder", "solution", "spray"];
const UNITS = ["tablet", "capsule", "mg", "mcg", "g", "ml", "drop", "puff", "unit", "patch", "sachet", "application"];

export function VerificationPage() {
  const q = useQuery({ queryKey: ["verifications"], queryFn: () => api.get("/api/doctor/verifications") });
  const [sel, setSel] = useState<any>(null);
  return (
    <>
      <PageHeader title="Prescription Verification" subtitle="Uploaded prescriptions reviewed by patients. Nothing activates until you approve it." />
      {q.isError ? <ErrorState error={q.error} /> : q.isLoading ? <Skeleton className="h-40" /> : q.data.length === 0 ? <EmptyState icon={<BadgeCheck className="h-6 w-6" />} title="Queue is empty" /> : (
        <ul className="space-y-2">{q.data.map((e: any) => (
          <li key={e.id} className="card flex flex-wrap items-center gap-3 p-4">
            <FileText className="h-5 w-5 text-primary" />
            <div className="flex-1"><p className="font-semibold">{e.patient_name} · {e.document.title}</p><p className="text-xs text-ink-3">Uploaded {fmtDateTime(e.document.created_at)} · engine {e.engine}{e.confidence != null && ` · confidence ${Math.round(e.confidence * 100)}%`}</p></div>
            <Badge tone={e.status === "patient_reviewed" ? "warn" : "neutral"}>{e.status === "patient_reviewed" ? "Ready to verify" : "Awaiting patient review"}</Badge>
            <Button size="sm" disabled={e.status !== "patient_reviewed"} onClick={() => setSel(e)}>Verify</Button>
          </li>))}</ul>
      )}
      {sel && <VerifyModal e={sel} onClose={() => setSel(null)} />}
    </>
  );
}

function parseDose(d: string) {
  const m = /([\d.]+)\s*(\w+)?/.exec(d || "");
  return { amount: m ? Number(m[1]) : 1, unit: m?.[2] && UNITS.includes(m[2].replace(/s$/, "")) ? m[2].replace(/s$/, "") : "tablet" };
}

function VerifyModal({ e, onClose }: { e: any; onClose: () => void }) {
  const src = e.patient_corrected ?? e.extracted;
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  const [items, setItems] = useState<any[]>(() => (src.medications ?? []).map((m: any) => {
    const d = parseDose(m.dose);
    return { generic_name: m.name, strength: m.strength || "", dosage_form: "tablet", dose_amount: d.amount, dose_unit: d.unit, route: m.route?.toLowerCase() || "oral",
      frequency_label: m.frequency || "Once daily", times_of_day: ["09:00"], start_date: today, is_prn: false };
  }));
  const [note, setNote] = useState("");
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  useEffect(() => {
    let url: string | null = null;
    fetch(`/api/patients/${e.patient_id}/documents/${e.document_id}/download`, { credentials: "same-origin" }).then(async (r) => {
      if (r.headers.get("content-type")?.includes("json")) setImgUrl((await r.json()).url);
      else { url = URL.createObjectURL(await r.blob()); setImgUrl(url); }
    }).catch(() => {});
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [e.patient_id, e.document_id]);
  const m = useMutation({
    mutationFn: (approve: boolean) => api.post(`/api/doctor/verifications/${e.id}`, { approve, note, items: approve ? items : [] }),
    onSuccess: (r) => { toast("ok", r.status === "verified" ? "Verified. Prescription created and reminders activated." : "Rejected; patient notified."); qc.invalidateQueries({ queryKey: ["verifications"] }); onClose(); },
    onError: (x) => toast("danger", errorMessage(x)),
  });
  const upd = (i: number, k: string, v: any) => setItems(items.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  return (
    <Modal open onClose={onClose} title={`Verify prescription — ${e.patient_name}`} size="xl"
      footer={<><Button variant="outline" onClick={() => m.mutate(false)} disabled={note.length < 3} icon={<XCircle className="h-4 w-4" />}>Reject</Button>
        <Button onClick={() => m.mutate(true)} disabled={note.length < 3 || !items.length} loading={m.isPending} icon={<CheckCircle2 className="h-4 w-4" />}>Approve & activate</Button></>}>
      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <p className="label mb-2">Original document</p>
          {imgUrl ? (e.document.mime_type === "application/pdf" ? <a className="link" href={imgUrl} target="_blank" rel="noreferrer">Open PDF</a> :
            <img src={imgUrl} alt="Uploaded prescription" className="max-h-[480px] w-full rounded-xl border border-line object-contain" />) : <Skeleton className="h-64" />}
          <Notice tone="warn" title="Patient-reviewed, unverified">{(src.medications ?? []).map((x: any) => `${x.name} ${x.strength} ${x.dose} ${x.frequency} ${x.duration}`).join(" · ")}</Notice>
          {e.possible_duplicates?.length > 0 && <Notice tone="danger" title="Possible duplicates">{e.possible_duplicates.map((d: any) => d.name ?? d.title).join(", ")}</Notice>}
        </div>
        <div className="space-y-3">
          <p className="label">Structured medication record to approve</p>
          {items.map((it, i) => (
            <div key={i} className="grid grid-cols-2 gap-2 rounded-xl bg-surface-2 p-3">
              <Input aria-label="Generic name" value={it.generic_name} onChange={(x) => upd(i, "generic_name", x.target.value)} />
              <Input aria-label="Strength" value={it.strength} onChange={(x) => upd(i, "strength", x.target.value)} />
              <Select aria-label="Form" value={it.dosage_form} onChange={(x) => upd(i, "dosage_form", x.target.value)}>{FORMS.map((f) => <option key={f}>{f}</option>)}</Select>
              <div className="flex gap-1"><Input aria-label="Dose" type="number" value={it.dose_amount} onChange={(x) => upd(i, "dose_amount", Number(x.target.value))} />
                <Select aria-label="Unit" value={it.dose_unit} onChange={(x) => upd(i, "dose_unit", x.target.value)}>{UNITS.map((u) => <option key={u}>{u}</option>)}</Select></div>
              <Input aria-label="Frequency" value={it.frequency_label} onChange={(x) => upd(i, "frequency_label", x.target.value)} />
              <Input aria-label="Dose times (comma separated)" value={it.times_of_day.join(",")} onChange={(x) => upd(i, "times_of_day", x.target.value.split(",").map((s: string) => s.trim()).filter(Boolean))} />
              <Input aria-label="Start date" type="date" value={it.start_date} onChange={(x) => upd(i, "start_date", x.target.value)} />
              <Input aria-label="End date" type="date" value={it.end_date ?? ""} onChange={(x) => upd(i, "end_date", x.target.value || null)} />
            </div>
          ))}
          <Field label="Verification note" required>{(p) => <Textarea {...p} value={note} onChange={(x) => setNote(x.target.value)} placeholder="e.g. Checked against original; dose confirmed" />}</Field>
        </div>
      </div>
    </Modal>
  );
}
