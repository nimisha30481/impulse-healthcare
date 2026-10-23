import { useQuery } from "@tanstack/react-query";
import { Download, FileDown, RefreshCw } from "lucide-react";
import { Badge, Button, Skeleton } from "@/components/ui/primitives";
import { PageHeader, SectionTitle, StatCard } from "@/components/ui/domain";
import { AdherenceCard } from "@/features/adherence/AdherenceCard";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, titleCase } from "@/lib/format";
import type { MedItem } from "@/lib/types";

export default function Reports() {
  const { user } = useAuth();
  const pid = user!.patient_id!;
  const meds = useQuery({ queryKey: ["medications", pid], queryFn: () => api.get<MedItem[]>(`/api/patients/${pid}/medications`) });
  const refills = useQuery({ queryKey: ["refills", pid], queryFn: () => api.get(`/api/patients/${pid}/refills`) });
  const all = meds.data ?? [];
  return (
    <>
      <PageHeader title="Reports" subtitle="Your adherence and medication activity, explained."
        actions={<a href="/api/account/export" download><Button variant="outline" icon={<FileDown className="h-4 w-4" />}>Download my data</Button></a>} />
      <div className="mb-6 grid gap-4 sm:grid-cols-4">
        <StatCard label="Current medicines" value={all.filter((m) => m.bucket === "current").length} />
        <StatCard label="Upcoming" value={all.filter((m) => m.bucket === "upcoming").length} tone="info" />
        <StatCard label="Completed courses" value={all.filter((m) => m.bucket === "completed").length} tone="ok" />
        <StatCard label="Discontinued" value={all.filter((m) => m.bucket === "discontinued").length} tone="warn" />
      </div>
      <AdherenceCard patientId={pid} />
      <section className="mt-6">
        <SectionTitle title="Refill requests" icon={<RefreshCw className="h-5 w-5 text-primary" />} />
        {refills.isLoading ? <Skeleton className="h-16" /> : (
          <ul className="card divide-y divide-line">
            {refills.data?.map((r: any) => {
              const med = all.find((m) => m.id === r.item_id);
              return (
                <li key={r.id} className="flex items-center justify-between p-4 text-sm">
                  <span><b>{med?.current.generic_name ?? "Medicine"}</b> · requested {fmtDate(r.created_at)}{r.review_note && ` · ${r.review_note}`}</span>
                  <Badge tone={r.status === "approved" ? "ok" : r.status === "declined" ? "danger" : "warn"}>{titleCase(r.status)}</Badge>
                </li>
              );
            })}
            {refills.data?.length === 0 && <li className="p-4 text-sm text-ink-3">No refill requests. Request one from a medicine's detail page.</li>}
          </ul>
        )}
      </section>
      <p className="mt-6 flex items-center gap-1.5 text-xs text-ink-3"><Download className="h-3.5 w-3.5" />Data downloads are recorded in your access history.</p>
    </>
  );
}
