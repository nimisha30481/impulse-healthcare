import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

/** Subscribes to server-sent update hints and invalidates the matching queries, which then
 *  refetch through the normal authorised API (so revoked access is enforced on refetch). */
const TOPIC_KEYS: Record<string, string[][]> = {
  doses: [["overview"], ["doses"], ["adherence"], ["caregiver-patients"], ["doctor-dashboard"]],
  medications: [["medications"], ["medication"], ["overview"], ["doctor-patient"]],
  notifications: [["notifications"]],
  appointments: [["appointments"], ["overview"], ["doctor-dashboard"], ["doctor-appointments"]],
  permissions: [["permissions"], ["caregiver-patients"], ["doctor-patients"], ["care-team"]],
  messages: [["messages"]],
  instructions: [["instructions"]],
  support_cases: [["support-cases"]],
};

export function useRealtime(enabled: boolean) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") return;
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout>;
    const connect = () => {
      es = new EventSource("/api/events/stream");
      es.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as { topic: string };
          for (const key of TOPIC_KEYS[msg.topic] ?? []) qc.invalidateQueries({ queryKey: key });
          if (msg.topic === "doses" || msg.topic === "notifications") maybeBrowserNotify();
        } catch {
          /* ignore malformed hint */
        }
      };
      es.onerror = () => {
        es?.close();
        retry = setTimeout(connect, 5000);
      };
    };
    connect();
    return () => {
      es?.close();
      clearTimeout(retry);
    };
  }, [enabled, qc]);
}

/** Browser notifications carry no medical detail - just a prompt to open the app. */
function maybeBrowserNotify() {
  if (typeof Notification === "undefined" || Notification.permission !== "granted" || !document.hidden) return;
  new Notification("IMPULSE", { body: "You have a new update. Open IMPULSE to view it.", tag: "impulse-update" });
}
