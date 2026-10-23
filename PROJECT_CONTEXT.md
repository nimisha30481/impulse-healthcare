# Impulse Healthcare: Project Context

> This is the living record for the project. It is updated after every prompt in a Claude session,
> so the latest state, decisions, and history are always here. Newest timeline entries go at the bottom.

**Last updated:** 2026-10-23
**Repository:** https://github.com/nimisha30481/impulse-healthcare (branch `main`)
**Source briefs:** `Healthcare_Medication_Coordination_Tabular.pdf` (2 pages) and the full product spec
`PROJECT prompt.pdf` (63 pages, 52 sections: "IMPULSE — Smart Healthcare & Medication Management Platform"), both on the owner's Desktop.
**Stack chosen by the owner (prompt 6):** React frontend, Python backend, SQL database, AWS cloud services.

---

## 1. Problem Statement: Patient–Doctor Medication Coordination

Patients often get prescriptions from several doctors. Their medication schedules, dosage changes,
allergies, and treatment histories can end up scattered across different hospitals and pharmacies.
That leads to duplicated medication, missed doses, wrong administration, and dangerous drug interactions.

## 2. Minimum Viable Product (MVP)

The MVP is a centralised healthcare coordination platform. Doctors, patients, and authorised
pharmacies/caregivers use it to coordinate medication administration securely. The system should:

- [ ] Maintain a patient's current medication profile.
- [ ] Allow doctors to prescribe, modify, or discontinue medicines.
- [ ] Detect potential drug–drug interactions.
- [ ] Track whether prescribed medicines were actually taken.
- [ ] Alert patients about missed or upcoming doses.
- [ ] Notify doctors/caregivers about significant adherence problems.
- [ ] Maintain a complete history of prescriptions and dosage changes.
- [ ] Allow patients to locate nearby pharmacies/hospitals with the required medication.

### 2a. Expanded scope (`PROJECT prompt.pdf`)

IMPULSE is a full product, not just the MVP above: a public marketing site; role-aware auth (sign-up,
email verification, MFA, recovery, sessions; no privilege by self-selected role; doctor verification);
separate **patient, doctor, caregiver, care-coordinator (support) and admin** portals; versioned
prescriptions with validated status transitions; a reminder engine with honest dose statuses
(reported taken / missed / unconfirmed — never assumed); structured human escalation; medical records
with provenance and amendment (no silent overwrite); prescription upload → OCR → patient review →
doctor verification; interaction checking only from a licensed source ("unavailable" otherwise);
source-linked automatic clinical briefs; appointment booking without double booking; emergency
assistance that never claims to dispatch responders; a healthcare directory (no invented stock);
settings (5 languages, themes, region, notifications, privacy); fine-grained consent-based
permissions with break-glass; audit logging; WCAG-conscious accessibility; synthetic demo data; tests;
and an AWS architecture using every listed service with honest status reporting. Brand: deep teal /
mint, Manrope + Inter, tagline "Better medication management. More connected care."

## 3. Suggested AWS Architecture

| Module / Functional Area | Suggested AWS Tools |
|---|---|
| Patient Medication Profile & History | Amazon HealthLake, Amazon DynamoDB, Amazon S3 |
| Doctor Prescription & Management | Amazon API Gateway, AWS Lambda, Amazon Cognito |
| Drug–Drug Interaction Detection | Amazon Bedrock, Amazon Comprehend Medical, AWS Step Functions |
| Medication Adherence & Dose Tracking | Amazon Timestream, AWS AppSync, Amazon DynamoDB |
| Alerts & Notifications | Amazon Simple Notification Service (SNS), Amazon Pinpoint, Amazon EventBridge |
| Pharmacy & Hospital Location Finder | Amazon Location Service, Amazon OpenSearch Service |
| Security & Compliance | AWS Key Management Service (KMS), AWS CloudTrail, AWS IAM Identity Center |

**Decisions (2026-10-23):** Amazon Pinpoint is replaced by SES + AWS End User Messaging (Pinpoint
end of support 30 Oct 2026); Timestream for LiveAnalytics is replaced by Timestream for InfluxDB
(closed to new customers June 2025); Amazon Textract added for OCR. Full matrix:
[docs/AWS_ARCHITECTURE.md](docs/AWS_ARCHITECTURE.md).

## 4. Expected Outcome

The platform gives doctors, pharmacies, and caregivers one real-time source of truth for patient
prescriptions and treatment histories. Medical NLP drives real-time drug-interaction detection,
and automated dose alerts go out on several channels. Together these aim to:

- prevent adverse drug events
- improve medication adherence
- make essential medicines easier to find nearby
- keep data secure and private to HIPAA-compliant standards

---

## 5. Current State of the Repository

| Path | Purpose |
|---|---|
| `README.md` | Overview, quick start, demo personas, tests, layout. |
| `backend/` | FastAPI + SQLAlchemy app: `app/api` (routers), `app/services` (prescriptions, schedules, reminder/escalation engine, booking, interactions, OCR, clinical brief, notifications, real-time, FHIR), `app/models` (48 tables), `app/integrations` (S3/local storage, Cognito, one adapter per AWS service, status registry), `app/seed.py` (fictional demo data), `migrations/` (Alembic), `tests/` (26 pytest), `Dockerfile` (Lambda image), `.env.example`. |
| `frontend/` | Vite + React + TS + Tailwind: public site, auth pages, patient / doctor / caregiver / support / admin portals, shared Notifications, Settings, Messages, Find Care, Platform status; `src/test` (8 vitest). |
| `infra/` | AWS CDK v2 (Python) stack: KMS, S3, DynamoDB, Cognito, RDS PostgreSQL, Lambda ×3, API Gateway, EventBridge, Step Functions, SNS, SES, CloudTrail, CloudFront, alarms, budget; optional OpenSearch/Location/HealthLake/Identity Center. |
| `docs/` | ARCHITECTURE, AWS_ARCHITECTURE (service matrix, deployment, costs, limitations, test results), SECURITY, DATA_GOVERNANCE (backup & recovery), API, PRODUCTION_READINESS. |
| `.claude/launch.json` | Dev-server launch configs (backend :8000, frontend :5173). |
| `index.html` | Original "Hello World" page from prompt 2 (kept; not used by the app). |
| `PROJECT_CONTEXT.md` / `CLAUDE.md` | This living record / standing instructions. |

