import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { LifeBuoy, Phone } from "lucide-react";
import { Button, Field, Select, Textarea } from "@/components/ui/primitives";
import { Notice, useToast } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/domain";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const FAQ = [
  ["What does 'Unconfirmed' mean?", "We sent a reminder but didn't hear back. IMPULSE doesn't assume the dose was taken or missed."],
  ["Why can't I see information about my medicine?", "We only show medicine information from reviewed, trustworthy sources. Until one is connected, ask your pharmacist or doctor."],
  ["How do I give my daughter or son access?", "Go to Care Team → Invite caregiver. They use their own account, and you approve exactly what they can see."],
  ["I missed a dose — should I take two next time?", "Not unless your doctor told you to. Check your medicine's detail page for your doctor's missed-dose guidance, or ask them."],
  ["Is my information private?", "Only people you authorise can see it, and every access is listed in Care Team → History."],
];

export default function HelpCenter() {
  const { user } = useAuth();
  const [kind, setKind] = useState("general");
  const [text, setText] = useState("");
  const toast = useToast();
  const m = useMutation({ mutationFn: () => api.post(`/api/patients/${user!.patient_id}/concerns`, { kind, description: text }),
    onSuccess: (r) => { toast("ok", r.message); setText(""); }, onError: (e) => toast("danger", errorMessage(e)) });
  return (
    <>
      <PageHeader title="Help & Support" />
      <Notice tone="danger" title="Emergency?" icon={<Phone className="h-[18px] w-[18px]" />}>Call 112. IMPULSE support is not an emergency service.</Notice>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="font-bold">Common questions</h2>
          <div className="mt-3 divide-y divide-line">{FAQ.map(([q, a]) => (
            <details key={q} className="group py-3"><summary className="cursor-pointer font-semibold">{q}</summary><p className="mt-2 text-sm text-ink-2">{a}</p></details>))}</div>
        </section>
        {user!.role === "patient" && (
          <section className="card space-y-4 p-5">
            <h2 className="flex items-center gap-2 font-bold"><LifeBuoy className="h-5 w-5 text-primary" />Ask a care coordinator</h2>
            <Field label="Topic">{(p) => <Select {...p} value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="general">General question</option><option value="affordability">Medicine is too expensive</option><option value="medicine_unavailable">Medicine unavailable</option>
              <option value="refill_difficulty">Refill difficulty</option><option value="concerning_symptoms">I'm worried about symptoms</option></Select>}</Field>
            <Field label="Details">{(p) => <Textarea {...p} value={text} onChange={(e) => setText(e.target.value)} />}</Field>
            <Button onClick={() => m.mutate()} disabled={text.length < 5} loading={m.isPending}>Send</Button>
            <p className="text-xs text-ink-3">A person reviews requests during staffed hours. You'll get a reply in Notifications.</p>
          </section>
        )}
      </div>
    </>
  );
}
