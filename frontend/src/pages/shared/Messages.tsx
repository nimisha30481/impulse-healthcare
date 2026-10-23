import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Send } from "lucide-react";
import clsx from "clsx";
import { Avatar, Badge, Button, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { EmptyState, ErrorState, useToast } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDateTime, titleCase } from "@/lib/format";

export function MessageThread({ patientId }: { patientId: string }) {
  const { user } = useAuth();
  const q = useQuery({ queryKey: ["messages", patientId], queryFn: () => api.get(`/api/patients/${patientId}/messages`), refetchInterval: 30_000 });
  const team = useQuery({ queryKey: ["care-team", patientId], queryFn: () => api.get(`/api/patients/${patientId}/care-team`) });
  const [to, setTo] = useState("");
  const [body, setBody] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const recipients = [
    team.data?.patient, ...(team.data?.doctors ?? []).map((d: any) => d.doctor), ...(team.data?.caregivers ?? []).map((c: any) => c.caregiver),
  ].filter((p: any) => p && p.id !== user!.id);
  useEffect(() => { if (!to && recipients[0]) setTo(recipients[0].id); }, [recipients.length]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [q.data?.length]);
  const send = useMutation({ mutationFn: () => api.post(`/api/patients/${patientId}/messages`, { recipient_id: to, body }),
    onSuccess: () => { setBody(""); qc.invalidateQueries({ queryKey: ["messages", patientId] }); }, onError: (e) => toast("danger", errorMessage(e)) });
  if (q.isError) return <ErrorState error={q.error} />;
  return (
    <div className="flex flex-col gap-3">
      <div className="max-h-[420px] min-h-[160px] space-y-3 overflow-y-auto rounded-xl bg-surface-2 p-3" aria-live="polite">
        {q.isLoading ? <Skeleton className="h-20" /> : q.data.length === 0 ? <p className="p-6 text-center text-sm text-ink-3">No messages yet.</p> :
          q.data.map((m: any) => {
            const mine = m.sender.id === user!.id;
            return (
              <div key={m.id} className={clsx("flex gap-2", mine && "flex-row-reverse")}>
                <Avatar name={m.sender.name} color={m.sender.avatar_color} size={30} />
                <div className={clsx("max-w-[78%] rounded-2xl px-3.5 py-2 text-sm", mine ? "bg-primary text-primary-ink" : "bg-surface shadow-card")}>
                  {m.kind !== "message" && <Badge tone="info" className="mb-1">{titleCase(m.kind)}</Badge>}
                  <p className="whitespace-pre-wrap">{m.body}</p>
                  <p className={clsx("mt-1 text-[11px]", mine ? "opacity-80" : "text-ink-3")}>{mine ? "You" : m.sender.name} · {fmtDateTime(m.created_at)}</p>
                </div>
              </div>
            );
          })}
        <div ref={end} />
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Select aria-label="Recipient" className="sm:w-56" value={to} onChange={(e) => setTo(e.target.value)}>
          {recipients.map((r: any) => <option key={r.id} value={r.id}>{r.name} ({r.role})</option>)}
        </Select>
        <Textarea aria-label="Message" className="min-h-[44px] flex-1" value={body} onChange={(e) => setBody(e.target.value)} placeholder="Write a message…" />
        <Button onClick={() => send.mutate()} disabled={!body.trim() || !to} loading={send.isPending} icon={<Send className="h-4 w-4" />}>Send</Button>
      </div>
      <p className="text-xs text-ink-3">Messages aren't monitored in real time. For urgent symptoms call 112.</p>
    </div>
  );
}

export default function Messages() {
  const { user } = useAuth();
  const docPts = useQuery({ queryKey: ["doctor-patients", "", ""], queryFn: () => api.get("/api/doctor/patients"), enabled: user!.role === "doctor" });
  const cgPts = useQuery({ queryKey: ["caregiver-patients"], queryFn: () => api.get("/api/caregiver/patients"), enabled: user!.role === "caregiver" });
  const options: { id: string; name: string }[] = user!.role === "patient" ? [{ id: user!.patient_id!, name: "My care team" }]
    : user!.role === "doctor" ? (docPts.data ?? []).map((p: any) => ({ id: p.id, name: p.name }))
    : (cgPts.data ?? []).filter((r: any) => r.status === "active" && r.scopes.includes("messages.patient")).map((r: any) => ({ id: r.patient_id, name: r.patient_name }));
  const [sel, setSel] = useState<string | null>(null);
  const current = sel ?? options[0]?.id;
  return (
    <>
      <PageHeader title="Messages" subtitle="Secure messages with the care team. Everything is timestamped." />
      {options.length === 0 ? <EmptyState icon={<MessageSquare className="h-6 w-6" />} title="No conversations available" body="Conversations appear for patients you're authorised to message." /> : (
        <div className="grid gap-5 lg:grid-cols-[240px_1fr]">
          {options.length > 1 && (
            <nav className="card h-fit p-2" aria-label="Conversations">
              {options.map((o) => <button key={o.id} onClick={() => setSel(o.id)} className={clsx("flex w-full items-center gap-2 rounded-xl p-2.5 text-left text-sm font-semibold", current === o.id ? "bg-primary-soft text-primary" : "hover:bg-surface-2")}>
                <Avatar name={o.name} size={28} />{o.name}</button>)}
            </nav>
          )}
          <div className={clsx("card p-4", options.length === 1 && "lg:col-span-2")}>{current && <MessageThread key={current} patientId={current} />}</div>
        </div>
      )}
    </>
  );
}
