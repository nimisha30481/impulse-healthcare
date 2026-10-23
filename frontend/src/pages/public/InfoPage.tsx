import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/primitives";

const PAGES: Record<string, { title: string; intro: string; sections: [string, ReactNode][] }> = {
  privacy: {
    title: "Privacy Policy",
    intro: "Draft for development. Final wording requires legal review for the jurisdiction DoseWISE operates in (for an Indian launch, including the Digital Personal Data Protection framework).",
    sections: [
      ["What we store", "Account details, medication records, appointments, documents you upload, and records your care team adds. Each record shows where it came from (clinician-verified, patient-reported, OCR-extracted, imported)."],
      ["Who can access it", "You; doctors you grant access to or book with (time-limited); caregivers you invite and authorise with specific permissions; care coordinators only for cases assigned to them. Administrators have no clinical access by role."],
      ["Why it is accessed", "To provide care coordination. Every sensitive access is logged and visible to you under Care Team → Access history."],
      ["Your controls", "Revoke access at any time, download your data, request corrections, and close your account under Settings. Revocation stops new access immediately; it cannot recall information someone already downloaded."],
      ["Retention", "Clinical records are retained for the period required by applicable law and then deleted per policy. Retention periods are configurable per jurisdiction."],
      ["Notifications", "SMS and email contain no medical details — only a prompt to sign in."],
    ],
  },
  terms: {
    title: "Terms of Use",
    intro: "Draft for development; requires legal review.",
    sections: [
      ["Not emergency care", "DoseWISE does not provide emergency services or dispatch responders. Call 112 in an emergency."],
      ["Not medical advice", "DoseWISE organises information from your care team. It does not diagnose, prescribe or recommend medication changes."],
      ["Accounts", "Keep your credentials private. Caregivers must use their own accounts, never a patient's credentials."],
    ],
  },
  security: {
    title: "Security",
    intro: "How DoseWISE protects accounts and health information.",
    sections: [
      ["Authentication", "Argon2-hashed passwords, authenticator-app MFA with backup codes, HttpOnly session cookies, CSRF protection, lockout after repeated failures. Amazon Cognito can be enabled for hosted identity."],
      ["Authorisation", "Every patient-data request is checked on the server against active, unexpired grants. Front-end role checks are cosmetic only."],
      ["Data protection", "Encryption in transit (TLS) and at rest (KMS-managed keys in AWS). Documents are stored privately and downloaded through short-lived links."],
      ["Audit", "Sensitive actions are recorded in a hash-chained, tamper-evident audit log, alongside AWS CloudTrail for infrastructure activity."],
      ["Reporting a vulnerability", "Please contact the security team via the Contact page. Do not include patient information in reports."],
    ],
  },
  accessibility: {
    title: "Accessibility",
    intro: "DoseWISE is designed for older adults and people with disabilities, with WCAG 2.2 AA as the target.",
    sections: [
      ["Features", "Keyboard navigation, visible focus, screen-reader labels, larger text options, high-contrast mode, reduced motion, touch-friendly controls, and statuses that never rely on colour alone."],
      ["Known gaps", "Full screen-reader testing on all portals and professional review of non-English interface text are still in progress."],
      ["Feedback", "Tell us about any barrier through the Contact page."],
    ],
  },
  contact: {
    title: "Contact",
    intro: "This is a development build. No support line is staffed yet.",
    sections: [
      ["General", "Use the Help & Support area inside the app to report a concern; it creates a case for a care coordinator during staffed hours."],
      ["Emergencies", "Call 112."],
    ],
  },
  help: {
    title: "Help",
    intro: "Quick answers.",
    sections: [
      ["Trying DoseWISE", <>Use <Link className="link" to="/login">the demo login</Link> to explore every portal with fictional data.</>],
      ["Why does a dose say 'Unconfirmed'?", "Nobody responded to the reminder. DoseWISE doesn't assume it was taken or missed."],
      ["Why is interaction checking 'unavailable'?", "Drug–drug checking needs a licensed clinical knowledge source. Until one is connected, DoseWISE says so rather than implying safety."],
    ],
  },
  "404": { title: "Page not found", intro: "The page you're looking for doesn't exist or has moved.", sections: [] },
};

export default function InfoPage({ slug }: { slug: string }) {
  const p = PAGES[slug] ?? PAGES["404"];
  return (
    <div className="container-page max-w-3xl py-16">
      <h1 className="text-4xl font-extrabold">{p.title}</h1>
      <p className="mt-4 text-ink-2">{p.intro}</p>
      <div className="mt-10 space-y-6">
        {p.sections.map(([h, b]) => (
          <section key={h} className="card p-6">
            <h2 className="text-lg font-bold">{h}</h2>
            <div className="mt-2 text-[15px] leading-relaxed text-ink-2">{b}</div>
          </section>
        ))}
      </div>
      {slug === "404" && <Link to="/"><Button className="mt-8">Back to home</Button></Link>}
    </div>
  );
}
