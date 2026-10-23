import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { HeartHandshake, MailCheck, Pill, Stethoscope } from "lucide-react";
import clsx from "clsx";
import { AuthCard } from "./AuthCard";
import { Button, Checkbox, Field, Input } from "@/components/ui/primitives";
import { Notice } from "@/components/ui/feedback";
import { api, ApiError, errorMessage } from "@/lib/api";
import { registerSchema, zodErrors } from "@/lib/schemas";

const ROLES = [
  { id: "patient", label: "Patient", d: "Manage my own medicines and records", icon: <Pill className="h-5 w-5" /> },
  { id: "caregiver", label: "Caregiver", d: "Help someone who invites me", icon: <HeartHandshake className="h-5 w-5" /> },
  { id: "doctor", label: "Doctor", d: "Requires registration verification", icon: <Stethoscope className="h-5 w-5" /> },
] as const;

export default function Register() {
  const [form, setForm] = useState<any>({ role: "patient", full_name: "", email: "", phone: "", password: "", confirm: "", accept_terms: false });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const parsed = registerSchema.safeParse(form);
    if (!parsed.success) return setErrors(zodErrors(parsed.error));
    setErrors({});
    setBusy(true);
    try {
      const { confirm: _c, ...body } = form;
      setDone(await api.post("/api/auth/register", { ...body, phone: body.phone || null }));
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fields);
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <AuthCard title="Check your email" subtitle="We sent a verification link to finish setting up your account.">
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="grid h-14 w-14 place-items-center rounded-2xl bg-ok-soft text-ok"><MailCheck className="h-7 w-7" /></span>
          <p className="text-sm text-ink-2">{done.message}</p>
          {form.role === "doctor" && (
            <Notice tone="info">After you verify your email, IMPULSE staff will check your medical registration before you can access any clinical features.</Notice>
          )}
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
    <AuthCard title="Create your account" subtitle="Your role decides what you can request — never what you can access. Access is always granted by the patient or verified by our team." wide>
      <form onSubmit={submit} className="space-y-5" noValidate>
        {error && <Notice tone="danger">{error}</Notice>}
        <fieldset>
          <legend className="label mb-2">I am a…</legend>
          <div className="grid gap-2 sm:grid-cols-3">
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
          <Field label="Mobile (optional)" hint="Used for SMS reminders if you turn them on">{(p) => <Input {...p} type="tel" autoComplete="tel" value={form.phone} onChange={set("phone")} />}</Field>
          <div />
          <Field label="Password" error={errors.password} hint="10+ characters with a mix of types" required>{(p) => <Input {...p} type="password" autoComplete="new-password" value={form.password} onChange={set("password")} />}</Field>
          <Field label="Confirm password" error={errors.confirm} required>{(p) => <Input {...p} type="password" autoComplete="new-password" value={form.confirm} onChange={set("confirm")} />}</Field>
        </div>
        {form.role === "doctor" && (
          <div className="grid gap-4 rounded-2xl bg-surface-2 p-4 sm:grid-cols-3">
            <Field label="Speciality" error={errors.speciality} required>{(p) => <Input {...p} value={form.speciality ?? ""} onChange={set("speciality")} />}</Field>
            <Field label="Registration no." error={errors.registration_number} required>{(p) => <Input {...p} value={form.registration_number ?? ""} onChange={set("registration_number")} />}</Field>
            <Field label="Council">{(p) => <Input {...p} value={form.registration_council ?? ""} onChange={set("registration_council")} />}</Field>
          </div>
        )}
        <div>
          <Checkbox checked={form.accept_terms} onChange={(v) => setForm({ ...form, accept_terms: v })}
            label={<>I agree to the <Link to="/terms" className="link">Terms</Link> and <Link to="/privacy" className="link">Privacy Policy</Link></>} />
          {errors.accept_terms && <p role="alert" className="ml-10 text-sm text-danger">{errors.accept_terms}</p>}
        </div>
        <Button type="submit" size="lg" className="w-full" loading={busy}>Create account</Button>
        <p className="text-center text-sm text-ink-3">Already have an account? <Link to="/login" className="link">Sign in</Link></p>
      </form>
    </AuthCard>
  );
}
