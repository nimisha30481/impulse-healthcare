import clsx from "clsx";

/** IMPULSE wordmark: a rounded square with a heartbeat line that resolves into a steady line -
 *  "a pulse, kept on track". */
export function LogoMark({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden>
      <defs>
        <linearGradient id="impulse-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="rgb(var(--primary))" />
          <stop offset="1" stopColor="#0b4a4e" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#impulse-g)" />
      <path d="M5 17h5l2.5-6 4 11 3-8 1.5 3H27" fill="none" stroke="#bff0dd" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ className, size = 30 }: { className?: string; size?: number }) {
  return (
    <span className={clsx("inline-flex items-center gap-2.5", className)}>
      <LogoMark size={size} />
      <span className="font-display text-[19px] font-extrabold tracking-[0.12em] text-ink">IMPULSE</span>
    </span>
  );
}
