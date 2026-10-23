import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { HeartHandshake, LifeBuoy, Pill, ShieldCheck, Stethoscope, UserRound } from "lucide-react";
import { AuthCard } from "./AuthCard";
import { Button, Checkbox, Field, Input } from "@/components/ui/primitives";
import { Notice } from "@/components/ui/feedback";
import { api, errorMessage } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { loginSchema, zodErrors } from "@/lib/schemas";

const PERSONAS = [
  { id: "patient", label: "Patient", who: "Ananya · upcoming doses & appointment", icon: <Pill className="h-4 w-4" /> },
  { id: "patient2", label: "Patient", who: "Rahul · unconfirmed doses", icon: <UserRound className="h-4 w-4" /> },
  { id: "doctor", label: "Doctor", who: "Dr. Mehra · verification & follow-ups", icon: <Stethoscope className="h-4 w-4" /> },
  { id: "caregiver", label: "Caregiver", who: "Kavya · linked to Ananya", icon: <HeartHandshake className="h-4 w-4" /> },
  { id: "support", label: "Coordinator", who: "Priya · assigned case", icon: <LifeBuoy className="h-4 w-4" /> },
  { id: "admin", label: "Admin", who: "Verification, audit, integrations", icon: <ShieldCheck className="h-4 w-4" /> },
];

export default function Login() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const { session } = useAuth();
  const [form, setForm] = useState({ email: "", password: "", remember_device: false });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const finish = async (role?: string) => {
    await qc.invalidateQueries({ queryKey: ["session"] });
    const next = params.get("next");
    nav(next && next.startsWith("/") ? next : role ? homeFor(role as any) : "/app", { replace: true });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const parsed = loginSchema.safeParse(form);
    if (!parsed.success) return setErrors(zodErrors(parsed.error));
    setErrors({});
    setError(null);
    setBusy("login");
    try {
      const r = await api.post("/api/auth/login", form);
      if (r.mfa_required) return nav("/mfa" + (params.get("next") ? `?next=${params.get("next")}` : ""));
      await finish(r.user.role);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const demo = async (persona: string) => {
    setBusy(persona);
    setError(null);
    try {
      const r = await api.post("/api/auth/demo-login", { persona });
      await finish(r.user.role);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <AuthCard title="Welcome back" subtitle="Sign in to your DoseWISE account.">
      {session?.auth_provider === "cognito" ? (
        <a href="/api/auth/cognito/login"><Button className="w-full" size="lg">Continue to secure sign-in</Button></a>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          {error && <Notice tone="danger">{error}</Notice>}
          <Field label="Email" error={errors.email} required>
            {(p) => <Input {...p} type="email" autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
          </Field>
          <Field label="Password" error={errors.password} required>
            {(p) => <Input {...p} type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />}
          </Field>
          <div className="flex items-center justify-between">
            <Checkbox checked={form.remember_device} onChange={(v) => setForm({ ...form, remember_device: v })} label="Trust this device" />
            <Link to="/forgot-password" className="link text-sm">Forgot password?</Link>
          </div>
          <Button type="submit" size="lg" className="w-full" loading={busy === "login"}>Sign in</Button>
          <p className="text-center text-sm text-ink-3">New to DoseWISE? <Link to="/register" className="link">Create an account</Link></p>
        </form>
      )}

      {session?.demo_enabled && (
        <div className="mt-8 border-t border-line pt-6">
          <p className="text-sm font-bold">Explore with demo data</p>
          <p className="mt-0.5 text-xs text-ink-3">Development only · fictional people and records · no password needed.</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {PERSONAS.map((p) => (
              <button key={p.id} onClick={() => demo(p.id)} disabled={!!busy}
                className="flex items-start gap-2.5 rounded-xl border border-line p-3 text-left transition hover:border-primary/40 hover:bg-primary-soft/50 disabled:opacity-60">
                <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary">{p.icon}</span>
                <span>
                  <span className="block text-sm font-semibold">{busy === p.id ? "Signing in…" : p.label}</span>
                  <span className="block text-xs text-ink-3">{p.who}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </AuthCard>
  );
}
