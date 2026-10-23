import { Link } from "react-router-dom";
import { AlertTriangle, Bot, CircleHelp, FileSearch, Link2 } from "lucide-react";
import { Badge } from "@/components/ui/primitives";
import { Notice } from "@/components/ui/feedback";
import { Provenance } from "@/components/ui/domain";
import { fmtDateTime } from "@/lib/format";

export function BriefView({ brief, patientId }: { brief: any; patientId: string }) {
  const c = brief.content;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge tone="info" icon={<FileSearch className="h-3 w-3" />}>Generated {fmtDateTime(c.generated_at)}</Badge>
        <span className="text-ink-3">{c.label}</span>
      </div>
      {c.conflicts.length > 0 && (
        <Notice tone="danger" title="Conflicting records">
          <ul className="list-disc pl-4">{c.conflicts.map((x: any, i: number) => <li key={i}>{x.text}</li>)}</ul>
        </Notice>
      )}
      {c.missing_information.length > 0 && (
        <Notice tone="warn" title="Missing information" icon={<CircleHelp className="h-[18px] w-[18px]" />}>
          <ul className="list-disc pl-4">{c.missing_information.map((x: string) => <li key={x}>{x}</li>)}</ul>
        </Notice>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {Object.entries(c.sections).map(([key, s]: any) => (
          <section key={key} className="rounded-2xl border border-line p-4">
            <h3 className="text-sm font-bold uppercase tracking-wide text-ink-3">{s.title}</h3>
            {s.items.length === 0 ? <p className="mt-2 text-sm text-ink-3">Not documented.</p> : (
              <ul className="mt-2 space-y-2">
                {s.items.map((it: any, i: number) => (
                  <li key={i} className="text-sm">
                    <span className="text-ink">{it.text}</span>
                    <span className="ml-1.5 inline-flex flex-wrap items-center gap-1 align-middle">
                      {it.provenance && <Provenance value={it.provenance} />}
                      {it.sources?.map((src: any) => (
                        <Link key={src.id} to={src.type === "medical_record" || src.type === "diagnosis" || src.type === "allergy"
                          ? `/doctor/patients/${patientId}?tab=history` : `/doctor/patients/${patientId}?tab=prescriptions`}
                          className="inline-flex items-center gap-0.5 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-semibold text-ink-3 hover:text-primary"
                          title={`Source: ${src.type} ${src.id}`}>
                          <Link2 className="h-2.5 w-2.5" />{src.type.replace("_", " ")}
                        </Link>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
      <section className="rounded-2xl border border-dashed border-line p-4">
        <h3 className="flex items-center gap-2 text-sm font-bold"><Bot className="h-4 w-4" />AI narrative (Amazon Bedrock)</h3>
        {brief.ai_status === "ok" ? (
          <>
            <Badge tone="warn" icon={<AlertTriangle className="h-3 w-3" />} className="mt-2">AI-generated · unverified · not a clinical fact</Badge>
            <p className="mt-2 whitespace-pre-line text-sm text-ink-2">{brief.ai_summary}</p>
          </>
        ) : (
          <p className="mt-1 text-sm text-ink-3">{brief.ai_status === "not_configured" ? "Not configured — the brief above is assembled directly from records." : "The AI summary failed validation and was discarded."}</p>
        )}
      </section>
      <ul className="text-xs text-ink-3">{c.uncertainty.map((u: string) => <li key={u}>• {u}</li>)}</ul>
    </div>
  );
}
