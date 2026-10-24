import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, ShieldCheck } from "lucide-react";
import { AuthCard } from "./AuthCard";
import { Button, Field, Input, Spinner } from "@/components/ui/primitives";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Notice } from "@/components/ui/feedback";
import { api, errorMessage } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { password as passwordRule } from "@/lib/schemas";

const codeInputClass = "text-center font-mono text-2xl tracking-[0.4em]";

/** Email-code verification for accounts stored in Amazon Cognito. */
export function VerifyCodeForm({ email: initialEmail = "" }: { email?: string }) {
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "ok">("idle");
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setState("busy");
    try { await api.post("/api/auth/verify-email", { email, code }); setState("ok"); }
    catch (x) { setErr(errorMessage(x)); setState("idle"); }
  };
  const resend = async () => {
    setErr(null);
    try { await api.post("/api/auth/resend-verification", { email }); setInfo("A new code is on its way. It can take a minute."); }
    catch (x) { setErr(errorMessage(x)); }
  };
  if (state === "ok") {
    return (
      <div className="space-y-4 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-ok" />
        <p>Your email is verified. You can sign in now.</p>
        <Link to="/login"><Button className="w-full">Sign in</Button></Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-4 text-left">
      {err && <Notice tone="danger">{err}</Notice>}
      {info && <Notice tone="ok">{info}</Notice>}
      {!initialEmail && <Field label="Email" required>{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>}
      <Field label="6-digit code from your email" required>
        {(p) => <Input {...p} inputMode="numeric" autoComplete="one-time-code" maxLength={8} className={codeInputClass}
          value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />}
      </Field>
      <Button type="submit" className="w-full" loading={state === "busy"} disabled={code.length < 6 || !email}>Verify email</Button>
      <p className="text-center text-sm text-ink-3">Use the code from the newest email; sending a new code cancels older ones.
        No email? Check spam, or <button type="button" className="link" onClick={resend} disabled={!email}>send a new code</button>.</p>
    </form>
  );
}

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [msg, setMsg] = useState("");
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current || !token) return;
    ran.current = true;
    api.post("/api/auth/verify-email", { token })
      .then(() => setState("ok"))
      .catch((e) => { setMsg(errorMessage(e)); setState("error"); });
  }, [token]);
  if (!token) {
    return <AuthCard title="Verify your email" subtitle="Enter the code we emailed you."><VerifyCodeForm email={params.get("email") ?? ""} /></AuthCard>;
  }
  return (
    <AuthCard title="Email verification">
      {state === "working" && <Spinner label="Verifying" />}
      {state === "ok" && (
        <div className="space-y-4 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-ok" />
          <p>Your email is verified. You can sign in now.</p>
          <Link to="/login"><Button className="w-full">Sign in</Button></Link>
        </div>
      )}
      {state === "error" && <Notice tone="danger" title="We couldn't verify your email">{msg}</Notice>}
    </AuthCard>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try { setRes(await api.post("/api/auth/forgot-password", { email })); }
    catch (x) { setErr(errorMessage(x)); }
    finally { setBusy(false); }
  };
  if (res?.status === "code_sent") {
    return (
      <AuthCard title="Reset your password" subtitle={res.message}>
        <ResetWithCode email={email} />
        {res.dev_link && <p className="mt-4 text-center text-sm"><Link className="link" to={new URL(res.dev_link).pathname + new URL(res.dev_link).search}>Older account? Reset with a link instead</Link></p>}
      </AuthCard>
    );
  }
  return (
    <AuthCard title="Reset your password" subtitle="We'll email you a code or a link to set a new password.">
      {res ? (
        <div className="space-y-3">
          <Notice tone="ok">{res.message}</Notice>
          {res.dev_link ? (
            <>
              <Notice tone="warn" title="Email isn't connected in this environment">Nothing was emailed, so use the button below to set a new password now.</Notice>
              <Link to={new URL(res.dev_link).pathname + new URL(res.dev_link).search}><Button className="w-full" icon={<KeyRound className="h-4 w-4" />}>Reset my password now</Button></Link>
            </>
          ) : (
            <Notice tone="info">No email after a few minutes? Check the address is the one you registered with, and your spam folder.</Notice>
          )}
          <p className="text-center text-sm"><Link className="link" to="/login">Back to sign in</Link></p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {err && <Notice tone="danger">{err}</Notice>}
          <Field label="Email" required>{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
          <Button type="submit" className="w-full" loading={busy}>Send reset email</Button>
          <p className="text-center text-sm"><Link className="link" to="/login">Back to sign in</Link></p>
        </form>
      )}
    </AuthCard>
  );
}

