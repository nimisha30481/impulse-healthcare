import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CalendarPlus, MapPin, Video } from "lucide-react";
import { Avatar, Badge, Button, Skeleton, Textarea } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader, SectionTitle } from "@/components/ui/domain";
import { BookingWizard } from "@/features/appointments/BookingWizard";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, fmtDateTime, titleCase } from "@/lib/format";
import type { Appointment, Instruction } from "@/lib/types";

export function AppointmentsView({ patientId, canBook }: { patientId: string; canBook: boolean }) {
  const [params, setParams] = useSearchParams();
  const q = useQuery({ queryKey: ["appointments", patientId], queryFn: () => api.get(`/api/patients/${patientId}/appointments`) });
  const [booking, setBooking] = useState<{ followUp?: string | null; reschedule?: any } | null>(null);
  const [view, setView] = useState<Appointment | null>(null);
  const [cancel, setCancel] = useState<Appointment | null>(null);
  const [reason, setReason] = useState("");
  const qc = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    if (!q.data) return;
    const all: Appointment[] = [...q.data.upcoming, ...q.data.past];
    if (params.get("book")) setBooking({ followUp: params.get("follow_up") });
    const find = (k: string) => all.find((a) => a.id === params.get(k));
    if (params.get("view")) setView(find("view") ?? null);
    if (params.get("cancel")) setCancel(find("cancel") ?? null);
    const r = find("reschedule");
    if (r) setBooking({ reschedule: { id: r.id, doctorId: r.doctor.id, speciality: r.doctor.speciality } });
    if ([...params.keys()].length) setParams({}, { replace: true });
  }, [q.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const cancelM = useMutation({
    mutationFn: () => api.post(`/api/appointments/${cancel!.id}/cancel`, { reason }),
    onSuccess: () => { toast("ok", "Appointment cancelled."); setCancel(null); setReason(""); qc.invalidateQueries({ queryKey: ["appointments"] }); qc.invalidateQueries({ queryKey: ["overview"] }); },
    onError: (e) => toast("danger", errorMessage(e)),
  });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const Card = ({ a }: { a: Appointment }) => (
    <li className="card flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
      <div className="flex w-16 shrink-0 flex-col items-center rounded-xl bg-primary-soft py-2 text-primary">
        <span className="text-xs font-semibold uppercase">{fmtDate(a.starts_at, { month: "short", day: undefined, year: undefined })}</span>
        <span className="font-display text-2xl font-extrabold">{fmtDate(a.starts_at, { day: "numeric", month: undefined, year: undefined })}</span>
      </div>
      <div className="flex flex-1 items-center gap-3">
        <Avatar name={a.doctor.name} color={a.doctor.avatar_color} size={40} />
        <div>
          <p className="font-bold">{a.doctor.name} <span className="text-sm font-medium text-ink-3">· {a.doctor.speciality}</span></p>
          <p className="text-sm text-ink-2">{fmtDateTime(a.starts_at)}{a.location && ` · ${a.location.name}`}</p>
        </div>
      </div>
      <Badge tone={a.status === "confirmed" ? "ok" : a.status === "cancelled" ? "danger" : "neutral"}>{titleCase(a.status)}</Badge>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={() => setView(a)}>Details</Button>
        {canBook && a.status === "confirmed" && new Date(a.starts_at) > new Date() && <>
          <Button size="sm" variant="outline" onClick={() => setBooking({ reschedule: { id: a.id, doctorId: a.doctor.id, speciality: a.doctor.speciality } })}>Reschedule</Button>
          <Button size="sm" variant="ghost" onClick={() => setCancel(a)}>Cancel</Button>
        </>}
      </div>
    </li>
  );

  return (
    <div className="space-y-8">
      {canBook && <div><Button onClick={() => setBooking({})} icon={<CalendarPlus className="h-4 w-4" />}>Book appointment</Button></div>}
      {q.data?.recommended_follow_ups?.length > 0 && (
        <section>
          <SectionTitle title="Recommended follow-ups (not booked)" />
          <ul className="space-y-2">{q.data.recommended_follow_ups.map((f: Instruction) => (
            <li key={f.id} className="card flex flex-wrap items-center gap-3 border-dashed p-4">
              <Badge tone="info">Recommendation</Badge>
              <div className="flex-1"><p className="font-semibold">{f.title}</p><p className="text-sm text-ink-3">{f.author?.name} · {f.due_date ? `by ${fmtDate(f.due_date)}` : f.timeframe}</p></div>
              {f.appointment_id ? <Badge tone="ok">Booked</Badge> : canBook && <Button size="sm" variant="secondary" onClick={() => setBooking({ followUp: f.id })}>Book now</Button>}
            </li>))}
          </ul>
        </section>
      )}
      <section>
        <SectionTitle title="Upcoming" icon={<CalendarDays className="h-5 w-5 text-primary" />} />
        {q.isLoading ? <Skeleton className="h-24" /> : q.data.upcoming.length === 0 ? <EmptyState icon={<CalendarDays className="h-6 w-6" />} title="No upcoming appointments" /> :
          <ul className="space-y-3">{q.data.upcoming.map((a: Appointment) => <Card key={a.id} a={a} />)}</ul>}
      </section>
      <section>
        <SectionTitle title="History" />
        {q.data?.past?.length ? <ul className="space-y-3">{q.data.past.map((a: Appointment) => <Card key={a.id} a={a} />)}</ul> : <p className="text-sm text-ink-3">No past appointments.</p>}
      </section>

      <BookingWizard patientId={patientId} open={!!booking} onClose={() => setBooking(null)} followUpId={booking?.followUp} reschedule={booking?.reschedule} />
      <Modal open={!!view} onClose={() => setView(null)} title="Appointment details">
        {view && (
          <div className="space-y-3 text-sm">
            <p className="text-lg font-bold">{view.doctor.name}</p>
            <p className="text-ink-3">{view.doctor.speciality}</p>
            <p className="flex items-center gap-2"><CalendarDays className="h-4 w-4" />{fmtDateTime(view.starts_at)}</p>
            {view.location && <p className="flex items-center gap-2"><MapPin className="h-4 w-4" />{view.location.name}, {view.location.address}</p>}
            <p className="flex items-center gap-2"><Video className="h-4 w-4" />{titleCase(view.consultation_type)}</p>
            {view.reason && <p><b>Reason:</b> {view.reason}</p>}
            {view.consultation_type === "video" && <Notice tone="info">Joining video consultations from IMPULSE isn't available yet.</Notice>}
            <div><p className="font-semibold">History</p><ul className="mt-1 text-ink-3">{view.history.map((h, i) => <li key={i}>{fmtDateTime(h.at)} — {h.event}</li>)}</ul></div>
          </div>
        )}
      </Modal>
      <Modal open={!!cancel} onClose={() => setCancel(null)} title="Cancel appointment" size="sm"
        footer={<><Button variant="outline" onClick={() => setCancel(null)}>Keep it</Button><Button variant="danger" onClick={() => cancelM.mutate()} disabled={reason.trim().length < 3} loading={cancelM.isPending}>Cancel appointment</Button></>}>
        <p className="text-sm text-ink-2">{cancel && `${cancel.doctor.name}, ${fmtDateTime(cancel.starts_at)}`}</p>
        <Textarea className="mt-3" aria-label="Reason for cancelling" placeholder="Reason (shared with the clinic)" value={reason} onChange={(e) => setReason(e.target.value)} />
      </Modal>
    </div>
  );
}

export default function Appointments() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader title="Appointments" subtitle="Book, reschedule and review your visits." />
      <AppointmentsView patientId={user!.patient_id!} canBook />
    </>
  );
}
