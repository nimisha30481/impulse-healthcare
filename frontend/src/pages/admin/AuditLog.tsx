import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, ShieldX } from "lucide-react";
import { Badge, Input, Skeleton } from "@/components/ui/primitives";
import { ErrorState, Notice } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

export default function AuditLog() {
  const [action, setAction] = useState("");
  const q = useQuery({ queryKey: ["audit", action], queryFn: () => api.get(`/api/admin/audit?action=${encodeURIComponent(action)}&limit=200`) });
  return (
    <>
      <PageHeader title="Audit log" subtitle="Hash-chained, tamper-evident record of sensitive actions. Viewing this log is itself audited." />
      {q.data && (
        <div className="mb-4">{q.data.chain.valid
          ? <Notice tone="ok" icon={<ShieldCheck className="h-[18px] w-[18px]" />} title="Chain verified">{q.data.chain.entries} entries; no tampering detected.</Notice>
          : <Notice tone="danger" icon={<ShieldX className="h-[18px] w-[18px]" />} title="Chain broken">Integrity check failed at entry #{q.data.chain.broken_at_seq}. Investigate immediately.</Notice>}</div>
      )}
      <Input aria-label="Filter by action" placeholder="Filter by action (e.g. prescription, login, permission)" className="mb-4 max-w-md" value={action} onChange={(e) => setAction(e.target.value)} />
      {q.isError ? <ErrorState error={q.error} /> : q.isLoading ? <Skeleton className="h-96" /> : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="border-b border-line text-xs uppercase text-ink-3"><tr><th className="p-2.5">#</th><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Context</th><th>Reason / version</th><th>Outcome</th></tr></thead>
            <tbody>{q.data.entries.map((e: any) => (
              <tr key={e.seq} className="border-b border-line last:border-0">
                <td className="p-2.5 font-mono text-xs text-ink-3">{e.seq}</td>
                <td className="whitespace-nowrap">{fmtDateTime(e.at)}</td>
                <td className="text-xs">{e.role ?? "system"} <span className="font-mono text-ink-3">{e.user_id?.slice(0, 8)}</span></td>
                <td className="font-semibold">{e.action}</td>
                <td className="text-xs">{e.resource_type} <span className="font-mono text-ink-3">{e.resource_id?.slice(0, 8)}</span></td>
                <td className="text-xs">{e.auth_context ?? "—"}</td>
                <td className="max-w-[220px] truncate text-xs text-ink-3" title={e.reason ?? ""}>{e.version_ref ?? e.reason ?? ""}</td>
                <td><Badge tone={e.outcome === "success" ? "ok" : "danger"}>{e.outcome}</Badge></td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </>
  );
}
