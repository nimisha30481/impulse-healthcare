import { HeartHandshake, ShieldCheck, Target } from "lucide-react";

export default function About() {
  return (
    <div className="container-page max-w-4xl py-16">
      <p className="text-sm font-semibold uppercase tracking-wider text-primary">About DoseWISE</p>
      <h1 className="mt-3 text-4xl font-extrabold sm:text-5xl">One trustworthy view of every medicine.</h1>
      <p className="mt-6 text-lg leading-relaxed text-ink-2">
        People often receive prescriptions from several doctors, while dosage changes, allergies and treatment histories
        sit in different hospitals and pharmacies. DoseWISE brings patients, doctors, caregivers and care coordinators onto
        one platform so the medication record stays current, every change is versioned, and help arrives when someone
        stops responding.
      </p>
      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {[
          { i: <Target className="h-5 w-5" />, t: "Our focus", d: "Medication safety, adherence support and connected care — not a generic hospital portal." },
          { i: <ShieldCheck className="h-5 w-5" />, t: "Our standards", d: "Clinical facts are never invented. Unverified data is labelled. Integrations that aren't connected say so." },
          { i: <HeartHandshake className="h-5 w-5" />, t: "Our users", d: "Patients first — with doctors, caregivers and coordinators working inside the permissions patients grant." },
        ].map((c) => (
          <div key={c.t} className="card p-6">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-soft text-primary">{c.i}</span>
            <h2 className="mt-4 text-lg font-bold">{c.t}</h2>
            <p className="mt-1 text-sm text-ink-2">{c.d}</p>
          </div>
        ))}
      </div>
      <p className="mt-12 rounded-2xl border border-dashed border-line p-5 text-sm text-ink-3">
        DoseWISE is under active development. It is not yet a certified medical device and makes no regulatory compliance
        claims.
      </p>
    </div>
  );
}
