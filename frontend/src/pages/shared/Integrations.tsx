import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Cloud, Replace, Server } from "lucide-react";
import { Badge, Skeleton } from "@/components/ui/primitives";
import { ErrorState, Notice } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { api } from "@/lib/api";

const STATE = {
  configured: { tone: "ok" as const, label: "Configured", icon: <CheckCircle2 className="h-3 w-3" /> },
  not_configured: { tone: "warn" as const, label: "Not configured — local fallback", icon: <CircleDashed className="h-3 w-3" /> },
  infrastructure: { tone: "info" as const, label: "Infrastructure (IaC)", icon: <Server className="h-3 w-3" /> },
  replaced: { tone: "neutral" as const, label: "Replaced", icon: <Replace className="h-3 w-3" /> },
};

export default function Integrations() {
  const q = useQuery({ queryKey: ["integrations"], queryFn: () => api.get("/api/integrations/status") });
  if (q.isError) return <ErrorState error={q.error} />;
  return (
    <>
      <PageHeader title="Platform status" subtitle="Which AWS services this environment actually uses. 'Configured' means credentials are set — not that the integration has been tested."
        eyebrow={<span className="inline-flex items-center gap-1"><Cloud className="h-4 w-4" />AWS integrations</span>} />
      {q.data && <div className="mb-5"><Notice tone="info">Environment: <b>{q.data.environment}</b> · Sign-in: <b>{q.data.auth_provider === "cognito" ? "Amazon Cognito" : "IMPULSE local auth"}</b>. Full details: docs/AWS_ARCHITECTURE.md.</Notice></div>}
      {!q.data ? <Skeleton className="h-96" /> : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-line text-xs uppercase text-ink-3"><tr><th className="p-3">Service</th><th>Used for</th><th>State</th><th>Phase</th><th>Fallback / note</th></tr></thead>
            <tbody>{q.data.services.map((s: any) => {
              const st = STATE[s.state as keyof typeof STATE] ?? STATE.not_configured;
              return (
                <tr key={s.service} className="border-b border-line last:border-0 align-top">
                  <td className="p-3 font-semibold">{s.service}</td><td className="py-3 pr-3">{s.module}</td>
                  <td className="py-3 pr-3"><Badge tone={st.tone} icon={st.icon}>{st.label}</Badge></td><td className="py-3">{s.phase}</td>
                  <td className="py-3 pr-3 text-ink-3">{s.fallback}{s.note && <span className="block text-xs">{s.note}</span>}</td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      )}
    </>
  );
}
