import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { HeartHandshake } from "lucide-react";
import { AuthCard } from "@/pages/auth/AuthCard";
import { Badge, Button } from "@/components/ui/primitives";
import { Notice } from "@/components/ui/feedback";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function CaregiverAccept() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { user, loading } = useAuth();
  const [res, setRes] = useState<any>(null);
  const m = useMutation({ mutationFn: () => api.post("/api/caregiver/invitations/accept", { token }), onSuccess: setRes });
  const next = encodeURIComponent(`/caregiver/accept?token=${token}`);
  return (
    <AuthCard title="Caregiver invitation" subtitle="Someone asked you to help with their care on DoseWISE.">
      {loading ? null : !user ? (
        <div className="space-y-3">
          <Notice tone="info">Sign in or create a <b>caregiver</b> account with the email or phone the invitation was sent to. Never use the patient's own login.</Notice>
          <Link to={`/login?next=${next}`}><Button className="w-full">Sign in</Button></Link>
          <Link to="/register"><Button variant="outline" className="w-full">Create caregiver account</Button></Link>
        </div>
      ) : user.role !== "caregiver" ? (
        <Notice tone="warn">You're signed in as a {user.role}. Invitations must be accepted from a caregiver account.</Notice>
      ) : res ? (
        <div className="space-y-3 text-center">
          <HeartHandshake className="mx-auto h-10 w-10 text-primary" />
          <p className="font-semibold">Accepted. {res.patient_name} will now confirm your access.</p>
          <div className="flex flex-wrap justify-center gap-1">{res.requested_scopes.map((s: string) => <Badge key={s} tone="primary">{s}</Badge>)}</div>
          <Link to="/caregiver"><Button className="w-full">Go to dashboard</Button></Link>
        </div>
      ) : (
        <div className="space-y-4">
          {m.isError && <Notice tone="danger">{errorMessage(m.error)}</Notice>}
          <p className="text-sm text-ink-2">Accepting confirms your identity for this invitation. Access starts only after the patient approves it, and they can change or revoke it at any time.</p>
          <Button className="w-full" onClick={() => m.mutate()} loading={m.isPending} disabled={!token}>Accept invitation</Button>
        </div>
      )}
    </AuthCard>
  );
}
