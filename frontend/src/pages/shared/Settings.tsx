import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { KeyRound, Laptop, LogOut, Monitor, Moon, ShieldCheck, Sun, Trash2 } from "lucide-react";
import clsx from "clsx";
import { Badge, Button, Field, Input, Select, Toggle } from "@/components/ui/primitives";
import { ConfirmDialog, Modal, Notice, useToast } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LANGUAGES, useLanguage } from "@/lib/i18n";
import { fmtDate, fmtDateTime, titleCase } from "@/lib/format";
import { password as passwordRule } from "@/lib/schemas";
import type { Preferences } from "@/lib/types";

type Section = "account" | "security" | "language" | "appearance" | "region" | "notifications" | "privacy";
const SECTIONS: { id: Section; label: string }[] = [
  { id: "account", label: "Account" }, { id: "security", label: "Security" }, { id: "language", label: "Language" },
  { id: "appearance", label: "Appearance" }, { id: "region", label: "Region" }, { id: "notifications", label: "Notifications" }, { id: "privacy", label: "Privacy & data" },
];

function usePrefs() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (p: Partial<Preferences>) => api.patch("/api/account/preferences", p),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["session"] }); toast("ok", "Saved."); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
}

function Panel({ title, desc, children }: { title: string; desc?: string; children: ReactNode }) {
  return <section className="card p-5 sm:p-6"><h2 className="text-lg font-bold">{title}</h2>{desc && <p className="mt-1 text-sm text-ink-3">{desc}</p>}<div className="mt-5 space-y-4">{children}</div></section>;
}

export default function Settings() {
  const [section, setSection] = useState<Section>("account");
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <nav aria-label="Settings sections" className="flex gap-1 overflow-x-auto lg:flex-col">
          {SECTIONS.map((s) => (
            <button key={s.id} onClick={() => setSection(s.id)} aria-current={section === s.id ? "page" : undefined}
              className={clsx("whitespace-nowrap rounded-xl px-3 py-2.5 text-left text-sm font-semibold", section === s.id ? "bg-primary-soft text-primary" : "text-ink-2 hover:bg-surface-2")}>{s.label}</button>
          ))}
        </nav>
        <div>
          {section === "account" && <Account />}
          {section === "security" && <Security />}
          {section === "language" && <Language />}
          {section === "appearance" && <Appearance />}
          {section === "region" && <Region />}
          {section === "notifications" && <NotificationPrefs />}
          {section === "privacy" && <Privacy />}
        </div>
      </div>
    </>
  );
}

function Account() {
  const { user, logout } = useAuth();
  const isDoctor = user!.role === "doctor";
  const [f, setF] = useState({ full_name: user!.full_name, preferred_name: user!.preferred_name ?? "", phone: user!.phone ?? "", avatar_color: user!.avatar_color });
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const [close, setClose] = useState(false);
  const [confirm, setConfirm] = useState("");
  const m = useMutation({
    mutationFn: () => {
      if (f.phone && !/^\d{10}$/.test(f.phone)) throw new Error("Enter a 10-digit mobile number");
      const { preferred_name, ...rest } = f;
      return api.patch("/api/account/profile", isDoctor ? rest : { ...rest, preferred_name });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["session"] }); toast("ok", "Profile updated."); },
    onError: (e) => toast("danger", errorMessage(e)),
  });
  const closeM = useMutation({ mutationFn: () => api.post("/api/account/close", { confirm: confirm.trim().toUpperCase() }),
    onSuccess: async (r) => { toast("ok", r.retention_note); await logout(); nav("/"); }, onError: (e) => toast("danger", errorMessage(e)) });
  return (
    <div className="space-y-6">
      <Panel title="Account" desc={`Signed in as ${user!.email}${user!.mrn ? ` · Patient ID ${user!.mrn}` : ""}`}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name">{(p) => <Input {...p} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />}</Field>
          {!isDoctor && <Field label="Preferred name">{(p) => <Input {...p} value={f.preferred_name} onChange={(e) => setF({ ...f, preferred_name: e.target.value })} />}</Field>}
          <Field label="Mobile number" hint="10 digits">{(p) => <Input {...p} type="tel" inputMode="numeric" maxLength={10} value={f.phone}
            onChange={(e) => setF({ ...f, phone: e.target.value.replace(/\D/g, "").slice(0, 10) })} />}</Field>
          <Field label="Profile colour">{(p) => <div className="flex gap-2">{["#0f766e", "#0e7490", "#7c3aed", "#db2777", "#c2410c", "#2563eb"].map((c) => (
            <button key={c} {...(c === f.avatar_color ? { "aria-pressed": true } : {})} aria-label={`Colour ${c}`} onClick={() => setF({ ...f, avatar_color: c })}
              className={clsx("h-9 w-9 rounded-full ring-offset-2 ring-offset-surface", c === f.avatar_color && "ring-2 ring-ink")} style={{ background: c }} />))}<span className="sr-only" id={p.id} /></div>}</Field>
        </div>
        <p className="text-xs text-ink-3">To change your email, contact support (email changes require re-verification).</p>
        <Button onClick={() => m.mutate()} loading={m.isPending}>Save profile</Button>
      </Panel>
      <Panel title="Close account">
        <p className="text-sm text-ink-2">You'll be signed out everywhere and your Access ID stops working. Medical records are kept only for the period the law requires.</p>
        <Button variant="danger" onClick={() => setClose(true)} icon={<Trash2 className="h-4 w-4" />}>Close my account</Button>
      </Panel>
      <ConfirmDialog open={close} onClose={() => setClose(false)} onConfirm={() => { if (confirm.trim().toUpperCase() === "CLOSE") closeM.mutate(); else toast("danger", "Type CLOSE to confirm"); }} loading={closeM.isPending} tone="danger" title="Close your account?" confirmLabel="Close account"
        body={<div className="space-y-3"><p>Type <b>CLOSE</b> to confirm.</p><Input aria-label="Type CLOSE" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></div>} />
    </div>
  );
}

