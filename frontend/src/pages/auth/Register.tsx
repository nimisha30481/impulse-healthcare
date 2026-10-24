import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MailCheck, Pill, Stethoscope } from "lucide-react";
import clsx from "clsx";
import { AuthCard } from "./AuthCard";
import { VerifyCodeForm } from "./AccountFlows";
import { Button, Checkbox, Field, Input, Select } from "@/components/ui/primitives";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Modal, Notice } from "@/components/ui/feedback";
import { LegalText } from "@/pages/public/InfoPage";
import { api, ApiError, errorMessage } from "@/lib/api";
import { homeFor } from "@/lib/auth";
import { PASSWORD_RULES, registerSchema, zodErrors } from "@/lib/schemas";

/** Red message listing the rules a typed password still misses (shown as soon as the field is left). */
function passwordProblem(pw: string): string | undefined {
  if (!pw) return undefined;
  const missing = PASSWORD_RULES.filter((r) => !r.test(pw)).map((r) => r.label);
  return missing.length ? `Password needs: ${missing.join(" · ")}` : undefined;
}

const ROLES = [
  { id: "patient", label: "Patient", d: "Manage my own medicines and records", icon: <Pill className="h-5 w-5" /> },
  { id: "doctor", label: "Doctor", d: "Prescribe and follow up with your patients", icon: <Stethoscope className="h-5 w-5" /> },
] as const;

// The draft (never the password) is kept for this browser tab so details survive reading the terms
// or a refresh; it's cleared once the account is created.
const DRAFT_KEY = "dosewise-register-draft";
const EMPTY = { role: "patient", full_name: "", email: "", phone: "", password: "", confirm: "", accept_terms: false,
  speciality: "", registration_council: "", registration_number: "" };

function loadDraft() {
  try { return { ...EMPTY, ...JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "{}"), password: "", confirm: "" }; }
  catch { return EMPTY; }
}

