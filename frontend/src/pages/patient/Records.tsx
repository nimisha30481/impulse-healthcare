import { useEffect, useState } from "react";
import { DateInput } from "@/components/ui/DateInput";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AlertTriangle, Building2, CircleHelp, CircleSlash, ClipboardList, Download, FileText, FlaskConical, HeartPulse,
  Hospital, Pencil, Pill, Search, Stethoscope, Syringe, Upload,
} from "lucide-react";
import type { ReactNode } from "react";
import { Badge, Button, Checkbox, Field, Input, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Modal, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader, Provenance, Tabs } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, titleCase } from "@/lib/format";
import type { RecordItem } from "@/lib/types";
import { OcrReview } from "@/features/ocr/OcrReview";

const TYPE_ICON: Record<string, ReactNode> = {
  consultation: <Stethoscope className="h-4 w-4" />, hospital_visit: <Hospital className="h-4 w-4" />,
  diagnosis: <HeartPulse className="h-4 w-4" />, prescription: <Pill className="h-4 w-4" />, lab_report: <FlaskConical className="h-4 w-4" />,
  procedure: <Syringe className="h-4 w-4" />, discharge_summary: <FileText className="h-4 w-4" />, follow_up: <ClipboardList className="h-4 w-4" />,
};

export function Timeline({ patientId, canRequestCorrection }: { patientId: string; canRequestCorrection?: boolean }) {
  const [f, setF] = useState({ record_type: "", doctor: "", organization: "", medication: "" });
  // Only the type goes to the server, so every record of that type in the whole history comes back;
  // the doctor / hospital / medication dropdowns are filled from those records.
  const q = useQuery({ queryKey: ["records", patientId, f.record_type],
    queryFn: () => api.get(`/api/patients/${patientId}/records${f.record_type ? `?record_type=${f.record_type}` : ""}`) });
  const [correct, setCorrect] = useState<RecordItem | null>(null);
  const [text, setText] = useState("");
  const toast = useToast();
  const qc = useQueryClient();
  const corr = useMutation({
    mutationFn: () => api.post(`/api/patients/${patientId}/records/${correct!.id}/correction`, { description: text }),
    onSuccess: () => { toast("ok", "Correction requested. The original record stays unchanged until reviewed."); setCorrect(null); setText(""); qc.invalidateQueries({ queryKey: ["records"] }); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  const all: RecordItem[] = q.data?.records ?? [];
  const uniq = (xs: (string | null | undefined)[]) => [...new Set(xs.filter(Boolean) as string[])].sort();
  const doctors = uniq(all.map((r) => r.doctor?.name));
  const hospitals = uniq(all.map((r) => r.organization));
  const meds = uniq(all.flatMap((r) => r.medication_names));
  const records = all.filter((r) => (!f.doctor || r.doctor?.name === f.doctor) && (!f.organization || r.organization === f.organization)
    && (!f.medication || r.medication_names.includes(f.medication)));
  const pending = new Set((q.data?.corrections ?? []).filter((c: any) => c.status === "open").map((c: any) => c.record_id));

  return (
    <div className="space-y-4">
      <div className="card grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Select aria-label="Record type" value={f.record_type} onChange={(e) => setF({ record_type: e.target.value, doctor: "", organization: "", medication: "" })}>
          <option value="">All types</option>
          {Object.keys(TYPE_ICON).map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
        </Select>
        <Select aria-label="Doctor" value={f.doctor} onChange={(e) => setF({ ...f, doctor: e.target.value })} disabled={!doctors.length}>
          <option value="">All doctors</option>{doctors.map((d) => <option key={d}>{d}</option>)}
        </Select>
        <Select aria-label="Hospital" value={f.organization} onChange={(e) => setF({ ...f, organization: e.target.value })} disabled={!hospitals.length}>
          <option value="">All hospitals</option>{hospitals.map((d) => <option key={d}>{d}</option>)}
        </Select>
        <Select aria-label="Medication" value={f.medication} onChange={(e) => setF({ ...f, medication: e.target.value })} disabled={!meds.length}>
          <option value="">All medications</option>{meds.map((d) => <option key={d}>{d}</option>)}
        </Select>
      </div>
      {!q.isLoading && f.record_type && <p className="text-sm text-ink-3">{records.length} {titleCase(f.record_type).toLowerCase()} record{records.length === 1 ? "" : "s"} in your full history</p>}
      {q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : q.isLoading ? <Skeleton className="h-64" /> :
        records.length === 0 ? <EmptyState icon={<FileText className="h-6 w-6" />} title="No matching records" /> : (
          <ol className="relative space-y-4 border-l-2 border-line pl-6">
            {records.map((r, i) => (
              <motion.li key={r.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i * 0.03, 0.3) }} className="relative">
                <span className="absolute -left-[37px] top-3 grid h-7 w-7 place-items-center rounded-full border-2 border-bg bg-primary-soft text-primary">{TYPE_ICON[r.record_type] ?? <FileText className="h-4 w-4" />}</span>
                <div className={`card p-4 ${r.status !== "current" ? "opacity-70" : ""}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-bold">{r.title}</p>
                    <Badge>{titleCase(r.record_type)}</Badge>
                    <Provenance value={r.provenance} />
                    {r.status === "amended" && <Badge tone="warn">Amended — see newer entry</Badge>}
                    {r.amends_id && <Badge tone="info">Amendment</Badge>}
                    {pending.has(r.id) && <Badge tone="info">Correction requested</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-ink-3">
                    {fmtDate(r.occurred_at)}{r.doctor && ` · ${r.doctor.name}`}{r.organization && ` · ${r.organization}`}
                  </p>
                  {r.summary && <p className="mt-2 text-sm text-ink-2">{r.summary}</p>}
                  {Object.keys(r.data ?? {}).length > 0 && (
                    <dl className="mt-2 flex flex-wrap gap-3 text-sm">{Object.entries(r.data).map(([k, v]) => <div key={k} className="rounded-lg bg-surface-2 px-2.5 py-1"><dt className="inline text-ink-3">{k}: </dt><dd className="inline font-semibold">{v}</dd></div>)}</dl>
                  )}
                  {canRequestCorrection && r.status === "current" && !pending.has(r.id) && (
                    <button className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-ink-3 hover:text-ink" onClick={() => setCorrect(r)}>
                      <Pencil className="h-3.5 w-3.5" /> Request a correction
                    </button>
                  )}
                </div>
              </motion.li>
            ))}
          </ol>
        )}
      <Modal open={!!correct} onClose={() => setCorrect(null)} title="Request a correction" size="sm"
        footer={<><Button variant="outline" onClick={() => setCorrect(null)}>Cancel</Button><Button onClick={() => corr.mutate()} disabled={text.length < 10} loading={corr.isPending}>Send request</Button></>}>
        <p className="text-sm text-ink-2">Describe what's wrong in <b>{correct?.title}</b>. Your doctor reviews it; the original stays in your history with an amendment trail — nothing is silently overwritten.</p>
        <Textarea className="mt-3" aria-label="Correction details" value={text} onChange={(e) => setText(e.target.value)} />
      </Modal>
    </div>
  );
}

function KnowledgeTag({ status }: { status: string }) {
  const map: Record<string, [string, "ok" | "neutral" | "warn", ReactNode]> = {
    has_allergies: ["Known — recorded below", "ok", <AlertTriangle key="a" className="h-3 w-3" />],
    has_conditions: ["Known — recorded below", "ok", <HeartPulse key="b" className="h-3 w-3" />],
    none_known: ["Known negative — none reported", "neutral", <CircleSlash key="c" className="h-3 w-3" />],
    unknown: ["Unknown — not yet recorded", "warn", <CircleHelp key="d" className="h-3 w-3" />],
  };
  const [l, t, i] = map[status] ?? map.unknown;
  return <Badge tone={t} icon={i}>{l}</Badge>;
}

function HealthOverview({ patientId }: { patientId: string }) {
  const q = useQuery({ queryKey: ["health", patientId], queryFn: () => api.get(`/api/patients/${patientId}/health`) });
  const [edit, setEdit] = useState<false | "info" | "body">(false);
  const [form, setForm] = useState<any>({});
  const qc = useQueryClient();
  const toast = useToast();
  const save = useMutation({
    mutationFn: () => api.patch(`/api/patients/${patientId}/health/self-reported`, edit === "body" ? {
      date_of_birth: form.date_of_birth || null, sex: form.sex || null,
      height_cm: form.height_cm === "" ? null : Number(form.height_cm), weight_kg: form.weight_kg === "" ? null : Number(form.weight_kg) } : form),
    onSuccess: () => { toast("ok", "Saved as patient-reported information."); setEdit(false); qc.invalidateQueries({ queryKey: ["health"] }); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-64" />;
  const h = q.data;
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="card p-5">
        <div className="flex items-center justify-between"><h2 className="font-bold">Documented conditions</h2><KnowledgeTag status={h.conditions.status} /></div>
        <ul className="mt-3 space-y-2">{h.conditions.items.map((c: any) => (
          <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-surface-2 px-3 py-2 text-sm">
            <span className="font-semibold">{c.name}{c.code && <span className="ml-1 text-ink-3">({c.code})</span>}</span>
            <span className="flex gap-1.5"><Badge>{titleCase(c.status)}</Badge><Provenance value={c.provenance} /></span>
          </li>))}
          {h.conditions.items.length === 0 && <li className="text-sm text-ink-3">Nothing recorded. This does not mean you have no conditions.</li>}
        </ul>
      </section>
      <section className="card p-5">
        <div className="flex items-center justify-between"><h2 className="font-bold">Allergies</h2><KnowledgeTag status={h.allergies.status} /></div>
        <ul className="mt-3 space-y-2">{h.allergies.items.map((a: any) => (
          <li key={a.id} className="rounded-xl bg-danger-soft/60 px-3 py-2 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">{a.substance}</span><Provenance value={a.provenance} /></div>
            {a.reaction && <p className="text-ink-2">{a.reaction}{a.severity && ` · ${a.severity}`}</p>}
          </li>))}
          {h.allergies.items.length === 0 && <li className="text-sm text-ink-3">{h.allergies.status === "none_known" ? "No known allergies reported." : "Allergy status unknown — this is not the same as 'no allergies'."}</li>}
        </ul>
      </section>
      <section className="card p-5 lg:col-span-2">
        <div className="flex items-center justify-between"><h2 className="font-bold">Body measurements</h2>
          <Button size="sm" variant="outline" onClick={() => { setForm({ date_of_birth: h.demographics.date_of_birth ?? "", sex: h.demographics.sex ?? "", height_cm: h.demographics.height_cm ?? "", weight_kg: h.demographics.weight_kg ?? "" }); setEdit("body"); }}
            icon={<Pencil className="h-4 w-4" />}>Edit</Button></div>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
          <div className="rounded-xl bg-surface-2 p-3"><dt className="text-ink-3">Age</dt><dd className="font-display text-lg font-bold">{h.demographics.age != null ? `${h.demographics.age} years` : "—"}</dd></div>
          <div className="rounded-xl bg-surface-2 p-3"><dt className="text-ink-3">Sex</dt><dd className="font-display text-lg font-bold">{h.demographics.sex ?? "—"}</dd></div>
          <div className="rounded-xl bg-surface-2 p-3"><dt className="text-ink-3">Height</dt><dd className="font-display text-lg font-bold">{h.demographics.height_cm ? `${h.demographics.height_cm} cm` : "—"}</dd></div>
          <div className="rounded-xl bg-surface-2 p-3"><dt className="text-ink-3">Weight</dt><dd className="font-display text-lg font-bold">{h.demographics.weight_kg ? `${h.demographics.weight_kg} kg` : "—"}</dd></div>
          <div className="rounded-xl bg-surface-2 p-3"><dt className="text-ink-3">BMI</dt><dd className="font-display text-lg font-bold">{h.demographics.bmi ?? "—"}</dd>
            {h.demographics.bmi_category && <dd className="text-xs text-ink-3">{h.demographics.bmi_category}</dd>}</div>
        </dl>
        <p className="mt-2 text-xs text-ink-3">BMI is calculated from your height and weight.</p>
      </section>
      <section className="card p-5">
        <h2 className="font-bold">Current medicines</h2>
        <ul className="mt-3 space-y-1.5 text-sm">{h.current_medicines.map((m: any) => <li key={m.id} className="flex items-center gap-2"><Pill className="h-4 w-4 text-primary" />{m.current.generic_name} {m.current.strength} — {m.current.frequency_label}</li>)}
          {h.current_medicines.length === 0 && <li className="text-ink-3">None recorded.</li>}</ul>
      </section>
      <section className="card p-5">
        <div className="flex items-center justify-between"><h2 className="font-bold">Emergency information</h2>
          <Button size="sm" variant="outline" onClick={() => { setForm({ emergency_contact_name: h.emergency.contact_name ?? "", emergency_contact_phone: h.emergency.contact_phone ?? "", emergency_contact_relation: h.emergency.relation ?? "", blood_group: h.emergency.blood_group ?? "", emergency_info_shareable: h.emergency.shareable, patient_reported_notes: h.patient_reported ?? "", allergy_status: h.allergies.status }); setEdit("info"); }}
            icon={<Pencil className="h-4 w-4" />}>Edit</Button></div>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-ink-3">Contact</dt><dd className="font-semibold">{h.emergency.contact_name ?? "Not set"}{h.emergency.relation && ` (${h.emergency.relation})`}</dd></div>
          <div><dt className="text-ink-3">Phone</dt><dd className="font-semibold">{h.emergency.contact_phone ?? "—"}</dd></div>
          <div><dt className="text-ink-3">Blood group</dt><dd className="font-semibold">{h.emergency.blood_group ?? "Unknown"}</dd></div>
          <div><dt className="text-ink-3">Shareable in emergencies</dt><dd className="font-semibold">{h.emergency.shareable ? "Yes" : "No"}</dd></div>
        </dl>
        {h.patient_reported && <p className="mt-3 rounded-xl bg-primary-soft/60 p-3 text-sm"><Provenance value="patient_reported" /> <span className="ml-1">{h.patient_reported}</span></p>}
      </section>
      <Modal open={edit === "body"} onClose={() => setEdit(false)} title="Update body measurements"
        footer={<><Button variant="outline" onClick={() => setEdit(false)}>Cancel</Button><Button onClick={() => save.mutate()} loading={save.isPending}>Save</Button></>}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Date of birth">{(p) => <DateInput {...p} value={form.date_of_birth ?? ""} max={new Date().toISOString().slice(0, 10)} onChange={(v) => setForm({ ...form, date_of_birth: v })} />}</Field>
          <Field label="Sex">{(p) => <Select {...p} value={form.sex ?? ""} onChange={(e) => setForm({ ...form, sex: e.target.value })}>
            <option value="">Not recorded</option><option>Female</option><option>Male</option><option>Other</option></Select>}</Field>
          <Field label="Height (cm)">{(p) => <Input {...p} type="number" inputMode="decimal" min={40} max={250} value={form.height_cm ?? ""} onChange={(e) => setForm({ ...form, height_cm: e.target.value })} />}</Field>
          <Field label="Weight (kg)">{(p) => <Input {...p} type="number" inputMode="decimal" min={2} max={350} step="0.1" value={form.weight_kg ?? ""} onChange={(e) => setForm({ ...form, weight_kg: e.target.value })} />}</Field>
        </div>
      </Modal>
      <Modal open={edit === "info"} onClose={() => setEdit(false)} title="Update your details" size="lg"
        footer={<><Button variant="outline" onClick={() => setEdit(false)}>Cancel</Button><Button onClick={() => save.mutate()} loading={save.isPending}>Save</Button></>}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Emergency contact name">{(p) => <Input {...p} value={form.emergency_contact_name ?? ""} onChange={(e) => setForm({ ...form, emergency_contact_name: e.target.value })} />}</Field>
          <Field label="Emergency contact phone">{(p) => <Input {...p} type="tel" value={form.emergency_contact_phone ?? ""} onChange={(e) => setForm({ ...form, emergency_contact_phone: e.target.value })} />}</Field>
          <Field label="Relationship">{(p) => <Input {...p} value={form.emergency_contact_relation ?? ""} onChange={(e) => setForm({ ...form, emergency_contact_relation: e.target.value })} />}</Field>
          <Field label="Blood group">{(p) => <Input {...p} value={form.blood_group ?? ""} onChange={(e) => setForm({ ...form, blood_group: e.target.value })} />}</Field>
          <Field label="Allergy status">{(p) => <Select {...p} value={form.allergy_status} onChange={(e) => setForm({ ...form, allergy_status: e.target.value })}>
            <option value="unknown">I'm not sure / not recorded</option><option value="none_known">I have no known allergies</option><option value="has_allergies">I have allergies</option></Select>}</Field>
          <Field label="Add an allergy (patient-reported)">{(p) => <Input {...p} placeholder="e.g. Peanuts" value={form.new_allergy ?? ""} onChange={(e) => setForm({ ...form, new_allergy: e.target.value })} />}</Field>
          <div className="sm:col-span-2"><Field label="Anything else your care team should know">{(p) => <Textarea {...p} value={form.patient_reported_notes ?? ""} onChange={(e) => setForm({ ...form, patient_reported_notes: e.target.value })} />}</Field></div>
          <div className="sm:col-span-2"><Checkbox checked={!!form.emergency_info_shareable} onChange={(v) => setForm({ ...form, emergency_info_shareable: v })} label="Allow sharing this emergency information when I trigger an emergency alert" /></div>
        </div>
        <Notice tone="info">Details you add are labelled "Patient reported" so doctors can tell them apart from verified records.</Notice>
      </Modal>
    </div>
  );
}

function Documents({ patientId, openUpload }: { patientId: string; openUpload: boolean }) {
  const [qText, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [upload, setUpload] = useState(openUpload);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["documents", patientId, qText, cat], queryFn: () => api.get(`/api/patients/${patientId}/documents?q=${encodeURIComponent(qText)}&category=${cat}`) });
  const download = async (id: string) => {
    const r = await fetch(`/api/patients/${patientId}/documents/${id}/download`, { credentials: "same-origin" });
    if (r.headers.get("content-type")?.includes("json")) { const j = await r.json(); window.open(j.url, "_blank", "noopener"); return; }
    const url = URL.createObjectURL(await r.blob());
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <Input aria-label="Search documents" className="pl-9" placeholder="Search documents" value={qText} onChange={(e) => setQ(e.target.value)} /></div>
        <Select aria-label="Filter category" className="w-48" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">All categories</option><option value="prescription">Prescriptions</option><option value="lab_report">Lab reports</option>
          <option value="discharge_summary">Discharge summaries</option><option value="other">Other</option>
        </Select>
        <Button onClick={() => setUpload(true)} icon={<Upload className="h-4 w-4" />}>Upload</Button>
      </div>
      {q.isError ? <ErrorState error={q.error} /> : q.isLoading ? <Skeleton className="h-40" /> : q.data.length === 0 ? <EmptyState icon={<FileText className="h-6 w-6" />} title="No documents" body="Upload PDFs or photos of reports and prescriptions." /> : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {q.data.map((d: any) => (
            <li key={d.id} className="card flex items-start gap-3 p-4">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-soft text-primary"><FileText className="h-5 w-5" /></span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{d.title}</p>
                <p className="text-xs text-ink-3">{titleCase(d.category)} · {(d.size_bytes / 1024).toFixed(0)} KB · {fmtDate(d.created_at)}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {d.ocr_status && <Badge tone={d.ocr_status === "verified" ? "ok" : d.ocr_status === "rejected" ? "danger" : "warn"}>
                    {d.ocr_status === "extracted" ? "Needs your review" : d.ocr_status === "patient_reviewed" ? "Awaiting doctor verification" : titleCase(d.ocr_status)}</Badge>}
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <Button size="sm" variant="ghost" onClick={() => download(d.id)} icon={<Download className="h-4 w-4" />} aria-label={`Download ${d.title}`} />
                {d.ocr_id && d.ocr_status === "extracted" && <Button size="sm" variant="secondary" onClick={() => setReviewId(d.ocr_id)}>Review</Button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      <UploadDialog patientId={patientId} open={upload} onClose={() => setUpload(false)} onOcr={(id) => { setUpload(false); setReviewId(id); }} />
      {reviewId && <OcrReview patientId={patientId} extractionId={reviewId} onClose={() => setReviewId(null)} />}
    </div>
  );
}

function UploadDialog({ patientId, open, onClose, onOcr }: { patientId: string; open: boolean; onClose: () => void; onOcr: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("prescription");
  const [err, setErr] = useState<string | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  // every time the dialog opens it starts fresh (so the notice below is always seen)
  useEffect(() => { if (open) { setFile(null); setTitle(""); setCategory("prescription"); setErr(null); } }, [open]);
  const m = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("file", file!);
      fd.append("title", title || file!.name);
      fd.append("category", category);
      return api.post(`/api/patients/${patientId}/documents`, fd);
    },
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["records"] });
      setFile(null); setTitle("");
      if (r.ocr) onOcr(r.ocr.id); else { toast("ok", "Uploaded."); onClose(); }
    },
    onError: (e) => setErr(errorMessage(e)),
  });
  const pick = (f: File | null) => {
    setErr(null);
    if (f && !["application/pdf", "image/png", "image/jpeg"].includes(f.type)) return setErr("Only PDF, JPG and PNG files are supported.");
    if (f && f.size > 10 * 1024 * 1024) return setErr("Files must be 10 MB or smaller.");
    setFile(f);
  };
  return (
    <Modal open={open} onClose={onClose} title="Upload a document"
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={() => m.mutate()} disabled={!file} loading={m.isPending} icon={<Upload className="h-4 w-4" />}>Upload</Button></>}>
      <div className="space-y-4">
        {err && <Notice tone="danger">{err}</Notice>}
        <label className="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-line p-8 text-center hover:border-primary/50 hover:bg-primary-soft/30"
          onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files[0] ?? null); }}>
          <Upload className="h-7 w-7 text-primary" />
          <span className="font-semibold">{file ? file.name : "Drop a file or click to choose"}</span>
          <span className="text-xs text-ink-3">PDF, JPG or PNG · up to 10 MB · stored privately</span>
          <input type="file" className="sr-only" accept="application/pdf,image/png,image/jpeg" onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Title">{(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Blood test March" />}</Field>
          <Field label="Type">{(p) => <Select {...p} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="prescription">Prescription (will be checked by a doctor)</option><option value="lab_report">Lab report</option>
            <option value="discharge_summary">Discharge summary</option><option value="other">Other</option></Select>}</Field>
        </div>
        <Notice tone="warn" title="Before you upload">Upload only your own documents. A prescription you upload is checked by a doctor first: nothing becomes an active medicine or reminder until a doctor approves it.</Notice>
      </div>
    </Modal>
  );
}

export default function Records() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<"timeline" | "health" | "documents">(params.get("upload") ? "documents" : "timeline");
  useEffect(() => { if (params.get("upload")) setTab("documents"); }, [params]);
  const pid = user!.patient_id!;
  return (
    <>
      <PageHeader title="Medical Records" subtitle="Your history in one timeline, with the source of every entry." />
      <div className="mb-5"><Tabs label="Records sections" value={tab} onChange={setTab} tabs={[
        { id: "timeline", label: "Timeline" }, { id: "health", label: "Health overview" }, { id: "documents", label: "Documents" }]} /></div>
      {tab === "timeline" && <Timeline patientId={pid} canRequestCorrection />}
      {tab === "health" && <HealthOverview patientId={pid} />}
      {tab === "documents" && <Documents patientId={pid} openUpload={!!params.get("upload")} />}
      <p className="mt-8 flex items-center gap-1.5 text-xs text-ink-3"><Building2 className="h-3.5 w-3.5" /> Records from providers outside DoseWISE aren't included unless uploaded or imported.</p>
    </>
  );
}
