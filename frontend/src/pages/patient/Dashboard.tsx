import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, Bell, CalendarDays, ClipboardCheck, HeartHandshake, MapPin, Phone, Pill, Video } from "lucide-react";
import { Avatar, Badge, Button, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState } from "@/components/ui/feedback";
import { SectionTitle } from "@/components/ui/domain";
import { DoseCard } from "@/features/doses/DoseCard";
import { AdherenceCard } from "@/features/adherence/AdherenceCard";
import { InstructionsList } from "@/features/instructions/InstructionsList";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, fmtDateTime, fmtRelative, greetingKey, titleCase } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { Appointment, NotificationItem } from "@/lib/types";

export default function PatientDashboard() {
  const { user } = useAuth();
  const pid = user!.patient_id!;
  const t = useT();
  const q = useQuery({ queryKey: ["overview", pid], queryFn: () => api.get(`/api/patients/${pid}/overview`), refetchInterval: 60_000 });
  const notes = useQuery({ queryKey: ["notifications", "list"], queryFn: () => api.get("/api/notifications") });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const doses = d?.today ?? [];
  const reported = doses.filter((x: any) => ["taken_reported", "missed_reported", "skipped"].includes(x.status)).length;

  return (
    <div className="space-y-6">
      <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary to-[#0b4a4e] p-6 text-white shadow-lift sm:p-8 dark:from-primary-soft dark:to-surface dark:text-ink">
        <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-mint/20 blur-2xl" />
        <div className="relative flex flex-wrap items-center gap-4">
          <Avatar name={user!.full_name} color="rgb(255 255 255 / 0.18)" size={56} className="ring-2 ring-white/30" />
          <div className="flex-1">
            <p className="text-sm opacity-80">{fmtDate(new Date(), { weekday: "long", year: undefined })}</p>
            <h1 className="text-2xl font-extrabold text-inherit sm:text-3xl">{t(greetingKey())}, {d?.patient.preferred_name ?? user!.preferred_name ?? ""}</h1>
            <p className="mt-1 text-sm opacity-85">
              {q.isLoading ? "Loading your day…" : doses.length ? `${reported} of ${doses.length} doses answered today.` : "No doses scheduled today."}
            </p>
          </div>
          <Link to="/notifications" className="flex items-center gap-2 rounded-xl bg-white/15 px-3 py-2 text-sm font-semibold backdrop-blur hover:bg-white/25">
            <Bell className="h-4 w-4" /> {notes.data?.unread ?? 0} new
          </Link>
        </div>
      </motion.section>

      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <section aria-labelledby="today">
          <SectionTitle title={`${t("common.today")}'s medication schedule`} icon={<Pill className="h-5 w-5 text-primary" />}
            action={<Link to="/patient/medicines" className="link text-sm">All medicines</Link>} />
          <div className="space-y-3" id="today">
            {q.isLoading ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-32" />) :
              doses.length === 0 ? <EmptyState icon={<Pill className="h-6 w-6" />} title="Nothing scheduled today" body="Medicines your doctor prescribes in IMPULSE appear here with reminders." /> :
              doses.map((dose: any, i: number) => (
                <DoseCard key={dose.id} dose={dose} patientId={pid} index={i} detailHref={`/patient/medicines/${dose.item_id}`} />
              ))}
          </div>
        </section>
        <div className="space-y-6">
          <NextAppointment appt={d?.next_appointment} loading={q.isLoading} />
          <InstructionsList patientId={pid} compact />
          <CareTeamCard team={d?.care_team} loading={q.isLoading} />
        </div>
      </div>

      {d && <AdherenceCard patientId={pid} initial={d.adherence} />}

      <section>
        <SectionTitle title="Recent notifications" icon={<Bell className="h-5 w-5 text-primary" />} action={<Link to="/notifications" className="link text-sm">View all</Link>} />
        <div className="card divide-y divide-line">
          {(notes.data?.items ?? []).slice(0, 5).map((n: NotificationItem) => (
            <div key={n.id} className="flex items-start gap-3 p-4">
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read_at ? "bg-line" : "bg-primary"}`} aria-hidden />
              <div className="flex-1">
                <p className="text-sm font-semibold">{n.title}</p>
                <p className="text-sm text-ink-3">{n.body}</p>
              </div>
              <span className="text-xs text-ink-3">{fmtRelative(n.created_at)}</span>
            </div>
          ))}
          {notes.data?.items?.length === 0 && <p className="p-4 text-sm text-ink-3">You're all caught up.</p>}
        </div>
      </section>
    </div>
  );
}

function NextAppointment({ appt, loading }: { appt?: Appointment | null; loading: boolean }) {
  return (
    <section className="card p-5" aria-labelledby="next-appt">
      <SectionTitle title="Upcoming appointment" icon={<CalendarDays className="h-5 w-5 text-primary" />} />
      {loading ? <Skeleton className="h-28" /> : !appt ? (
        <div className="text-sm text-ink-3">
          No upcoming appointments. <Link to="/patient/appointments?book=1" className="link">Book one</Link>
        </div>
      ) : (
        <div id="next-appt">
          <div className="flex items-center gap-3">
            <Avatar name={appt.doctor.name} color={appt.doctor.avatar_color} size={44} />
            <div>
              <p className="font-bold">{appt.doctor.name}</p>
              <p className="text-sm text-ink-3">{appt.doctor.speciality}</p>
            </div>
            <Badge tone="ok" className="ml-auto">{titleCase(appt.status)}</Badge>
          </div>
          <dl className="mt-4 space-y-1.5 text-sm">
            <div className="flex gap-2"><dt className="sr-only">When</dt><CalendarDays className="h-4 w-4 text-ink-3" /><dd className="font-semibold">{fmtDateTime(appt.starts_at)}</dd></div>
            {appt.location && <div className="flex gap-2"><dt className="sr-only">Where</dt><MapPin className="h-4 w-4 text-ink-3" /><dd>{appt.location.name}</dd></div>}
            <div className="flex gap-2"><dt className="sr-only">Type</dt>{appt.consultation_type === "video" ? <Video className="h-4 w-4 text-ink-3" /> : <ClipboardCheck className="h-4 w-4 text-ink-3" />}<dd>{titleCase(appt.consultation_type)}</dd></div>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to={`/patient/appointments?view=${appt.id}`}><Button size="sm" variant="outline">View details</Button></Link>
            <Link to={`/patient/appointments?reschedule=${appt.id}`}><Button size="sm" variant="outline">Reschedule</Button></Link>
            <Link to={`/patient/appointments?cancel=${appt.id}`}><Button size="sm" variant="ghost">Cancel</Button></Link>
          </div>
        </div>
      )}
    </section>
  );
}

function CareTeamCard({ team, loading }: { team?: any; loading: boolean }) {
  return (
    <section className="card p-5">
      <SectionTitle title="Care team" icon={<HeartHandshake className="h-5 w-5 text-primary" />} action={<Link to="/patient/care-team" className="link text-sm">Manage</Link>} />
      {loading ? <Skeleton className="h-24" /> : (
        <ul className="space-y-3">
          {team?.doctors?.map((d: any) => (
            <li key={d.access_id} className="flex items-center gap-3">
              <Avatar name={d.doctor.name} color={d.doctor.avatar_color} size={36} />
              <div className="flex-1"><p className="text-sm font-semibold">{d.doctor.name}</p><p className="text-xs text-ink-3">{d.doctor.speciality}</p></div>
              {d.phone && <a href={`tel:${d.phone}`} className="rounded-lg p-2 text-ink-3 hover:bg-surface-2" aria-label={`Call ${d.doctor.name}`}><Phone className="h-4 w-4" /></a>}
            </li>
          ))}
          {team?.caregivers?.filter((c: any) => c.status !== "revoked").map((c: any) => (
            <li key={c.id} className="flex items-center gap-3">
              <Avatar name={c.caregiver?.name ?? c.contact} color={c.caregiver?.avatar_color ?? "#94a3b8"} size={36} />
              <div className="flex-1"><p className="text-sm font-semibold">{c.caregiver?.name ?? c.contact}</p><p className="text-xs text-ink-3">{c.label}</p></div>
              <Badge tone={c.status === "active" ? "ok" : "warn"}>{titleCase(c.status)}</Badge>
            </li>
          ))}
          {!team?.doctors?.length && !team?.caregivers?.length && <p className="text-sm text-ink-3">No one is on your care team yet.</p>}
        </ul>
      )}
      <Link to="/messages" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-primary">Message your care team <ArrowRight className="h-4 w-4" /></Link>
    </section>
  );
}
