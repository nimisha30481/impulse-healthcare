import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, ShieldCheck } from "lucide-react";
import { AuthCard } from "./AuthCard";
import { Button, Field, Input, Spinner } from "@/components/ui/primitives";
import { Notice } from "@/components/ui/feedback";
import { api, errorMessage } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { password as passwordRule } from "@/lib/schemas";

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [msg, setMsg] = useState("");
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    api.post("/api/auth/verify-email", { token: params.get("token") ?? "" })
      .then(() => setState("ok"))
      .catch((e) => { setMsg(errorMessage(e)); setState("error"); });
  }, [params]);
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
  return (
    <AuthCard title="Reset your password" subtitle="We'll email you a link that expires in one hour.">
      {res ? (
        <div className="space-y-3">
          <Notice tone="ok">{res.message}</Notice>
          {res.dev_link && <Notice tone="warn" title="Development mode">Email isn't configured. <a className="link" href={res.dev_link}>Open reset link</a></Notice>}
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {err && <Notice tone="danger">{err}</Notice>}
          <Field label="Email" required>{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
          <Button type="submit" className="w-full" loading={busy}>Send reset link</Button>
          <p className="text-center text-sm"><Link className="link" to="/login">Back to sign in</Link></p>
        </form>
      )}
    </AuthCard>
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
          <Field label="New password" hint="10+ characters with a mix of types" required>{(p) => <Input {...p} type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />}</Field>
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
  if (session && !session.mfa_pending && !session.authenticated) return <AuthCard title="Session expired"><Link to="/login" className="link">Sign in again</Link></AuthCard>;
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
