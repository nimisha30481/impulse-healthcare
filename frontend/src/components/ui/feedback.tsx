import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, RefreshCw, X, XCircle } from "lucide-react";
import clsx from "clsx";
import { Button } from "./primitives";
import { errorMessage } from "@/lib/api";

export function EmptyState({ icon, title, body, action }: { icon?: ReactNode; title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line px-6 py-12 text-center">
      {icon && <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-primary-soft text-primary">{icon}</div>}
      <h3 className="text-base font-bold text-ink">{title}</h3>
      {body && <p className="mt-1 max-w-md text-sm text-ink-3">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl border border-danger/30 bg-danger-soft p-4 text-danger">
      <XCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <div className="flex-1">
        <p className="font-semibold">We couldn't load this.</p>
        <p className="text-sm opacity-90">{errorMessage(error)}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry} icon={<RefreshCw className="h-4 w-4" />}>Retry</Button>
      )}
    </div>
  );
}

export function Notice({ tone = "info", title, children, icon }: { tone?: "info" | "warn" | "danger" | "ok"; title?: string; children: ReactNode; icon?: ReactNode }) {
  const styles = {
    info: "bg-info-soft text-info border-info/20",
    warn: "bg-warn-soft text-warn border-warn/25",
    danger: "bg-danger-soft text-danger border-danger/25",
    ok: "bg-ok-soft text-ok border-ok/20",
  }[tone];
  const Icon = { info: Info, warn: AlertTriangle, danger: XCircle, ok: CheckCircle2 }[tone];
  return (
    <div className={clsx("flex gap-3 rounded-xl border p-3.5 text-sm", styles)}>
      <span className="mt-0.5 shrink-0">{icon ?? <Icon className="h-4.5 w-4.5 h-[18px] w-[18px]" aria-hidden />}</span>
      <div className="text-ink-2 [&_strong]:text-ink">
        {title && <p className="mb-0.5 font-semibold text-ink">{title}</p>}
        {children}
      </div>
    </div>
  );
}

/* ---------------- Modal ---------------- */
export function Modal({ open, onClose, title, children, footer, size = "md", labelledBy }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; size?: "sm" | "md" | "lg" | "xl"; labelledBy?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const t = setTimeout(() => ref.current?.querySelector<HTMLElement>("input,select,textarea,button:not([data-close])")?.focus(), 50);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && ref.current) {
        const els = ref.current.querySelectorAll<HTMLElement>("a,button,input,select,textarea,[tabindex]:not([tabindex='-1'])");
        const first = els[0], last = els[els.length - 1];
        if (e.shiftKey && document.activeElement === first) { last?.focus(); e.preventDefault(); }
        else if (!e.shiftKey && document.activeElement === last) { first?.focus(); e.preventDefault(); }
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      prev?.focus?.();
    };
  }, [open, onClose]);
  const width = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" }[size];
  // Rendered at <body> level: a dialog opened from the blurred sticky header (e.g. Emergency) was
  // otherwise positioned inside the header and cut off.
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
          <motion.div className="absolute inset-0 bg-ink/40 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            exit={{ opacity: 0 }} onClick={onClose} />
          <motion.div ref={ref} role="dialog" aria-modal="true" aria-labelledby={labelledBy ?? "modal-title"}
            className={clsx("relative flex max-h-[calc(100dvh-1rem)] w-full flex-col sm:max-h-[calc(100dvh-3rem)] rounded-t-3xl bg-surface shadow-lift sm:rounded-3xl", width)}
            initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}>
            <div className="flex shrink-0 items-center justify-between border-b border-line px-5 py-4">
              <h2 id={labelledBy ?? "modal-title"} className="text-lg font-bold">{title}</h2>
              <button data-close onClick={onClose} className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2" aria-label="Close dialog">
                <X className="h-5 w-5" />
              </button>
            </div>
            {/* min-h-0 lets the body shrink and scroll inside the dialog instead of pushing the top off-screen */}
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
            {footer && <div className="flex shrink-0 flex-wrap justify-end gap-2 border-t border-line px-5 py-3.5">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export function ConfirmDialog({ open, onClose, onConfirm, title, body, confirmLabel = "Confirm", tone = "primary", loading }: {
  open: boolean; onClose: () => void; onConfirm: () => void; title: string; body: ReactNode; confirmLabel?: string;
  tone?: "primary" | "danger"; loading?: boolean;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm"
      footer={<>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button variant={tone === "danger" ? "danger" : "primary"} onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
      </>}>
      <div className="text-sm text-ink-2">{body}</div>
    </Modal>
  );
}

/* ---------------- Toasts ---------------- */
type Toast = { id: number; tone: "ok" | "danger" | "info"; text: string };
const ToastCtx = createContext<(tone: Toast["tone"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const push = useCallback((tone: Toast["tone"], text: string) => {
    // Same message again (e.g. several settings saved at once) refreshes one toast instead of stacking.
    const key = `${tone}:${text}`;
    clearTimeout(timers.current.get(key));
    setItems((s) => (s.some((t) => `${t.tone}:${t.text}` === key) ? s : [...s.slice(-2), { id: Date.now() + Math.random(), tone, text }]));
    timers.current.set(key, setTimeout(() => {
      setItems((s) => s.filter((t) => `${t.tone}:${t.text}` !== key));
      timers.current.delete(key);
    }, tone === "danger" ? 4000 : 2000));
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(92vw,380px)] flex-col gap-2">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div key={t.id} layout initial={{ opacity: 0, y: 12, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40 }} className={clsx("pointer-events-auto flex items-start gap-2.5 rounded-xl border bg-surface p-3.5 shadow-lift",
                t.tone === "ok" ? "border-ok/30" : t.tone === "danger" ? "border-danger/30" : "border-line")}>
              {t.tone === "ok" ? <CheckCircle2 className="h-5 w-5 text-ok" /> : t.tone === "danger" ? <XCircle className="h-5 w-5 text-danger" /> : <Info className="h-5 w-5 text-info" />}
              <p className="text-sm text-ink">{t.text}</p>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
