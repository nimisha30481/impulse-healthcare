import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Activity, BadgeCheck, Bell, BookOpen, CalendarDays, ChevronDown, ClipboardList, Cloud, FileText, HeartHandshake,
  HelpCircle, Inbox, LayoutDashboard, LifeBuoy, LogOut, MapPin, Menu, MessageSquare, Pill, ScrollText, Settings,
  ShieldAlert, ShieldCheck, Stethoscope, Users, X,
} from "lucide-react";
import { Logo } from "../Logo";
import { Avatar, Badge } from "../ui/primitives";
import { ThemeToggle } from "./PublicLayout";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { useRealtime } from "@/lib/realtime";
import { api } from "@/lib/api";
import { EmergencyButton } from "@/features/emergency/EmergencyButton";
import type { Role } from "@/lib/types";

type NavItem = { to: string; label: string; icon: ReactNode; end?: boolean };

function useNav(role: Role): NavItem[] {
  const t = useT();
  const i = (C: any) => <C className="h-[18px] w-[18px]" aria-hidden />;
  switch (role) {
    case "patient":
      return [
        { to: "/patient", label: t("nav.dashboard"), icon: i(LayoutDashboard), end: true },
        { to: "/patient/medicines", label: t("nav.medicines"), icon: i(Pill) },
        { to: "/patient/records", label: t("nav.records"), icon: i(FileText) },
        { to: "/patient/appointments", label: t("nav.appointments"), icon: i(CalendarDays) },
        { to: "/patient/care-team", label: t("nav.careTeam"), icon: i(HeartHandshake) },
        { to: "/patient/reports", label: t("nav.reports"), icon: i(Activity) },
        { to: "/messages", label: t("nav.messages"), icon: i(MessageSquare) },
        { to: "/find-care", label: t("nav.directory"), icon: i(MapPin) },
        { to: "/notifications", label: t("nav.notifications"), icon: i(Bell) },
        { to: "/settings", label: t("nav.settings"), icon: i(Settings) },
        { to: "/support-help", label: t("nav.help"), icon: i(HelpCircle) },
      ];
    case "doctor":
      return [
        { to: "/doctor", label: "Dashboard", icon: i(LayoutDashboard), end: true },
        { to: "/doctor/patients", label: "Patients", icon: i(Users) },
        { to: "/doctor/appointments", label: "Appointments", icon: i(CalendarDays) },
        { to: "/doctor/prescriptions", label: "Prescriptions", icon: i(Pill) },
        { to: "/doctor/adherence", label: "Adherence Alerts", icon: i(Activity) },
        { to: "/doctor/briefs", label: "Clinical Briefs", icon: i(BookOpen) },
        { to: "/doctor/follow-ups", label: "Follow-ups", icon: i(ClipboardList) },
        { to: "/doctor/verification", label: "Prescription Verification", icon: i(BadgeCheck) },
        { to: "/messages", label: "Messages", icon: i(MessageSquare) },
        { to: "/settings", label: "Settings", icon: i(Settings) },
      ];
    case "caregiver":
      return [
        { to: "/caregiver", label: "Dashboard", icon: i(LayoutDashboard), end: true },
        { to: "/messages", label: "Messages", icon: i(MessageSquare) },
        { to: "/find-care", label: "Find Care", icon: i(MapPin) },
        { to: "/notifications", label: "Notifications", icon: i(Bell) },
        { to: "/settings", label: "Settings", icon: i(Settings) },
        { to: "/support-help", label: "Help & Support", icon: i(HelpCircle) },
      ];
    case "support":
      return [
        { to: "/support", label: "My Cases", icon: i(Inbox), end: true },
        { to: "/notifications", label: "Notifications", icon: i(Bell) },
        { to: "/settings", label: "Settings", icon: i(Settings) },
      ];
    case "admin":
      return [
        { to: "/admin", label: "Overview", icon: i(ShieldCheck), end: true },
        { to: "/admin/audit", label: "Audit Log", icon: i(ScrollText) },
        { to: "/integrations", label: "AWS Integrations", icon: i(Cloud) },
        { to: "/settings", label: "Settings", icon: i(Settings) },
      ];
  }
}

const ROLE_LABEL: Record<Role, { label: string; icon: ReactNode }> = {
  patient: { label: "Patient", icon: <Pill className="h-3 w-3" /> },
  doctor: { label: "Clinician", icon: <Stethoscope className="h-3 w-3" /> },
  caregiver: { label: "Caregiver", icon: <HeartHandshake className="h-3 w-3" /> },
  support: { label: "Care coordinator", icon: <LifeBuoy className="h-3 w-3" /> },
  admin: { label: "Administrator", icon: <ShieldAlert className="h-3 w-3" /> },
};

