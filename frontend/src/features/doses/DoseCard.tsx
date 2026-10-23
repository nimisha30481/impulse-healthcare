import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlarmClock, Check, Flag, Info, Pill, XCircle } from "lucide-react";
import clsx from "clsx";
import { Button, Select, Textarea } from "@/components/ui/primitives";
import { Modal, Notice, useToast } from "@/components/ui/feedback";
import { DoseStatusPill } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { Dose } from "@/lib/types";

const REASONS = [
  ["unwell", "Feeling unwell"], ["unavailable", "Medicine unavailable"], ["forgot", "Forgot"],
  ["side_effects", "Side effects"], ["cost", "Cost concerns"], ["other", "Other"],
] as const;

const ACTIONABLE = new Set(["upcoming", "due", "snoozed", "awaiting_confirmation", "unconfirmed"]);

export function DoseCard({ dose, patientId, detailHref, actor = "patient", index = 0, readOnly }: {
  dose: Dose; patientId: string; detailHref?: string; actor?: "patient" | "caregiver"; index?: number; readOnly?: boolean;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const t = useT();
  const [cantOpen, setCantOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [reason, setReason] = useState("forgot");
  const [note, setNote] = useState("");
  const respond = useMutation({
    mutationFn: (body: any) => api.post(`/api/patients/${patientId}/doses/${dose.id}/respond`, {
      ...body, idempotency_key: `${dose.id}:${body.kind}:${Date.now()}`,
    }),
    onSuccess: (_d, body) => {
      qc.invalidateQueries({ queryKey: ["overview"] });
      qc.invalidateQueries({ queryKey: ["adherence"] });
      qc.invalidateQueries({ queryKey: ["doses"] });
      toast("ok", body.kind === "taken_reported" ? "Recorded as taken." : body.kind === "snoozed" ? "Snoozed for 15 minutes." : "Thanks — we've let your care team know if needed.");
      setCantOpen(false);
    },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  const report = useMutation({
    mutationFn: () => api.post(`/api/patients/${patientId}/concerns`, { kind: "general", description: `${dose.medicine}: ${note}` }),
    onSuccess: (r) => { toast("ok", r.message); setReportOpen(false); setNote(""); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  const opensAt = new Date(dose.scheduled_at).getTime() - 2 * 3600_000; // server accepts responses from 2h before
  const tooEarly = Date.now() < opensAt;
  const actionable = !readOnly && !tooEarly && ACTIONABLE.has(dose.status);
  const due = dose.status === "due" || dose.status === "awaiting_confirmation";

  return (
    <motion.article layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}
      className={clsx("card p-4 transition-shadow", due && "ring-2 ring-primary/30")} aria-label={`${dose.medicine} at ${fmtTime(dose.scheduled_at)}`}>
      <div className="flex items-start gap-3">
        <span className={clsx("grid h-11 w-11 shrink-0 place-items-center rounded-xl", due ? "bg-primary text-primary-ink" : "bg-primary-soft text-primary")}>
          <Pill className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-base font-bold">{dose.medicine} <span className="font-medium text-ink-3">{dose.strength}</span></h3>
            <DoseStatusPill status={dose.status} />
          </div>
          {/* Clinical values are shown plainly - no animation on the numbers themselves */}
          <p className="mt-0.5 text-sm text-ink-2">
            <time dateTime={dose.scheduled_at} className="font-semibold text-ink">{fmtTime(dose.scheduled_at)}</time> · {dose.dose} · {dose.route}
          </p>
          {dose.instructions && <p className="mt-1 text-sm text-ink-3">{dose.instructions}</p>}
          {dose.status === "snoozed" && dose.snoozed_until && <p className="mt-1 text-xs text-info">Reminder again at {fmtTime(dose.snoozed_until)}</p>}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {!readOnly && tooEarly && ACTIONABLE.has(dose.status) && (
          <span className="text-xs text-ink-3">You can respond from {fmtTime(new Date(opensAt).toISOString())}</span>
        )}
        {actionable && (
          <>
            <Button size="sm" onClick={() => respond.mutate({ kind: "taken_reported" })} loading={respond.isPending && respond.variables?.kind === "taken_reported"}
              icon={<Check className="h-4 w-4" />}>{actor === "caregiver" ? "Confirm taken" : t("dose.markTaken")}</Button>
            {actor === "patient" && (
              <Button size="sm" variant="outline" onClick={() => respond.mutate({ kind: "snoozed", snooze_minutes: 15 })}
                loading={respond.isPending && respond.variables?.kind === "snoozed"} icon={<AlarmClock className="h-4 w-4" />}>{t("dose.snooze")}</Button>
            )}
            <Button size="sm" variant="outline" onClick={() => setCantOpen(true)} icon={<XCircle className="h-4 w-4" />}>
              {actor === "caregiver" ? "Couldn't take" : t("dose.cantTake")}
            </Button>
          </>
        )}
        {detailHref && <Link to={detailHref}><Button size="sm" variant="ghost" icon={<Info className="h-4 w-4" />}>{t("dose.details")}</Button></Link>}
        {actor === "patient" && <Button size="sm" variant="ghost" onClick={() => setReportOpen(true)} icon={<Flag className="h-4 w-4" />}>Report a problem</Button>}
      </div>

      <Modal open={cantOpen} onClose={() => setCantOpen(false)} title={`Can't take ${dose.medicine}?`} size="sm"
        footer={<>
          <Button variant="outline" onClick={() => setCantOpen(false)}>Cancel</Button>
          <Button onClick={() => respond.mutate({ kind: "cant_take", reason, note: note || undefined })} loading={respond.isPending}>Save</Button>
        </>}>
        <div className="space-y-3">
          <label className="label" htmlFor="reason">What's the reason? (optional detail helps your care team)</label>
          <Select id="reason" value={reason} onChange={(e) => setReason(e.target.value)}>
            {REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
          <Textarea placeholder="Anything else to add?" value={note} onChange={(e) => setNote(e.target.value)} />
          <Notice tone="info">
            Don't double up on the next dose unless your doctor told you to. {(reason === "cost" || reason === "unavailable") && "A care coordinator will follow up about access to this medicine."}
            {" "}You can message your care team from <Link to="/messages" className="link">Messages</Link>.
          </Notice>
        </div>
      </Modal>
      <Modal open={reportOpen} onClose={() => setReportOpen(false)} title="Report a problem" size="sm"
        footer={<><Button variant="outline" onClick={() => setReportOpen(false)}>Cancel</Button>
          <Button onClick={() => report.mutate()} disabled={note.trim().length < 5} loading={report.isPending}>Send to care team</Button></>}>
        <div className="space-y-3">
          <Textarea aria-label="Describe the problem" placeholder="e.g. The tablets look different from last time" value={note} onChange={(e) => setNote(e.target.value)} />
          <Notice tone="warn">For severe symptoms or an emergency, call 112 now.</Notice>
        </div>
      </Modal>
    </motion.article>
  );
}
