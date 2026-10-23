import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, KeyRound, Lock, RefreshCw } from "lucide-react";
import { Button, Input, Select, Skeleton } from "@/components/ui/primitives";
import { ConfirmDialog, EmptyState, ErrorState, Notice, useToast } from "@/components/ui/feedback";
import { DoseStateBadge } from "./ReadOnlyChart";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, fmtDateTime, fmtTime } from "@/lib/format";

/** Patient dashboard: their Patient Access ID with copy and regenerate. */
export function AccessIdCard() {
  const q = useQuery({ queryKey: ["access-id"], queryFn: () => api.get("/api/me/access-id") });
  const [copied, setCopied] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const qc = useQueryClient();
  const toast = useToast();
  const regen = useMutation({ mutationFn: () => api.post("/api/me/access-id/regenerate"),
    onSuccess: (d) => { qc.setQueryData(["access-id"], d); setConfirm(false); toast("ok", "New Access ID created. The old one no longer works."); },
    onError: (e) => toast("danger", errorMessage(e)) });
  const copy = async () => {
    try { await navigator.clipboard.writeText(q.data.access_id); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { toast("danger", "Couldn't copy. Select the ID and copy it manually."); }
  };
  if (q.isLoading) return <Skeleton className="h-9 w-64" />;
  if (q.isError) return null;
  return (
    <div className="flex flex-wrap items-center gap-2" data-no-translate>
      <span className="inline-flex items-center gap-2 rounded-xl bg-white/15 px-3 py-1.5 text-sm backdrop-blur">
        <KeyRound className="h-4 w-4" /> Patient Access ID: <b className="font-mono text-base tracking-wider">{q.data.access_id}</b>
        <button onClick={copy} aria-label="Copy Access ID" className="rounded-md p-1 hover:bg-white/20">
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </button>
      </span>
      <button onClick={() => setConfirm(true)} className="inline-flex items-center gap-1.5 rounded-xl bg-white/15 px-3 py-1.5 text-sm font-semibold backdrop-blur hover:bg-white/25">
        <RefreshCw className="h-4 w-4" /> Regenerate ID
      </button>
      <span className="text-xs opacity-80">Share it only with doctors treating you · valid until {fmtDate(q.data.expires_at)}</span>
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={() => regen.mutate()} loading={regen.isPending}
        title="Regenerate your Access ID?" confirmLabel="Regenerate"
        body="Anyone holding your current ID (including guest doctors) won't be able to use it any more. Doctors who already opened your record keep their time-limited access; revoke that in Care Team." />
    </div>
  );
}

/** Doctor: enter a Patient Access ID to open (and get time-limited access to) a patient's chart. */
export function AccessIdUnlock({ compact }: { compact?: boolean }) {
  const [code, setCode] = useState("");
  const nav = useNavigate();
  const qc = useQueryClient();
  const { session } = useAuth();
  const m = useMutation({ mutationFn: () => api.post("/api/doctor/access-id", { access_id: code }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["doctor-patients"] }); qc.invalidateQueries({ queryKey: ["doctor-dashboard"] }); nav(`/doctor/patients/${r.patient_id}`); } });
  const submit = (e: FormEvent) => { e.preventDefault(); if (code.trim()) m.mutate(); };
  return (
    <section className={compact ? "card p-5" : "card mx-auto max-w-xl p-6 text-center sm:p-8"}>
      {!compact && <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-danger-soft text-danger"><Lock className="h-6 w-6" /></span>}
      <h2 className={compact ? "flex items-center gap-2 font-bold" : "mt-4 text-xl font-extrabold"}>{compact && <KeyRound className="h-5 w-5 text-primary" />}Open a patient's record</h2>
      <p className="mt-2 text-sm text-ink-2">Records are private. Ask the patient for their <b>Patient Access ID</b> to view their history, prescribe and track their doses.</p>
      <form onSubmit={submit} className={compact ? "mt-3 flex gap-2" : "mt-5 space-y-3 text-left"}>
        <label className="sr-only" htmlFor="access-id">Patient Access ID</label>
        <Input id="access-id" className="font-mono uppercase tracking-wider" placeholder="DW-XXXXXX" autoComplete="off"
          value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />
        <Button type="submit" loading={m.isPending} disabled={!code.trim()} className={compact ? "" : "w-full"} icon={<KeyRound className="h-4 w-4" />}>
          {compact ? "Open" : "Unlock patient record"}
        </Button>
      </form>
      {m.isError && <div className="mt-3 text-left"><Notice tone="danger">{errorMessage(m.error)}</Notice></div>}
      {session?.demo_enabled && <p className="mt-2 text-xs text-ink-3">Demo: try DW-ANANYA or DW-RAHULV</p>}
    </section>
  );
}

/** Doctor / care team: dose-by-dose history (taken, late, missed, not logged). */
export function DoseLog({ patientId }: { patientId: string }) {
  const [days, setDays] = useState("14");
  const q = useQuery({ queryKey: ["dose-log", patientId, days], queryFn: () => api.get(`/api/doctor/patients/${patientId}/dose-log?days=${days}`),
    refetchInterval: 30_000 });
  return (
    <section className="card p-5" aria-labelledby="dose-log-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="dose-log-title" className="font-bold">Dose history</h2>
        <Select aria-label="Period" className="w-40" value={days} onChange={(e) => setDays(e.target.value)}>
          <option value="7">Last 7 days</option><option value="14">Last 14 days</option><option value="30">Last 30 days</option>
        </Select>
      </div>
      {q.isError ? <div className="mt-3"><ErrorState error={q.error} onRetry={() => q.refetch()} /></div> : q.isLoading ? <Skeleton className="mt-3 h-48" /> : (
        <>
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            {(["taken", "late", "missed", "not_logged"] as const).map((k) => (
              <span key={k} className="inline-flex items-center gap-1.5"><DoseStateBadge state={k} /><b>{q.data.counts[k]}</b></span>
            ))}
          </div>
          {q.data.rows.length === 0 ? <div className="mt-4"><EmptyState title="No doses in this period" body="Doses appear here once a prescription is active." /></div> : (
            <div className="mt-4 max-h-[480px] overflow-auto rounded-xl border border-line">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="sticky top-0 bg-surface-2 text-xs uppercase text-ink-3">
                  <tr><th className="px-3 py-2">Medication</th><th className="px-3 py-2">Scheduled time</th><th className="px-3 py-2">Time logged</th><th className="px-3 py-2">Status</th></tr>
                </thead>
                <tbody>{q.data.rows.map((r: any) => (
                  <tr key={r.id} className="border-t border-line">
                    <td className="px-3 py-2"><b>{r.medication}</b> <span className="text-ink-3">{r.dose}</span></td>
                    <td className="px-3 py-2">{fmtDateTime(r.scheduled_at)}</td>
                    <td className="px-3 py-2">{r.logged_at ? fmtTime(r.logged_at) : "—"}</td>
                    <td className="px-3 py-2"><DoseStateBadge state={r.state} /></td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
          <p className="mt-2 text-xs text-ink-3">"Taken" means the patient used Log dosage. Logged more than {q.data.late_after_minutes} minutes after the scheduled time counts as late. "Not logged" means no response; it isn't assumed missed. Updates automatically.</p>
        </>
      )}
    </section>
  );
}
