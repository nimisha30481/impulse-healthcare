import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Flag, Lock, Pill, Siren } from "lucide-react";
import { Avatar, Button, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { SectionTitle, Tabs } from "@/components/ui/domain";
import { DoseCard } from "@/features/doses/DoseCard";
import { AdherenceCard } from "@/features/adherence/AdherenceCard";
import { InstructionsList } from "@/features/instructions/InstructionsList";
import { AppointmentsView } from "@/pages/patient/Appointments";
import { MessageThread } from "@/pages/shared/Messages";
import { EmergencyDialog } from "@/features/emergency/EmergencyButton";
import { api, errorMessage } from "@/lib/api";

type Tab = "today" | "appointments" | "instructions" | "messages";

export default function CaregiverPatientView() {
  const { patientId } = useParams();
  const rels = useQuery({ queryKey: ["caregiver-patients"], queryFn: () => api.get("/api/caregiver/patients") });
  const rel = rels.data?.find((r: any) => r.patient_id === patientId && r.status === "active");
  const scopes: string[] = rel?.scopes ?? [];
  const has = (s: string) => scopes.includes(s);
  const [tab, setTab] = useState<Tab>("today");
  const [concern, setConcern] = useState(false);
  const [emergency, setEmergency] = useState(false);
  const overview = useQuery({ queryKey: ["overview", patientId], queryFn: () => api.get(`/api/patients/${patientId}/overview`), enabled: has("medications.view"), refetchInterval: 60_000 });

  if (rels.isLoading) return <Skeleton className="h-64" />;
  if (!rel) return <EmptyState icon={<Lock className="h-6 w-6" />} title="No active access" body="This person hasn't granted you access, or it was revoked or expired." action={<Link to="/caregiver"><Button>Back</Button></Link>} />;
  const tabs = [
    has("medications.view") && { id: "today", label: "Medication schedule" },
    (has("appointments.view") || has("appointments.book")) && { id: "appointments", label: "Appointments" },
    has("instructions.view") && { id: "instructions", label: "Doctor instructions" },
    has("messages.patient") && { id: "messages", label: "Messages" },
  ].filter(Boolean) as { id: Tab; label: string }[];
  const current = tabs.find((t) => t.id === tab) ? tab : tabs[0]?.id;

  return (
    <div className="space-y-5">
      <Link to="/caregiver" className="inline-flex items-center gap-1 text-sm font-semibold text-ink-3 hover:text-ink"><ArrowLeft className="h-4 w-4" />All patients</Link>
      <div className="card flex flex-wrap items-center gap-4 p-5">
        <Avatar name={rel.patient_name} size={52} />
        <div className="flex-1"><h1 className="text-2xl font-extrabold">{rel.patient_name}</h1><p className="text-sm text-ink-3">You are their {rel.label.toLowerCase()} · access set by {rel.patient_name.split(" ")[0]}</p></div>
        {has("concerns.report") && <Button variant="outline" onClick={() => setConcern(true)} icon={<Flag className="h-4 w-4" />}>Report a concern</Button>}
        {has("careteam.contact") && <Button variant="danger" onClick={() => setEmergency(true)} icon={<Siren className="h-4 w-4" />}>Emergency</Button>}
      </div>
      {tabs.length === 0 ? <Notice tone="info">You have limited access. Ask {rel.patient_name} to adjust your permissions if you need more.</Notice> : (
        <Tabs label="Patient sections" value={current!} onChange={setTab} tabs={tabs} />
      )}
      {current === "today" && (
        <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <section>
            <SectionTitle title="Today" icon={<Pill className="h-5 w-5 text-primary" />} />
            {overview.isError ? <ErrorState error={overview.error} /> : overview.isLoading ? <Skeleton className="h-40" /> : overview.data.today.length === 0 ? <EmptyState title="Nothing scheduled today" /> : (
              <div className="space-y-3">{overview.data.today.map((d: any, i: number) => (
                <DoseCard key={d.id} dose={d} patientId={patientId!} index={i} actor="caregiver" readOnly={!has("checkin.submit")} />
              ))}</div>
            )}
            {!has("checkin.submit") && <p className="mt-2 text-xs text-ink-3">You can view the schedule but not submit check-ins.</p>}
          </section>
          {overview.data && <AdherenceCard patientId={patientId!} initial={overview.data.adherence} compact />}
        </div>
      )}
      {current === "appointments" && <AppointmentsView patientId={patientId!} canBook={has("appointments.book")} />}
      {current === "instructions" && <InstructionsList patientId={patientId!} bookHref={`/caregiver/patients/${patientId}`} />}
      {current === "messages" && <div className="card p-5"><MessageThread patientId={patientId!} /></div>}
      <ConcernModal open={concern} onClose={() => setConcern(false)} patientId={patientId!} />
      <EmergencyDialog open={emergency} onClose={() => setEmergency(false)} patientId={patientId!} />
    </div>
  );
}

function ConcernModal({ open, onClose, patientId }: { open: boolean; onClose: () => void; patientId: string }) {
  const [kind, setKind] = useState("general");
  const [text, setText] = useState("");
  const toast = useToast();
  const m = useMutation({ mutationFn: () => api.post(`/api/patients/${patientId}/concerns`, { kind, description: text }),
    onSuccess: (r) => { toast("ok", r.message); onClose(); setText(""); }, onError: (e) => toast("danger", errorMessage(e)) });
  return (
    <Modal open={open} onClose={onClose} title="Report a medication concern"
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={() => m.mutate()} disabled={text.length < 5} loading={m.isPending}>Send</Button></>}>
      <div className="space-y-3">
        <Select aria-label="Concern type" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="general">General concern</option><option value="concerning_symptoms">Concerning symptoms</option>
          <option value="affordability">Medicine too expensive</option><option value="medicine_unavailable">Medicine unavailable</option><option value="refill_difficulty">Refill difficulty</option>
        </Select>
        <Textarea aria-label="Details" value={text} onChange={(e) => setText(e.target.value)} placeholder="What's happening?" />
        <Notice tone="warn">A care coordinator reviews this during support hours. In an emergency, call 112.</Notice>
      </div>
    </Modal>
  );
}
