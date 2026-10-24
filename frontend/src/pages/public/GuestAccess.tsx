import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { KeyRound, Stethoscope } from "lucide-react";
import { Button, Field, Input } from "@/components/ui/primitives";
import { Notice } from "@/components/ui/feedback";
import { ReadOnlyChart } from "@/features/access/ReadOnlyChart";
import { api, errorMessage } from "@/lib/api";

/** Guest / One-Time Doctor Access: read-only record lookup with the patient's Access ID. */
export default function GuestAccess() {
  const [f, setF] = useState({ access_id: "", doctor_name: "", doctor_license: "", hospital: "" });
  const m = useMutation({ mutationFn: () => api.post("/api/access/guest-view", {
    access_id: f.access_id, doctor_name: f.doctor_name || null, doctor_license: f.doctor_license || null, hospital: f.hospital || null }) });
  const submit = (e: FormEvent) => { e.preventDefault(); setEnded(false); if (f.access_id.trim()) m.mutate(); };
  // The guest view lasts 15 minutes, then the chart is wiped from the page (the guest is signed out).
  const [left, setLeft] = useState<number | null>(null);
  const [ended, setEnded] = useState(false);
  const end = (timedOut: boolean) => { m.reset(); setLeft(null); setEnded(timedOut); setF({ access_id: "", doctor_name: "", doctor_license: "", hospital: "" }); };
  useEffect(() => {
    if (!m.data) return;
    const until = new Date(m.data.session.expires_at).getTime();
    const tick = () => {
      const s = Math.max(0, Math.round((until - Date.now()) / 1000));
      setLeft(s);
      if (s === 0) end(true);
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [m.data]); // eslint-disable-line react-hooks/exhaustive-deps

  if (m.data) return <div className="container-page max-w-6xl py-10"><ReadOnlyChart data={m.data} secondsLeft={left ?? undefined} onNewSearch={() => end(false)} /></div>;

  return (
    <div className="container-page max-w-2xl py-12">
      <div className="card p-7 sm:p-9">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-primary text-primary-ink"><Stethoscope className="h-7 w-7" /></span>
        <h1 className="mt-5 text-center text-3xl font-extrabold">Guest / Emergency Doctor Access</h1>
        <p className="mt-3 text-center text-ink-2">
          Read-only access for emergency physicians and doctors at other hospitals. Enter the patient's
          <b> Patient Access ID</b> to see their active medicines, dose history, allergies and records.
        </p>
        <form onSubmit={submit} className="mt-8 space-y-4">
          {ended && <Notice tone="info" title="Guest session ended">The 15-minute read-only view has closed and the chart was cleared from this screen. The Access ID you used no longer works; ask the patient for their new one.</Notice>}
          {m.isError && <Notice tone="danger">{errorMessage(m.error)}</Notice>}
          <Field label="Patient Access ID" hint="Given by the patient from their DoseWISE dashboard, e.g. DW-7K2M9Q" required>
            {(p) => <Input {...p} autoFocus autoComplete="off" className="font-mono uppercase tracking-wider" placeholder="DW-XXXXXX"
              value={f.access_id} onChange={(e) => setF({ ...f, access_id: e.target.value.toUpperCase() })} />}
          </Field>
          <details className="rounded-xl bg-surface-2 p-3" open>
            <summary className="cursor-pointer text-sm font-semibold">About you (optional, recorded in the access log)</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <Field label="Your name">{(p) => <Input {...p} value={f.doctor_name} onChange={(e) => setF({ ...f, doctor_name: e.target.value })} />}</Field>
              <Field label="Licence / reg. no.">{(p) => <Input {...p} value={f.doctor_license} onChange={(e) => setF({ ...f, doctor_license: e.target.value })} />}</Field>
              <Field label="Hospital">{(p) => <Input {...p} value={f.hospital} onChange={(e) => setF({ ...f, hospital: e.target.value })} />}</Field>
            </div>
          </details>
          <Button type="submit" size="lg" className="w-full" loading={m.isPending} disabled={!f.access_id.trim()} icon={<KeyRound className="h-5 w-5" />}>Unlock patient record</Button>
          <p className="text-center text-xs text-ink-3">Every attempt is logged with time and IP address, and the patient is notified. Each Access ID works once, for 15 minutes. Registered doctor? <Link to="/login" className="link">Sign in</Link> to prescribe.</p>
        </form>
      </div>
    </div>
  );
}