function ResetWithCode({ email }: { email: string }) {
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const check = passwordRule.safeParse(pw);
    if (!check.success) return setErr(check.error.issues[0].message);
    setBusy(true);
    setErr(null);
    try { await api.post("/api/auth/reset-password", { email, code, password: pw }); setOk(true); }
    catch (x) { setErr(errorMessage(x)); }
    finally { setBusy(false); }
  };
  if (ok) return <div className="space-y-4"><Notice tone="ok">Password updated.</Notice><Link to="/login"><Button className="w-full">Sign in</Button></Link></div>;
  return (
    <form onSubmit={submit} className="space-y-4">
      {err && <Notice tone="danger">{err}</Notice>}
      <Field label="6-digit code from your email" required>
        {(p) => <Input {...p} inputMode="numeric" autoComplete="one-time-code" maxLength={8} className={codeInputClass}
          value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />}
      </Field>
      <Field label="New password" required>{(p) => <PasswordInput {...p} showRules autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />}</Field>
      <Button type="submit" className="w-full" loading={busy} disabled={code.length < 6} icon={<KeyRound className="h-4 w-4" />}>Update password</Button>
      <p className="text-center text-sm"><Link className="link" to="/login">Back to sign in</Link></p>
    </form>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const check = passwordRule.safeParse(pw);
    if (!check.success) return setErr(check.error.issues[0].message);
    setBusy(true);
    try { await api.post("/api/auth/reset-password", { token: params.get("token"), password: pw }); setOk(true); }
    catch (x) { setErr(errorMessage(x)); }
    finally { setBusy(false); }
  };
  return (
    <AuthCard title="Choose a new password" subtitle="You'll be signed out of all other devices.">
      {ok ? (
        <div className="space-y-4"><Notice tone="ok">Password updated.</Notice><Link to="/login"><Button className="w-full">Sign in</Button></Link></div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {err && <Notice tone="danger">{err}</Notice>}
          <Field label="New password" required>{(p) => <PasswordInput {...p} showRules autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />}</Field>
          <Button type="submit" className="w-full" loading={busy} icon={<KeyRound className="h-4 w-4" />}>Update password</Button>
        </form>
      )}
    </AuthCard>
  );
}

export function MfaChallengePage() {
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const { session } = useAuth();
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api.post("/api/auth/mfa/verify", { code });
      await qc.invalidateQueries({ queryKey: ["session"] });
      const next = params.get("next");
      nav(next?.startsWith("/") ? next : homeFor(r.user.role), { replace: true });
    } catch (x) { setErr(errorMessage(x)); }
    finally { setBusy(false); }
  };
  // re-check the session once on arrival, so a stale cached state never hides the code box
  const [checked, setChecked] = useState(false);
  useEffect(() => { qc.refetchQueries({ queryKey: ["session"] }).finally(() => setChecked(true)); }, [qc]);
  if (!checked) return <AuthCard title="Two-step verification"><Spinner label="Loading" /></AuthCard>;
  if (session?.authenticated) return <Navigate to={homeFor(session.user!.role)} replace />;
  if (session && !session.mfa_pending) return <AuthCard title="Session expired" subtitle="Your sign-in step timed out. Enter your email and password again to get a new code prompt."><Link to="/login" className="link">Sign in again</Link></AuthCard>;
  return (
    <AuthCard title="Two-step verification" subtitle="Enter the 6-digit code from your authenticator app, or a backup code.">
      <form onSubmit={submit} className="space-y-4">
        {err && <Notice tone="danger">{err}</Notice>}
        <Field label="Verification code" required>
          {(p) => <Input {...p} inputMode="numeric" autoComplete="one-time-code" className="text-center font-mono text-2xl tracking-[0.4em]"
            maxLength={12} value={code} onChange={(e) => setCode(e.target.value.trim())} />}
        </Field>
        <Button type="submit" className="w-full" size="lg" loading={busy} icon={<ShieldCheck className="h-5 w-5" />}>Verify</Button>
      </form>
    </AuthCard>
  );
}
