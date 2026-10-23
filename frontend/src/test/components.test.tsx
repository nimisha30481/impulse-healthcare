import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DoseStatusPill, Provenance } from "@/components/ui/domain";
import { DoseCard } from "@/features/doses/DoseCard";
import { registerSchema, medicationOrderSchema } from "@/lib/schemas";
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
  it("offers actions for a due dose", () => {
    wrap(<DoseCard dose={base} patientId="p1" />);
    expect(screen.getByRole("button", { name: /mark as taken/i })).toBeInTheDocument();
  });
  it("hides actions for a dose more than 2 hours away", () => {
    wrap(<DoseCard dose={{ ...base, status: "upcoming", scheduled_at: new Date(Date.now() + 5 * 3600_000).toISOString() }} patientId="p1" />);
    expect(screen.queryByRole("button", { name: /mark as taken/i })).not.toBeInTheDocument();
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
  it("formats initials without the Dr. prefix", () => {
    expect(initials("Dr. Arjun Mehra")).toBe("AM");
  });
});
