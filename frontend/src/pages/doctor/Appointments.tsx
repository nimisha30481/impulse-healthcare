import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarOff, Plus, Save, Trash2 } from "lucide-react";
import clsx from "clsx";
import { Avatar, Badge, Button, Field, Input, Select, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader, Tabs } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtTime, titleCase, WEEKDAYS } from "@/lib/format";
import type { Appointment } from "@/lib/types";
import { DateInput } from "@/components/ui/DateInput";

export default function DoctorAppointments() {
  const [tab, setTab] = useState<"upcoming" | "past" | "availability">("upcoming");
  return (
    <>
      <PageHeader title="Appointments" subtitle="Your consultations and bookable availability." />
      <div className="mb-5"><Tabs label="Appointment views" value={tab} onChange={setTab} tabs={[{ id: "upcoming", label: "Upcoming" }, { id: "past", label: "Past" }, { id: "availability", label: "Availability" }]} /></div>
      {tab === "availability" ? <Availability /> : <List scope={tab} />}
    </>
  );
}

function List({ scope }: { scope: string }) {
  const q = useQuery({ queryKey: ["doctor-appointments", scope], queryFn: () => api.get<Appointment[]>(`/api/doctor/appointments?scope=${scope}`) });
  const qc = useQueryClient();
  const toast = useToast();
  const m = useMutation({ mutationFn: ({ id, status }: { id: string; status: string }) => api.post(`/api/doctor/appointments/${id}/status`, { status }),
    onSuccess: () => { toast("ok", "Updated."); qc.invalidateQueries({ queryKey: ["doctor-appointments"] }); }, onError: (e) => toast("danger", errorMessage(e)) });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.isLoading) return <Skeleton className="h-48" />;
  if (!q.data!.length) return <EmptyState title="No appointments" />;
  return (
    <ul className="space-y-2">
      {q.data!.map((a) => (
        <li key={a.id} className="card flex flex-wrap items-center gap-3 p-4">
          <div className="w-28"><p className="font-display font-bold">{fmtTime(a.starts_at)}</p><p className="text-xs text-ink-3">{fmtDate(a.starts_at, { weekday: "short" })}</p></div>
          <Avatar name={a.patient_name ?? "?"} size={36} />
          <div className="flex-1"><Link to={`/doctor/patients/${a.patient_id}`} className="font-semibold hover:underline">{a.patient_name}</Link><p className="text-xs text-ink-3">{a.reason ?? "No reason given"} · {a.location?.name}</p></div>
          <Badge tone={a.status === "confirmed" ? "ok" : a.status === "cancelled" ? "danger" : "neutral"}>{titleCase(a.status)}</Badge>
          {a.status === "confirmed" && new Date(a.starts_at) < new Date(Date.now() + 3600e3) && <>
            <Button size="sm" variant="outline" onClick={() => m.mutate({ id: a.id, status: "completed" })}>Mark completed</Button>
            <Button size="sm" variant="ghost" onClick={() => m.mutate({ id: a.id, status: "no_show" })}>No-show</Button>
          </>}
        </li>
      ))}
    </ul>
  );
}

