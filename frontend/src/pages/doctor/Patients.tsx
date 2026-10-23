import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Search, ShieldAlert, Users } from "lucide-react";
import { Avatar, Badge, Button, Field, Input, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { AccessIdUnlock } from "@/features/access/AccessComponents";
import { api, errorMessage } from "@/lib/api";
import { fmtDate } from "@/lib/format";

const FILTERS = [["", "All patients"], ["upcoming_appointment", "Upcoming appointment"], ["requires_follow_up", "Requires follow-up"],
  ["new_patient", "New patient"], ["adherence_concern", "Adherence concern"], ["active_treatment", "Active treatment"]];

export default function DoctorPatients() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("");
  const [bg, setBg] = useState(false);
  const list = useQuery({ queryKey: ["doctor-patients", q, filter], queryFn: () => api.get(`/api/doctor/patients?q=${encodeURIComponent(q)}&filter=${filter}`) });
  return (
    <>
      <PageHeader title="Patients" subtitle="Patients who shared their Access ID with you or booked with you. Search never reveals anyone else."
        actions={<Button variant="outline" onClick={() => setBg(true)} icon={<ShieldAlert className="h-4 w-4" />}>Emergency access</Button>} />
      <div className="mb-5"><AccessIdUnlock compact /></div>
      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_240px]">
        <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <Input aria-label="Search patients" className="pl-9" placeholder="Search by name or patient ID" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Select aria-label="Filter patients" value={filter} onChange={(e) => setFilter(e.target.value)}>{FILTERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>
      </div>
      {list.isError ? <ErrorState error={list.error} onRetry={() => list.refetch()} /> : list.isLoading ? <Skeleton className="h-64" /> : list.data.length === 0 ? (
        <EmptyState icon={<Users className="h-6 w-6" />} title="No matching patients" />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-line text-xs uppercase tracking-wide text-ink-3">
              <tr><th className="p-3">Patient</th><th className="p-3">ID</th><th className="p-3">Last consultation</th><th className="p-3">Next appointment</th><th className="p-3">Status</th><th className="p-3">Permission</th><th className="p-3"><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {list.data.map((p: any) => (
                <tr key={p.id} className="border-b border-line last:border-0 hover:bg-surface-2/60">
                  <td className="p-3"><div className="flex items-center gap-2.5"><Avatar name={p.name} color={p.avatar_color} size={32} /><span className="font-semibold">{p.name}</span></div></td>
                  <td className="p-3 font-mono text-xs">{p.mrn}</td>
                  <td className="p-3">{p.last_consultation ? fmtDate(p.last_consultation) : "—"}</td>
                  <td className="p-3">{p.next_appointment ? fmtDate(p.next_appointment) : "—"}</td>
                  <td className="p-3"><div className="flex flex-wrap gap-1">
                    {p.flags.adherence_concern && <Badge tone="danger">Adherence</Badge>}
                    {p.flags.requires_follow_up && <Badge tone="warn">Follow-up</Badge>}
                    {p.flags.new_patient && <Badge tone="info">New</Badge>}
                    {p.flags.active_treatment && (
                      <span title="Active: this patient has at least one medicine currently prescribed and being taken"
                        aria-label="Active: has at least one medicine currently prescribed" tabIndex={0} className="cursor-help rounded-full focus-visible:outline">
                        <Badge tone="ok">Active</Badge>
                      </span>
                    )}
                  </div></td>
                  <td className="p-3 text-xs">{p.permission.status}{p.permission.expires_at && <span className="block text-ink-3">until {fmtDate(p.permission.expires_at)}</span>}</td>
                  <td className="p-3"><Link to={`/doctor/patients/${p.id}`}><Button size="sm" variant="outline">Open</Button></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <BreakGlass open={bg} onClose={() => setBg(false)} />
    </>
  );
}

function BreakGlass({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [mrn, setMrn] = useState("");
  const [why, setWhy] = useState("");
  const toast = useToast();
  const m = useMutation({
    mutationFn: () => api.post("/api/break-glass", { patient_mrn: mrn, justification: why }),
    onSuccess: (r) => { toast("ok", r.note); onClose(); window.location.href = `/doctor/patients/${r.patient_id}`; },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  return (
    <Modal open={open} onClose={onClose} title="Emergency (break-glass) access"
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button variant="danger" onClick={() => m.mutate()} disabled={!mrn || why.length < 20} loading={m.isPending}>Request 1-hour read access</Button></>}>
      <div className="space-y-4">
        <Notice tone="danger" title="Use only in a genuine clinical emergency">Access is read-only, lasts one hour, notifies the patient, alerts administrators and is reviewed afterwards.</Notice>
        <Field label="Patient ID (e.g. IMP-DEMO-0001)" required>{(p) => <Input {...p} value={mrn} onChange={(e) => setMrn(e.target.value.trim())} />}</Field>
        <Field label="Clinical justification" hint="At least 20 characters" required>{(p) => <Textarea {...p} value={why} onChange={(e) => setWhy(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
