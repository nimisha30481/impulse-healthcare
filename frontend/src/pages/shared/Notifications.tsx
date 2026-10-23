import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, BellRing, CalendarDays, CheckCheck, ClipboardList, FileText, HeartHandshake, Pill, ShieldAlert, Siren } from "lucide-react";
import type { ReactNode } from "react";
import { Badge, Button, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState, useToast } from "@/components/ui/feedback";
import { PageHeader, Tabs } from "@/components/ui/domain";
import { api } from "@/lib/api";
import { fmtDateTime, fmtRelative, titleCase } from "@/lib/format";
import type { NotificationItem } from "@/lib/types";

const ICON: Record<string, ReactNode> = {
  medication_reminder: <Pill className="h-4 w-4" />, new_prescription: <Pill className="h-4 w-4" />, prescription_change: <Pill className="h-4 w-4" />,
  appointment_reminder: <CalendarDays className="h-4 w-4" />, doctor_instruction: <ClipboardList className="h-4 w-4" />, record_uploaded: <FileText className="h-4 w-4" />,
  caregiver_update: <HeartHandshake className="h-4 w-4" />, important_alert: <BellRing className="h-4 w-4" />, security: <ShieldAlert className="h-4 w-4" />, emergency: <Siren className="h-4 w-4" />,
};

export default function Notifications() {
  const [tab, setTab] = useState<"all" | "unread">("all");
  const q = useQuery({ queryKey: ["notifications", "list", tab], queryFn: () => api.get(`/api/notifications${tab === "unread" ? "?unread=true" : ""}`) });
  const qc = useQueryClient();
  const nav = useNavigate();
  const toast = useToast();
  const read = useMutation({ mutationFn: (id: string) => api.post(`/api/notifications/${id}/read`), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });
  const all = useMutation({ mutationFn: () => api.post("/api/notifications/read-all"), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });
  const enableBrowser = async () => {
    if (typeof Notification === "undefined") return toast("danger", "This browser doesn't support notifications.");
    const p = await Notification.requestPermission();
    toast(p === "granted" ? "ok" : "info", p === "granted" ? "Browser notifications on. They never include medical details." : "Browser notifications were not enabled.");
  };
  return (
    <>
      <PageHeader title="Notifications" actions={<><Button variant="outline" onClick={enableBrowser} icon={<Bell className="h-4 w-4" />}>Browser alerts</Button><Button variant="outline" onClick={() => all.mutate()} icon={<CheckCheck className="h-4 w-4" />}>Mark all read</Button></>} />
      <div className="mb-4"><Tabs label="Notification filter" value={tab} onChange={setTab} tabs={[{ id: "all", label: "All" }, { id: "unread", label: "Unread", count: q.data?.unread }]} /></div>
      {q.isError ? <ErrorState error={q.error} /> : q.isLoading ? <Skeleton className="h-64" /> : q.data.items.length === 0 ? <EmptyState icon={<Bell className="h-6 w-6" />} title="You're all caught up" /> : (
        <ul className="card divide-y divide-line">
          <AnimatePresence initial={false}>
            {q.data.items.map((n: NotificationItem) => (
              <motion.li key={n.id} layout initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <button className="flex w-full items-start gap-3 p-4 text-left hover:bg-surface-2" onClick={() => { if (!n.read_at) read.mutate(n.id); if (n.link) nav(n.link); }}>
                  <span className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl ${n.priority === "emergency" ? "bg-danger text-white" : n.priority === "high" ? "bg-warn-soft text-warn" : "bg-primary-soft text-primary"}`}>{ICON[n.category] ?? <Bell className="h-4 w-4" />}</span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2"><span className={`font-semibold ${n.read_at ? "text-ink-2" : "text-ink"}`}>{n.title}</span>{!n.read_at && <Badge tone="primary">New</Badge>}</span>
                    <span className="block text-sm text-ink-3">{n.body}</span>
                    {n.other_channels && n.other_channels.length > 0 && (
                      <span className="mt-1 flex flex-wrap gap-1">{n.other_channels.map((c, i) => <Badge key={i} tone={c.status === "sent" || c.status === "delivered" ? "ok" : c.status === "failed" ? "danger" : "neutral"}>{c.channel}: {c.status === "not_configured" ? "not sent (provider not configured)" : titleCase(c.status)}</Badge>)}</span>
                    )}
                  </span>
                  <time className="shrink-0 text-xs text-ink-3" dateTime={n.created_at} title={fmtDateTime(n.created_at)}>{fmtRelative(n.created_at)}</time>
                </button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </>
  );
}
