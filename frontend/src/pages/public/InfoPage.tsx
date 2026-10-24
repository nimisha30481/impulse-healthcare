import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/primitives";

const PAGES: Record<string, { title: string; intro: string; sections: [string, ReactNode][] }> = {
  privacy: {
    title: "Privacy Policy",
    intro: "Effective 23 October 2026. This policy explains what personal and health information DoseWISE collects, why, who can see it, and the choices you have. DoseWISE is a medication-management platform for patients and doctors in India. This is a project draft and must be reviewed by a qualified lawyer, including against the Digital Personal Data Protection Act, 2023, before real patients use it.",
    sections: [
      ["1. Who we are", "DoseWISE (\"we\", \"us\") operates the DoseWISE website and services. For this policy we act as the data fiduciary for account data, and as a custodian of health records that patients and their doctors create on the platform."],
      ["2. Information we collect", <ul key="c" className="list-disc space-y-1 pl-5"><li><b>Account details:</b> name, email, 10-digit mobile number, password (stored only as a secure hash) and your role (patient or doctor).</li><li><b>Doctor verification details:</b> speciality, medical council and registration number, checked before any clinical access is allowed.</li><li><b>Health information:</b> prescriptions and every change to them, dose logs (when you log a dose), allergies, conditions, appointments, uploaded reports and prescriptions, and doctors' notes.</li><li><b>Technical and security data:</b> sign-in history, device/browser type, IP address and an audit trail of who viewed or changed records.</li></ul>],
      ["3. How we use it", <ul key="u" className="list-disc space-y-1 pl-5"><li>To show your current medicines, send reminders and record the doses you log.</li><li>To let doctors you authorise view your record, write or change prescriptions, and see your dose history.</li><li>To detect duplicate medicines and documented allergies, and to flag adherence concerns.</li><li>To keep accounts secure, investigate misuse and meet legal obligations.</li><li>We do <b>not</b> sell your data, use it for advertising, or use it for research without your separate consent.</li></ul>],
      ["4. Patient Access ID", "Each patient has a Patient Access ID (for example DW-XXXXXX). Sharing it lets a doctor open your record for 15 minutes (a guest doctor sees it read-only). Each ID works only once: as soon as it is used, it stops working and you automatically get a new one. Every use is logged and you are notified."],
      ["5. Who can see your information", <ul key="w" className="list-disc space-y-1 pl-5"><li>You.</li><li>Doctors you authorise (by Access ID or by booking with them), for the purpose of your care, for a limited time.</li><li>Guest doctors who enter your Access ID: read-only, logged, and you are notified.</li><li>DoseWISE staff only for verification, support cases you raise, or security incidents, with every access audited.</li><li>Service providers who host our systems (Amazon Web Services, India region) under contract, who may not use your data for their own purposes.</li><li>Authorities, only where the law requires it.</li></ul>],
      ["6. Notifications", "Email and SMS reminders never contain medical details. They only ask you to open DoseWISE."],
      ["7. Security", "We use encryption in transit and at rest, private document storage with short-lived download links, multi-factor authentication, strict per-patient access checks on every request, and a tamper-evident audit log. No system is perfectly secure; tell us at once if you suspect misuse."],
      ["8. Retention", "Medical records are kept for the period required by Indian medical-records rules and then deleted. Closing your account stops all sign-in and sharing; records may be kept for that legal period but are not shown to anyone without a lawful reason."],
      ["9. Your rights", "You can view your information, ask us to correct it (the original is kept with an amendment trail, never silently overwritten), withdraw consent for future sharing, regenerate your Access ID, nominate someone to act for you, and raise a grievance. Contact our Grievance Officer through Help & Support. We aim to respond within 30 days."],
      ["10. Children", "Patients under 18 must be registered and managed by a parent or legal guardian."],
      ["11. Changes", "We will tell you about material changes in the app before they take effect."],
    ],
  },
  terms: {
    title: "Terms of Use",
    intro: "Effective 23 October 2026. These terms govern your use of DoseWISE. By creating an account you agree to them. This is a project draft that needs legal review before launch.",
    sections: [
      ["1. What DoseWISE is", "DoseWISE helps patients keep an up-to-date medication list, get reminders and log doses, and helps doctors prescribe, review dose history and coordinate care. It organises information; it does not replace a doctor's judgement."],
      ["2. Not emergency care", "DoseWISE does not provide emergency services, does not monitor you 24/7 and does not dispatch ambulances. In an emergency in India, call 112."],
      ["3. Not medical advice", "DoseWISE does not diagnose, prescribe or recommend changes to your medicines. Do not stop, start or double a medicine because of something in the app. Ask your doctor or pharmacist."],
      ["4. Your account", <ul key="a" className="list-disc space-y-1 pl-5"><li>Give accurate details, including a valid 10-digit mobile number.</li><li>Keep your password private and turn on two-step verification. Never share your login.</li><li>You are responsible for activity on your account. Tell us at once if it is compromised.</li></ul>],
      ["5. Doctors", <ul key="d" className="list-disc space-y-1 pl-5"><li>You must hold a valid registration with the National Medical Commission or a State Medical Council, and your details must be true. We verify them before granting clinical access.</li><li>Open a patient's record only for their care and only with their Access ID or other authorisation. Guest access is read-only and logged.</li><li>You remain responsible for every prescription and clinical decision you make.</li></ul>],
      ["6. Patients", "Log a dose only when you have actually taken it. Dose logs are shared with the doctors you authorise. Keep your Access ID private and regenerate it if you think someone has it who shouldn't."],
      ["7. Acceptable use", "No attempts to access other people's records, guess Access IDs, upload malware, scrape the service, or use it for unlawful purposes. Every access is logged and misuse may be reported to the authorities."],
      ["8. Availability", "We work to keep DoseWISE available, but it may be interrupted for maintenance or reasons beyond our control. Don't rely on it as your only reminder for critical medicines."],
      ["9. Liability", "To the extent the law allows, DoseWISE is not liable for losses arising from clinical decisions, from information entered incorrectly by users, or from service interruptions. Nothing here limits rights you have under the Consumer Protection Act, 2019."],
      ["10. Ending your account", "You can close your account from Settings → Account at any time. We may suspend accounts that break these terms."],
      ["11. Governing law", "These terms are governed by the laws of India. Disputes are subject to the courts of Bengaluru, Karnataka."],
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
      ["Trying DoseWISE", <><Link className="link" to="/register">Create an account</Link> as a patient or doctor, or sign in if you already have one.</>],
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

/** Same legal text, for showing inside a dialog (e.g. during registration, so typed details aren't lost). */
export function LegalText({ slug }: { slug: "privacy" | "terms" }) {
  const p = PAGES[slug];
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-3">{p.intro}</p>
      {p.sections.map(([h, b]) => (
        <section key={h}><h3 className="font-bold">{h}</h3><div className="mt-1 text-sm leading-relaxed text-ink-2">{b}</div></section>
      ))}
    </div>
  );
}
