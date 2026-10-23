import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
  Activity, ArrowRight, BadgeCheck, Bell, BookOpen, CalendarCheck2, CalendarDays, Check, CheckCircle2, ClipboardList,
  Clock, FileScan, FileText, Fingerprint, HeartHandshake, KeyRound, Lock, Pill, ScanLine, ShieldCheck, Sparkles,
  Stethoscope, UserCheck, Users, Workflow,
} from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/primitives";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.6, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] } }),
};

function Reveal({ children, i = 0, className }: { children: ReactNode; i?: number; className?: string }) {
  return (
    <motion.div variants={fadeUp} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }} className={className}>
      {children}
    </motion.div>
  );
}

export default function Landing() {
  return (
    <>
      <Hero />
      <Problem />
      <Features />
      <HowItWorks />
      <ForPatients />
      <ForDoctors />
      <Trust />
      <CTA />
    </>
  );
}

/* ---------------- Hero ---------------- */
function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="grid-bg pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_70%)]" />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[520px] w-[900px] -translate-x-1/2 rounded-full bg-mint/50 blur-3xl dark:bg-primary/20" />
      <div className="container-page relative grid items-center gap-14 pb-20 pt-12 lg:grid-cols-[1.05fr_1fr] lg:pt-20">
        <div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-xs font-semibold text-ink-2 shadow-card backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" /> Medication coordination for patients, doctors & caregivers
          </motion.div>
          <motion.h1 initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05, duration: 0.6 }}
            className="mt-6 text-[42px] font-extrabold leading-[1.05] text-ink sm:text-[56px] lg:text-[64px]">
            Better medication management.{" "}
            <span className="bg-gradient-to-r from-primary via-[#1f8a83] to-[#3fae9a] bg-clip-text text-transparent">More connected care.</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12, duration: 0.6 }}
            className="mt-6 max-w-xl text-lg leading-relaxed text-ink-2">
            Your health information, medication schedules, care team, and appointments — together in one secure healthcare platform.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.6 }}
            className="mt-8 flex flex-wrap gap-3">
            <Link to="/register"><Button size="lg" icon={<ArrowRight className="h-5 w-5" />} className="flex-row-reverse">Get Started</Button></Link>
            <a href="#features"><Button size="lg" variant="outline">Explore IMPULSE</Button></a>
          </motion.div>
          <motion.ul initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }} className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-3">
            {["Patient-controlled sharing", "Versioned prescriptions", "Every access logged"].map((t) => (
              <li key={t} className="flex items-center gap-1.5"><Check className="h-4 w-4 text-ok" />{t}</li>
            ))}
          </motion.ul>
        </div>
        <DashboardPreview />
      </div>
    </section>
  );
}

const trend = [62, 70, 68, 80, 77, 86, 91].map((v, i) => ({ i, v }));

function Float({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div initial={{ opacity: 0, y: 20, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.3 + delay, duration: 0.7, ease: [0.22, 1, 0.36, 1] }} className={className}>
      <motion.div animate={reduce ? {} : { y: [0, -6, 0] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay }}>
        {children}
      </motion.div>
    </motion.div>
  );
}

