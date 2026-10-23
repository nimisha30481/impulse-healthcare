import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, BadgeCheck, CalendarDays, ClipboardList, Users } from "lucide-react";
import { Avatar, Badge, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState } from "@/components/ui/feedback";
import { PageHeader, SectionTitle, StatCard } from "@/components/ui/domain";
import { AccessIdUnlock } from "@/features/access/AccessComponents";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, fmtDateTime, fmtTime } from "@/lib/format";
import type { Appointment } from "@/lib/types";

export default function DoctorDashboard() {
  const { user } = useAuth();
  const q = useQuery({ queryKey: ["doctor-dashboard"], queryFn: () => api.get("/api/doctor/dashboard"), refetchInterval: 60_000 });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  return (
    <>
      <PageHeader eyebrow={fmtDate(new Date(), { weekday: "long" })} title={`Good to see you, ${user!.full_name}`} subtitle="Here's what needs your attention, in priority order." />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatCard label="Today's appointments" value={d?.today_appointments.length ?? "—"} icon={<CalendarDays className="h-4 w-4" />} />
        <StatCard label="Adherence alerts" value={d?.adherence_alerts.length ?? "—"} icon={<Activity className="h-4 w-4" />} tone="danger" />
        <StatCard label="Patients" value={d?.patient_count ?? "—"} icon={<Users className="h-4 w-4" />} tone="info" />
      </div>
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-6">
          <AccessIdUnlock compact />
          <section>
            <SectionTitle title="Today & upcoming consultations" icon={<CalendarDays className="h-5 w-5 text-primary" />} action={<Link to="/doctor/appointments" className="link text-sm">Schedule</Link>} />
            {q.isLoading ? <Skeleton className="h-32" /> : [...d.today_appointments, ...d.upcoming].length === 0 ? <EmptyState icon={<CalendarDays className="h-6 w-6" />} title="No upcoming consultations" /> : (
              <ul className="space-y-2">
                {[...d.today_appointments, ...d.upcoming].map((a: Appointment) => (
                  <li key={a.id}><Link to={`/doctor/patients/${a.patient_id}`} className="card flex items-center gap-3 p-3.5 hover:shadow-lift">
                    <span className="w-20 shrink-0 text-center"><span className="block font-display text-lg font-bold">{fmtTime(a.starts_at)}</span><span className="text-xs text-ink-3">{fmtDate(a.starts_at, { year: undefined })}</span></span>
                    <Avatar name={a.patient_name ?? "Patient"} size={36} />
                    <div className="flex-1"><p className="font-semibold">{a.patient_name}</p><p className="text-xs text-ink-3">{a.reason ?? "No reason given"}</p></div>
                    <Badge tone="info">{a.consultation_type.replace("_", " ")}</Badge>
                  </Link></li>
                ))}
              </ul>
            )}
          </section>
        </div>
        <div className="space-y-6">
          <section className="card p-5">
            <SectionTitle title="Adherence alerts" icon={<Activity className="h-5 w-5 text-danger" />} action={<Link to="/doctor/adherence" className="link text-sm">All</Link>} />
            {d?.adherence_alerts.length === 0 ? <p className="text-sm text-ink-3">No open adherence concerns.</p> : (
              <ul className="space-y-2">{d?.adherence_alerts.map((a: any) => (
                <li key={a.patient_id}><Link to={`/doctor/patients/${a.patient_id}`} className="flex items-center justify-between rounded-xl bg-danger-soft/50 px-3 py-2.5 text-sm hover:bg-danger-soft">
                  <span className="font-semibold">{a.patient_name}</span><span className="text-xs">{a.consecutive_unconfirmed} unconfirmed · stage {a.stage}</span>
                </Link></li>))}</ul>
            )}
          </section>
          <section className="card p-5">
            <SectionTitle title="Patients requiring follow-up" icon={<ClipboardList className="h-5 w-5 text-primary" />} action={<Link to="/doctor/follow-ups" className="link text-sm">All</Link>} />
            {d?.follow_ups.length === 0 ? <p className="text-sm text-ink-3">No open follow-ups.</p> : (
              <ul className="space-y-2 text-sm">{d?.follow_ups.slice(0, 6).map((f: any) => (
                <li key={f.id} className="flex items-center justify-between gap-2"><Link to={`/doctor/patients/${f.patient_id}`} className="font-semibold hover:underline">{f.patient_name}</Link>
                  <span className="text-xs text-ink-3">{f.title}{f.due_date && ` · ${fmtDate(f.due_date)}`}</span></li>))}</ul>
            )}
          </section>
          <section className="card p-5">
            <SectionTitle title="Prescription verification" icon={<BadgeCheck className="h-5 w-5 text-primary" />} />
            <p className="text-sm text-ink-2">{d?.pending_verifications ?? 0} uploaded prescription(s) awaiting your verification.</p>
            <Link to="/doctor/verification" className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-primary">Open queue <ArrowRight className="h-4 w-4" /></Link>
          </section>
          <p className="text-xs text-ink-3">Updated {fmtDateTime(new Date().toISOString())}. Data refreshes automatically.</p>
        </div>
      </div>
    </>
  );
}
