import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Info } from "lucide-react";
import { Skeleton } from "@/components/ui/primitives";
import { ErrorState } from "@/components/ui/feedback";
import { Tabs } from "@/components/ui/domain";
import { api } from "@/lib/api";
import { fmtDate, pct } from "@/lib/format";
import type { Adherence } from "@/lib/types";

const SERIES = [
  { key: "taken_reported", label: "Reported taken", color: "rgb(var(--ok))" },
  { key: "missed_reported", label: "Reported missed", color: "rgb(var(--danger))" },
  { key: "skipped", label: "Skipped", color: "rgb(var(--warn) / 0.6)" },
  { key: "unconfirmed", label: "Unconfirmed", color: "rgb(var(--warn))" },
];

export function AdherenceCard({ patientId, initial, compact }: { patientId: string; initial?: Adherence; compact?: boolean }) {
  const [days, setDays] = useState<"7" | "30">("7");
  const q = useQuery({
    queryKey: ["adherence", patientId, days],
    queryFn: () => api.get<Adherence>(`/api/patients/${patientId}/adherence?days=${days}`),
    initialData: days === "7" ? initial : undefined,
  });
  const [showTable, setShowTable] = useState(false);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const a = q.data;
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-bold">Adherence overview</h2>
        <Tabs label="Adherence window" value={days} onChange={setDays} tabs={[{ id: "7", label: "Weekly" }, { id: "30", label: "Monthly" }]} />
      </div>
      {!a ? <Skeleton className="mt-4 h-48" /> : (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[["Scheduled", a.scheduled], ["Reported taken", a.taken_reported], ["Missed reports", a.missed_reported], ["Unconfirmed", a.unconfirmed]].map(([l, v]) => (
              <div key={l} className="rounded-xl bg-surface-2 p-3">
                <dt className="text-xs font-medium text-ink-3">{l}</dt>
                <dd className="font-display text-xl font-extrabold">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-sm text-ink-2">
            <b className="text-ink">{pct(a.reported_rate)}</b> of answered doses were reported taken
            {" "}({a.responses_received} of {a.scheduled} scheduled doses have a response, {pct(a.response_coverage)}).
          </p>
          {!compact && a.trend.length > 0 && (
            <div className="mt-4 h-56" role="img" aria-label={`Daily dose responses for the last ${a.window_days} days. Use the table toggle for exact values.`}>
              <ResponsiveContainer>
                <BarChart data={a.trend.map((d) => ({ ...d, label: fmtDate(d.date, { year: undefined }) }))}>
                  <CartesianGrid vertical={false} stroke="rgb(var(--line))" />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: "rgb(var(--ink-3))" }} tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "rgb(var(--ink-3))" }} tickLine={false} axisLine={false} width={24} />
                  <Tooltip contentStyle={{ background: "rgb(var(--surface))", border: "1px solid rgb(var(--line))", borderRadius: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {SERIES.map((s) => <Bar key={s.key} dataKey={s.key} name={s.label} stackId="a" fill={s.color} radius={[0, 0, 0, 0]} />)}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {!compact && (
            <button className="link mt-2 text-sm" onClick={() => setShowTable(!showTable)} aria-expanded={showTable}>
              {showTable ? "Hide" : "Show"} data table
            </button>
          )}
          {showTable && (
            <table className="mt-2 w-full text-left text-sm">
              <thead className="text-ink-3"><tr><th className="py-1">Date</th>{SERIES.map((s) => <th key={s.key}>{s.label}</th>)}</tr></thead>
              <tbody>{a.trend.map((d) => (
                <tr key={d.date} className="border-t border-line"><td className="py-1">{fmtDate(d.date)}</td>{SERIES.map((s) => <td key={s.key}>{(d as any)[s.key]}</td>)}</tr>
              ))}</tbody>
            </table>
          )}
          <details className="mt-3 rounded-xl bg-info-soft/60 p-3 text-sm">
            <summary className="flex cursor-pointer items-center gap-1.5 font-semibold text-info"><Info className="h-4 w-4" /> How is this calculated?</summary>
            <p className="mt-2 text-ink-2">{a.method}</p>
          </details>
        </>
      )}
    </div>
  );
}