function Availability() {
  const q = useQuery({ queryKey: ["availability"], queryFn: () => api.get("/api/doctor/availability") });
  const [rules, setRules] = useState<any[]>([]);
  const [leave, setLeave] = useState({ start_date: "", end_date: "", reason: "" });
  const [day, setDay] = useState(new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" }));
  const slots = useQuery({ queryKey: ["my-slots", day], queryFn: () => api.get(`/api/doctor/slots?day=${day}`) });
  const qc = useQueryClient();
  const toast = useToast();
  useEffect(() => { if (q.data) setRules(q.data.rules); }, [q.data]);
  const save = useMutation({ mutationFn: () => api.put("/api/doctor/availability", { rules: rules.map(({ id: _i, organization_id: _o, ...r }) => ({ ...r, slot_minutes: Number(r.slot_minutes), capacity: Number(r.capacity) })) }),
    onSuccess: (r) => { toast("ok", `Saved. ${r.slots_created} new slots opened.`); qc.invalidateQueries({ queryKey: ["availability"] }); qc.invalidateQueries({ queryKey: ["my-slots"] }); }, onError: (e) => toast("danger", errorMessage(e)) });
  const addLeave = useMutation({ mutationFn: () => api.post("/api/doctor/leave", leave),
    onSuccess: (r) => { toast("ok", `${r.slots_blocked} slots blocked. ${r.note}`); qc.invalidateQueries({ queryKey: ["availability"] }); qc.invalidateQueries({ queryKey: ["my-slots"] }); }, onError: (e) => toast("danger", errorMessage(e)) });
  const block = useMutation({ mutationFn: ({ id, blocked }: { id: string; blocked: boolean }) => api.post(`/api/doctor/slots/${id}/block`, { blocked, reason: "Blocked by doctor" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-slots"] }), onError: (e) => toast("danger", errorMessage(e)) });
  if (!q.data) return <Skeleton className="h-64" />;
  const upd = (i: number, k: string, v: any) => setRules(rules.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <section className="card p-5">
        <h2 className="font-bold">Weekly working hours</h2>
        <div className="mt-3 space-y-2">
          {rules.map((r, i) => (
            <div key={i} className="grid grid-cols-2 items-end gap-2 rounded-xl bg-surface-2 p-3 sm:grid-cols-[1fr_1fr_1fr_90px_80px_auto]">
              <Select aria-label="Weekday" value={r.weekday} onChange={(e) => upd(i, "weekday", Number(e.target.value))}>{WEEKDAYS.map((d, k) => <option key={d} value={k}>{d}</option>)}</Select>
              <Input aria-label="Start" type="time" value={r.start_time} onChange={(e) => upd(i, "start_time", e.target.value)} />
              <Input aria-label="End" type="time" value={r.end_time} onChange={(e) => upd(i, "end_time", e.target.value)} />
              <Input aria-label="Slot minutes" type="number" min={10} max={120} value={r.slot_minutes} onChange={(e) => upd(i, "slot_minutes", e.target.value)} title="Consultation minutes" />
              <Input aria-label="Capacity" type="number" min={1} max={10} value={r.capacity} onChange={(e) => upd(i, "capacity", e.target.value)} title="Capacity per slot" />
              <Button size="sm" variant="ghost" aria-label="Remove" onClick={() => setRules(rules.filter((_, j) => j !== i))} icon={<Trash2 className="h-4 w-4" />} />
            </div>
          ))}
          <p className="text-xs text-ink-3">Columns: day · start · end · consultation minutes · capacity per slot</p>
        </div>
        <div className="mt-3 flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setRules([...rules, { weekday: 0, start_time: "10:00", end_time: "13:00", slot_minutes: 20, capacity: 1, consultation_type: "in_person" }])} icon={<Plus className="h-4 w-4" />}>Add hours</Button>
          <Button size="sm" onClick={() => save.mutate()} loading={save.isPending} icon={<Save className="h-4 w-4" />}>Save availability</Button>
        </div>
        <Notice tone="info">Booked appointments are never removed when you change hours.</Notice>
      </section>
      <div className="space-y-6">
        <section className="card p-5">
          <h2 className="flex items-center gap-2 font-bold"><CalendarOff className="h-5 w-5 text-primary" />Leave</h2>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Field label="From">{(p) => <DateInput {...p} value={leave.start_date} onChange={(v) => setLeave({ ...leave, start_date: v })} />}</Field>
            <Field label="To">{(p) => <DateInput {...p} value={leave.end_date} onChange={(v) => setLeave({ ...leave, end_date: v })} />}</Field>
          </div>
          <Input className="mt-2" aria-label="Reason" placeholder="Reason (optional)" value={leave.reason} onChange={(e) => setLeave({ ...leave, reason: e.target.value })} />
          <Button className="mt-2" size="sm" disabled={!leave.start_date || !leave.end_date} onClick={() => addLeave.mutate()} loading={addLeave.isPending}>Add leave</Button>
          <ul className="mt-3 text-sm text-ink-2">{q.data.leave.map((l: any) => <li key={l.id}>{fmtDate(l.start_date)} – {fmtDate(l.end_date)} {l.reason && `· ${l.reason}`}</li>)}</ul>
        </section>
        <section className="card p-5">
          <h2 className="font-bold">Slots on a day</h2>
          <div className="mt-2"><DateInput aria-label="Day" value={day} onChange={(v) => v && setDay(v)} /></div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {slots.data?.map((s: any) => (
              <button key={s.id} disabled={s.booked > 0} onClick={() => block.mutate({ id: s.id, blocked: s.status !== "blocked" })}
                title={s.booked ? "Booked" : s.status === "blocked" ? "Click to unblock" : "Click to block"}
                className={clsx("rounded-lg px-2 py-1.5 text-xs font-semibold", s.booked ? "bg-ok-soft text-ok" : s.status === "blocked" ? "bg-surface-2 text-ink-3 line-through" : "border border-line hover:bg-surface-2")}>
                {fmtTime(s.starts_at)} {s.booked ? `· ${s.booked}/${s.capacity}` : ""}
              </button>
            ))}
            {slots.data?.length === 0 && <p className="col-span-3 text-sm text-ink-3">No slots.</p>}
          </div>
          <p className="mt-2 text-xs text-ink-3">Updated {fmtDateTime(new Date().toISOString())}</p>
        </section>
      </div>
    </div>
  );
}
