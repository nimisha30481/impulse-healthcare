import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Mail, Phone, UserRound, Users } from "lucide-react";
import { Badge, Button, Field, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { DoseStatusPill, PageHeader, SectionTitle } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { fmtDateTime, titleCase } from "@/lib/format";
import { PRIORITY_TONE } from "./Cases";

export default function CaseDetail() {
  const { caseId } = useParams();
  const q = useQuery({ queryKey: ["support-case", caseId], queryFn: () => api.get(`/api/support/cases/${caseId}`) });
  const qc = useQueryClient();
  const toast = useToast();
  const [attempt, setAttempt] = useState({ method: "phone", target: "patient", outcome: "no_answer", note: "" });
  const [note, setNote] = useState("");
  const [modal, setModal] = useState<"resolve" | "escalate" | null>(null);
  const [text, setText] = useState("");
  const refresh = () => { qc.invalidateQueries({ queryKey: ["support-case", caseId] }); qc.invalidateQueries({ queryKey: ["support-cases"] }); };
  const add = useMutation({ mutationFn: () => api.post(`/api/support/cases/${caseId}/attempts`, { ...attempt, note: attempt.note || null }), onSuccess: () => { toast("ok", "Contact attempt recorded."); setAttempt({ ...attempt, note: "" }); refresh(); }, onError: (e) => toast("danger", errorMessage(e)) });
  const addNote = useMutation({ mutationFn: () => api.post(`/api/support/cases/${caseId}/notes`, { body: note }), onSuccess: () => { setNote(""); refresh(); } });
  const act = useMutation({
    mutationFn: () => modal === "resolve" ? api.post(`/api/support/cases/${caseId}/resolve`, { resolution: text }) : api.post(`/api/support/cases/${caseId}/escalate`, { reason: text, priority: "urgent" }),
    onSuccess: (r) => { toast("ok", modal === "resolve" ? "Case resolved." : `Escalated. Supervisor alert: ${r.supervisor_alert}.`); setModal(null); setText(""); refresh(); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  if (q.isError) return <ErrorState error={q.error} />;
  if (!q.data) return <Skeleton className="h-96" />;
  const c = q.data;
  const pc = c.patient_contact;
  return (
    <div className="space-y-5">
      <Link to="/support" className="inline-flex items-center gap-1 text-sm font-semibold text-ink-3 hover:text-ink"><ArrowLeft className="h-4 w-4" />Cases</Link>
      <PageHeader title={`${titleCase(c.case_type)} — ${c.patient_name}`} subtitle={c.reason}
        eyebrow={<span className="flex gap-1.5"><Badge tone={PRIORITY_TONE[c.priority]}>{titleCase(c.priority)}</Badge><Badge>{titleCase(c.status)}</Badge></span>}
        actions={c.status !== "resolved" && <><Button variant="outline" onClick={() => setModal("escalate")}>Escalate</Button><Button onClick={() => setModal("resolve")}>Resolve</Button></>} />
      <Notice tone="info">{c.operational_note}</Notice>
      <div className="grid gap-5 lg:grid-cols-3">
        <section className="card p-5">
          <SectionTitle title="Patient contact" icon={<UserRound className="h-5 w-5 text-primary" />} />
          <p className="font-semibold">{pc.name}</p>
          {pc.phone && <a className="mt-1 flex items-center gap-2 text-sm text-primary" href={`tel:${pc.phone}`}><Phone className="h-4 w-4" />{pc.phone}</a>}
          <a className="mt-1 flex items-center gap-2 text-sm text-primary" href={`mailto:${pc.email}`}><Mail className="h-4 w-4" />{pc.email}</a>
          <p className="mt-3 text-xs text-ink-3">Time zone {pc.timezone}</p>
          {pc.emergency_contact.name && <div className="mt-3 rounded-xl bg-surface-2 p-3 text-sm"><p className="font-semibold">Emergency contact</p><p>{pc.emergency_contact.name} ({pc.emergency_contact.relation}) · {pc.emergency_contact.phone}</p></div>}
        </section>
        <section className="card p-5">
          <SectionTitle title="Authorised caregivers" icon={<Users className="h-5 w-5 text-primary" />} />
          {c.caregivers.length === 0 ? <p className="text-sm text-ink-3">None.</p> : c.caregivers.map((g: any) => (
            <div key={g.email} className="mb-2 text-sm"><p className="font-semibold">{g.name} <span className="font-normal text-ink-3">· {g.relationship}</span></p>
              <p>{g.phone} · {g.email}</p>{!g.can_be_notified && <Badge tone="warn">Not authorised for adherence alerts</Badge>}</div>
          ))}
        </section>
        <section className="card p-5">
          <SectionTitle title="Recent check-ins" />
          <ul className="space-y-1.5 text-sm">{c.checkin_history.map((o: any, i: number) => <li key={i} className="flex items-center justify-between gap-2"><span className="text-ink-3">{fmtDateTime(o.scheduled_at)}</span><DoseStatusPill status={o.status} /></li>)}</ul>
        </section>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card p-5">
          <SectionTitle title="Contact attempts" />
          {c.status !== "resolved" && (
            <div className="mb-4 grid gap-2 rounded-xl bg-surface-2 p-3 sm:grid-cols-3">
              <Select aria-label="Method" value={attempt.method} onChange={(e) => setAttempt({ ...attempt, method: e.target.value })}><option value="phone">Phone</option><option value="sms">SMS</option><option value="email">Email</option><option value="in_app">In-app</option></Select>
              <Select aria-label="Who" value={attempt.target} onChange={(e) => setAttempt({ ...attempt, target: e.target.value })}><option value="patient">Patient</option><option value="caregiver">Caregiver</option><option value="emergency_contact">Emergency contact</option></Select>
              <Select aria-label="Outcome" value={attempt.outcome} onChange={(e) => setAttempt({ ...attempt, outcome: e.target.value })}><option value="reached">Reached</option><option value="no_answer">No answer</option><option value="voicemail">Voicemail</option><option value="wrong_number">Wrong number</option><option value="message_sent">Message sent</option></Select>
              <Textarea aria-label="Attempt note" className="min-h-[60px] sm:col-span-3" placeholder="Note (optional)" value={attempt.note} onChange={(e) => setAttempt({ ...attempt, note: e.target.value })} />
              <Button size="sm" className="sm:col-span-3" onClick={() => add.mutate()} loading={add.isPending}>Record attempt</Button>
            </div>
          )}
          <ul className="space-y-2 text-sm">{c.attempts.map((a: any) => <li key={a.id} className="rounded-xl border border-line p-2.5"><b>{titleCase(a.method)}</b> → {titleCase(a.target)}: <Badge tone={a.outcome === "reached" ? "ok" : "neutral"}>{titleCase(a.outcome)}</Badge><span className="ml-2 text-xs text-ink-3">{fmtDateTime(a.at)}</span>{a.note && <p className="mt-1 text-ink-2">{a.note}</p>}</li>)}
            {c.attempts.length === 0 && <li className="text-ink-3">No attempts yet.</li>}</ul>
        </section>
        <section className="card p-5">
          <SectionTitle title="Notes & history" />
          <div className="flex gap-2"><Textarea aria-label="New note" className="min-h-[60px]" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a case note" /><Button onClick={() => addNote.mutate()} disabled={note.length < 2}>Add</Button></div>
          <ul className="mt-3 space-y-2 text-sm">{c.notes.map((n: any) => <li key={n.id} className="rounded-xl bg-surface-2 p-2.5"><p>{n.body}</p><p className="text-xs text-ink-3">{n.author} · {fmtDateTime(n.at)}</p></li>)}</ul>
          {c.escalation && <div className="mt-4"><p className="text-sm font-semibold">Automated escalation (stage {c.escalation.stage})</p><ul className="mt-1 text-xs text-ink-3">{c.escalation.history.map((h: any, i: number) => <li key={i}>{fmtDateTime(h.at)} — stage {h.stage}: {h.event}</li>)}</ul></div>}
          <ul className="mt-3 border-t border-line pt-3 text-xs text-ink-3">{c.history.map((h: any, i: number) => <li key={i}>{fmtDateTime(h.at)} — {h.event}</li>)}</ul>
          {c.resolution && <Notice tone="ok" title="Resolution">{c.resolution}</Notice>}
        </section>
      </div>
      <Modal open={!!modal} onClose={() => setModal(null)} title={modal === "resolve" ? "Resolve case" : "Escalate per procedure"} size="sm"
        footer={<><Button variant="outline" onClick={() => setModal(null)}>Cancel</Button><Button variant={modal === "escalate" ? "danger" : "primary"} disabled={text.length < 5} onClick={() => act.mutate()} loading={act.isPending}>{modal === "resolve" ? "Resolve" : "Escalate"}</Button></>}>
        <Field label={modal === "resolve" ? "Resolution summary" : "Reason for escalation"} required>{(p) => <Textarea {...p} value={text} onChange={(e) => setText(e.target.value)} />}</Field>
      </Modal>
    </div>
  );
}
