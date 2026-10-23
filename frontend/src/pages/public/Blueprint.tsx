/** Project blueprint: the idea, design and plan in one public page, ordered by the Round 1 judging criteria. */
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle, ArrowDown, ArrowRight, Cloud, Database, ExternalLink, Gauge, KeyRound, Layers, Lightbulb,
  Lock, Monitor, Network, Rocket, ShieldCheck, Smartphone, Target, Users, Wallet,
} from "lucide-react";
import { Badge } from "@/components/ui/primitives";

const SECTIONS = [
  ["problem", "1. Problem & use case"], ["aws", "2. AWS selection"], ["architecture", "3. Architecture & security"],
  ["mvp", "4. MVP plan & scope"], ["scale", "5. Scalability & cost"], ["innovation", "6. Innovation"], ["pitch", "7. Team & pitch"],
] as const;

function Section({ id, icon, title, lead, children }: { id: string; icon: ReactNode; title: string; lead: string; children: ReactNode }) {
  return (
    // Content is always visible (no scroll-triggered hiding) so anchor links and printouts never show blank sections.
    <motion.section id={id} initial={{ y: 8 }} animate={{ y: 0 }} transition={{ duration: 0.35 }}
      className="scroll-mt-32 border-t border-line py-14">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-soft text-primary">{icon}</span>
        <h2 className="text-2xl font-extrabold sm:text-3xl">{title}</h2>
      </div>
      <p className="mt-3 max-w-3xl text-ink-2">{lead}</p>
      <div className="mt-8">{children}</div>
    </motion.section>
  );
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b border-line bg-surface-2 text-xs uppercase tracking-wide text-ink-3">
          <tr>{head.map((h) => <th key={h} className="px-4 py-3 font-semibold">{h}</th>)}</tr>
        </thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i} className="border-b border-line align-top last:border-0">{r.map((c, j) => <td key={j} className={`px-4 py-3 ${j === 0 ? "font-semibold text-ink" : "text-ink-2"}`}>{c}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function Box({ title, sub, tone = "surface", icon }: { title: string; sub?: string; tone?: "surface" | "primary" | "mint" | "warn"; icon?: ReactNode }) {
  const t = { surface: "bg-surface border-line", primary: "bg-primary text-primary-ink border-primary", mint: "bg-mint/70 border-mint", warn: "bg-warn-soft border-warn/30" }[tone];
  return (
    <div className={`rounded-xl border px-3 py-2.5 text-center shadow-card ${t}`}>
      <p className="flex items-center justify-center gap-1.5 text-sm font-bold">{icon}{title}</p>
      {sub && <p className={`mt-0.5 text-[11px] ${tone === "primary" ? "opacity-85" : "text-ink-3"}`}>{sub}</p>}
    </div>
  );
}

const Down = () => <div className="flex justify-center py-1.5 text-ink-3"><ArrowDown className="h-4 w-4" /></div>;

export default function Blueprint() {
  return (
    <div className="container-page max-w-6xl py-12">
      <p className="text-sm font-semibold uppercase tracking-wider text-primary">Project blueprint</p>
      <h1 className="mt-3 text-4xl font-extrabold sm:text-5xl">What IMPULSE is, how it's built, and why.</h1>
      <p className="mt-4 max-w-3xl text-lg text-ink-2">
        The idea, design and plan on one page: problem, AWS choices, architecture and security, MVP scope,
        scalability and cost, what's new, and who presents what.
      </p>
      <nav aria-label="Blueprint sections" className="sticky top-16 z-10 -mx-4 mt-8 flex gap-2 overflow-x-auto bg-bg/90 px-4 py-3 backdrop-blur">
        {SECTIONS.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="whitespace-nowrap rounded-full border border-line bg-surface px-3.5 py-1.5 text-sm font-semibold text-ink-2 hover:border-primary/50 hover:text-primary">{label}</a>
        ))}
      </nav>

      {/* 1 ------------------------------------------------------------------ */}
      <Section id="problem" icon={<Target className="h-5 w-5" />} title="1. Problem & use case"
        lead="People with long-term conditions get prescriptions from several doctors. Schedules, dose changes and allergies end up scattered across hospitals and pharmacies, which leads to duplicate medicines, missed doses and dangerous combinations nobody sees.">
        <div className="grid gap-5 lg:grid-cols-3">
          <div className="card p-5">
            <h3 className="flex items-center gap-2 font-bold"><Users className="h-4 w-4 text-primary" />Who the users are</h3>
            <ul className="mt-3 space-y-2 text-sm text-ink-2">
              <li><b className="text-ink">Primary:</b> adults on 3+ long-term medicines (e.g. diabetes + hypertension), often older.</li>
              <li><b className="text-ink">Doctors</b> who need the full current medication list before prescribing.</li>
              <li><b className="text-ink">Caregivers</b> (often adult children) supporting a parent remotely.</li>
              <li><b className="text-ink">Care coordinators</b> who follow up when a patient stops responding.</li>
            </ul>
          </div>
          <div className="card p-5">
            <h3 className="flex items-center gap-2 font-bold"><AlertTriangle className="h-4 w-4 text-warn" />The exact problem</h3>
            <ul className="mt-3 space-y-2 text-sm text-ink-2">
              <li>No single, current, versioned medication list across prescribers.</li>
              <li>Missed doses go unnoticed until the next visit.</li>
              <li>Duplicate ingredients and documented allergies aren't checked across prescriptions.</li>
              <li>Family can't help without sharing the patient's login.</li>
            </ul>
          </div>
          <div className="card p-5">
            <h3 className="flex items-center gap-2 font-bold"><ShieldCheck className="h-4 w-4 text-ok" />Proof</h3>
            <p className="mt-3 text-sm text-ink-2">
              The WHO report <i>Adherence to long-term therapies</i> (2003) estimates adherence to chronic-disease treatment at
              about <b className="text-ink">50% in developed countries</b>, and lower in developing countries — e.g. 43% for
              blood-pressure medicine in China and 27% in The Gambia.
            </p>
            <p className="mt-2 text-xs text-ink-3">
              Honest caveat: a 2012 review argues the 50% figure rests on limited studies. We'd validate locally with a
              pilot (target: 30 patients, measure response coverage and reported adherence before/after).
            </p>
            <div className="mt-3 flex flex-col gap-1 text-xs">
              <a className="link inline-flex items-center gap-1" href="https://www.who.int/news/item/01-07-2003-failure-to-take-prescribed-medicine-for-chronic-diseases-is-a-massive-world-wide-problem" target="_blank" rel="noreferrer">WHO press release (2003) <ExternalLink className="h-3 w-3" /></a>
              <a className="link inline-flex items-center gap-1" href="https://pmc.ncbi.nlm.nih.gov/articles/PMC3525884" target="_blank" rel="noreferrer">Critique of the 50% figure (2012) <ExternalLink className="h-3 w-3" /></a>
            </div>
          </div>
        </div>
        <div className="card mt-5 bg-gradient-to-r from-primary-soft to-surface p-5">
          <h3 className="flex items-center gap-2 font-bold"><Cloud className="h-4 w-4 text-primary" />Why this needs the cloud</h3>
          <div className="mt-3 grid gap-3 text-sm text-ink-2 sm:grid-cols-2 lg:grid-cols-4">
            <p><b className="text-ink">Shared source of truth.</b> Patient, doctors and caregivers are in different places; the record can't live on one phone.</p>
            <p><b className="text-ink">Always-on scheduling.</b> Reminders and follow-ups must fire on time even when the app is closed.</p>
            <p><b className="text-ink">Real-time hand-offs.</b> A doctor's change must reach the patient's schedule and caregiver within seconds.</p>
            <p><b className="text-ink">Managed security.</b> Encryption keys, audit trails, private storage and identity as managed services, not hand-built.</p>
          </div>
        </div>
      </Section>

      {/* 2 ------------------------------------------------------------------ */}
      <Section id="aws" icon={<Cloud className="h-5 w-5" />} title="2. AWS service selection"
        lead="The MVP runs on 12 services, each with a job the product can't do without. Everything else is added only when a named trigger is reached — nothing is there for decoration.">
        <h3 className="mb-3 font-bold">MVP (Phase 1) — deployed by our CDK stack</h3>
        <Table head={["Service", "Its single job in IMPULSE", "Why this one (and not…)"]} rows={[
          ["Amazon Cognito", "Sign-up, email verification, MFA, password recovery", "Managed identity with MFA; we don't store patient passwords in our own DB"],
          ["API Gateway (HTTP API)", "One HTTPS entry point with throttling", "Cheaper and simpler than REST API; built-in rate limits"],
          ["AWS Lambda", "Runs the FastAPI backend, the 1-minute reminder tick and workflow steps", "Pay per request; no idle servers for a pilot"],
          ["Amazon RDS (PostgreSQL)", "Source of truth: users, consent, prescriptions + versions, appointments", "Relational integrity + transactions (double-booking, versioning) — not DynamoDB"],
          ["Amazon S3", "Private storage for uploaded prescriptions and reports", "Files don't belong in database rows; 5-minute signed download links"],
          ["AWS KMS", "One customer-managed key encrypting S3, RDS, DynamoDB, logs", "Central key control + rotation + audit of key use"],
          ["Amazon DynamoDB", "Idempotency records + dose-event mirror", "Conditional writes make retried reminders/responses never double-count"],
          ["Amazon EventBridge", "1-minute schedule + domain events (prescription changed, permission revoked)", "Decouples features; event archive for replay"],
          ["AWS Step Functions", "Retries/timeouts for the medication-safety follow-up", "Visible, retryable workflow instead of hidden try/except"],
          ["Amazon SES + SNS", "Email reminders (generic text) / operations alerts", "Cheap, managed delivery; SNS fans alerts to on-call"],
          ["AWS CloudTrail", "Audit of every AWS API call and document access", "Required evidence alongside our app-level audit log"],
          ["Amazon CloudFront", "Serves the React app and proxies /api on one domain", "Same-origin cookies (no tokens in the browser), HTTPS, caching"],
        ]} />
        <h3 className="mb-3 mt-8 font-bold">Added later — only when the trigger happens</h3>
        <Table head={["Service", "Job", "Trigger to add it"]} rows={[
          ["Amazon Textract", "Read text from prescription photos/PDFs", "Manual transcription becomes the bottleneck (>50 uploads/day)"],
          ["Comprehend Medical", "Find medicine names/doses in that text (still unverified)", "Same as Textract; legal sign-off for cross-region processing"],
          ["Amazon Bedrock", "Plain-language wording of a doctor's brief — never clinical decisions", "Doctors ask for narrative summaries"],
          ["AWS AppSync (Events)", "Push live updates to browsers", "Moving from polling to live updates in AWS (Lambda can't hold long connections)"],
          ["Amazon HealthLake", "FHIR copy of records for hospital interoperability", "First hospital integration"],
          ["End User Messaging (SMS)", "SMS reminders for patients without smartphones", "Pilot users request SMS (it's the largest variable cost)"],
          ["OpenSearch / Location Service", "Directory search / 'near me'", "Directory exceeds a few thousand verified entries"],
          ["Timestream for InfluxDB", "Long-term adherence analytics", "Reporting needs exceed what PostgreSQL handles comfortably"],
          ["IAM Identity Center", "Staff/developer access to AWS", "Second engineer joins (from day one in a real team)"],
        ]} />
        <p className="mt-4 text-sm text-ink-3">
          Not used: <b>Amazon Pinpoint</b> (AWS ends support on 30 Oct 2026 → SES + End User Messaging instead) and
          <b> Timestream for LiveAnalytics</b> (closed to new customers → Timestream for InfluxDB).
        </p>
      </Section>

      {/* 3 ------------------------------------------------------------------ */}
      <Section id="architecture" icon={<Network className="h-5 w-5" />} title="3. Architecture & security design"
        lead="End to end: the browser talks to one domain; every request is authenticated and checked against the patient's grants before any data is read; all data is encrypted with our KMS key.">
        <div className="card p-5 sm:p-7" role="img" aria-label="Architecture diagram: users to CloudFront, API Gateway, Lambda, then RDS, S3, DynamoDB, EventBridge and Step Functions, with KMS and CloudTrail across all">
          <div className="mx-auto max-w-3xl">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Box title="Patient" icon={<Smartphone className="h-3.5 w-3.5" />} /><Box title="Doctor" icon={<Monitor className="h-3.5 w-3.5" />} />
              <Box title="Caregiver" icon={<Users className="h-3.5 w-3.5" />} /><Box title="Coordinator" icon={<Users className="h-3.5 w-3.5" />} />
            </div>
            <Down />
            <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
              <Box title="CloudFront" sub="React app + /api on one HTTPS domain" tone="mint" />
              <Box title="Cognito" sub="sign-in · MFA" tone="mint" />
            </div>
            <Down />
            <Box title="API Gateway (HTTP API)" sub="throttling · HTTPS only" tone="mint" />
            <Down />
            <Box title="Lambda — FastAPI" sub="session check → CSRF check → authorize_patient(user, patient, scope) → audit log" tone="primary" />
            <Down />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <Box title="RDS PostgreSQL" sub="source of truth" icon={<Database className="h-3.5 w-3.5" />} />
              <Box title="S3" sub="private documents" />
              <Box title="DynamoDB" sub="idempotency" />
              <Box title="EventBridge" sub="events · 1-min tick" />
              <Box title="Step Functions" sub="safety follow-up" />
            </div>
            <Down />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Box title="Reminder Lambda" sub="every minute" />
              <Box title="SES / SNS" sub="email · ops alerts" />
              <Box title="KMS + CloudTrail" sub="encrypts & audits all of the above" tone="warn" icon={<Lock className="h-3.5 w-3.5" />} />
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <div className="card p-5">
            <h3 className="font-bold">Data flow A — a doctor changes a prescription</h3>
            <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-ink-2">
              <li>Doctor saves an edit → CloudFront → API Gateway → Lambda.</li>
              <li>Lambda checks the session, CSRF token and that this doctor has an active grant for this patient.</li>
              <li>In one RDS transaction: new immutable version (v2), old future doses cancelled, new doses created, audit row written. A stale edit gets 409.</li>
              <li>Safety checks run (duplicate ingredients, documented allergies; drug pairs only from a licensed source).</li>
              <li>After commit: event to EventBridge → Step Functions notifies the prescriber if alerts need review; patient and caregivers are notified.</li>
              <li>The patient's app refetches through the same authorised API and shows v2.</li>
            </ol>
          </div>
          <div className="card p-5">
            <h3 className="font-bold">Data flow B — a dose reminder</h3>
            <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-ink-2">
              <li>EventBridge triggers the reminder Lambda every minute.</li>
              <li>It finds due doses in RDS and sends one reminder each (a unique key prevents duplicates).</li>
              <li>Patient taps "Taken" → stored as an append-only event (idempotent).</li>
              <li>No reply after the follow-up window → status "unconfirmed" (never assumed missed).</li>
              <li>Repeated silence → check-in → caregiver (only if the patient opted in) → coordinator case.</li>
            </ol>
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            [<KeyRound key="k" className="h-4 w-4" />, "No hard-coded keys", "Lambdas use IAM roles (no access keys anywhere). The database password is generated by RDS into Secrets Manager and read at start-up. `.env` is git-ignored; only `.env.example` with blank values is committed."],
            [<Lock key="l" className="h-4 w-4" />, "Least privilege", "Each function is granted only the specific bucket, tables, topic and key it uses. Patients reach only their own record; caregivers only the scopes granted; doctors only patients who authorised them; admins get no clinical access."],
            [<ShieldCheck key="s" className="h-4 w-4" />, "Encryption", "TLS everywhere; KMS key (rotation on) for S3, RDS, DynamoDB, SNS, logs; S3 public access blocked; download links expire in 5 minutes."],
            [<Layers key="a" className="h-4 w-4" />, "Audit & sessions", "HttpOnly session cookie + CSRF token, MFA, lockout, hash-chained tamper-evident audit log, CloudTrail with file validation."],
          ].map(([icon, t, d]) => (
            <div key={t as string} className="card p-4">
              <p className="flex items-center gap-2 font-bold text-ink"><span className="text-primary">{icon}</span>{t}</p>
              <p className="mt-2 text-sm text-ink-2">{d}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* 4 ------------------------------------------------------------------ */}
      <Section id="mvp" icon={<Rocket className="h-5 w-5" />} title="4. Feature plan & scope"
        lead="Prioritised with MoSCoW. The Must list is the MVP from the brief and is already working in this build with demo data; the timeline below is for taking it to a real pilot.">
        <div className="grid gap-5 lg:grid-cols-3">
          {[
            ["Must (MVP)", "ok", ["Current medication profile per patient", "Doctors prescribe / edit (versioned) / discontinue", "Duplicate-ingredient & documented-allergy checks", "Track whether doses were taken (honest statuses)", "Reminders for upcoming & missed doses", "Notify caregiver/doctor on adherence problems", "Full prescription & dosage-change history", "Find nearby pharmacies/hospitals"]],
            ["Should", "info", ["Caregiver invitations with scoped, revocable access", "Appointment booking without double booking", "Prescription upload → patient review → doctor verification", "Source-linked clinical brief for doctors", "Care-coordinator cases & escalation"]],
            ["Could / later", "neutral", ["OCR (Textract) + entity extraction", "Licensed drug–drug interaction source", "SMS reminders", "HealthLake interoperability", "Bedrock plain-language summaries", "Video consultations, mobile push"]],
          ].map(([t, tone, items]) => (
            <div key={t as string} className="card p-5">
              <Badge tone={tone as any}>{t as string}</Badge>
              <ul className="mt-3 space-y-1.5 text-sm text-ink-2">{(items as string[]).map((i) => <li key={i}>• {i}</li>)}</ul>
            </div>
          ))}
        </div>
        <h3 className="mb-3 mt-8 font-bold">Realistic timeline to a pilot (team of 4)</h3>
        <Table head={["Weeks", "Deliverable", "Status"]} rows={[
          ["0", "Working app with demo data, tests, CDK stack that synthesizes", <Badge key="0" tone="ok">Done</Badge>],
          ["1–2", "Deploy Phase 1 to a dev AWS account; run live integration tests; Cognito sign-in", <Badge key="1" tone="warn">Next</Badge>],
          ["3–4", "Usability test with 5 older adults + 2 doctors; fix accessibility issues", <Badge key="2">Planned</Badge>],
          ["5–6", "Clinical & legal review (wording, consent, DPDP); staffed support hours", <Badge key="3">Planned</Badge>],
          ["7–8", "Pilot with ~30 patients; measure response coverage & reported adherence", <Badge key="4">Planned</Badge>],
        ]} />
        <p className="mt-3 text-sm text-ink-3">Out of scope for the MVP: drug-interaction database (needs a licence), medicine stock at pharmacies, emergency dispatch, 24/7 monitoring.</p>
      </Section>

      {/* 5 ------------------------------------------------------------------ */}
      <Section id="scale" icon={<Gauge className="h-5 w-5" />} title="5. Scalability & cost"
        lead="Sized for a pilot first, with a clear list of what fails first and the specific fix for each.">
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="card p-5">
            <h3 className="font-bold">Expected load</h3>
            <Table head={["", "Pilot", "Year 1 target"]} rows={[
              ["Patients", "1,000", "50,000"],
              ["Scheduled doses / day (≈4 each)", "4,000", "200,000"],
              ["Peak API requests / s (morning dose rush)", "~5", "~150"],
              ["Documents uploaded / day", "~50", "~2,500"],
            ]} />
            <p className="mt-2 text-xs text-ink-3">Assumptions, not measurements — the pilot will measure them.</p>
          </div>
          <div className="card p-5">
            <h3 className="font-bold">What breaks first → plan</h3>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-ink-2">
              <li><b className="text-ink">Database connections.</b> Many Lambdas each open a connection to a small RDS → add <b>RDS Proxy</b>, then a larger instance / read replica for reports.</li>
              <li><b className="text-ink">The 1-minute reminder tick.</b> One worker scans all active medicines → shard by patient (SQS fan-out to parallel workers); index on due time already exists.</li>
              <li><b className="text-ink">Live updates.</b> Lambda can't hold long-lived connections → switch to <b>AppSync Events</b> (in the design).</li>
              <li><b className="text-ink">SMS cost</b>, not compute, grows fastest → in-app/email by default, SMS opt-in.</li>
              <li><b className="text-ink">API throttling</b> (50 req/s set deliberately low) → raise limits per stage after load testing.</li>
            </ol>
          </div>
        </div>
        <h3 className="mb-3 mt-8 flex items-center gap-2 font-bold"><Wallet className="h-4 w-4 text-primary" />Rough monthly cost (ap-south-1, USD)</h3>
        <Table head={["Item", "Dev / pilot (1k patients)", "Year 1 (50k patients)"]} rows={[
          ["RDS PostgreSQL (+ storage, backups)", "$15–20 (t4g.micro)", "$150–300 (Multi-AZ, larger + Proxy)"],
          ["VPC endpoints / NAT", "$40–50", "$80–120"],
          ["Lambda + API Gateway", "< $5", "$40–100"],
          ["DynamoDB + S3 + KMS + SNS + EventBridge + Step Functions", "$5–10", "$40–80"],
          ["CloudWatch + CloudTrail", "$5–10", "$30–60"],
          ["SES email", "< $1", "$20–60"],
          [<b key="t">Total (SMS off, optional services off)</b>, <b key="a">≈ $70–95</b>, <b key="b">≈ $360–720</b>],
        ]} />
        <p className="mt-3 text-sm text-ink-3">
          Rough estimates from public on-demand pricing; verify with the AWS Pricing Calculator. HealthLake and
          OpenSearch Serverless each add roughly $175–200+/month even when idle, so they stay off until their trigger.
          A budget alert fires at 80% of the monthly limit.
        </p>
      </Section>

      {/* 6 ------------------------------------------------------------------ */}
      <Section id="innovation" icon={<Lightbulb className="h-5 w-5" />} title="6. Innovation & differentiation"
        lead="Typical reminder apps track one person's own list. IMPULSE coordinates the whole care team around one versioned record — and refuses to fake certainty.">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["Honest adherence", "'Reported taken', 'reported missed' and 'unconfirmed' stay separate; silence is never counted as taken, missed or an emergency."],
            ["Doctor-verified OCR", "Uploaded prescriptions never become reminders until a verified clinician approves the structured record."],
            ["Safety checks that admit limits", "Shows 'interaction checking unavailable' instead of a false 'no interactions' when no licensed source is connected."],
            ["Source-linked clinical brief", "Every line links to its record; missing and conflicting data are listed; any AI wording is labelled unverified."],
            ["Consent-scoped caregivers", "Own accounts, per-permission scopes, expiry and instant revocation, with an access history the patient can read."],
            ["Human escalation, not alarms", "Reminder → follow-up → check-in → opted-in caregiver → coordinator case, using EventBridge + Step Functions."],
          ].map(([t, d]) => (
            <div key={t} className="card p-5"><p className="font-bold">{t}</p><p className="mt-2 text-sm text-ink-2">{d}</p></div>
          ))}
        </div>
      </Section>

      {/* 7 ------------------------------------------------------------------ */}
      <Section id="pitch" icon={<Users className="h-5 w-5" />} title="7. Team understanding & pitch"
        lead="Each member owns one part end to end and answers questions on it. Replace the role names with your team members.">
        <Table head={["Member", "Owns", "Must be able to explain"]} rows={[
          ["Member 1 — Product", "Problem, users, MVP scope, demo", "Who the user is, the WHO evidence and its caveat, the Must list, the pilot plan"],
          ["Member 2 — Backend", "FastAPI, database, reminders, permissions", "Prescription versioning, the reminder tick, how authorize_patient blocks access, double-booking prevention"],
          ["Member 3 — Cloud & security", "AWS services, CDK, security", "Why each service, the data flow, IAM roles/no keys, KMS, cost and what breaks first"],
          ["Member 4 — Frontend & UX", "React portals, accessibility", "Patient/doctor/caregiver journeys, honest statuses, accessibility choices"],
        ]} />
        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <div className="card p-5">
            <h3 className="font-bold">3-minute pitch outline</h3>
            <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-ink-2">
              <li>(30 s) Problem + who it hurts + WHO evidence.</li>
              <li>(60 s) Live demo: doctor edits a prescription → patient sees v2 → caregiver sees the update.</li>
              <li>(45 s) Architecture diagram + the two data flows.</li>
              <li>(30 s) Security: grants checked server-side, no keys, encryption, audit.</li>
              <li>(15 s) Cost ≈ $70–95/month for a pilot; what breaks first and the fix.</li>
            </ol>
          </div>
          <div className="card p-5">
            <h3 className="font-bold">Likely questions — answer from facts, never guess</h3>
            <dl className="mt-3 space-y-2 text-sm">
              {[
                ["Why not just DynamoDB?", "Prescriptions, consent and bookings need transactions and foreign keys; DynamoDB only handles idempotency."],
                ["Is it HIPAA/DPDP compliant?", "We claim no compliance. Controls exist; legal review is a planned step."],
                ["What if the interaction service is down?", "The result says 'failed/unavailable' and is never shown as safe."],
                ["Has it run on AWS?", "The stack synthesizes (106 resources); live deployment is the next milestone. The app runs locally with fallbacks."],
              ].map(([q, a]) => <div key={q}><dt className="font-semibold text-ink">{q}</dt><dd className="text-ink-2">{a}</dd></div>)}
            </dl>
          </div>
        </div>
        <p className="mt-6 flex items-center gap-1.5 text-sm text-ink-3"><ArrowRight className="h-4 w-4" />Full pitch notes: <code>docs/ROUND1_PITCH.md</code> in the repository.</p>
      </Section>
    </div>
  );
}
