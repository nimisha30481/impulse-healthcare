import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldCheck, X } from "lucide-react";
import { Button, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { Modal, Notice, useToast } from "@/components/ui/feedback";
import { InteractionPanel } from "./InteractionPanel";
import { api, ApiError, errorMessage } from "@/lib/api";
import { medicationOrderSchema, zodErrors } from "@/lib/schemas";
import type { Assessment, MedItem, Version } from "@/lib/types";
import { DateInput, DateTimeInput } from "@/components/ui/DateInput";

const FORMS = ["tablet", "capsule", "syrup", "suspension", "injection", "inhaler", "drops", "cream", "ointment", "patch", "powder", "solution", "spray"];
// Units follow the Indian (metric) system; count units are for whole tablets/capsules/etc.
const COUNT_UNITS = ["tablet", "capsule", "drop", "puff", "sachet", "patch", "application", "unit"];
const UNIT_GROUPS: [string, string[]][] = [
  ["Count", COUNT_UNITS], ["Mass", ["mcg", "mg", "g", "kg"]], ["Volume", ["ml"]], ["Other", ["IU"]],
];
const ROUTES = ["oral", "sublingual", "topical", "inhaled", "nasal", "ophthalmic", "otic", "subcutaneous", "intramuscular", "intravenous", "rectal", "transdermal"];
const FREQUENCIES: { label: string; times: string[] | null; prn?: boolean; weekly?: boolean }[] = [
  { label: "Once daily", times: ["09:00"] },
  { label: "Twice daily", times: ["09:00", "21:00"] },
  { label: "Three times daily", times: ["08:00", "14:00", "20:00"] },
  { label: "Four times daily", times: ["08:00", "12:00", "16:00", "20:00"] },
  { label: "Every 8 hours", times: ["06:00", "14:00", "22:00"] },
  { label: "At bedtime", times: ["21:30"] },
  { label: "Once weekly", times: ["09:00"], weekly: true },
  { label: "As needed", times: [], prn: true },
  { label: "Custom", times: null },
];
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
const plusDays = (iso: string, n: number) => { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };

function presetOf(f: any): string {
  if (f.is_prn) return "As needed";
  const hit = FREQUENCIES.find((x) => x.times && !x.prn && x.label === f.frequency_label
    && JSON.stringify(x.times) === JSON.stringify(f.times_of_day));
  return hit ? hit.label : "Custom";
}

/** Supply needed from start date up to the follow-up date, e.g. "60 tablets" or "60 doses (30000 mg total)". */
export function calcQuantity(f: any): string {
  if (f.is_prn || !f.end_date || !f.start_date || !(Number(f.dose_amount) > 0)) return "";
  const days = Math.round((new Date(f.end_date).getTime() - new Date(f.start_date).getTime()) / 86400000) + 1;
  if (days <= 0) return "";
  const perDay = f.days_of_week?.length ? (f.times_of_day.length * f.days_of_week.length) / 7 : f.times_of_day.length / Number(f.interval_days || 1);
  const doses = Math.ceil(perDay * days);
  const total = +(Number(f.dose_amount) * doses).toFixed(2);
  if (COUNT_UNITS.includes(f.dose_unit)) return `${Math.ceil(total)} ${f.dose_unit}${Math.ceil(total) === 1 ? "" : "s"}`;
  return `${doses} doses (${total} ${f.dose_unit} total)`;
}

function fromVersion(v?: Version) {
  return {
    generic_name: v?.generic_name ?? "", brand_name: v?.brand_name ?? "", strength: v?.strength ?? "", dosage_form: v?.dosage_form ?? "tablet",
    dose_amount: v?.dose_amount ?? 1, dose_unit: v?.dose_unit ?? "tablet", route: v?.route ?? "oral", frequency_label: v?.frequency_label ?? "Once daily",
    times_of_day: v?.schedule?.times_of_day ?? ["09:00"], days_of_week: v?.schedule?.days_of_week ?? null, interval_days: v?.schedule?.interval_days ?? 1,
    is_prn: v?.is_prn ?? false, indication: v?.indication ?? "", duration_days: v?.duration_days ?? "", start_date: v?.start_date ?? today(),
    end_date: v ? v.end_date ?? "" : plusDays(today(), 30), quantity: v?.quantity ?? "", refills_allowed: v?.refills_allowed ?? 0, refill_instructions: v?.refill_instructions ?? "",
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
  const [f, setF] = useState<any>(() => { const v = fromVersion(item?.current); return { ...v, quantity: v.quantity || calcQuantity(v) }; });
  const [qtyTouched, setQtyTouched] = useState(!!item?.current.quantity);
  // Any change to dose, frequency or dates recalculates the quantity unless the doctor typed one.
  const update = (patch: any) => setF((prev: any) => {
    const next = { ...prev, ...patch };
    return qtyTouched ? next : { ...next, quantity: calcQuantity(next) };
  });
  const applyPreset = (label: string) => {
    const p = FREQUENCIES.find((x) => x.label === label)!;
    if (!p.times) return update({ frequency_label: f.frequency_label === "Custom" ? "As prescribed" : f.frequency_label, is_prn: false });
    update({ frequency_label: p.label, times_of_day: p.times, is_prn: !!p.prn, interval_days: 1,
      days_of_week: p.weekly ? [new Date(f.start_date + "T12:00:00").getDay() === 0 ? 6 : new Date(f.start_date + "T12:00:00").getDay() - 1] : null });
  };
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [effective, setEffective] = useState("");
  const [newTime, setNewTime] = useState("");
  const [preview, setPreview] = useState<Assessment | null>(null);
  const [step, setStep] = useState<"edit" | "review">("edit");
  const [result, setResult] = useState<any>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const set = (k: string) => (e: any) => update({ [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

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
        <div className="space-y-4">
          {item?.external && <Notice tone="warn">This medicine was prescribed by another provider. Edit only if you are now responsible for it.</Notice>}
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="sm:col-span-2"><Field label="Medicine (generic name)" error={errors.generic_name} required>{(p) => <Input {...p} value={f.generic_name} onChange={set("generic_name")} placeholder="e.g. Metformin" />}</Field></div>
            <Field label="Strength" error={errors.strength} required>{(p) => <Input {...p} placeholder="e.g. 500 mg" value={f.strength} onChange={set("strength")} />}</Field>
            <Field label="Form" required>{(p) => <Select {...p} value={f.dosage_form} onChange={set("dosage_form")}>{FORMS.map((x) => <option key={x}>{x}</option>)}</Select>}</Field>
            <Field label="Dose" error={errors.dose_amount} required>{(p) => <Input {...p} type="number" min={0} step="any" value={f.dose_amount} onChange={set("dose_amount")} />}</Field>
            <Field label="Unit" required>{(p) => <Select {...p} value={f.dose_unit} onChange={set("dose_unit")}>
              {UNIT_GROUPS.map(([g, us]) => <optgroup key={g} label={g}>{us.map((u) => <option key={u} value={u}>{u}</option>)}</optgroup>)}</Select>}</Field>
            <div className="sm:col-span-2"><Field label="Frequency" error={errors.frequency_label || errors.times_of_day} required>
              {(p) => <Select {...p} value={presetOf(f)} onChange={(e) => applyPreset(e.target.value)}>
                {FREQUENCIES.map((x) => <option key={x.label} value={x.label}>{x.label}{x.times?.length ? ` (${x.times.join(", ")})` : ""}</option>)}</Select>}
            </Field></div>
            <Field label="Start date" error={errors.start_date} required>{(p) => <DateInput {...p} value={f.start_date} onChange={(v) => update({ start_date: v })} />}</Field>
            <Field label="Next follow-up date" error={errors.end_date} hint="Medicine is supplied until this visit">{(p) => <DateInput {...p} min={f.start_date} value={f.end_date} onChange={(v) => update({ end_date: v })} />}</Field>
            <div className="sm:col-span-2"><Field label="Quantity" hint={qtyTouched ? "Edited manually" : "Calculated from dose × frequency × days until follow-up"}>
              {(p) => <Input {...p} value={f.quantity} onChange={(e) => { setQtyTouched(true); setF({ ...f, quantity: e.target.value }); }} placeholder="Set a follow-up date to calculate" />}
            </Field></div>
          </div>
          {presetOf(f) === "Custom" && !f.is_prn && (
            <div className="rounded-2xl bg-surface-2 p-3">
              <Input aria-label="Frequency as shown to the patient" className="mb-2" placeholder="Frequency as shown to the patient, e.g. Every other day"
                value={f.frequency_label} onChange={(e) => update({ frequency_label: e.target.value })} />
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold">Dose times:</span>
                {f.times_of_day.map((t: string) => (
                  <span key={t} className="inline-flex items-center gap-1 rounded-full bg-surface px-3 py-1 text-sm font-semibold shadow-card">{t}
                    <button aria-label={`Remove ${t}`} onClick={() => update({ times_of_day: f.times_of_day.filter((x: string) => x !== t) })}><X className="h-3.5 w-3.5" /></button></span>
                ))}
                <Input type="time" aria-label="Add dose time" className="w-32" value={newTime} onChange={(e) => setNewTime(e.target.value)} />
                <Button size="sm" variant="outline" icon={<Plus className="h-4 w-4" />} disabled={!newTime}
                  onClick={() => { if (!f.times_of_day.includes(newTime)) update({ times_of_day: [...f.times_of_day, newTime].sort() }); setNewTime(""); }}>Add time</Button>
              </div>
            </div>
          )}
          <details className="rounded-2xl border border-line p-3">
            <summary className="cursor-pointer text-sm font-semibold">More options (brand, route, instructions, refills)</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <Field label="Brand (if applicable)">{(p) => <Input {...p} value={f.brand_name} onChange={set("brand_name")} />}</Field>
              <Field label="Route">{(p) => <Select {...p} value={f.route} onChange={set("route")}>{ROUTES.map((x) => <option key={x}>{x}</option>)}</Select>}</Field>
              <Field label="Documented indication" hint="Shown to the patient as 'why am I taking it'">{(p) => <Input {...p} value={f.indication} onChange={set("indication")} />}</Field>
              <Field label="Food instructions">{(p) => <Input {...p} placeholder="e.g. Take with meals" value={f.food_instructions} onChange={set("food_instructions")} />}</Field>
              <Field label="Refills allowed">{(p) => <Input {...p} type="number" min={0} max={12} value={f.refills_allowed} onChange={set("refills_allowed")} />}</Field>
              <Field label="Refill instructions">{(p) => <Input {...p} value={f.refill_instructions} onChange={set("refill_instructions")} />}</Field>
              <div className="sm:col-span-3 grid gap-3 sm:grid-cols-2">
                <Field label="Special instructions">{(p) => <Textarea {...p} className="min-h-[64px]" value={f.special_instructions} onChange={set("special_instructions")} />}</Field>
                <Field label="Missed-dose guidance" hint="Shown to the patient. Leave empty if not applicable.">{(p) => <Textarea {...p} className="min-h-[64px]" value={f.missed_dose_guidance} onChange={set("missed_dose_guidance")} />}</Field>
              </div>
            </div>
          </details>
          {item && (
            <div className="grid gap-3 rounded-2xl border border-warn/30 bg-warn-soft/40 p-3 sm:grid-cols-2">
              <Field label="Reason for change" error={errors.reason} required>{(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
              <Field label="Effective from" hint="Leave empty for immediately">{(p) => <DateTimeInput {...p} value={effective} onChange={setEffective} />}</Field>
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
        <Field label="Effective" hint="Leave empty for now. Future dates keep reminders until then.">{(p) => <DateTimeInput {...p} value={f.effective_at} onChange={(v) => setF({ ...f, effective_at: v })} />}</Field>
        <Field label="Reason" required>{(p) => <Input {...p} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} />}</Field>
        <Field label="Special instructions for the patient">{(p) => <Textarea {...p} value={f.special_instructions} onChange={(e) => setF({ ...f, special_instructions: e.target.value })} />}</Field>
        <Field label="Follow-up requirements">{(p) => <Input {...p} value={f.follow_up} onChange={(e) => setF({ ...f, follow_up: e.target.value })} />}</Field>
        <Notice tone="info">The patient and authorised caregivers are notified. The prescription and its versions remain in the history.</Notice>
      </div>
    </Modal>
  );
}
