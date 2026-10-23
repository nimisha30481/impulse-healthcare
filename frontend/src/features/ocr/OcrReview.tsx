import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus, Trash2 } from "lucide-react";
import { Badge, Button, Field, Input, Skeleton } from "@/components/ui/primitives";
import { Modal, Notice, useToast } from "@/components/ui/feedback";
import { api, errorMessage } from "@/lib/api";

const MED_FIELDS = ["name", "strength", "dose", "route", "frequency", "duration"] as const;
type Med = Record<(typeof MED_FIELDS)[number], string>;
const blank = (): Med => ({ name: "", strength: "", dose: "", route: "", frequency: "", duration: "" });

/** Patient review of OCR output (or manual transcription when OCR isn't configured). */
export function OcrReview({ patientId, extractionId, onClose }: { patientId: string; extractionId: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["ocr", extractionId], queryFn: () => api.get(`/api/patients/${patientId}/ocr/${extractionId}`) });
  const [meds, setMeds] = useState<Med[]>([blank()]);
  const [header, setHeader] = useState({ doctor_name: "", date: "", instructions: "" });
  const qc = useQueryClient();
  const toast = useToast();
  useEffect(() => {
    const src = q.data?.patient_corrected ?? q.data?.extracted;
    if (src?.medications?.length) setMeds(src.medications.map((m: any) => ({ ...blank(), ...Object.fromEntries(MED_FIELDS.map((k) => [k, m[k] ?? ""])) })));
  }, [q.data]);
  const submit = useMutation({
    mutationFn: () => api.post(`/api/patients/${patientId}/ocr/${extractionId}/review`, { ...header, medications: meds.filter((m) => m.name.trim()), submit_for_verification: true }),
    onSuccess: () => { toast("ok", "Sent to your doctor for verification."); qc.invalidateQueries({ queryKey: ["documents"] }); onClose(); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  const e = q.data;
  const uncertain = new Set<string>(e?.uncertain_fields ?? []);
  return (
    <Modal open onClose={onClose} title="Review your prescription" size="xl"
      footer={<><Button variant="outline" onClick={onClose}>Save for later</Button>
        <Button onClick={() => submit.mutate()} loading={submit.isPending} disabled={!meds.some((m) => m.name.trim())}>Submit for doctor verification</Button></>}>
      {!e ? <Skeleton className="h-64" /> : (
        <div className="space-y-4">
          <Notice tone="warn" title="Unverified">{e.label}</Notice>
          {e.engine === "manual" && <Notice tone="info">Automatic reading (OCR) isn't configured, so please type what the prescription says. A doctor will compare it with your upload.</Notice>}
          {e.quality?.warnings?.length > 0 && <Notice tone="warn" title="Image quality">{e.quality.warnings.join(" ")}</Notice>}
          {e.possible_duplicates?.length > 0 && (
            <Notice tone="warn" title="Possible duplicates">{e.possible_duplicates.map((d: any) => d.kind === "already_active" ? `${d.name} is already an active medicine.` : `This file was uploaded before (${d.title}).`).join(" ")}</Notice>
          )}
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge>Engine: {e.engine}</Badge>
            {e.confidence != null && <Badge tone={e.confidence > 0.85 ? "ok" : "warn"}>Confidence {Math.round(e.confidence * 100)}%</Badge>}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Doctor's name">{(p) => <Input {...p} value={header.doctor_name} onChange={(ev) => setHeader({ ...header, doctor_name: ev.target.value })} />}</Field>
            <Field label="Date on prescription">{(p) => <Input {...p} value={header.date} onChange={(ev) => setHeader({ ...header, date: ev.target.value })} placeholder="DD/MM/YYYY" />}</Field>
            <Field label="General instructions">{(p) => <Input {...p} value={header.instructions} onChange={(ev) => setHeader({ ...header, instructions: ev.target.value })} />}</Field>
          </div>
          <div className="space-y-3">
            {meds.map((m, i) => (
              <div key={i} className="rounded-2xl border border-line p-3">
                <div className="mb-2 flex items-center justify-between"><p className="text-sm font-bold">Medicine {i + 1}</p>
                  {meds.length > 1 && <Button size="sm" variant="ghost" aria-label={`Remove medicine ${i + 1}`} onClick={() => setMeds(meds.filter((_, k) => k !== i))} icon={<Trash2 className="h-4 w-4" />} />}</div>
                <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
                  {MED_FIELDS.map((k) => (
                    <div key={k}>
                      <label className="text-xs font-medium text-ink-3" htmlFor={`m${i}${k}`}>{k[0].toUpperCase() + k.slice(1)}
                        {uncertain.has(`medications[${i}].${k}`) && <AlertTriangle className="ml-1 inline h-3 w-3 text-warn" aria-label="uncertain" />}</label>
                      <Input id={`m${i}${k}`} value={m[k]} onChange={(ev) => setMeds(meds.map((x, j) => j === i ? { ...x, [k]: ev.target.value } : x))}
                        className={uncertain.has(`medications[${i}].${k}`) ? "border-warn" : ""} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <Button size="sm" variant="outline" onClick={() => setMeds([...meds, blank()])} icon={<Plus className="h-4 w-4" />}>Add medicine</Button>
          </div>
          {e.raw_text && <details className="text-sm"><summary className="cursor-pointer font-semibold">Raw extracted text</summary><pre className="mt-2 whitespace-pre-wrap rounded-xl bg-surface-2 p-3 text-xs">{e.raw_text}</pre></details>}
        </div>
      )}
    </Modal>
  );
}
