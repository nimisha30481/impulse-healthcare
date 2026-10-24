import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, Stethoscope, UserPlus } from "lucide-react";
import { Badge, Button, Field, Input, Skeleton } from "@/components/ui/primitives";
import { EmptyState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader, SectionTitle } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

export default function AdminHome() {
  const docs = useQuery({ queryKey: ["pending-doctors"], queryFn: () => api.get("/api/admin/doctors/pending") });
  const bg = useQuery({ queryKey: ["break-glass"], queryFn: () => api.get("/api/admin/break-glass") });
  const [staff, setStaff] = useState(false);
  const qc = useQueryClient();
  const toast = useToast();
  const decide = useMutation({ mutationFn: ({ id, approve }: { id: string; approve: boolean }) => api.post(`/api/admin/doctors/${id}/verify`, { approve, note: approve ? "Registration details checked" : "Could not verify registration" }),
    onSuccess: (r) => { toast("ok", r.note); qc.invalidateQueries({ queryKey: ["pending-doctors"] }); }, onError: (e) => toast("danger", errorMessage(e)) });
  const review = useMutation({ mutationFn: (id: string) => api.post(`/api/admin/break-glass/${id}/review`, { outcome: "Justified — reviewed" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["break-glass"] }) });
  return (
    <>
      <PageHeader title="Administration" subtitle="Controlled onboarding, emergency-access review and auditing. Administrators have no clinical access by role."
        actions={<><Link to="/admin/audit"><Button variant="outline">Audit log</Button></Link><Button onClick={() => setStaff(true)} icon={<UserPlus className="h-4 w-4" />}>Add care coordinator</Button></>} />
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <SectionTitle title="Doctor verification queue" icon={<Stethoscope className="h-5 w-5 text-primary" />} />
          {docs.isLoading ? <Skeleton className="h-24" /> : docs.data.length === 0 ? <EmptyState title="No pending doctors" /> : (
            <ul className="space-y-3">{docs.data.map((d: any) => (
              <li key={d.user_id} className="rounded-xl border border-line p-3 text-sm">
                <p className="font-semibold">{d.name} <span className="font-normal text-ink-3">· {d.speciality}</span></p>
                <p className="text-ink-3">{d.email} · Reg. {d.registration_number} {d.registration_council && `(${d.registration_council})`}</p>
                <p className="text-xs text-ink-3">Registered {fmtDateTime(d.registered_at)} · email {d.email_verified ? "verified" : "not verified"}</p>
                <div className="mt-2 flex gap-2"><Button size="sm" onClick={() => decide.mutate({ id: d.user_id, approve: true })}>Approve</Button><Button size="sm" variant="outline" onClick={() => decide.mutate({ id: d.user_id, approve: false })}>Reject</Button></div>
              </li>))}</ul>
          )}
          <Notice tone="info">Approve only after checking the registration with the issuing medical council. Approval doesn't grant access to any patient.</Notice>
        </section>
        <section className="card p-5">
          <SectionTitle title="Emergency (break-glass) access review" icon={<ShieldAlert className="h-5 w-5 text-danger" />} />
          {bg.data?.length === 0 ? <p className="text-sm text-ink-3">No emergency access events.</p> : (
            <ul className="space-y-2">{bg.data?.map((b: any) => (
              <li key={b.id} className="rounded-xl border border-line p-3 text-sm">
                <p className="text-ink-2">{b.justification}</p>
                <p className="text-xs text-ink-3">{fmtDateTime(b.created_at)} · patient {b.patient_id.slice(0, 8)}</p>
                {b.reviewed_at ? <Badge tone="ok">{b.review_outcome}</Badge> : <Button size="sm" className="mt-2" onClick={() => review.mutate(b.id)}>Mark reviewed</Button>}
              </li>))}</ul>
          )}
        </section>
      </div>
      <StaffModal open={staff} onClose={() => setStaff(false)} />
    </>
  );
}

function StaffModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [f, setF] = useState({ full_name: "", email: "", phone: "", temporary_password: "" });
  const toast = useToast();
  const m = useMutation({ mutationFn: () => api.post("/api/admin/support-staff", f), onSuccess: () => { toast("ok", "Coordinator account created. Share the temporary password securely."); onClose(); }, onError: (e) => toast("danger", errorMessage(e)) });
  return (
    <Modal open={open} onClose={onClose} title="Add care coordinator" footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={() => m.mutate()} loading={m.isPending}>Create</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        {(["full_name", "email", "phone", "temporary_password"] as const).map((k) => (
          <Field key={k} label={k.replace("_", " ")}>{(p) => <Input {...p} type={k === "temporary_password" ? "password" : "text"} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />}</Field>
        ))}
      </div>
    </Modal>
  );
}
