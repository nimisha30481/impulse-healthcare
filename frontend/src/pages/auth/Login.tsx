import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { AuthCard } from "./AuthCard";
import { Button, Field, Input } from "@/components/ui/primitives";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Notice } from "@/components/ui/feedback";
import { ApiError, api, errorMessage } from "@/lib/api";
import { homeFor } from "@/lib/auth";
import { loginSchema, zodErrors } from "@/lib/schemas";


export default function Login() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const [form, setForm] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [unverified, setUnverified] = useState(false);

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
      if (r.mfa_required) {
        // load the new "waiting for code" session before showing the code page (the cached one says signed out)
        await qc.refetchQueries({ queryKey: ["session"] });
        return nav("/mfa" + (params.get("next") ? `?next=${params.get("next")}` : ""));
      }
      await finish(r.user.role);
    } catch (err) {
      setError(errorMessage(err));
      setUnverified(err instanceof ApiError && err.status === 403);
    } finally {
      setBusy(null);
    }
  };

  return (
    <AuthCard title="Welcome back" subtitle="Sign in to your DoseWISE account.">
      {(
        <form onSubmit={submit} className="space-y-4" noValidate>
          {error && <Notice tone="danger">{error}{unverified && <> <Link className="link" to={`/verify-email?email=${encodeURIComponent(form.email)}`}>Enter your code</Link></>}</Notice>}
          <Field label="Email" error={errors.email} required>
            {(p) => <Input {...p} type="email" autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
          </Field>
          <Field label="Password" error={errors.password} required>
            {(p) => <PasswordInput {...p} autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />}
          </Field>
          <div className="flex justify-end">
            <Link to="/forgot-password" className="link text-sm">Forgot password?</Link>
          </div>
          <Button type="submit" size="lg" className="w-full" loading={busy === "login"}>Sign in</Button>
          <p className="text-center text-sm text-ink-3">New to DoseWISE? <Link to="/register" className="link">Create an account</Link></p>
        </form>
      )}

    </AuthCard>
  );
}
