import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ChevronRight, Pill, Search, Upload } from "lucide-react";
import { Button, Input, Select, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState } from "@/components/ui/feedback";
import { PageHeader, RxStatus, Tabs } from "@/components/ui/domain";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { MedItem } from "@/lib/types";

type Bucket = "current" | "upcoming" | "completed" | "discontinued";

export function MedicineList({ patientId, hrefFor }: { patientId: string; hrefFor: (id: string) => string }) {
  const [bucket, setBucket] = useState<Bucket>("current");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("name");
  const [route, setRoute] = useState("");
  const q = useQuery({ queryKey: ["medications", patientId], queryFn: () => api.get<MedItem[]>(`/api/patients/${patientId}/medications`) });
  const all = q.data ?? [];
  const counts = useMemo(() => Object.fromEntries((["current", "upcoming", "completed", "discontinued"] as Bucket[])
    .map((b) => [b, all.filter((m) => m.bucket === b).length])), [all]);
  const rows = all
    .filter((m) => m.bucket === bucket)
    .filter((m) => !route || m.current.route === route)
    .filter((m) => !search || `${m.current.generic_name} ${m.current.brand_name ?? ""}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => sort === "name" ? a.current.generic_name.localeCompare(b.current.generic_name)
      : sort === "start" ? b.current.start_date.localeCompare(a.current.start_date) : b.updated_at.localeCompare(a.updated_at));
  const routes = [...new Set(all.map((m) => m.current.route))];

  return (
    <div className="space-y-4">
      <Tabs label="Medicine groups" value={bucket} onChange={setBucket} tabs={[
        { id: "current", label: "Current", count: counts.current }, { id: "upcoming", label: "Upcoming", count: counts.upcoming },
        { id: "completed", label: "Completed", count: counts.completed }, { id: "discontinued", label: "Discontinued", count: counts.discontinued },
      ]} />
      <div className="grid gap-3 sm:grid-cols-[1fr_180px_180px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <Input aria-label="Search medicines" placeholder="Search by name or brand" className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Select aria-label="Filter by route" value={route} onChange={(e) => setRoute(e.target.value)}>
          <option value="">All routes</option>{routes.map((r) => <option key={r} value={r}>{r}</option>)}
        </Select>
        <Select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="name">Sort: Name</option><option value="start">Sort: Start date</option><option value="updated">Sort: Recently changed</option>
        </Select>
      </div>
      {q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : q.isLoading ? (
        <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}</div>
      ) : rows.length === 0 ? (
        <EmptyState icon={<Pill className="h-6 w-6" />} title={`No ${bucket} medicines`} body={search ? "Try a different search." : undefined} />
      ) : (
        <ul className="space-y-2.5">
          {rows.map((m, i) => (
            <motion.li key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
              <Link to={hrefFor(m.id)} className="card flex items-center gap-4 p-4 transition hover:-translate-y-0.5 hover:shadow-lift">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary-soft text-primary"><Pill className="h-5 w-5" /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-bold">{m.current.generic_name} <span className="font-medium text-ink-3">{m.current.strength}</span></p>
                    <RxStatus status={m.status} />
                    {m.pending_change && <span className="text-xs font-semibold text-info">Change scheduled</span>}
                  </div>
                  <p className="truncate text-sm text-ink-2">{m.current.dose_amount} {m.current.dose_unit} · {m.current.route} · {m.current.frequency_label}
                    {m.current.schedule?.times_of_day?.length ? ` · ${m.current.schedule.times_of_day.join(", ")}` : ""}</p>
                  <p className="text-xs text-ink-3">{m.prescriber?.name ?? "External provider"} · since {fmtDate(m.current.start_date)}{m.current.end_date ? ` → ${fmtDate(m.current.end_date)}` : ""}</p>
                </div>
                <ChevronRight className="h-5 w-5 text-ink-3" />
              </Link>
            </motion.li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Medicines() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader title="My Medicines" subtitle="Everything prescribed to you, including past changes."
        actions={<Link to="/patient/records?upload=prescription"><Button variant="outline" icon={<Upload className="h-4 w-4" />}>Upload a prescription</Button></Link>} />
      <MedicineList patientId={user!.patient_id!} hrefFor={(id) => `/patient/medicines/${id}`} />
    </>
  );
}
