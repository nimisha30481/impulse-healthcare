import { forwardRef, useState, type InputHTMLAttributes } from "react";
import { Check, Eye, EyeOff, Info, X } from "lucide-react";
import clsx from "clsx";
import { PASSWORD_RULES } from "@/lib/schemas";

/** Password field with a show/hide (eye) button and, optionally, an (i) button whose hover/focus
 *  panel lists the requirements and ticks them off as you type. */
export const PasswordInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { showRules?: boolean }>(
  function PasswordInput({ showRules, className, value, ...rest }, ref) {
    const [visible, setVisible] = useState(false);
    const [rulesOpen, setRulesOpen] = useState(false);
    const v = String(value ?? "");
    return (
      <div className="relative">
        <input ref={ref} type={visible ? "text" : "password"} value={value}
          className={clsx("input", showRules ? "pr-20" : "pr-11", className)} {...rest} />
        <div className="absolute inset-y-0 right-1.5 flex items-center gap-0.5">
          {showRules && (
            <span className="relative" onMouseEnter={() => setRulesOpen(true)} onMouseLeave={() => setRulesOpen(false)}>
              <button type="button" aria-label="Password requirements" aria-expanded={rulesOpen}
                onFocus={() => setRulesOpen(true)} onBlur={() => setRulesOpen(false)} onClick={() => setRulesOpen((o) => !o)}
                className="grid h-8 w-8 place-items-center rounded-lg text-ink-3 hover:bg-surface-2 hover:text-ink">
                <Info className="h-4 w-4" />
              </button>
              {rulesOpen && (
                <div role="tooltip" className="absolute bottom-full right-0 z-30 mb-2 w-72 rounded-xl border border-line bg-surface p-3 text-left shadow-lift">
                  <p className="mb-1.5 text-xs font-bold text-ink">Password must have</p>
                  <ul className="space-y-1">
                    {PASSWORD_RULES.map((r) => {
                      const ok = v.length > 0 && r.test(v);
                      return (
                        <li key={r.id} className={clsx("flex items-center gap-1.5 text-xs", ok ? "text-ok" : "text-ink-2")}>
                          {ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5 text-ink-3" />}{r.label}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </span>
          )}
          <button type="button" onClick={() => setVisible((x) => !x)} aria-label={visible ? "Hide password" : "Show password"}
            aria-pressed={visible} className="grid h-8 w-8 place-items-center rounded-lg text-ink-3 hover:bg-surface-2 hover:text-ink">
            {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
    );
  },
);
