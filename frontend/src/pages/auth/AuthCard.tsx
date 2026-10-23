import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { LogoMark } from "@/components/Logo";

export function AuthCard({ title, subtitle, children, wide }: { title: string; subtitle?: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden py-12">
      <div className="pointer-events-none absolute -top-32 left-1/2 h-[420px] w-[720px] -translate-x-1/2 rounded-full bg-mint/40 blur-3xl dark:bg-primary/15" />
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
        className={`relative mx-auto px-4 ${wide ? "max-w-2xl" : "max-w-md"}`}>
        <div className="card p-7 shadow-lift sm:p-9">
          <LogoMark size={40} />
          <h1 className="mt-5 text-2xl font-extrabold">{title}</h1>
          {subtitle && <p className="mt-1.5 text-[15px] text-ink-3">{subtitle}</p>}
          <div className="mt-7">{children}</div>
        </div>
      </motion.div>
    </div>
  );
}
