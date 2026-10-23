import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldCheck, X } from "lucide-react";
import clsx from "clsx";
import { Button, Checkbox, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { Modal, Notice, useToast } from "@/components/ui/feedback";
import { InteractionPanel } from "./InteractionPanel";
import { api, ApiError, errorMessage } from "@/lib/api";
import { medicationOrderSchema, zodErrors } from "@/lib/schemas";
import { WEEKDAYS } from "@/lib/format";
import type { Assessment, MedItem, Version } from "@/lib/types";

const FORMS = ["tablet", "capsule", "syrup", "suspension", "injection", "inhaler", "drops", "cream", "ointment", "patch", "powder", "solution", "spray"];
const UNITS = ["tablet", "capsule", "mg", "mcg", "g", "ml", "drop", "puff", "unit", "patch", "sachet", "application"];
const ROUTES = ["oral", "sublingual", "topical", "inhaled", "nasal", "ophthalmic", "otic", "subcutaneous", "intramuscular", "intravenous", "rectal", "transdermal"];
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

function fromVersion(v?: Version) {
  return {
    generic_name: v?.generic_name ?? "", brand_name: v?.brand_name ?? "", strength: v?.strength ?? "", dosage_form: v?.dosage_form ?? "tablet",
    dose_amount: v?.dose_amount ?? 1, dose_unit: v?.dose_unit ?? "tablet", route: v?.route ?? "oral", frequency_label: v?.frequency_label ?? "Once daily",
    times_of_day: v?.schedule?.times_of_day ?? ["09:00"], days_of_week: v?.schedule?.days_of_week ?? null, interval_days: v?.schedule?.interval_days ?? 1,
    is_prn: v?.is_prn ?? false, indication: v?.indication ?? "", duration_days: v?.duration_days ?? "", start_date: v?.start_date ?? today(),
    end_date: v?.end_date ?? "", quantity: v?.quantity ?? "", refills_allowed: v?.refills_allowed ?? 0, refill_instructions: v?.refill_instructions ?? "",
    food_instructions: v?.food_instructions ?? "", special_instructions: v?.special_instructions ?? "", missed_dose_guidance: v?.missed_dose_guidance ?? "",
    timezone: v?.schedule?.timezone ?? "Asia/Kolkata",
  };
}

function clean(f: any) {
  const out: any = { ...f, dose_amount: Number(f.dose_amount), refills_allowed: Number(f.refills_allowed || 0), interval_days: Number(f.interval_days || 1) };
  for (const k of ["brand_name", "indication", "end_date", "quantity", "refill_instructions", "food_instructions", "special_instructions", "missed_dose_guidance"]) if (!out[k]) out[k] = null;
  out.duration_days = f.duration_days ? Number(f.duration_days) : null;
  if (out.is_prn) out.times_of_day = [];
  return out;
}

/** Create (patientId) or edit (item) a prescription. Edits publish a new immutable version. */
export function PrescriptionForm({ patientId, item, open, onClose }: { patientId: string; item?: MedItem | null; open: boolean; onClose: () => void }) {
  const [f, setF] = useState<any>(() => fromVersion(item?.current));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [effective, setEffective] = useState("");
  const [newTime, setNewTime] = useState("");
  const [preview, setPreview] = useState<Assessment | null>(null);
  const [step, setStep] = useState<"edit" | "review">("edit");
  const [result, setResult] = useState<any>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const validate = () => {
    const r = medicationOrderSchema.safeParse({ ...f, end_date: f.end_date || undefined });
    if (!r.success) { setErrors(zodErrors(r.error)); return false; }
    if (item && reason.trim().length < 3) { setErrors({ reason: "Record why this prescription is changing" }); return false; }
    setErrors({});
    return true;
  };
  const previewM = useMutation({
    mutationFn: () => api.post<Assessment>("/api/doctor/interaction-preview", { patient_id: patientId, order: clean(f) }),
    onSuccess: setPreview, onError: (e) => toast("danger", errorMessage(e)),
  });
  const save = useMutation({
    mutationFn: () => item
      ? api.put(`/api/doctor/prescription-items/${item.id}`, { order: clean(f), change_reason: reason, expected_lock_version: item.lock_version,
          effective_from: effective ? new Date(effective).toISOString() : null })
      : api.post("/api/doctor/prescriptions", { patient_id: patientId, items: [clean(f)], publish: true }),
    onSuccess: (r) => {
      setResult(r);
      qc.invalidateQueries({ queryKey: ["doctor-patient"] });
      qc.invalidateQueries({ queryKey: ["medication"] });
      toast("ok", item ? "New version published. The patient has been notified." : "Prescription published. The patient has been notified.");
    },
    onError: (e) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) { setErrors(Object.fromEntries(Object.entries(e.fields).map(([k, v]) => [k.replace(/^(items\.0\.|order\.)/, ""), v]))); setStep("edit"); }
      toast("danger", errorMessage(e));
    },
  });
  const close = () => { setResult(null); setStep("edit"); setPreview(null); onClose(); };
  const changed = item ? Object.entries(clean(f)).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify((clean(fromVersion(item.current)) as any)[k])) : [];

  return (
    <Modal open={open} onClose={close} size="xl" title={item ? `Edit ${item.current.generic_name}` : "New prescription"}
      footer={result ? <Button onClick={close}>Done</Button> : step === "edit" ? <>
        <Button variant="outline" onClick={() => validate() && previewM.mutate()} loading={previewM.isPending} icon={<ShieldCheck className="h-4 w-4" />}>Check safety</Button>
        <Button onClick={() => validate() && setStep("review")}>Review</Button>
      </> : <>
        <Button variant="outline" onClick={() => setStep("edit")}>Back to edit</Button>
        <Button onClick={() => save.mutate()} loading={save.isPending}>{item ? "Publish new version" : "Publish prescription"}</Button>
      </>}>
      {result ? (
        <div className="space-y-4">
          <Notice tone="ok" title="Published">Reminders follow the new effective schedule. Version history is preserved.</Notice>
          {(result.assessments ?? [result.assessment]).filter(Boolean).map((a: Assessment) => <InteractionPanel key={a.id} a={a} />)}
        </div>
      ) : step === "review" ? (
        <div className="space-y-4">
          <h3 className="font-bold">Review {item ? "changes" : "prescription"}</h3>
          {item ? (
            changed.length === 0 ? <Notice tone="warn">No fields changed.</Notice> : (
              <table className="w-full text-sm"><thead className="text-left text-ink-3"><tr><th className="py-1">Field</th><th>Current</th><th>New</th></tr></thead>
                <tbody>{changed.map(([k, v]) => <tr key={k} className="border-t border-line"><td className="py-1.5 font-medium">{k.replace(/_/g, " ")}</td>
                  <td className="text-ink-3 line-through">{JSON.stringify((clean(fromVersion(item.current)) as any)[k])}</td><td className="font-semibold">{JSON.stringify(v)}</td></tr>)}</tbody></table>
            )
          ) : (
            <p className="rounded-xl bg-surface-2 p-3 text-sm">{f.generic_name} {f.strength} — {f.dose_amount} {f.dose_unit} {f.route}, {f.frequency_label}{!f.is_prn && ` at ${f.times_of_day.join(", ")}`}, from {f.start_date}{f.end_date && ` to ${f.end_date}`}.</p>
          )}
          {item && <p className="text-sm"><b>Reason:</b> {reason} · <b>Effective:</b> {effective ? new Date(effective).toLocaleString() : "immediately"}</p>}
          {preview ? <InteractionPanel a={preview} reviewable={false} /> : <Notice tone="info">Safety checks run automatically when you publish.</Notice>}
        </div>
      ) : (
        <div className="space-y-5">
          {item?.external && <Notice tone="warn">This medicine was prescribed by another provider. Edit only if you are now responsible for it.</Notice>}
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Generic name" error={errors.generic_name} required>{(p) => <Input {...p} value={f.generic_name} onChange={set("generic_name")} />}</Field>
            <Field label="Brand (if applicable)">{(p) => <Input {...p} value={f.brand_name} onChange={set("brand_name")} />}</Field>
            <Field label="Strength" error={errors.strength} required>{(p) => <Input {...p} placeholder="e.g. 500 mg" value={f.strength} onChange={set("strength")} />}</Field>
            <Field label="Dosage form" required>{(p) => <Select {...p} value={f.dosage_form} onChange={set("dosage_form")}>{FORMS.map((x) => <option key={x}>{x}</option>)}</Select>}</Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Dose" error={errors.dose_amount} required>{(p) => <Input {...p} type="number" min={0} step="any" value={f.dose_amount} onChange={set("dose_amount")} />}</Field>
              <Field label="Unit" required>{(p) => <Select {...p} value={f.dose_unit} onChange={set("dose_unit")}>{UNITS.map((x) => <option key={x}>{x}</option>)}</Select>}</Field>
            </div>
            <Field label="Route" required>{(p) => <Select {...p} value={f.route} onChange={set("route")}>{ROUTES.map((x) => <option key={x}>{x}</option>)}</Select>}</Field>
            <Field label="Frequency (as shown to patient)" error={errors.frequency_label} required>{(p) => <Input {...p} value={f.frequency_label} onChange={set("frequency_label")} />}</Field>
            <Field label="Documented indication" hint="Shown to the patient as 'why am I taking it'">{(p) => <Input {...p} value={f.indication} onChange={set("indication")} />}</Field>
            <Field label="Duration (days)">{(p) => <Input {...p} type="number" min={1} value={f.duration_days} onChange={set("duration_days")} />}</Field>
          </div>
          <div className="rounded-2xl bg-surface-2 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold">Schedule</p>
              <Checkbox checked={f.is_prn} onChange={(v) => setF({ ...f, is_prn: v })} label="As needed (no reminders)" />
            </div>
            {!f.is_prn && (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {f.times_of_day.map((t: string) => (
                    <span key={t} className="inline-flex items-center gap-1 rounded-full bg-surface px-3 py-1 text-sm font-semibold shadow-card">{t}
                      <button aria-label={`Remove ${t}`} onClick={() => setF({ ...f, times_of_day: f.times_of_day.filter((x: string) => x !== t) })}><X className="h-3.5 w-3.5" /></button></span>
                  ))}
                  <Input type="time" aria-label="Add dose time" className="w-32" value={newTime} onChange={(e) => setNewTime(e.target.value)} />
                  <Button size="sm" variant="outline" icon={<Plus className="h-4 w-4" />} disabled={!newTime}
                    onClick={() => { if (!f.times_of_day.includes(newTime)) setF({ ...f, times_of_day: [...f.times_of_day, newTime].sort() }); setNewTime(""); }}>Add time</Button>
                </div>
                {errors.times_of_day && <p role="alert" className="mt-1 text-sm text-danger">{errors.times_of_day}</p>}
                <div className="mt-3 flex flex-wrap items-center gap-1.5" role="group" aria-label="Days of week">
                  <span className="mr-1 text-sm text-ink-3">Days:</span>
                  {WEEKDAYS.map((d, i) => {
                    const on = !f.days_of_week || f.days_of_week.includes(i);
                    return <button key={d} aria-pressed={on} onClick={() => {
                      const cur: number[] = f.days_of_week ?? [0, 1, 2, 3, 4, 5, 6];
                      const next = on ? cur.filter((x) => x !== i) : [...cur, i].sort();
                      setF({ ...f, days_of_week: next.length === 7 ? null : next.length ? next : cur });
                    }} className={clsx("h-8 w-11 rounded-lg text-xs font-semibold", on ? "bg-primary text-primary-ink" : "bg-surface text-ink-3")}>{d}</button>;
                  })}
                  <span className="ml-3 text-sm text-ink-3">Every</span>
                  <Input aria-label="Interval in days" type="number" min={1} max={30} className="w-20" value={f.interval_days} onChange={set("interval_days")} />
                  <span className="text-sm text-ink-3">day(s)</span>
                </div>
              </>
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Start date" error={errors.start_date} required>{(p) => <Input {...p} type="date" value={f.start_date} onChange={set("start_date")} />}</Field>
            <Field label="End date" error={errors.end_date}>{(p) => <Input {...p} type="date" value={f.end_date} onChange={set("end_date")} />}</Field>
            <Field label="Quantity">{(p) => <Input {...p} value={f.quantity} onChange={set("quantity")} />}</Field>
            <Field label="Refills allowed">{(p) => <Input {...p} type="number" min={0} max={12} value={f.refills_allowed} onChange={set("refills_allowed")} />}</Field>
            <Field label="Refill instructions">{(p) => <Input {...p} value={f.refill_instructions} onChange={set("refill_instructions")} />}</Field>
            <Field label="Food instructions">{(p) => <Input {...p} placeholder="e.g. Take with meals" value={f.food_instructions} onChange={set("food_instructions")} />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Special instructions">{(p) => <Textarea {...p} value={f.special_instructions} onChange={set("special_instructions")} />}</Field>
            <Field label="Missed-dose guidance (medication-specific)" hint="Shown to the patient. Leave empty if not applicable.">{(p) => <Textarea {...p} value={f.missed_dose_guidance} onChange={set("missed_dose_guidance")} />}</Field>
          </div>
          {item && (
            <div className="grid gap-4 rounded-2xl border border-warn/30 bg-warn-soft/40 p-4 sm:grid-cols-2">
              <Field label="Reason for change" error={errors.reason} required>{(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
              <Field label="Effective from" hint="Leave empty for immediately. Future dates keep the current version until then.">{(p) => <Input {...p} type="datetime-local" value={effective} onChange={(e) => setEffective(e.target.value)} />}</Field>
            </div>
          )}
          {preview && <InteractionPanel a={preview} reviewable={false} />}
        </div>
      )}
    </Modal>
  );
}

export function DiscontinueForm({ item, open, onClose }: { item: MedItem; open: boolean; onClose: () => void }) {
  const [f, setF] = useState({ effective_at: "", reason: "", special_instructions: "", follow_up: "" });
  const qc = useQueryClient();
  const toast = useToast();
  const m = useMutation({
    mutationFn: () => api.post(`/api/doctor/prescription-items/${item.id}/discontinue`, {
      ...f, effective_at: f.effective_at ? new Date(f.effective_at).toISOString() : null, expected_lock_version: item.lock_version,
      special_instructions: f.special_instructions || null, follow_up: f.follow_up || null }),
    onSuccess: () => { toast("ok", "Discontinued. Future reminders were cancelled and history kept."); qc.invalidateQueries({ queryKey: ["doctor-patient"] }); onClose(); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  return (
    <Modal open={open} onClose={onClose} title={`Discontinue ${item.current.generic_name}`}
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button variant="danger" onClick={() => m.mutate()} disabled={f.reason.length < 3} loading={m.isPending}>Confirm discontinuation</Button></>}>
      <div className="space-y-4">
        <Field label="Effective" hint="Leave empty for now. Future dates keep reminders until then.">{(p) => <Input {...p} type="datetime-local" value={f.effective_at} onChange={(e) => setF({ ...f, effective_at: e.target.value })} />}</Field>
        <Field label="Reason" required>{(p) => <Input {...p} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} />}</Field>
        <Field label="Special instructions for the patient">{(p) => <Textarea {...p} value={f.special_instructions} onChange={(e) => setF({ ...f, special_instructions: e.target.value })} />}</Field>
        <Field label="Follow-up requirements">{(p) => <Input {...p} value={f.follow_up} onChange={(e) => setF({ ...f, follow_up: e.target.value })} />}</Field>
        <Notice tone="info">The patient and authorised caregivers are notified. The prescription and its versions remain in the history.</Notice>
      </div>
    </Modal>
  );
}