**How to run:** see README (seed → uvicorn :8000 → `npm run dev` :5173 → demo login).
**Verified locally:** 26 backend + 8 frontend tests pass; typecheck and production build pass; landing,
patient dashboard, medicine detail, doctor dashboard, OCR verification, clinical brief, prescription
safety check, caregiver dashboard and support case were exercised in the browser.
**Not verified:** any live AWS integration (no AWS account/credentials in this environment).

**Environment notes**
- Windows 11, PowerShell. `git` is **not on PATH**. The copy bundled with GitHub Desktop is at
  `%LOCALAPPDATA%\GitHubDesktop\app-3.6.7\resources\app\git\cmd\git.exe`.
- Claude sessions can't authenticate to GitHub over HTTPS, so pushes have to be made from GitHub Desktop
  or a signed-in terminal.

**Sync status:** local `main` is 2 commits ahead of `origin`. Commit `b81248d` (Hello World) and the commit
that added this file and `CLAUDE.md` have not been pushed.

## 6. Open Items / Next Steps

- [x] Commit `PROJECT_CONTEXT.md` and `CLAUDE.md`.
- [ ] Push pending commits to `origin/main` (needs GitHub sign-in via GitHub Desktop).
- [x] Choose the stack and build the application (React / FastAPI / SQL / AWS).
- [x] Expand `README.md`. (`index.html` kept as-is; delete it if no longer wanted.)
- [ ] Deploy `infra/` to a dev AWS account and run the 20 live AWS integration tests (docs/PRODUCTION_READINESS.md).
- [ ] Contract a licensed drug-interaction knowledge source and a reviewed medicine-education source.
- [ ] Add the AppSync Events API and Timestream for InfluxDB to the CDK stack; write the OpenSearch indexing job.
- [ ] CI pipeline; Playwright end-to-end tests; professional translation review; legal/clinical review.

---

## 7. Timeline / History

| # | Date & time (IST) | Prompt / event | Outcome |
|---|---|---|---|
| 1 | 2026-10-23 10:46 | Repository created on GitHub | Commit `ad93761` "Initial commit" (`README.md`, `.gitignore`). |
| 2 | 2026-10-23 10:55 | Asked: create a Hello World `index.html`, then stage, commit, and push | `index.html` created and committed as `b81248d`. **Push failed** because a GitHub login was needed; the user must push manually. |
| 3 | 2026-10-23 ~10:57 | Shared the project brief PDF and asked for a `.md` file that keeps the full project context, history, and timeline, updated after every prompt | Created `PROJECT_CONTEXT.md` (this file) from the PDF, plus `CLAUDE.md` with the standing rule to update it after each prompt. Not yet committed. |
| 4 | 2026-10-23 11:01 | New session: re-sent the brief (as a screenshot) with the same request for a context/history/timeline `.md` updated after every prompt | Checked `PROJECT_CONTEXT.md`: it already exists and sections 1–4 match the screenshot word for word, so it was kept, not recreated. Added this row. `CLAUDE.md` and `PROJECT_CONTEXT.md` are still untracked (not committed). `main` is 1 commit ahead of `origin`. |
| 5 | 2026-10-23 11:03 | Asked: commit `PROJECT_CONTEXT.md` and `CLAUDE.md` to `main` | Both files committed together with this row in the commit "Add project context and Claude instructions" (run `git log` for the hash; a commit can't contain its own hash). `main` is now 2 commits ahead of `origin`, not pushed. |
| 6 | 2026-10-23 12:05–14:35 | Shared `PROJECT prompt.pdf` (63-page IMPULSE spec) and asked to build it with a React frontend, Python backend, SQL database and AWS services, update all files, and push as needed | Built the full application in three commits: `9afe96b` backend (FastAPI, 48-table SQL schema, auth + MFA + CSRF, resource-level permissions, versioned prescriptions, reminder/escalation engine, booking, OCR verification, interaction checks, clinical briefs, audit hash chain, AWS adapters, seed, 26 tests); `17cc93e` React frontend (landing site, auth, 5 role portals, design system, 8 tests); `775a6b2` CDK infra, Alembic, Lambda handlers, docs, README. A final commit adds this row and the synth result (`cdk synth` passes, 106 resources). Verified in the browser: landing, patient dashboard/medicine detail, doctor dashboard, OCR verification, clinical brief, safety check, caregiver, support case. Fixed during testing: interaction "checks run" list wasn't persisted; dose buttons shown too early; support check-ins listed future doses; nav wrapping. **Not done:** no live AWS deploy/tests (no credentials); **push failed again** (no GitHub login) — user must push via GitHub Desktop. Decisions: SQLite locally / PostgreSQL in AWS; Pinpoint → SES + End User Messaging; Timestream LiveAnalytics → Timestream for InfluxDB; Textract added. |
