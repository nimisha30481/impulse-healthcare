import { useQuery } from "@tanstack/react-query";
import { BadgeIndianRupee, CheckCircle2, CircleDashed, Cloud, FileKey, MapPinOff, Replace, Rocket, Server } from "lucide-react";
import { Badge, Skeleton } from "@/components/ui/primitives";
import { ErrorState, Notice } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { api } from "@/lib/api";

const STATE = {
  configured: { tone: "ok" as const, label: "Configured", icon: <CheckCircle2 className="h-3 w-3" /> },
  not_configured: { tone: "warn" as const, label: "Not configured — local fallback", icon: <CircleDashed className="h-3 w-3" /> },
  infrastructure: { tone: "info" as const, label: "Infrastructure (IaC)", icon: <Server className="h-3 w-3" /> },
  replaced: { tone: "neutral" as const, label: "Replaced", icon: <Replace className="h-3 w-3" /> },
  covered: { tone: "ok" as const, label: "Covered by another service", icon: <Replace className="h-3 w-3" /> },
  deploy_only: { tone: "info" as const, label: "Used when deployed to AWS", icon: <Rocket className="h-3 w-3" /> },
  optional_cost: { tone: "neutral" as const, label: "Optional · off (monthly cost)", icon: <BadgeIndianRupee className="h-3 w-3" /> },
  unavailable_region: { tone: "neutral" as const, label: "Not offered in Mumbai region", icon: <MapPinOff className="h-3 w-3" /> },
  licence_required: { tone: "neutral" as const, label: "Needs a licensed provider", icon: <FileKey className="h-3 w-3" /> },
};

export default function Integrations() {
  const q = useQuery({ queryKey: ["integrations"], queryFn: () => api.get("/api/integrations/status") });
  if (q.isError) return <ErrorState error={q.error} />;
  return (
    <>
      <PageHeader title="Platform status" subtitle="Which AWS services this environment actually uses. 'Configured' means credentials are set — not that the integration has been tested."
        eyebrow={<span className="inline-flex items-center gap-1"><Cloud className="h-4 w-4" />AWS integrations</span>} />
      {q.data && <div className="mb-5 space-y-3">
        <Notice tone="info">Environment: <b>{q.data.environment}</b> · Sign-in: <b>{q.data.auth_provider === "cognito" ? "Amazon Cognito" : "DoseWISE local auth"}</b> ·{" "}
          <b>{q.data.services.filter((s: any) => s.state === "configured").length}</b> services connected. Full details: docs/AWS_ARCHITECTURE.md.</Notice>
        {q.data.services.some((s: any) => s.state === "not_configured") && (
          <Notice tone="warn" title="Some services can still be switched on">
            Services marked "Not configured" turn on with one command, once the AWS user has the permissions in docs/aws-iam-policy.json:
            <code className="mt-1 block font-mono text-xs">backend\.venv\Scripts\python.exe scripts\aws_setup.py --extras --ses-email you@example.com</code>
          </Notice>
        )}
      </div>}
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