export function AppShell() {
  const { user, logout } = useAuth();
  const nav = useNav(user!.role);
  const [mobile, setMobile] = useState(false);
  const loc = useLocation();
  useRealtime(!!user);
  useEffect(() => setMobile(false), [loc.pathname]);

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5"><Link to="/" aria-label="IMPULSE home"><Logo size={28} /></Link></div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2" aria-label="Portal">
        {nav.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end}
            className={({ isActive }) => clsx("group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition-colors",
              isActive ? "text-primary" : "text-ink-2 hover:bg-surface-2 hover:text-ink")}>
            {({ isActive }) => (
              <>
                {isActive && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl bg-primary-soft" transition={{ duration: 0.22 }} />}
                <span className="relative">{n.icon}</span>
                <span className="relative">{n.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
      {user!.is_demo && (
        <div className="m-3 rounded-xl border border-dashed border-line p-3 text-xs text-ink-3">
          <b className="text-ink-2">Demo account.</b> All people and records are fictional.
        </div>
      )}
    </div>
  );

  return (
    <div className="flex min-h-screen">
      <a href="#app-main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">Skip to content</a>
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-line bg-surface lg:block">{sidebar}</aside>
      <AnimatePresence>
        {mobile && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <motion.div className="absolute inset-0 bg-ink/40" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMobile(false)} />
            <motion.aside initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ type: "tween", duration: 0.22 }}
              className="absolute inset-y-0 left-0 w-72 bg-surface shadow-lift">
              <button className="absolute right-3 top-4 rounded-lg p-2 hover:bg-surface-2" onClick={() => setMobile(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
              {sidebar}
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-line bg-bg/85 px-4 backdrop-blur-md sm:px-6">
          <button className="grid h-10 w-10 place-items-center rounded-xl hover:bg-surface-2 lg:hidden" onClick={() => setMobile(true)} aria-label="Open navigation">
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          {user!.role === "patient" && <EmergencyButton patientId={user!.patient_id!} />}
          <ThemeToggle />
          <NotificationBell />
          <UserMenu onLogout={logout} />
        </header>
        <main id="app-main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <motion.div key={loc.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="mx-auto max-w-6xl">
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}

function NotificationBell() {
  const q = useQuery({ queryKey: ["notifications", "count"], queryFn: () => api.get("/api/notifications?unread=true"), refetchInterval: 60_000 });
  const n = q.data?.unread ?? 0;
  return (
    <Link to="/notifications" className="relative grid h-10 w-10 place-items-center rounded-xl text-ink-2 hover:bg-surface-2"
      aria-label={n ? `${n} unread notifications` : "Notifications"}>
      <Bell className="h-5 w-5" />
      <AnimatePresence>
        {n > 0 && (
          <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}
            className="absolute right-1 top-1 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">
            {n > 99 ? "99+" : n}
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
  );
}

function UserMenu({ onLogout }: { onLogout: () => Promise<void> }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const nav = useNavigate();
  const t = useT();
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const r = ROLE_LABEL[user!.role];
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="menu"
        className="flex items-center gap-2 rounded-xl py-1 pl-1 pr-2 hover:bg-surface-2">
        <Avatar name={user!.full_name} color={user!.avatar_color} size={34} />
        <span className="hidden text-left sm:block">
          <span className="block text-sm font-semibold leading-tight text-ink">{user!.preferred_name || user!.full_name}</span>
          <span className="block text-xs text-ink-3">{r.label}</span>
        </span>
        <ChevronDown className="h-4 w-4 text-ink-3" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div role="menu" initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6 }}
            className="absolute right-0 mt-2 w-64 rounded-2xl border border-line bg-surface p-2 shadow-lift">
            <div className="px-3 py-2">
              <p className="truncate text-sm font-semibold">{user!.full_name}</p>
              <p className="truncate text-xs text-ink-3">{user!.email}</p>
              <Badge tone="primary" icon={r.icon} className="mt-2">{r.label}</Badge>
            </div>
            <div className="my-1 h-px bg-line" />
            <button role="menuitem" className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-surface-2" onClick={() => { setOpen(false); nav("/settings"); }}>
              <Settings className="h-4 w-4" /> {t("nav.settings")}
            </button>
            <button role="menuitem" className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-surface-2" onClick={() => { setOpen(false); nav("/integrations"); }}>
              <Cloud className="h-4 w-4" /> Platform status
            </button>
            <button role="menuitem" className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-danger hover:bg-danger-soft"
              onClick={async () => { await onLogout(); nav("/login"); }}>
              <LogOut className="h-4 w-4" /> {t("nav.signOut")}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
