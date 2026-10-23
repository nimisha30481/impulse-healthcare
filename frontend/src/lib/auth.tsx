import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Preferences, Role, User } from "./types";

interface SessionState {
  authenticated: boolean;
  mfa_pending?: boolean;
  user?: User | null;
  demo_enabled: boolean;
  auth_provider: string;
}

interface AuthCtx {
  session: SessionState | undefined;
  user: User | null;
  loading: boolean;
  refresh: () => Promise<unknown>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["session"],
    queryFn: () => api.get<SessionState>("/api/auth/session"),
    staleTime: 60_000,
  });

  useEffect(() => {
    const onUnauth = () => qc.invalidateQueries({ queryKey: ["session"] });
    window.addEventListener("impulse:unauthorized", onUnauth);
    return () => window.removeEventListener("impulse:unauthorized", onUnauth);
  }, [qc]);

  const logout = async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      qc.clear(); // drop every cached health record from memory on sign-out
      await qc.invalidateQueries({ queryKey: ["session"] });
    }
  };

  return (
    <Ctx.Provider
      value={{
        session: q.data,
        user: q.data?.authenticated ? (q.data.user ?? null) : null,
        loading: q.isLoading,
        refresh: () => q.refetch(),
        logout,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);

export function homeFor(role: Role): string {
  return { patient: "/patient", doctor: "/doctor", caregiver: "/caregiver", support: "/support", admin: "/admin" }[role];
}

/** Applies appearance preferences to <html>. Theme falls back to localStorage before sign-in
 *  (only the theme name is stored there - never health data). */
export function applyPreferences(p: Preferences | undefined) {
  const root = document.documentElement;
  const stored = (() => {
    try {
      return localStorage.getItem("impulse-theme");
    } catch {
      return null;
    }
  })();
  const theme = p?.theme ?? (stored as Preferences["theme"]) ?? "system";
  const dark = theme === "dark" || (theme === "system" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  root.dataset.theme = dark ? "dark" : "light";
  root.dataset.textSize = p?.text_size ?? "normal";
  root.dataset.contrast = p?.high_contrast ? "high" : "normal";
  root.lang = p?.language ?? "en";
}
