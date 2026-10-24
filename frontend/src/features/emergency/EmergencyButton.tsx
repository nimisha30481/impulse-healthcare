import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { HeartHandshake, MapPin, Phone, Siren, Users } from "lucide-react";
import { Button, Checkbox } from "@/components/ui/primitives";
import { Modal, Notice, useToast } from "@/components/ui/feedback";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";

/** Visually distinct from routine reminders (solid red, siren icon). DoseWISE never claims to
 *  dispatch responders: calling 112 is done by the user's own phone. */
export function EmergencyButton({ patientId, compact }: { patientId: string; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const t = useT();
  return (
    <>
      <Button variant="danger" size="sm" onClick={() => setOpen(true)} icon={<Siren className="h-4 w-4" />}
        className={compact ? "" : "mr-1"} aria-haspopup="dialog">
        <span className="hidden sm:inline">{t("common.emergency")}</span>
      </Button>
      <EmergencyDialog open={open} onClose={() => setOpen(false)} patientId={patientId} />
    </>
  );
}

export function EmergencyDialog({ open, onClose, patientId }: { open: boolean; onClose: () => void; patientId: string }) {
  const toast = useToast();
  const [shareInfo, setShareInfo] = useState(false);
  const [shareLoc, setShareLoc] = useState(false);
  const [result, setResult] = useState<any>(null);
  const m = useMutation({
    mutationFn: async (alert_type: string) => {
      let location: any = null;
      if (shareLoc && navigator.geolocation) {
        location = await new Promise((resolve) =>
          navigator.geolocation.getCurrentPosition((p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy_m: p.coords.accuracy }),
            () => resolve(null), { timeout: 5000 }));
      }
      return api.post(`/api/patients/${patientId}/emergency`, { alert_type, share_info: shareInfo, share_location: shareLoc && !!location, location });
    },
    onSuccess: (data) => setResult(data),
    onError: (e) => toast("danger", errorMessage(e)),
  });

  return (
    <Modal open={open} onClose={() => { setResult(null); onClose(); }} title="Emergency assistance" size="md">
      <div className="space-y-4">
        <a href="tel:112" onClick={() => m.mutate("call_services")}
          className="flex items-center gap-4 rounded-2xl bg-danger p-4 text-white shadow-lift transition hover:bg-danger/90">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-white/15"><Phone className="h-6 w-6" /></span>
          <span>
            <span className="block text-lg font-bold">Call 112 now</span>
            <span className="block text-sm opacity-90">India's emergency number. Your phone places the call.</span>
          </span>
        </a>
        <div className="grid gap-3 sm:grid-cols-2">
          <Button variant="outline" size="lg" className="h-auto justify-start py-3 text-left" loading={m.isPending && m.variables === "emergency_contact"}
            onClick={() => m.mutate("emergency_contact")} icon={<Users className="h-5 w-5 text-danger" />}>
            <span><span className="block">Alert my emergency contact</span><span className="block text-xs font-normal text-ink-3">and authorised caregivers</span></span>
          </Button>
          <Button variant="outline" size="lg" className="h-auto justify-start py-3 text-left" loading={m.isPending && m.variables === "care_team"}
            onClick={() => m.mutate("care_team")} icon={<HeartHandshake className="h-5 w-5 text-danger" />}>
            <span><span className="block">Contact my care team</span><span className="block text-xs font-normal text-ink-3">opens an urgent support case</span></span>
          </Button>
        </div>
        <div className="rounded-xl bg-surface-2 p-2">
          <Checkbox checked={shareInfo} onChange={setShareInfo} label="Share my emergency information (blood group, allergies, emergency contact)"
            description="Only if you've marked it shareable in Medical Records." />
          <Checkbox checked={shareLoc} onChange={setShareLoc} label={<span className="inline-flex items-center gap-1"><MapPin className="h-4 w-4" /> Share my current location with the people alerted</span>}
            description="Your browser will ask for permission. Location is attached to this alert only." />
        </div>
        {result && (
          <Notice tone="ok" title="Alert recorded">
            <ul className="mt-1 list-disc pl-4">
              {result.recipients.map((r: any, i: number) => (
                <li key={i}>{r.who}: <b>Delivered</b></li>
              ))}
            </ul>
          </Notice>
        )}
        <Notice tone="warn" title="Service limitations">
          DoseWISE does not dispatch ambulances or emergency responders. Care-team alerts are reviewed by people during
          support hours only. If you are in danger, call 112.
        </Notice>
      </div>
    </Modal>
  );
}
