import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Inbox } from "lucide-react";
import { Badge, Select, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Notice } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { api } from "@/lib/api";
import { fmtRelative, titleCase } from "@/lib/format";

export const PRIORITY_TONE: Record<string, any> = { urgent: "danger", high: "warn", normal: "info", low: "neutral" };

export default function SupportCases() {
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["support-cases", status], queryFn: () => api.get(`/api/support/cases${status ? `?status=${status}` : ""}`), refetchInterval: 60_000 });
  return (
    <>
      <PageHeader title="My Cases" subtitle="Cases assigned to you. You see only the details needed to help."
        actions={<Select aria-label="Status filter" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="escalated">Escalated</option><option value="resolved">Resolved</option></Select>} />
      {q.data && <div className="mb-4"><Notice tone="info" title="Operational limits">{q.data.operational_note}</Notice></div>}
      {q.isError ? <ErrorState error={q.error} /> : q.isLoading ? <Skeleton className="h-48" /> : q.data.cases.length === 0 ? <EmptyState icon={<Inbox className="h-6 w-6" />} title="No cases" /> : (
        <ul className="space-y-2">
          {q.data.cases.map((c: any) => (
            <li key={c.id}><Link to={`/support/cases/${c.id}`} className="card flex flex-wrap items-center gap-3 p-4 hover:shadow-lift">
              <Badge tone={PRIORITY_TONE[c.priority]}>{titleCase(c.priority)}</Badge>
              <div className="min-w-0 flex-1"><p className="font-semibold">{c.patient_name} · {titleCase(c.case_type)}</p><p className="truncate text-sm text-ink-3">{c.reason}</p></div>
              <Badge tone={c.status === "resolved" ? "ok" : c.status === "escalated" ? "danger" : "neutral"}>{titleCase(c.status)}</Badge>
              <span className="text-xs text-ink-3">{fmtRelative(c.created_at)}</span>
            </Link></li>
          ))}
        </ul>
      )}
    </>
  );
}
