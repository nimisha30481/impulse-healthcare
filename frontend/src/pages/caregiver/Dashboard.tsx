import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock, HeartHandshake } from "lucide-react";
import { Avatar, Badge, ProgressBar, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Notice } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, pct, titleCase } from "@/lib/format";

export default function CaregiverDashboard() {
  const { user } = useAuth();
  const q = useQuery({ queryKey: ["caregiver-patients"], queryFn: () => api.get("/api/caregiver/patients") });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const active = (q.data ?? []).filter((r: any) => r.status === "active");
  const pending = (q.data ?? []).filter((r: any) => ["invited", "accepted"].includes(r.status));
  return (
    <>
      <PageHeader title={`Hello, ${user!.preferred_name || user!.full_name.split(" ")[0]}`} subtitle="The people you support, and what they've allowed you to see." />
      {pending.length > 0 && <div className="mb-5"><Notice tone="info" title="Waiting for approval">{pending.map((p: any) => p.patient_name).join(", ")} still need to approve your access.</Notice></div>}
      {q.isLoading ? <Skeleton className="h-48" /> : active.length === 0 ? (
        <EmptyState icon={<HeartHandshake className="h-6 w-6" />} title="No linked patients yet" body="When someone invites you, open the link in their invitation while signed in to this account." />
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          {active.map((r: any) => (
            <Link key={r.id} to={`/caregiver/patients/${r.patient_id}`} className="card group p-5 transition hover:-translate-y-0.5 hover:shadow-lift">
              <div className="flex items-center gap-3">
                <Avatar name={r.patient_name} size={48} />
                <div className="flex-1"><p className="text-lg font-bold">{r.patient_name}</p><p className="text-sm text-ink-3">{r.label} · access {r.expires_at ? `until ${fmtDate(r.expires_at)}` : "ongoing"}</p></div>
                <ArrowRight className="h-5 w-5 text-ink-3 transition group-hover:translate-x-1" />
              </div>
              {r.adherence ? (
                <div className="mt-4 space-y-2">
                  <div className="flex justify-between text-sm"><span className="text-ink-2">Doses with a response (7 days)</span><b>{pct(r.adherence.response_coverage)}</b></div>
                  <ProgressBar value={(r.adherence.response_coverage ?? 0) * 100} label="Response coverage" tone="ok" />
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    <Badge tone="ok">{r.adherence.taken_reported} reported taken</Badge>
                    {r.adherence.unconfirmed > 0 && <Badge tone="warn" icon={<Clock className="h-3 w-3" />}>{r.adherence.unconfirmed} unconfirmed</Badge>}
                    {r.adherence.missed_reported > 0 && <Badge tone="danger">{r.adherence.missed_reported} missed</Badge>}
                  </div>
                </div>
              ) : <p className="mt-4 text-sm text-ink-3">Medication schedule not shared with you.</p>}
              <div className="mt-4 flex flex-wrap gap-1">{r.scopes.slice(0, 4).map((s: string) => <Badge key={s}>{titleCase(s.split(".")[0])}</Badge>)}{r.scopes.length > 4 && <Badge>+{r.scopes.length - 4}</Badge>}</div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
