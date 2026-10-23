import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, HeartHandshake, History, Mail, ShieldCheck, ShieldOff, Stethoscope, UserPlus } from "lucide-react";
import { Avatar, Badge, Button, Checkbox, Field, Input, Select, Skeleton, Toggle } from "@/components/ui/primitives";
import { ConfirmDialog, ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader, SectionTitle, Tabs } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { fmtDate, fmtDateTime, titleCase } from "@/lib/format";

const SCOPE_LABEL: Record<string, string> = {
  "medications.view": "See medication schedule",
  "records.view": "See selected medical records",
  "adherence.notify": "Get missed-dose alerts",
  "appointments.view": "See appointments",
  "appointments.book": "Help book appointments",
  "checkin.submit": "Submit check-ins for me",
  "concerns.report": "Report medication concerns",
  "instructions.view": "See doctor instructions",
  "messages.patient": "Message me and my care team",
  "careteam.contact": "Contact my care team",
};
const STATUS_TONE: Record<string, any> = { invited: "warn", accepted: "info", active: "ok", revoked: "danger", expired: "neutral", declined: "neutral" };

export default function CareTeam() {
  const q = useQuery({ queryKey: ["permissions"], queryFn: () => api.get("/api/me/permissions") });
  const [tab, setTab] = useState<"people" | "history">("people");
  const [invite, setInvite] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [revoke, setRevoke] = useState<{ kind: "caregiver" | "doctor"; id: string; name: string } | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const refresh = () => { qc.invalidateQueries({ queryKey: ["permissions"] }); qc.invalidateQueries({ queryKey: ["overview"] }); };

  const authorize = useMutation({ mutationFn: (id: string) => api.post(`/api/me/caregivers/${id}/authorize`),
    onSuccess: () => { toast("ok", "Access granted and recorded."); refresh(); }, onError: (e) => toast("danger", errorMessage(e)) });
  const revokeM = useMutation({
    mutationFn: () => api.post(revoke!.kind === "caregiver" ? `/api/me/caregivers/${revoke!.id}/revoke` : `/api/me/doctors/${revoke!.id}/revoke`, { reason: "Revoked by patient" }),
    onSuccess: (r) => { toast("ok", r.note ?? "Access revoked."); setRevoke(null); refresh(); }, onError: (e) => toast("danger", errorMessage(e)) });
  const policy = useMutation({ mutationFn: (v: boolean) => api.put("/api/me/escalation-policy", { notify_caregiver_approved: v }),
    onSuccess: () => { toast("ok", "Preference saved."); refresh(); }, onError: (e) => toast("danger", errorMessage(e)) });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  return (
    <>
      <PageHeader title="Care Team & Permissions" subtitle="You decide who can see what, for how long."
        actions={<Button onClick={() => setInvite(true)} icon={<UserPlus className="h-4 w-4" />}>Invite caregiver</Button>} />
      <div className="mb-5"><Tabs label="Care team sections" value={tab} onChange={setTab} tabs={[{ id: "people", label: "People & access" }, { id: "history", label: "History" }]} /></div>
      {!d ? <Skeleton className="h-64" /> : tab === "people" ? (
        <div className="space-y-8">
          <section>
            <SectionTitle title="Caregivers" icon={<HeartHandshake className="h-5 w-5 text-primary" />} />
            <ul className="space-y-3">
              {d.caregivers.length === 0 && <p className="text-sm text-ink-3">No caregivers yet. Invite someone you trust — they'll use their own account.</p>}
              {d.caregivers.map((c: any) => (
                <li key={c.id} className="card p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Avatar name={c.caregiver?.name ?? c.contact} color={c.caregiver?.avatar_color ?? "#94a3b8"} />
                    <div className="flex-1">
                      <p className="font-semibold">{c.caregiver?.name ?? c.contact} <span className="text-sm font-medium text-ink-3">· {c.label}</span></p>
                      <p className="text-xs text-ink-3">{c.expires_at ? `Expires ${fmtDate(c.expires_at)}` : "No expiry"}{c.authorized_at && ` · authorised ${fmtDate(c.authorized_at)}`}</p>
                    </div>
                    <Badge tone={STATUS_TONE[c.status]}>{c.status === "accepted" ? "Accepted — needs your approval" : titleCase(c.status)}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">{c.scopes.map((s: string) => <Badge key={s} tone="primary">{SCOPE_LABEL[s] ?? s}</Badge>)}</div>
                  {["invited", "accepted", "active"].includes(c.status) && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {c.status === "accepted" && <Button size="sm" onClick={() => authorize.mutate(c.id)} loading={authorize.isPending} icon={<ShieldCheck className="h-4 w-4" />}>Approve access</Button>}
                      <Button size="sm" variant="outline" onClick={() => setEditing(c)}>Edit permissions</Button>
                      <Button size="sm" variant="ghost" className="text-danger" onClick={() => setRevoke({ kind: "caregiver", id: c.id, name: c.caregiver?.name ?? c.contact })} icon={<ShieldOff className="h-4 w-4" />}>Revoke</Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <SectionTitle title="Doctors with access" icon={<Stethoscope className="h-5 w-5 text-primary" />} />
            <ul className="space-y-3">
              {d.doctors.filter((x: any) => x.status === "active").map((x: any) => (
                <li key={x.id} className="card flex flex-wrap items-center gap-3 p-4">
                  <Avatar name={x.doctor.name} color={x.doctor.avatar_color} />
                  <div className="flex-1">
                    <p className="font-semibold">{x.doctor.name} <span className="text-sm font-medium text-ink-3">· {x.doctor.speciality}</span></p>
                    <p className="text-xs text-ink-3">{x.purpose} · granted via {titleCase(x.granting_authority)}{x.expires_at && ` · until ${fmtDate(x.expires_at)}`}</p>
                  </div>
                  <Button size="sm" variant="ghost" className="text-danger" onClick={() => setRevoke({ kind: "doctor", id: x.id, name: x.doctor.name })}>Revoke</Button>
                </li>
              ))}
            </ul>
          </section>
          <section className="card p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-bold">Missed-dose alerts to caregivers</h2>
                <p className="mt-1 text-sm text-ink-2">If you don't respond to {d.escalation_policy.caregiver_after_consecutive} reminders in a row, notify caregivers who have "Get missed-dose alerts". Not responding is never treated as an emergency.</p>
              </div>
              <Toggle label="Notify caregivers about missed doses" checked={d.escalation_policy.notify_caregiver_approved} onChange={(v) => policy.mutate(v)} />
            </div>
          </section>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="card p-5">
            <SectionTitle title="Consent history" icon={<History className="h-5 w-5 text-primary" />} />
            <ul className="divide-y divide-line text-sm">{d.consent_history.map((c: any) => (
              <li key={c.id} className="py-2.5"><p className="font-semibold">{titleCase(c.action)} · {titleCase(c.resource)}</p><p className="text-xs text-ink-3">{fmtDateTime(c.at)}{c.note && ` · ${c.note}`}</p></li>))}</ul>
          </section>
          <section className="card p-5">
            <SectionTitle title="Who accessed your information" icon={<Eye className="h-5 w-5 text-primary" />} />
            <ul className="divide-y divide-line text-sm">{d.access_history.map((a: any, i: number) => (
              <li key={i} className="flex justify-between gap-3 py-2.5">
                <span><b>{a.who}</b> <span className="text-ink-3">({a.role})</span> — {a.action.replace("read:", "viewed ").replace(/_/g, " ")}{a.outcome === "denied" && <Badge tone="danger" className="ml-1">Denied</Badge>}</span>
                <span className="shrink-0 text-xs text-ink-3">{fmtDateTime(a.at)}</span>
              </li>))}
              {d.access_history.length === 0 && <li className="py-2 text-ink-3">No access by others yet.</li>}</ul>
          </section>
        </div>
      )}
      <InviteModal open={invite} onClose={() => setInvite(false)} scopes={d?.available_scopes ?? []} onDone={refresh} />
      {editing && <EditScopes rel={editing} onClose={() => setEditing(null)} scopes={d.available_scopes} onDone={refresh} />}
      <ConfirmDialog open={!!revoke} onClose={() => setRevoke(null)} onConfirm={() => revokeM.mutate()} loading={revokeM.isPending} tone="danger"
        title={`Revoke access for ${revoke?.name}?`} confirmLabel="Revoke access"
        body={<>Their access stops immediately for every new request, including dashboards and downloads. Information they already downloaded can't be recalled.</>} />
    </>
  );
}

function ScopePicker({ all, value, onChange }: { all: string[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="grid gap-1 sm:grid-cols-2">
      {all.map((s) => <Checkbox key={s} checked={value.includes(s)} onChange={(on) => onChange(on ? [...value, s] : value.filter((x) => x !== s))} label={SCOPE_LABEL[s] ?? s} />)}
    </div>
  );
}

function InviteModal({ open, onClose, scopes, onDone }: { open: boolean; onClose: () => void; scopes: string[]; onDone: () => void }) {
  const [f, setF] = useState({ contact: "", relationship_label: "Family member", scopes: ["medications.view", "appointments.view", "instructions.view"], expires_in_days: "" });
  const [res, setRes] = useState<any>(null);
  const toast = useToast();
  const m = useMutation({
    mutationFn: () => api.post("/api/me/caregivers/invite", { ...f, expires_in_days: f.expires_in_days ? Number(f.expires_in_days) : null }),
    onSuccess: (r) => { setRes(r); onDone(); }, onError: (e) => toast("danger", errorMessage(e)),
  });
  return (
    <Modal open={open} onClose={() => { setRes(null); onClose(); }} title="Invite a caregiver" size="lg"
      footer={res ? <Button onClick={() => { setRes(null); onClose(); }}>Done</Button> : <><Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={() => m.mutate()} loading={m.isPending} disabled={!f.contact || !f.scopes.length} icon={<Mail className="h-4 w-4" />}>Send invitation</Button></>}>
      {res ? (
        <div className="space-y-3">
          <Notice tone="ok" title="Invitation created">When {f.contact} accepts with their own account, you'll be asked to approve before any access starts.</Notice>
          {res.dev_link && <Notice tone="warn" title="Development mode">Delivery isn't configured ({res.delivery}). Share this link: <span className="break-all font-mono text-xs">{res.dev_link}</span></Notice>}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="sm:col-span-2"><Field label="Email or phone" required>{(p) => <Input {...p} value={f.contact} onChange={(e) => setF({ ...f, contact: e.target.value })} />}</Field></div>
            <Field label="Relationship">{(p) => <Input {...p} value={f.relationship_label} onChange={(e) => setF({ ...f, relationship_label: e.target.value })} />}</Field>
          </div>
          <div><p className="label mb-1">What can they do?</p><ScopePicker all={scopes} value={f.scopes} onChange={(s) => setF({ ...f, scopes: s })} /></div>
          <Field label="Access expires after">{(p) => <Select {...p} value={f.expires_in_days} onChange={(e) => setF({ ...f, expires_in_days: e.target.value })}>
            <option value="">No expiry (revoke any time)</option><option value="30">30 days</option><option value="90">90 days</option><option value="365">1 year</option></Select>}</Field>
          <Notice tone="info">Caregivers can never change prescriptions, edit records, or grant access to others. Never share your password with anyone.</Notice>
        </div>
      )}
    </Modal>
  );
}

function EditScopes({ rel, onClose, scopes, onDone }: { rel: any; onClose: () => void; scopes: string[]; onDone: () => void }) {
  const [value, setValue] = useState<string[]>(rel.scopes);
  const toast = useToast();
  const m = useMutation({ mutationFn: () => api.put(`/api/me/caregivers/${rel.id}`, { scopes: value, expires_at: rel.expires_at }),
    onSuccess: () => { toast("ok", "Permissions updated."); onDone(); onClose(); }, onError: (e) => toast("danger", errorMessage(e)) });
  return (
    <Modal open onClose={onClose} title={`Permissions for ${rel.caregiver?.name ?? rel.contact}`} size="lg"
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={() => m.mutate()} disabled={!value.length} loading={m.isPending}>Save</Button></>}>
      <ScopePicker all={scopes} value={value} onChange={setValue} />
    </Modal>
  );
}
