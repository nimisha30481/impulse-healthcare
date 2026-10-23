import { z } from "zod";

/** Same rules as the backend (core/security.py). */
export const PASSWORD_RULES = [
  { id: "len", label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { id: "upper", label: "One upper-case letter (A–Z)", test: (p: string) => /[A-Z]/.test(p) },
  { id: "lower", label: "One lower-case letter (a–z)", test: (p: string) => /[a-z]/.test(p) },
  { id: "digit", label: "One number (0–9)", test: (p: string) => /\d/.test(p) },
  { id: "special", label: "One special character: $ or _", test: (p: string) => /[$_]/.test(p) },
  { id: "allowed", label: "No other symbols (only $ and _ allowed)", test: (p: string) => /^[A-Za-z0-9$_]*$/.test(p) },
];

export const password = z.string().superRefine((p, ctx) => {
  const failed = PASSWORD_RULES.find((r) => !r.test(p));
  if (failed) ctx.addIssue({ code: z.ZodIssueCode.custom, message: `Password needs: ${failed.label.toLowerCase()}` });
});

export const registerSchema = z
  .object({
    role: z.enum(["patient", "doctor"]),
    full_name: z.string().trim().min(2, "Enter your full name"),
    email: z.string().email("Enter a valid email address"),
    phone: z.string().regex(/^\d{10}$/, "Enter a 10-digit mobile number"),
    password,
    confirm: z.string(),
    accept_terms: z.literal(true, { errorMap: () => ({ message: "Please accept the terms to continue" }) }),
    speciality: z.string().optional(),
    registration_number: z.string().optional(),
    registration_council: z.string().optional(),
  })
  .refine((d) => d.password === d.confirm, { path: ["confirm"], message: "Passwords don't match" })
  .refine((d) => d.role !== "doctor" || !!d.speciality, { path: ["speciality"], message: "Choose your speciality" })
  .refine((d) => d.role !== "doctor" || !!d.registration_council, { path: ["registration_council"], message: "Choose your medical council" })
  .refine((d) => d.role !== "doctor" || /^[A-Za-z0-9/-]{3,40}$/.test((d.registration_number ?? "").trim()), {
    path: ["registration_number"], message: "Enter your registration number (letters, numbers, / or -)",
  });

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

export const hhmm = /^([01]\d|2[0-3]):[0-5]\d$/;

export const medicationOrderSchema = z
  .object({
    generic_name: z.string().trim().min(2, "Medicine name is required"),
    brand_name: z.string().optional(),
    strength: z.string().trim().min(1, "Strength is required"),
    dosage_form: z.string().min(1),
    dose_amount: z.coerce.number().positive("Dose must be more than 0").max(10000),
    dose_unit: z.string().min(1),
    route: z.string().min(1),
    frequency_label: z.string().trim().min(2, "Describe the frequency"),
    times_of_day: z.array(z.string().regex(hhmm, "Use 24-hour HH:MM")),
    is_prn: z.boolean(),
    start_date: z.string().min(10, "Start date is required"),
    end_date: z.string().optional(),
  })
  .refine((d) => d.is_prn || d.times_of_day.length > 0, { path: ["times_of_day"], message: "Add at least one dose time" })
  .refine((d) => !d.end_date || d.end_date >= d.start_date, { path: ["end_date"], message: "End date is before start date" });

export function zodErrors(err: z.ZodError): Record<string, string> {
  const out: Record<string, string> = {};
  for (const i of err.issues) out[i.path.join(".")] ??= i.message;
  return out;
}