export default function Register() {
  const [form, setForm] = useState<any>(loadDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const qc = useQueryClient();
  const [exists, setExists] = useState(false);
  const [legal, setLegal] = useState<"terms" | "privacy" | null>(null);
  const ref = useQuery({ queryKey: ["reference"], queryFn: () => api.get("/api/reference"), staleTime: Infinity });
  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.value });

  useEffect(() => {
    const { password: _p, confirm: _c, ...safe } = form;
    try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify(safe)); } catch { /* storage unavailable */ }
  }, [form]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const parsed = registerSchema.safeParse(form);
    if (!parsed.success) return setErrors(zodErrors(parsed.error));
    setErrors({});
    setBusy(true);
    try {
      const { confirm: _c, ...body } = form;
      if (body.role !== "doctor") { delete body.speciality; delete body.registration_council; delete body.registration_number; }
      const r = await api.post("/api/auth/register", body);
      try { sessionStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
      if (r.status === "signed_in") {
        // account created and signed in: straight to the dashboard (no email-code step)
        await qc.refetchQueries({ queryKey: ["session"] });
        nav(homeFor(r.user.role), { replace: true });
        return;
      }
      setDone(r);
      try { sessionStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fields);
      setError(errorMessage(err));
      setExists(err instanceof ApiError && err.status === 409);
    } finally {
      setBusy(false);
    }
  };

  if (done?.status === "verify_code") {
    return (
      <AuthCard title="Check your email" subtitle={`Enter the 6-digit code we sent to ${done.email}.`}>
        <div className="mt-4"><VerifyCodeForm email={done.email} /></div>
        <p className="mt-3 text-center text-sm text-ink-3">
          Wrong email address? <button type="button" className="link" onClick={() => setDone(null)}>Go back and change it</button>
        </p>
      </AuthCard>
    );
  }

  if (done) {
    return (
      <AuthCard title="Check your email" subtitle="We sent a verification link to finish setting up your account.">
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="grid h-14 w-14 place-items-center rounded-2xl bg-ok-soft text-ok"><MailCheck className="h-7 w-7" /></span>
          <p className="text-sm text-ink-2">{done.message}</p>
          {done.dev_link && (
            <Notice tone="warn" title="Development mode: email is not configured">
              Nothing was sent. Use this link to continue: <a className="link break-all" href={done.dev_link}>verify email</a>
            </Notice>
          )}
          <Link to="/login" className="link text-sm">Back to sign in</Link>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Create your account" subtitle="Fields marked * are required." wide>
      <Link to="/guest" className="mb-6 flex items-center gap-3 rounded-xl border border-primary/30 bg-primary-soft/60 p-3.5 transition hover:bg-primary-soft">
        <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-ink"><Stethoscope className="h-5 w-5" /></span>
        <span className="flex-1"><span className="block font-semibold">Doctor without an account? Use Guest / One-Time Doctor Access</span>
          <span className="block text-xs text-ink-3">View a patient's record read-only with their Access ID. No sign-up needed.</span></span>
      </Link>
      <form onSubmit={submit} className="space-y-5" noValidate>
        {error && <Notice tone="danger">{error}{exists && <span className="mt-2 flex gap-4 font-semibold">
          <Link to="/login" className="link">Sign in</Link><Link to="/forgot-password" className="link">Forgot password</Link></span>}</Notice>}
        <fieldset>
          <legend className="label mb-2">I am a… <span className="text-danger">*</span></legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {ROLES.map((r) => (
              <label key={r.id} className={clsx("flex cursor-pointer flex-col gap-1.5 rounded-xl border p-3.5 transition",
                form.role === r.id ? "border-primary bg-primary-soft/60 ring-4 ring-primary/10" : "border-line hover:bg-surface-2")}>
                <input type="radio" name="role" value={r.id} checked={form.role === r.id} onChange={set("role")} className="sr-only" />
                <span className="text-primary">{r.icon}</span>
                <span className="font-semibold">{r.label}</span>
                <span className="text-xs text-ink-3">{r.d}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name" error={errors.full_name} required>{(p) => <Input {...p} autoComplete="name" value={form.full_name} onChange={set("full_name")} />}</Field>
          <Field label="Email" error={errors.email} required>{(p) => <Input {...p} type="email" autoComplete="email" value={form.email} onChange={set("email")} />}</Field>
          <Field label="Mobile number" error={errors.phone} hint="10 digits, without +91 or 0" required>
            {(p) => <Input {...p} type="tel" inputMode="numeric" autoComplete="tel-national" maxLength={10}
              value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value.replace(/\D/g, "").slice(0, 10) })} />}
          </Field>
          <div className="hidden sm:block" />
          <Field label="Password" error={errors.password} required>
            {(p) => <PasswordInput {...p} showRules autoComplete="new-password" value={form.password}
              onChange={(e) => { setForm({ ...form, password: e.target.value }); if (errors.password) setErrors({ ...errors, password: passwordProblem(e.target.value) ?? "" }); }}
              onBlur={() => setErrors({ ...errors, password: passwordProblem(form.password) ?? "" })} />}
          </Field>
          <Field label="Confirm password" error={errors.confirm} required>
            {(p) => <PasswordInput {...p} autoComplete="new-password" value={form.confirm} onChange={set("confirm")}
              onFocus={() => setErrors({ ...errors, password: passwordProblem(form.password) ?? "" })}
              onBlur={() => setErrors({ ...errors, confirm: form.confirm && form.confirm !== form.password ? "Passwords don't match" : "" })} />}
          </Field>
        </div>
        {form.role === "doctor" && (
          <div className="grid gap-4 rounded-2xl bg-surface-2 p-4 sm:grid-cols-2">
            <Field label="Speciality" error={errors.speciality} required>
              {(p) => <Select {...p} value={form.speciality} onChange={set("speciality")}>
                <option value="">Select speciality…</option>
                {ref.data?.specialities.map((s: string) => <option key={s}>{s}</option>)}
              </Select>}
            </Field>
            <Field label="Medical council" error={errors.registration_council} required>
              {(p) => <Select {...p} value={form.registration_council} onChange={set("registration_council")}>
                <option value="">Select council…</option>
                {ref.data?.councils.map((s: string) => <option key={s}>{s}</option>)}
              </Select>}
            </Field>
            <div className="sm:col-span-2">
              <Field label="Registration number" error={errors.registration_number} hint="As printed on your council registration certificate" required>
                {(p) => <Input {...p} value={form.registration_number} onChange={set("registration_number")} placeholder="e.g. KMC-123456" />}
              </Field>
            </div>
          </div>
        )}
        <div>
          <Checkbox checked={form.accept_terms} onChange={(v) => setForm({ ...form, accept_terms: v })}
            label={<>I agree to the{" "}
              <button type="button" className="link" onClick={(e) => { e.preventDefault(); setLegal("terms"); }}>Terms of Use</button>{" "}and{" "}
              <button type="button" className="link" onClick={(e) => { e.preventDefault(); setLegal("privacy"); }}>Privacy Policy</button>{" "}
              <span className="text-danger">*</span></>} />
          {errors.accept_terms && <p role="alert" className="ml-10 text-sm text-danger">{errors.accept_terms}</p>}
        </div>
        <Button type="submit" size="lg" className="w-full" loading={busy}>Create account</Button>
        <p className="text-center text-sm text-ink-3">Already have an account? <Link to="/login" className="link">Sign in</Link></p>
      </form>
      <Modal open={!!legal} onClose={() => setLegal(null)} title={legal === "terms" ? "Terms of Use" : "Privacy Policy"} size="lg"
        footer={<Button onClick={() => { setForm({ ...form, accept_terms: true }); setLegal(null); }}>I agree</Button>}>
        {legal && <LegalText slug={legal} />}
      </Modal>
    </AuthCard>
  );
}
