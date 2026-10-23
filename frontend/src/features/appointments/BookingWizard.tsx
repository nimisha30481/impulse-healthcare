import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, CalendarCheck2, CheckCircle2, Clock, MapPin, Stethoscope, Timer } from "lucide-react";
import clsx from "clsx";
import { Avatar, Badge, Button, Field, Input, Skeleton } from "@/components/ui/primitives";
import { EmptyState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { DemoTag } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtTime, titleCase } from "@/lib/format";

const STEPS = ["Speciality", "Doctor", "Date & time", "Review", "Done"];

function nextDays(n: number) {
  const out: string[] = [];
  const d = new Date();
  for (let i = 0; i < n; i++) {
    const x = new Date(d);
    x.setDate(d.getDate() + i);
    out.push(x.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" }));
  }
  return out;
}

export function BookingWizard({ patientId, open, onClose, followUpId, reschedule }: {
  patientId: string; open: boolean; onClose: () => void; followUpId?: string | null; reschedule?: { id: string; doctorId: string; speciality?: string } | null;
}) {
  const [step, setStep] = useState(reschedule ? 2 : 0);
  const [spec, setSpec] = useState<string | null>(reschedule?.speciality ?? null);
  const [doctor, setDoctor] = useState<any>(reschedule ? { id: reschedule.doctorId } : null);
  const [day, setDay] = useState(nextDays(1)[0]);
  const [hold, setHold] = useState<any>(null);
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<any>(null);
  const [now, setNow] = useState(Date.now());
  const qc = useQueryClient();
  const toast = useToast();

  useEffect(() => { if (!open) { setStep(reschedule ? 2 : 0); setHold(null); setDone(null); } }, [open, reschedule]);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);

  const specs = useQuery({ queryKey: ["specialities"], queryFn: () => api.get<string[]>("/api/specialities"), enabled: open });
  const docs = useQuery({ queryKey: ["doctors", spec], queryFn: () => api.get(`/api/doctors?speciality=${encodeURIComponent(spec ?? "")}`), enabled: open && !!spec });
  const slots = useQuery({ queryKey: ["slots", doctor?.id, day], queryFn: () => api.get(`/api/doctors/${doctor.id}/slots?day=${day}`), enabled: open && !!doctor && step === 2 });

  const holdM = useMutation({
    mutationFn: (slot_id: string) => api.post("/api/appointments/hold", { patient_id: patientId, slot_id }),
    onSuccess: (h) => { setHold(h); setStep(3); },
    onError: (e) => { toast("danger", errorMessage(e)); slots.refetch(); },
  });
  const confirmM = useMutation({
    mutationFn: () => api.post("/api/appointments/confirm", { patient_id: patientId, hold_id: hold.hold_id, reason: reason || null,
      follow_up_id: followUpId ?? null, reschedule_appointment_id: reschedule?.id ?? null }),
    onSuccess: (a) => { setDone(a); setStep(4); qc.invalidateQueries({ queryKey: ["appointments"] }); qc.invalidateQueries({ queryKey: ["overview"] }); qc.invalidateQueries({ queryKey: ["instructions"] }); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  const release = () => { if (hold) api.del(`/api/appointments/hold/${hold.hold_id}`).catch(() => {}); setHold(null); };
  const remaining = hold ? Math.max(0, Math.floor((new Date(hold.expires_at).getTime() - now) / 1000)) : 0;
  const days = useMemo(() => nextDays(14), []);

  return (
    <Modal open={open} onClose={() => { if (step === 3) release(); onClose(); }} title={reschedule ? "Reschedule appointment" : "Book an appointment"} size="lg">
      <ol className="mb-5 flex items-center gap-1.5" aria-label="Booking progress">
        {STEPS.map((s, i) => (
          <li key={s} className="flex flex-1 flex-col gap-1">
            <span className={clsx("h-1.5 rounded-full transition-colors", i <= step ? "bg-primary" : "bg-line")} />
            <span className={clsx("hidden text-[11px] font-semibold sm:block", i === step ? "text-ink" : "text-ink-3")} aria-current={i === step ? "step" : undefined}>{s}</span>
          </li>
        ))}
      </ol>
      <AnimatePresence mode="wait">
        <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.18 }}>
          {step === 0 && (
            <div className="grid gap-2 sm:grid-cols-2">
              {specs.isLoading && <Skeleton className="h-14" />}
              {specs.data?.map((s) => (
                <button key={s} onClick={() => { setSpec(s); setStep(1); }} className="flex items-center gap-3 rounded-xl border border-line p-4 text-left font-semibold hover:border-primary/50 hover:bg-primary-soft/40">
                  <Stethoscope className="h-5 w-5 text-primary" />{s}
                </button>
              ))}
            </div>
          )}
          {step === 1 && (
            <div className="space-y-2">
              <BackBtn onClick={() => setStep(0)} />
              {docs.isLoading ? <Skeleton className="h-20" /> : docs.data?.map((d: any) => (
                <button key={d.id} onClick={() => { setDoctor(d); setStep(2); }} className="flex w-full items-center gap-3 rounded-xl border border-line p-4 text-left hover:border-primary/50 hover:bg-primary-soft/40">
                  <Avatar name={d.name} color={d.avatar_color} />
                  <div className="flex-1">
                    <p className="font-semibold">{d.name}</p>
                    <p className="text-sm text-ink-3">{d.speciality} · {d.languages?.join(", ")}</p>
                    {d.organization && <p className="mt-0.5 flex items-center gap-1 text-xs text-ink-3"><MapPin className="h-3 w-3" />{d.organization.name}, {d.organization.address} {d.organization.is_demo && <DemoTag />}</p>}
                  </div>
                </button>
              ))}
            </div>
          )}
          {step === 2 && (
            <div className="space-y-4">
              {!reschedule && <BackBtn onClick={() => setStep(1)} />}
              <div className="flex gap-2 overflow-x-auto pb-1" role="listbox" aria-label="Choose a date">
                {days.map((d) => (
                  <button key={d} role="option" aria-selected={d === day} onClick={() => setDay(d)}
                    className={clsx("flex min-w-[64px] flex-col items-center rounded-xl border px-3 py-2 text-sm transition",
                      d === day ? "border-primary bg-primary text-primary-ink" : "border-line hover:bg-surface-2")}>
                    <span className="text-[11px] uppercase opacity-80">{new Date(d + "T12:00:00").toLocaleDateString("en-IN", { weekday: "short" })}</span>
                    <span className="font-display text-lg font-bold">{d.slice(8)}</span>
                  </button>
                ))}
              </div>
              {slots.isLoading ? <Skeleton className="h-24" /> : !slots.data?.length ? (
                <EmptyState icon={<Clock className="h-6 w-6" />} title="No open slots this day" body="Try another date." />
              ) : (
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                  {slots.data.map((s: any) => (
                    <button key={s.id} disabled={!s.available || holdM.isPending} onClick={() => holdM.mutate(s.id)}
                      className="rounded-xl border border-line px-2 py-2.5 text-sm font-semibold transition hover:border-primary hover:bg-primary-soft disabled:cursor-not-allowed disabled:opacity-40 disabled:line-through">
                      {fmtTime(s.starts_at)}
                    </button>
                  ))}
                </div>
              )}
              <p className="text-xs text-ink-3">Selecting a time holds it for you for 5 minutes while you review.</p>
            </div>
          )}
          {step === 3 && hold && (
            <div className="space-y-4">
              <div className={clsx("flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold", remaining < 60 ? "bg-warn-soft text-warn" : "bg-info-soft text-info")} role="timer" aria-live="off">
                <Timer className="h-4 w-4" /> Held for {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}
              </div>
              <dl className="grid gap-3 rounded-2xl bg-surface-2 p-4 text-sm sm:grid-cols-2">
                <div><dt className="text-ink-3">Doctor</dt><dd className="font-semibold">{hold.slot.doctor.name}</dd></div>
                <div><dt className="text-ink-3">Speciality</dt><dd className="font-semibold">{hold.slot.doctor.speciality}</dd></div>
                <div><dt className="text-ink-3">Date & time</dt><dd className="font-semibold">{fmtDateTime(hold.slot.starts_at)}</dd></div>
                <div><dt className="text-ink-3">Type</dt><dd className="font-semibold">{titleCase(hold.slot.consultation_type)}</dd></div>
                <div className="sm:col-span-2"><dt className="text-ink-3">Location</dt><dd className="font-semibold">{hold.slot.location ? `${hold.slot.location.name}, ${hold.slot.location.address}` : "—"}</dd></div>
              </dl>
              <Field label="Reason for visit (optional)" hint="Shared with your doctor to prepare the visit">{(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
              <Notice tone="info" title="Cancellation policy">{hold.cancellation_policy}</Notice>
              <div className="flex justify-between gap-2">
                <Button variant="outline" onClick={() => { release(); setStep(2); }}>Choose another time</Button>
                <Button onClick={() => confirmM.mutate()} loading={confirmM.isPending} disabled={remaining === 0} icon={<CalendarCheck2 className="h-4 w-4" />}>Confirm booking</Button>
              </div>
            </div>
          )}
          {step === 4 && done && (
            <div className="flex flex-col items-center py-4 text-center">
              <motion.span initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 260, damping: 18 }}
                className="grid h-16 w-16 place-items-center rounded-full bg-ok-soft text-ok"><CheckCircle2 className="h-9 w-9" /></motion.span>
              <h3 className="mt-4 text-xl font-bold">You're booked</h3>
              <p className="mt-1 text-ink-2">{done.doctor.name} · {fmtDate(done.starts_at, { weekday: "long" })} at {fmtTime(done.starts_at)}</p>
              <Badge tone="ok" className="mt-3">Confirmation sent to your notifications</Badge>
              <Button className="mt-6" onClick={onClose}>Done</Button>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </Modal>
  );
}

function BackBtn({ onClick }: { onClick: () => void }) {
  return <button onClick={onClick} className="mb-1 inline-flex items-center gap-1 text-sm font-semibold text-ink-3 hover:text-ink"><ArrowLeft className="h-4 w-4" />Back</button>;
}
