import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Building2, Clock, FlaskConical, LocateFixed, MapPin, Navigation, Phone, Pill, Search, Stethoscope } from "lucide-react";
import { Badge, Button, Input, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Notice } from "@/components/ui/feedback";
import { DemoTag, PageHeader, Tabs } from "@/components/ui/domain";
import { api } from "@/lib/api";

const KIND_ICON: Record<string, any> = { hospital: Building2, clinic: Stethoscope, pharmacy: Pill, laboratory: FlaskConical };

export default function Directory() {
  const [kind, setKind] = useState<"" | "hospital" | "pharmacy" | "laboratory" | "doctors">("");
  const [q, setQ] = useState("");
  const [service, setService] = useState("");
  const [near, setNear] = useState("");
  const [loc, setLoc] = useState<{ lat: number; lng: number } | null>(null);
  const [locErr, setLocErr] = useState<string | null>(null);
  const params = new URLSearchParams({ ...(q && { q }), ...(kind && kind !== "doctors" && { kind }), ...(service && { service }),
    ...(loc ? { lat: String(loc.lat), lng: String(loc.lng) } : near ? { near } : {}) }).toString();
  const orgs = useQuery({ queryKey: ["directory", params], queryFn: () => api.get(`/api/directory?${params}`), enabled: kind !== "doctors" });
  const docs = useQuery({ queryKey: ["directory-doctors", q], queryFn: () => api.get(`/api/directory/doctors?q=${encodeURIComponent(q)}`), enabled: kind === "doctors" });
  const useMyLocation = () => {
    setLocErr(null);
    if (!navigator.geolocation) return setLocErr("Location isn't available in this browser.");
    navigator.geolocation.getCurrentPosition((p) => setLoc({ lat: p.coords.latitude, lng: p.coords.longitude }), () => setLocErr("Location permission was not granted. You can type a place instead."), { timeout: 8000 });
  };
  return (
    <div className="container-page max-w-6xl py-2">
      <PageHeader title="Find care" subtitle="Hospitals, pharmacies, laboratories and doctors. Location is optional — type a place instead if you prefer." />
      <Notice tone="warn" title="Demonstration directory">Entries marked DEMO are fictional. Medicine stock is never shown unless a verified pharmacy integration supplies it.</Notice>
      <div className="my-5"><Tabs label="Directory type" value={kind} onChange={setKind} tabs={[{ id: "", label: "All" }, { id: "hospital", label: "Hospitals" }, { id: "pharmacy", label: "Pharmacies" }, { id: "laboratory", label: "Laboratories" }, { id: "doctors", label: "Doctors" }]} /></div>
      <div className="card mb-5 grid gap-3 p-4 md:grid-cols-[1.4fr_1fr_1fr_auto]">
        <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <Input aria-label="Search by name" className="pl-9" placeholder="Name, speciality or area" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        {kind !== "doctors" && <>
          <Input aria-label="Service" placeholder="Service (e.g. Cardiology, Blood tests)" value={service} onChange={(e) => setService(e.target.value)} />
          <Input aria-label="Near a place" placeholder="Near… (city or area)" value={near} onChange={(e) => { setNear(e.target.value); setLoc(null); }} />
          <Button variant={loc ? "secondary" : "outline"} onClick={useMyLocation} icon={<LocateFixed className="h-4 w-4" />}>{loc ? "Using my location" : "Use my location"}</Button>
        </>}
      </div>
      {locErr && <div className="mb-4"><Notice tone="info">{locErr}</Notice></div>}
      {kind === "doctors" ? (
        docs.isLoading ? <Skeleton className="h-40" /> : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{docs.data?.map((d: any) => (
            <li key={d.id} className="card p-4"><p className="font-bold">{d.name} {d.is_demo && <DemoTag />}</p><p className="text-sm text-ink-3">{d.speciality} · {d.organization ?? "Independent"}</p><p className="mt-1 text-xs text-ink-3">{d.languages?.join(", ")}</p></li>))}</ul>
        )
      ) : orgs.isError ? <ErrorState error={orgs.error} /> : orgs.isLoading ? <Skeleton className="h-64" /> : orgs.data.results.length === 0 ? <EmptyState icon={<MapPin className="h-6 w-6" />} title="No results" /> : (
        <>
          <p className="mb-3 text-xs text-ink-3">Search: {orgs.data.search_engine === "opensearch" ? "Amazon OpenSearch" : "database"}{orgs.data.geocoded && ` · near ${orgs.data.geocoded}`}{near && !orgs.data.geocoded && !loc && " · location lookup not configured, showing all"}</p>
          <ul className="grid gap-4 md:grid-cols-2">
            {orgs.data.results.map((o: any, i: number) => {
              const Icon = KIND_ICON[o.kind] ?? Building2;
              return (
                <motion.li key={o.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }} className="card p-5">
                  <div className="flex items-start gap-3">
                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary-soft text-primary"><Icon className="h-5 w-5" /></span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2"><p className="font-bold">{o.name}</p>{o.data_source === "demo" ? <DemoTag /> : o.is_verified && <Badge tone="ok">Verified</Badge>}</div>
                      <p className="text-sm text-ink-3">{o.address}, {o.city}</p>
                    </div>
                    {o.distance_km != null && <Badge tone="info">{o.distance_km} km</Badge>}
                  </div>
                  <dl className="mt-3 space-y-1 text-sm">
                    {o.opening_hours && <div className="flex gap-2"><Clock className="h-4 w-4 text-ink-3" /><dd>{o.opening_hours}</dd></div>}
                    {o.phone && <div className="flex gap-2"><Phone className="h-4 w-4 text-ink-3" /><dd><a className="link" href={`tel:${o.phone}`}>{o.phone}</a></dd></div>}
                  </dl>
                  {(o.departments?.length > 0 || o.services?.length > 0) && <div className="mt-3 flex flex-wrap gap-1">{[...o.departments, ...o.services].slice(0, 6).map((s: string) => <Badge key={s}>{s}</Badge>)}</div>}
                  {o.medicine_availability && <p className="mt-3 text-xs text-ink-3">Medicine availability: {o.medicine_availability.note}</p>}
                  {o.kind === "hospital" && <p className="mt-1 text-xs text-ink-3">Appointment availability: book through a doctor's profile in Appointments.</p>}
                  {o.directions_url && <a href={o.directions_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-primary"><Navigation className="h-4 w-4" />Directions</a>}
                </motion.li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