function Security() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api.get("/api/account/sessions") });
  const history = useQuery({ queryKey: ["login-history"], queryFn: () => api.get("/api/account/login-history") });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [mfa, setMfa] = useState<any>(null);
  const [code, setCode] = useState("");
  const [backup, setBackup] = useState<string[] | null>(null);
  const [disablePw, setDisablePw] = useState("");
  const changePw = useMutation({
    mutationFn: () => { const c = passwordRule.safeParse(pw.new_password); if (!c.success) throw new Error(c.error.issues[0].message); return api.post("/api/account/password", pw); },
    onSuccess: () => { toast("ok", "Password changed. Other devices were signed out."); setPw({ current_password: "", new_password: "" }); }, onError: (e) => toast("danger", errorMessage(e)) });
  const setup = useMutation({ mutationFn: () => api.post("/api/account/mfa/setup"), onSuccess: setMfa, onError: (e) => toast("danger", errorMessage(e)) });
  const enable = useMutation({ mutationFn: () => api.post("/api/account/mfa/enable", { code }), onSuccess: (r) => { setBackup(r.backup_codes); setMfa(null); qc.invalidateQueries({ queryKey: ["session"] }); }, onError: (e) => toast("danger", errorMessage(e)) });
  const disable = useMutation({ mutationFn: () => api.post("/api/account/mfa/disable", { password: disablePw }), onSuccess: () => { toast("ok", "MFA turned off."); qc.invalidateQueries({ queryKey: ["session"] }); }, onError: (e) => toast("danger", errorMessage(e)) });
  const revoke = useMutation({ mutationFn: (id: string) => api.del(`/api/account/sessions/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }) });
  const all = useMutation({ mutationFn: () => api.post("/api/account/sessions/revoke-all"), onSuccess: async () => { await logout(); nav("/login"); } });
  return (
    <div className="space-y-6">
      <Panel title="Two-step verification (MFA)" desc="Optional: you sign in with just your password unless you turn this on. It adds a code from an authenticator app.">
        {user!.mfa_enabled ? (
          <div className="space-y-3">
            <Badge tone="ok" icon={<ShieldCheck className="h-3 w-3" />}>On</Badge>
            <div className="flex flex-wrap gap-2"><Input type="password" aria-label="Password to disable MFA" placeholder="Password" className="max-w-xs" value={disablePw} onChange={(e) => setDisablePw(e.target.value)} />
              <Button variant="outline" onClick={() => disable.mutate()} disabled={!disablePw}>Turn off</Button></div>
          </div>
        ) : mfa ? (
          <div className="grid gap-5 sm:grid-cols-[auto_1fr]">
            <div className="rounded-2xl bg-white p-3"><QRCodeSVG value={mfa.otpauth_uri} size={160} /></div>
            <div className="space-y-3">
              <p className="text-sm text-ink-2">Scan with Google Authenticator, Microsoft Authenticator or similar, or enter this key:</p>
              <code className="block break-all rounded-lg bg-surface-2 p-2 text-sm">{mfa.secret}</code>
              <Field label="6-digit code">{(p) => <Input {...p} inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} />}</Field>
              <Button onClick={() => enable.mutate()} loading={enable.isPending} disabled={code.length !== 6}>Turn on</Button>
            </div>
          </div>
        ) : <Button onClick={() => setup.mutate()} loading={setup.isPending} icon={<KeyRound className="h-4 w-4" />}>Set up authenticator app</Button>}
        <p className="text-xs text-ink-3">Passkeys aren't supported yet.</p>
      </Panel>
      <Panel title="Password">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Current password">{(p) => <Input {...p} type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />}</Field>
          <Field label="New password" hint="10+ characters, mixed types">{(p) => <Input {...p} type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />}</Field>
        </div>
        <Button onClick={() => changePw.mutate()} loading={changePw.isPending} disabled={!pw.current_password || !pw.new_password}>Change password</Button>
      </Panel>
      <Panel title="Active sessions & trusted devices">
        <ul className="divide-y divide-line">{sessions.data?.map((s: any) => (
          <li key={s.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
            <Laptop className="h-5 w-5 text-ink-3" />
            <div className="min-w-0 flex-1"><p className="truncate font-medium">{s.user_agent || "Unknown device"}</p><p className="text-xs text-ink-3">{s.ip_address} · last active {s.last_seen_at ? fmtDateTime(s.last_seen_at) : "—"}</p></div>
            {s.current ? <Badge tone="ok">This device</Badge> : <Button size="sm" variant="ghost" onClick={() => revoke.mutate(s.id)}>Sign out</Button>}
            {s.trusted_device && <Badge>Trusted</Badge>}
          </li>))}</ul>
        <Button variant="outline" onClick={() => all.mutate()} icon={<LogOut className="h-4 w-4" />}>Sign out from all devices</Button>
      </Panel>
      <Panel title="Login history">
        <ul className="max-h-72 divide-y divide-line overflow-y-auto text-sm">{history.data?.map((h: any, i: number) => (
          <li key={i} className="flex justify-between gap-2 py-2"><span className={h.kind.includes("fail") || h.kind.includes("lock") ? "text-danger" : ""}>{titleCase(h.kind)}</span><span className="text-xs text-ink-3">{fmtDateTime(h.at)} · {h.ip_address}</span></li>))}</ul>
      </Panel>
      <Modal open={!!backup} onClose={() => setBackup(null)} title="Save your backup codes" footer={<Button onClick={() => setBackup(null)}>I've saved them</Button>}>
        <Notice tone="warn">Each code works once if you lose your phone. They won't be shown again.</Notice>
        <div className="mt-3 grid grid-cols-2 gap-2 font-mono">{backup?.map((c) => <span key={c} className="rounded-lg bg-surface-2 p-2 text-center">{c}</span>)}</div>
      </Modal>
    </div>
  );
}

function Language() {
  const { lang, setLang } = useLanguage();
  const toast = useToast();
  return (
    <Panel title="Language" desc="Changes the language across the whole website. Doctors' clinical instructions are always shown exactly as written — they are never machine-translated.">
      <div className="grid gap-2 sm:grid-cols-2">
        {LANGUAGES.map((l) => (
          <button key={l.code} onClick={() => { setLang(l.code); toast("ok", "Saved."); }} aria-pressed={lang === l.code} data-no-translate
            className={clsx("rounded-xl border p-3 text-left font-semibold", lang === l.code ? "border-primary bg-primary-soft" : "border-line hover:bg-surface-2")}>{l.label}</button>
        ))}
      </div>
      {lang !== "en" && <Notice tone="info">Translations are a preview awaiting professional review. Any text not yet translated appears in English.</Notice>}
    </Panel>
  );
}

function Appearance() {
  const { user } = useAuth();
  const p = user!.preferences;
  const m = usePrefs();
  const opt = (v: "light" | "dark" | "system", icon: ReactNode, label: string) => (
    <button onClick={() => m.mutate({ theme: v })} aria-pressed={(p.theme ?? "system") === v}
      className={clsx("flex flex-1 flex-col items-center gap-2 rounded-xl border p-4 font-semibold", (p.theme ?? "system") === v ? "border-primary bg-primary-soft" : "border-line hover:bg-surface-2")}>{icon}{label}</button>
  );
  return (
    <Panel title="Appearance">
      <div className="flex gap-3">{opt("light", <Sun className="h-5 w-5" />, "Light")}{opt("dark", <Moon className="h-5 w-5" />, "Dark")}{opt("system", <Monitor className="h-5 w-5" />, "System")}</div>
      <Field label="Text size">{(f) => <Select {...f} value={p.text_size ?? "normal"} onChange={(e) => m.mutate({ text_size: e.target.value as any })}><option value="normal">Standard</option><option value="large">Large</option><option value="x-large">Extra large</option></Select>}</Field>
    </Panel>
  );
}

function Region() {
  const { user } = useAuth();
  const p = user!.preferences;
  const ref = useQuery({ queryKey: ["reference"], queryFn: () => api.get("/api/reference"), staleTime: Infinity });
  const [state, setState] = useState(p.state ?? "");
  const [touched, setTouched] = useState(false);
  const m = usePrefs();
  const missing = !state;
  return (
    <Panel title="Region" desc="DoseWISE is available in India. Dates are shown as DD/MM/YYYY.">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Country">{(x) => <Input {...x} value="India" readOnly disabled />}</Field>
        <Field label="State" required error={touched && missing ? "Select your state or union territory" : undefined}>{(x) => <Select {...x} value={state} onChange={(e) => setState(e.target.value)}>
          <option value="">Select state / union territory…</option>
          {ref.data?.states.map((s: string) => <option key={s}>{s}</option>)}</Select>}</Field>
        <Field label="Date format">{(x) => <Input {...x} value={`DD/MM/YYYY (e.g. ${fmtDate(new Date())})`} readOnly disabled />}</Field>
      </div>
      <Button onClick={() => { setTouched(true); if (!missing) m.mutate({ country: "India", state, date_format: "DD/MM/YYYY" }); }}
        disabled={touched && missing} loading={m.isPending}>Save region</Button>
    </Panel>
  );
}

const NOTIF = [["medication_reminders", "Medication reminders"], ["appointment_reminders", "Appointment reminders"], ["doctor_messages", "Doctor messages & prescription changes"],
  ["caregiver_notifications", "Caregiver notifications"], ["security_alerts", "Security alerts"], ["emergency_notifications", "Emergency notifications"]] as const;

function NotificationPrefs() {
  const { user } = useAuth();
  const [n, setN] = useState<Record<string, { email?: boolean; sms?: boolean }>>(user!.preferences.notifications ?? {});
  const m = usePrefs();
  const integ = useQuery({ queryKey: ["integrations"], queryFn: () => api.get("/api/integrations/status") });
  // SMS only appears once it can really be delivered (switched on in backend/.env)
  const sms = !!integ.data?.channels?.sms;
  const email = integ.data?.channels?.email ?? true;
  return (
    <Panel title="Notifications" desc={`In-app notifications are always on.${sms ? " Email and SMS never contain" : " Emails never contain"} medical details.`}>
      {integ.data && !email && (
        <Notice tone="warn">Email isn't connected in this environment, so email notifications are recorded as "not sent".</Notice>
      )}
      <table className="w-full text-sm"><thead className="text-left text-ink-3"><tr><th className="py-2">Type</th><th>In-app</th><th>Email</th>{sms && <th>SMS</th>}</tr></thead>
        <tbody>{NOTIF.map(([k, l]) => (
          <tr key={k} className="border-t border-line">
            <td className="py-2.5 font-medium">{l}</td><td><Badge tone="ok">Always</Badge></td>
            <td><Toggle label={`${l} by email`} checked={!!n[k]?.email || k.startsWith("security") || k.startsWith("emergency")} disabled={k.startsWith("security") || k.startsWith("emergency")} onChange={(v) => setN({ ...n, [k]: { ...n[k], email: v } })} /></td>
            {sms && <td><Toggle label={`${l} by SMS`} checked={!!n[k]?.sms || k.startsWith("emergency")} disabled={k.startsWith("emergency") || !user!.phone} onChange={(v) => setN({ ...n, [k]: { ...n[k], sms: v } })} /></td>}
          </tr>))}</tbody></table>
      {sms && !user!.phone && <p className="text-xs text-ink-3">Add a phone number in Account to enable SMS.</p>}
      <Button onClick={() => m.mutate({ notifications: n })} loading={m.isPending}>Save notification settings</Button>
    </Panel>
  );
}

function Privacy() {
  const { user } = useAuth();
  const doctor = user!.role === "doctor";
  const points = doctor ? [
    "Your name, speciality, council and registration number are used to verify you before you can access any patient, and are shown to patients you treat.",
    "Records you open, prescriptions you write and changes you make are saved with your name and time, and kept in a tamper-evident audit log.",
    "You can open a patient's record only with their Patient Access ID or another authorisation they gave; access expires and patients can revoke it.",
    "Your mobile number and email are used for sign-in security and account notices, never for marketing.",
    "Patient information you see may be used only for that patient's care. Downloading or sharing it outside DoseWISE is your professional responsibility.",
  ] : [
    "Your medicines, dose logs, records and allergies are used to show your schedule, send reminders and help your doctors treat you safely.",
    "Only you and doctors you authorise (with your Access ID or by booking) can see your health information. Guest doctors get a one-time, read-only view and you are notified.",
    "Every time someone views or changes your record it is logged, and you can see who in Care Team → History.",
    "Reminders by SMS or email never include medical details.",
    "We never sell your data or use it for advertising. Regenerating your Access ID stops anyone who has the old one.",
  ];
  return (
    <Panel title="How your information is used" desc="A short summary. The full Privacy Policy has the details.">
      <ul className="space-y-3">
        {points.map((t) => <li key={t} className="flex gap-2.5 text-sm text-ink-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" />{t}</li>)}
      </ul>
      <Link to="/privacy" className="link text-sm">Read the full Privacy Policy →</Link>
    </Panel>
  );
}
