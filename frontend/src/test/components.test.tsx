import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DoseStatusPill, Provenance } from "@/components/ui/domain";
import { DoseCard } from "@/features/doses/DoseCard";
import { password, registerSchema, medicationOrderSchema } from "@/lib/schemas";
import { calcQuantity } from "@/features/prescriptions/PrescriptionForm";
import { initials } from "@/lib/format";
import type { Dose } from "@/lib/types";

function wrap(ui: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

describe("status display", () => {
  it("never relies on colour alone: every dose status has words", () => {
    render(<DoseStatusPill status="unconfirmed" />);
    expect(screen.getByText("Unconfirmed")).toBeInTheDocument();
  });
  it("labels unverified OCR data", () => {
    render(<Provenance value="ocr_extracted" />);
    expect(screen.getByText(/unverified/i)).toBeInTheDocument();
  });
});

describe("DoseCard", () => {
  const base: Dose = { id: "d1", item_id: "i1", scheduled_at: new Date(Date.now() - 60_000).toISOString(), status: "due",
    medicine: "Metformin", generic_name: "Metformin", strength: "500 mg", dose: "1 tablet", route: "oral", version_no: 1 };
  it("offers Log dosage for a due dose and no 'Logged today' before it is saved", () => {
    wrap(<DoseCard dose={base} patientId="p1" />);
    expect(screen.getByRole("button", { name: /log dosage/i })).toBeInTheDocument();
    expect(screen.queryByText(/logged today/i)).not.toBeInTheDocument();
  });
  it("shows 'Logged today' only for a saved log", () => {
    wrap(<DoseCard dose={{ ...base, status: "taken_reported", responded_at: new Date().toISOString() }} patientId="p1" />);
    expect(screen.getByText(/logged today/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /log dosage/i })).not.toBeInTheDocument();
  });
  it("hides actions for a dose more than 2 hours away", () => {
    wrap(<DoseCard dose={{ ...base, status: "upcoming", scheduled_at: new Date(Date.now() + 5 * 3600_000).toISOString() }} patientId="p1" />);
    expect(screen.queryByRole("button", { name: /log dosage/i })).not.toBeInTheDocument();
    expect(screen.getByText(/you can respond from/i)).toBeInTheDocument();
  });
  it("is read-only for caregivers without check-in permission", () => {
    wrap(<DoseCard dose={base} patientId="p1" actor="caregiver" readOnly />);
    expect(screen.queryByRole("button", { name: /confirm taken/i })).not.toBeInTheDocument();
  });
});

describe("validation", () => {
  it("rejects weak passwords and doctor sign-up without registration", () => {
    const r = registerSchema.safeParse({ role: "doctor", full_name: "A B", email: "a@b.com", password: "password", confirm: "password", accept_terms: true });
    expect(r.success).toBe(false);
  });
  it("requires a dose time unless as-needed", () => {
    const base = { generic_name: "Metformin", strength: "500 mg", dosage_form: "tablet", dose_amount: 1, dose_unit: "tablet", route: "oral",
      frequency_label: "Daily", start_date: "2026-01-01" };
    expect(medicationOrderSchema.safeParse({ ...base, times_of_day: [], is_prn: false }).success).toBe(false);
    expect(medicationOrderSchema.safeParse({ ...base, times_of_day: [], is_prn: true }).success).toBe(true);
    expect(medicationOrderSchema.safeParse({ ...base, times_of_day: ["25:00"], is_prn: false }).success).toBe(false);
  });
  it("applies the password rules: 8+, upper, lower, number, only $ or _", () => {
    const ok = (p: string) => password.safeParse(p).success;
    expect(ok("Str0ng_Pass")).toBe(true);
    expect(ok("Str0ng$x")).toBe(true);
    expect(ok("Str0ng!Pass")).toBe(false); // "!" not allowed
    expect(ok("str0ng_pass")).toBe(false); // no upper-case
    expect(ok("Sh0_rt")).toBe(false); // too short
  });
  it("requires a 10-digit mobile number", () => {
    const base = { role: "patient", full_name: "A B", email: "a@b.com", password: "Str0ng_Pass", confirm: "Str0ng_Pass", accept_terms: true };
    expect(registerSchema.safeParse({ ...base, phone: "98765" }).success).toBe(false);
    expect(registerSchema.safeParse({ ...base, phone: "9876543210" }).success).toBe(true);
  });
  it("calculates quantity until the follow-up date", () => {
    const f = { dose_amount: 1, dose_unit: "tablet", times_of_day: ["09:00", "21:00"], start_date: "2026-10-01", end_date: "2026-10-30", interval_days: 1 };
    expect(calcQuantity(f)).toBe("60 tablets");
    expect(calcQuantity({ ...f, dose_amount: 500, dose_unit: "mg" })).toBe("60 doses (30000 mg total)");
  });
  it("formats initials without the Dr. prefix", () => {
    expect(initials("Dr. Arjun Mehra")).toBe("AM");
  });
});