function DashboardPreview() {
  return (
    <div className="relative mx-auto w-full max-w-[560px]" aria-label="Example dashboard with synthetic data" role="img">
      <div className="absolute -inset-6 rounded-[36px] bg-gradient-to-br from-primary/15 via-transparent to-mint/40 blur-2xl" />
      <Float className="relative">
        <div className="card overflow-hidden p-5 shadow-lift">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-ink-3">Tuesday · Synthetic example</p>
              <p className="font-display text-lg font-bold">Good morning, Asha</p>
            </div>
            <span className="rounded-full bg-ok-soft px-2.5 py-1 text-xs font-semibold text-ok">3 of 4 reported today</span>
          </div>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-ink-3">Today's medications</p>
          <div className="mt-2 space-y-2">
            {[
              { n: "Metformin 500 mg", t: "8:00 AM", s: "Reported taken", c: "text-ok bg-ok-soft", i: <CheckCircle2 className="h-3.5 w-3.5" /> },
              { n: "Amlodipine 5 mg", t: "9:00 AM", s: "Reported taken", c: "text-ok bg-ok-soft", i: <CheckCircle2 className="h-3.5 w-3.5" /> },
              { n: "Atorvastatin 10 mg", t: "9:00 PM", s: "Upcoming", c: "text-ink-2 bg-surface-2", i: <Clock className="h-3.5 w-3.5" /> },
            ].map((m, k) => (
              <motion.div key={m.n} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.6 + k * 0.12 }}
                className="flex items-center gap-3 rounded-xl border border-line p-3">
                <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary-soft text-primary"><Pill className="h-4 w-4" /></span>
                <div className="flex-1">
                  <p className="text-sm font-semibold">{m.n}</p>
                  <p className="text-xs text-ink-3">{m.t} · with food</p>
                </div>
                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${m.c}`}>{m.i}{m.s}</span>
              </motion.div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-surface-2 p-3">
              <p className="text-xs font-medium text-ink-3">Reported this week</p>
              <p className="font-display text-2xl font-extrabold">91%</p>
              <div className="h-10"><ResponsiveContainer><AreaChart data={trend}><Area dataKey="v" stroke="rgb(var(--primary))" fill="rgb(var(--primary) / 0.15)" strokeWidth={2} isAnimationActive /></AreaChart></ResponsiveContainer></div>
            </div>
            <div className="rounded-xl bg-surface-2 p-3">
              <p className="text-xs font-medium text-ink-3">Next appointment</p>
              <p className="mt-1 text-sm font-semibold">Dr. Kiran (example)</p>
              <p className="text-xs text-ink-3">Endocrinology · Fri 10:40</p>
              <p className="mt-2 inline-flex items-center gap-1 rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-semibold text-primary"><CalendarCheck2 className="h-3 w-3" />Confirmed</p>
            </div>
          </div>
        </div>
      </Float>
      <Float className="absolute -bottom-8 -left-10 hidden w-56 sm:block" delay={0.4}>
        <div className="card flex items-center gap-3 p-3 shadow-lift">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-[#db2777] text-xs font-bold text-white">MR</span>
          <div><p className="text-xs font-semibold">Care team</p><p className="text-[11px] text-ink-3">Daughter · can view schedule</p></div>
        </div>
      </Float>
      <Float className="absolute -right-6 -top-6 hidden w-60 sm:block" delay={0.8}>
        <div className="card p-3 shadow-lift">
          <p className="flex items-center gap-1.5 text-xs font-semibold"><Bell className="h-3.5 w-3.5 text-primary" /> Notification</p>
          <p className="mt-1 text-[12px] text-ink-2">Dr. Kiran updated your Metformin instructions.</p>
        </div>
      </Float>
    </div>
  );
}

/* ---------------- Problem ---------------- */
function Problem() {
  const cards = [
    { icon: <Pill className="h-5 w-5" />, who: "For patients", line: "Understand and manage your medications.",
      body: "Prescriptions from several doctors, one clear schedule — with plain-language guidance from verified sources." },
    { icon: <Stethoscope className="h-5 w-5" />, who: "For doctors", line: "Spend less time navigating records.",
      body: "A source-linked clinical brief, versioned prescriptions and adherence you can actually interpret." },
    { icon: <HeartHandshake className="h-5 w-5" />, who: "For caregivers", line: "Support the people who depend on you.",
      body: "Your own account, only the access the patient grants — revocable at any time." },
  ];
  return (
    <section className="container-page py-20">
      <Reveal className="mx-auto max-w-2xl text-center">
        <p className="text-sm font-semibold uppercase tracking-wider text-primary">The problem</p>
        <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">Healthcare shouldn't feel disconnected.</h2>
        <p className="mt-4 text-ink-2">Schedules, dosage changes, allergies and histories scattered across hospitals and pharmacies lead to duplicated medicines, missed doses and avoidable risk.</p>
      </Reveal>
      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {cards.map((c, i) => (
          <Reveal key={c.who} i={i}>
            <div className="card group h-full p-6 transition-all hover:-translate-y-1 hover:shadow-lift">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary-soft text-primary transition-colors group-hover:bg-primary group-hover:text-primary-ink">{c.icon}</span>
              <p className="mt-5 text-xs font-bold uppercase tracking-wider text-ink-3">{c.who}</p>
              <h3 className="mt-1 text-xl font-bold">{c.line}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-2">{c.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

/* ---------------- Features bento ---------------- */
function Features() {
  const items = [
    { t: "Medication management", d: "Current, upcoming, completed and discontinued — with every version kept.", i: <Pill />, span: "md:col-span-2 md:row-span-2", big: true },
    { t: "Medical records", d: "A chronological timeline with clear provenance.", i: <FileText /> },
    { t: "Medication reminders", d: "Time-zone aware, no duplicates, snooze or 'I can't take it'.", i: <Bell /> },
    { t: "Caregiver access", d: "Invite, approve, scope, expire, revoke.", i: <Users /> },
    { t: "Doctor dashboard", d: "Priorities first: follow-ups, verifications, adherence.", i: <Stethoscope />, span: "md:col-span-2" },
    { t: "Appointment booking", d: "Real slots, short holds, no double booking.", i: <CalendarDays /> },
    { t: "Prescription scanning", d: "Upload → review → doctor verification. Never auto-activated.", i: <ScanLine /> },
    { t: "Drug interaction checking", d: "Licensed knowledge sources only. 'Unavailable' is shown honestly.", i: <ShieldCheck /> },
    { t: "Care coordination", d: "Configurable follow-up and human support workflows.", i: <Workflow />, span: "md:col-span-2" },
  ];
  return (
    <section id="features" className="scroll-mt-20 bg-surface/60 py-20">
      <div className="container-page">
        <Reveal className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-wider text-primary">Features</p>
          <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">Everything the care team needs, in one place.</h2>
        </Reveal>
        <div className="mt-10 grid auto-rows-[minmax(160px,auto)] gap-4 md:grid-cols-4">
          {items.map((f, i) => (
            <Reveal key={f.t} i={i % 4} className={f.span}>
              <div className={`card group relative h-full overflow-hidden p-6 transition-all hover:-translate-y-0.5 hover:shadow-lift ${f.big ? "bg-gradient-to-br from-surface to-primary-soft/60" : ""}`}>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-soft text-primary [&>svg]:h-5 [&>svg]:w-5">{f.i}</span>
                <h3 className={`mt-4 font-bold ${f.big ? "text-2xl" : "text-lg"}`}>{f.t}</h3>
                <p className="mt-1.5 text-sm text-ink-2">{f.d}</p>
                {f.big && (
                  <div className="mt-6 space-y-2">
                    {[["Metformin 500 mg", "v2 · food timing clarified"], ["Amlodipine 5 mg", "Active · Cardiology"], ["Ibuprofen 400 mg", "Discontinued · history kept"]].map(([a, b]) => (
                      <div key={a} className="flex items-center justify-between rounded-xl border border-line bg-surface/80 px-3 py-2.5 text-sm">
                        <span className="font-semibold">{a}</span><span className="text-xs text-ink-3">{b}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------------- How it works ---------------- */
function HowItWorks() {
  const steps = [
    { t: "Create an account.", d: "Verify your email and secure it with an authenticator app.", i: <Fingerprint /> },
    { t: "Connect with your healthcare provider.", d: "Book a visit or grant a doctor access — you decide who sees what.", i: <UserCheck /> },
    { t: "Manage prescriptions and medical records.", d: "Upload documents, track doses, keep a full history.", i: <ClipboardList /> },
    { t: "Stay informed and connected.", d: "Reminders, doctor instructions and caregiver updates.", i: <Activity /> },
  ];
  return (
    <section id="how-it-works" className="container-page scroll-mt-20 py-20">
      <Reveal className="mx-auto max-w-2xl text-center">
        <p className="text-sm font-semibold uppercase tracking-wider text-primary">How it works</p>
        <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">Up and running in four steps.</h2>
      </Reveal>
      <ol className="relative mt-12 grid gap-6 md:grid-cols-4">
        <div className="absolute left-0 right-0 top-6 hidden h-px bg-gradient-to-r from-transparent via-line to-transparent md:block" />
        {steps.map((s, i) => (
          <Reveal key={s.t} i={i}>
            <li className="relative">
              <span className="relative z-10 grid h-12 w-12 place-items-center rounded-2xl bg-primary text-primary-ink shadow-glow [&>svg]:h-5 [&>svg]:w-5">{s.i}</span>
              <p className="mt-4 text-xs font-bold text-ink-3">STEP {i + 1}</p>
              <h3 className="mt-1 text-lg font-bold">{s.t}</h3>
              <p className="mt-1 text-sm text-ink-2">{s.d}</p>
            </li>
          </Reveal>
        ))}
      </ol>
    </section>
  );
}

/* ---------------- Patients ---------------- */
function ForPatients() {
  return (
    <section id="patients" className="container-page scroll-mt-20 py-16">
      <div className="grid items-center gap-12 lg:grid-cols-2">
        <Reveal>
          <p className="text-sm font-semibold uppercase tracking-wider text-primary">For patients</p>
          <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">Clarity for every dose.</h2>
          <ul className="mt-6 space-y-4">
            {[
              ["Honest status", "'Reported taken', 'Unconfirmed' and 'Missed' are kept separate — no guesswork dressed up as data."],
              ["Plain-language detail", "What it is, when and how to take it — from your prescription, never invented."],
              ["You control sharing", "Invite a caregiver, choose exactly what they see, revoke any time."],
            ].map(([a, b]) => (
              <li key={a} className="flex gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-ok" />
                <span><b className="text-ink">{a}.</b> <span className="text-ink-2">{b}</span></span>
              </li>
            ))}
          </ul>
        </Reveal>
        <Reveal i={1}>
          <div className="card p-5 shadow-lift">
            <div className="flex items-center justify-between">
              <p className="font-display font-bold">Reminder</p><span className="text-xs text-ink-3">8:00 PM · example</span>
            </div>
            <div className="mt-3 rounded-2xl bg-primary-soft p-4">
              <p className="text-lg font-bold">Time for Metformin 500 mg</p>
              <p className="text-sm text-ink-2">1 tablet · oral · with dinner</p>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Button tabIndex={-1} aria-hidden>Mark as taken</Button>
              <Button tabIndex={-1} aria-hidden variant="outline">Snooze 15 min</Button>
              <Button tabIndex={-1} aria-hidden variant="outline">I can't take it</Button>
              <Button tabIndex={-1} aria-hidden variant="ghost">View instructions</Button>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ---------------- Doctors ---------------- */
function ForDoctors() {
  return (
    <section id="doctors" className="scroll-mt-20 py-20">
      <div className="container-page">
        <div className="relative overflow-hidden rounded-[32px] bg-[#0b3d40] px-6 py-14 text-white sm:px-12 dark:bg-surface-2">
          <div className="pointer-events-none absolute -right-20 -top-20 h-80 w-80 rounded-full bg-[#3fae9a]/30 blur-3xl" />
          <div className="relative grid items-center gap-12 lg:grid-cols-[1fr_1.15fr]">
            <Reveal>
              <p className="text-sm font-semibold uppercase tracking-wider text-[#9be6cf]">For doctors</p>
              <h2 className="mt-3 text-3xl font-extrabold text-white sm:text-4xl">Less time searching. More time caring.</h2>
              <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
                {[["Patient summaries", <BookOpen key="a" className="h-4 w-4" />], ["Prescription management", <Pill key="b" className="h-4 w-4" />],
                  ["Follow-up tasks", <ClipboardList key="c" className="h-4 w-4" />], ["Adherence insights", <Activity key="d" className="h-4 w-4" />]].map(([t, i]) => (
                  <div key={t as string} className="flex items-center gap-2 rounded-xl bg-white/10 px-3 py-2.5">{i}{t}</div>
                ))}
              </div>
            </Reveal>
            <Reveal i={1}>
              <div className="rounded-2xl bg-white p-5 text-[#1f2328] shadow-2xl dark:bg-surface dark:text-ink">
                <div className="flex items-center justify-between">
                  <p className="font-display font-bold">Clinical brief · example</p>
                  <span className="rounded-full bg-[#e2ecfb] px-2 py-0.5 text-[11px] font-semibold text-[#1e5aaa]">Source-linked</span>
                </div>
                <div className="mt-3 space-y-2 text-sm">
                  {[["Conditions", "Type 2 diabetes · Hypertension", "2 sources"], ["Current medicines", "3 active · 1 changed in 90 days", "4 sources"],
                    ["Adherence (30d)", "48 reported · 6 unconfirmed", "event log"], ["Missing", "No lab report in 6 months", "flagged"]].map(([a, b, c]) => (
                    <div key={a} className="flex items-center justify-between rounded-xl border border-[#e5e1d9] px-3 py-2 dark:border-line">
                      <span><b>{a}</b> <span className="text-[#4a5058] dark:text-ink-2">— {b}</span></span>
                      <span className="text-[11px] text-[#6b727a]">{c}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-[11px] text-[#6b727a]">Generated summaries are clearly separated from verified clinical facts.</p>
              </div>
            </Reveal>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------------- Trust ---------------- */
function Trust() {
  const items = [
    { t: "Access control", d: "Server-side, per-patient authorisation on every request — not just a hidden button.", i: <KeyRound /> },
    { t: "Privacy-focused design", d: "Minimum necessary data; generic text on SMS and email; no health data in browser storage.", i: <Lock /> },
    { t: "Secure information handling", d: "Private document storage, short-lived download links, tamper-evident audit log.", i: <FileScan /> },
    { t: "Account protection", d: "Strong passwords, authenticator-app MFA, session management and lockout.", i: <Fingerprint /> },
    { t: "Patient permissions", d: "Grant, scope, expire and revoke — with a full access history you can read.", i: <BadgeCheck /> },
  ];
  return (
    <section className="container-page py-16">
      <Reveal className="max-w-2xl">
        <p className="text-sm font-semibold uppercase tracking-wider text-primary">Trust</p>
        <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">Built around consent and accountability.</h2>
        <p className="mt-3 text-ink-2">We describe what the software does. We don't claim certifications, partnerships or regulatory approvals we haven't earned.</p>
      </Reveal>
      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {items.map((it, i) => (
          <Reveal key={it.t} i={i}>
            <div className="card h-full p-5">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-ok-soft text-ok [&>svg]:h-5 [&>svg]:w-5">{it.i}</span>
              <h3 className="mt-4 font-bold">{it.t}</h3>
              <p className="mt-1 text-sm text-ink-2">{it.d}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="container-page pt-10">
      <Reveal>
        <div className="card flex flex-col items-start justify-between gap-6 bg-gradient-to-r from-primary-soft to-mint/60 p-8 sm:flex-row sm:items-center sm:p-10">
          <div>
            <h2 className="text-2xl font-extrabold sm:text-3xl">See IMPULSE with demo data.</h2>
            <p className="mt-1 text-ink-2">Explore the patient, doctor, caregiver and coordinator portals — no real information needed.</p>
          </div>
          <div className="flex gap-3">
            <Link to="/login"><Button size="lg">Try the demo</Button></Link>
            <Link to="/register"><Button size="lg" variant="outline">Create account</Button></Link>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
