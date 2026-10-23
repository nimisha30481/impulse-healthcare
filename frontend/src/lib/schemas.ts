import { z } from "zod";

export const password = z
  .string()
  .min(10, "Use at least 10 characters")
  .refine(
    (p) => [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(p)).length >= 3,
    "Mix at least three of: lower-case, upper-case, numbers, symbols",
  );

export const registerSchema = z
  .object({
    role: z.enum(["patient", "caregiver", "doctor"]),
    full_name: z.string().trim().min(2, "Enter your full name"),
    email: z.string().email("Enter a valid email address"),
    phone: z.string().optional(),
    password,
    confirm: z.string(),
    accept_terms: z.literal(true, { errorMap: () => ({ message: "Please accept the terms to continue" }) }),
    speciality: z.string().optional(),
    registration_number: z.string().optional(),
    registration_council: z.string().optional(),
  })
  .refine((d) => d.password === d.confirm, { path: ["confirm"], message: "Passwords don't match" })
  .refine((d) => d.role !== "doctor" || (d.speciality && d.registration_number), {
    path: ["registration_number"],
    message: "Doctors must provide speciality and registration number",
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
