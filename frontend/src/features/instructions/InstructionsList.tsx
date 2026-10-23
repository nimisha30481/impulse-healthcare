import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, CheckCircle2, ClipboardList } from "lucide-react";
import { Badge, Button, Skeleton } from "@/components/ui/primitives";
import { ErrorState, useToast } from "@/components/ui/feedback";
import { SectionTitle } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Instruction } from "@/lib/types";

export function InstructionsList({ patientId, compact, bookHref = "/patient/appointments" }: { patientId: string; compact?: boolean; bookHref?: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["instructions", patientId], queryFn: () => api.get<Instruction[]>(`/api/patients/${patientId}/instructions`) });
  const ack = useMutation({
    mutationFn: (id: string) => api.post(`/api/patients/${patientId}/instructions/${id}/acknowledge`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["instructions"] }); toast("ok", "Acknowledged. Your doctor can see this."); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const items = (q.data ?? []).filter((i) => i.status === "open").slice(0, compact ? 3 : 50);
  return (
    <section className="card p-5">
      <SectionTitle title="Doctor instructions" icon={<ClipboardList className="h-5 w-5 text-primary" />} />
      {q.isLoading ? <Skeleton className="h-20" /> : items.length === 0 ? <p className="text-sm text-ink-3">No open instructions.</p> : (
        <ul className="space-y-3">
          {items.map((i) => (
            <li key={i.id} className="rounded-xl border border-line p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold">{i.title}</p>
                {i.kind === "follow_up" ? <Badge tone="info">Recommended follow-up</Badge> : <Badge>Instruction</Badge>}
                {i.priority === "high" && <Badge tone="danger">High priority</Badge>}
              </div>
              <p className="mt-1 text-sm text-ink-2">{i.description}</p>
              <p className="mt-1 text-xs text-ink-3">
                {i.author?.name} · {fmtDate(i.created_at)}
                {i.kind === "follow_up" && (i.due_date ? ` · recommended by ${fmtDate(i.due_date)}` : i.timeframe ? ` · ${i.timeframe}` : "")}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {i.kind === "follow_up" && (i.appointment_id ? <Badge tone="ok" icon={<CheckCircle2 className="h-3 w-3" />}>Appointment booked</Badge> :
                  <Link to={`${bookHref}?book=1&follow_up=${i.id}`}><Button size="sm" variant="secondary" icon={<CalendarPlus className="h-4 w-4" />}>Not booked yet — book now</Button></Link>)}
                {i.requires_ack && (i.acknowledged_at ? <Badge tone="ok" icon={<CheckCircle2 className="h-3 w-3" />}>Acknowledged</Badge> :
                  <Button size="sm" onClick={() => ack.mutate(i.id)} loading={ack.isPending && ack.variables === i.id}>Acknowledge</Button>)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
