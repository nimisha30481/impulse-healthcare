# Impulse Healthcare: Project Context

> This is the living record for the project. It is updated after every prompt in a Claude session,
> so the latest state, decisions, and history are always here. Newest timeline entries go at the bottom.

**Last updated:** 2026-10-23
**Repository:** https://github.com/nimisha30481/impulse-healthcare (branch `main`)
**Source briefs:** `Healthcare_Medication_Coordination_Tabular.pdf` (2 pages) and the full product spec
`PROJECT prompt.pdf` (63 pages, 52 sections: "IMPULSE — Smart Healthcare & Medication Management Platform"), both on the owner's Desktop.
**Stack chosen by the owner (prompt 6):** React frontend, Python backend, SQL database, AWS cloud services.
**Product name:** **DoseWISE** on the website, README and `docs/` (renamed from IMPULSE on 2026-10-23,
prompts 10–11). The repo name, infra stack/permission-set names and internal identifiers (cookies `impulse_session`/`impulse_csrf`,
storage keys, demo emails `*@impulse.test`) still say "impulse"; references to IMPULSE below are historical.

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
with provenance and amendment (no silent overwrite); prescription upload â†’ OCR â†’ patient review â†’
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
| `frontend/src/pages/public/Blueprint.tsx` (`/blueprint`) + `docs/ROUND1_PITCH.md` | Round 1 judging material: problem & proof, why cloud, AWS selection (12 MVP services + triggered additions), architecture diagram & data flows, security, MoSCoW MVP + timeline, load / what breaks first / cost, innovation, team ownership & Q&A. |
| `.claude/launch.json` | Dev-server launch configs (backend :8000, frontend :5173). |
| `index.html` | Original "Hello World" page from prompt 2 (kept; not used by the app). |
| `PROJECT_CONTEXT.md` / `CLAUDE.md` | This living record / standing instructions. |

**How to run:** see README (seed â†’ uvicorn :8000 â†’ `npm run dev` :5173 â†’ demo login).
**Verified locally:** 26 backend + 8 frontend tests pass; typecheck and production build pass; landing,
patient dashboard, medicine detail, doctor dashboard, OCR verification, clinical brief, prescription
safety check, caregiver dashboard and support case were exercised in the browser.
**Not verified:** any live AWS integration (no AWS account/credentials in this environment).

**Environment notes**
- Windows 11, PowerShell. `git` is **not on PATH**. The copy bundled with GitHub Desktop is at
  `%LOCALAPPDATA%\GitHubDesktop\app-3.6.7\resources\app\git\cmd\git.exe`.
- Claude sessions can't authenticate to GitHub over HTTPS, so pushes have to be made from GitHub Desktop
  or a signed-in terminal.

**Sync status (2026-10-23 14:09):** `origin/main` already has `8b78958`. Local `main` is ahead by the
IMPULSE build commits (`9afe96b`, `17cc93e`, `775a6b2`, `c7348ee` and the commit that updates this line).
Push from GitHub Desktop; pushing from Claude fails because there's no GitHub login.
**Update 2026-10-23 14:09:** the owner reports pushing from GitHub Desktop, but this could not be confirmed:
`git fetch` needs a GitHub login, and this checkout's `origin/main` still points at `8b78958` (last
recorded push 11:05). Check on github.com that `main` shows commit `c47b822` or later.

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
| 7 | 2026-10-23 14:09 | Owner said they pushed from GitHub Desktop; asked to confirm `origin/main` is up to date and update this file | **Not confirmed.** `git fetch` failed (no GitHub login) and the GitHub API was unreachable from the browser. Locally, `origin/main` = `8b78958` and `main` = `c47b822` (5 ahead). Updated the sync status and added this row. (Correction to row 6: the build ran about 12:05–13:55 IST; the "14:35" end time was an estimate.) |
| 8 | 2026-10-23 15:21 | Shared the Round 1 judging rubric (70 marks, 7 criteria) and asked whether the website covers each, to implement whatever is missing, and to answer each briefly | Only partly covered before (detail lived in `docs/`, nothing on team or pitch). Added a public `/blueprint` page covering all 7 criteria (linked in the navbar, footer and landing page). Added `docs/ROUND1_PITCH.md` with ownership, demo script and Q&A. Evidence uses the WHO 2003 ~50% adherence estimate, with its known critique. Fixed: the navbar overflowed at about 1000px (desktop nav now starts at 1280px). Typecheck clean; 8 frontend tests pass. Team member names still need to be filled in. |
| 9 | 2026-10-23 15:23 | (Correction to row 7) | The push did go through: this checkout recorded a push of `34cf01f` to `origin/main` at 14:10, just after row 7 was written at 14:09. Everything up to `34cf01f` is on GitHub. Still to push: `dacec75` (blueprint page) and the commit that adds this row. |
| 10 | 2026-10-23 15:27 | Asked to rename the website from "IMPULSE" to "DoseWISE" everywhere on the website | Replaced every user-visible IMPULSE with DoseWISE in `frontend/` (41 occurrences across 22 files + `index.html` title and description) and in backend user-facing text (notification and SMS/email text, error messages, API title). Wordmark restyled as "Dose**WISE**" in mixed case. Left unchanged on purpose: repo name, docs/README, infra names, cookie and storage keys, demo emails (changing them would sign everyone out or break the demo login). Also fixed garbled characters (e.g. "â€”" instead of "—") that earlier PowerShell edits had introduced in `PublicLayout.tsx` and this file. Verified: typecheck, 8 frontend + 26 backend tests pass; no "IMPULSE" left in the visible text of the landing, patient dashboard, blueprint or privacy pages. |
| 11 | 2026-10-23 15:28 | Asked to also rename IMPULSE to DoseWISE in README.md and docs/, keeping technical identifiers unchanged | Replaced 18 brand mentions across README.md and 7 docs files (API, ARCHITECTURE, AWS_ARCHITECTURE, DATA_GOVERNANCE, PRODUCTION_READINESS, ROUND1_PITCH, SECURITY). Kept: `impulse_session`/`impulse_csrf` cookies, `impulse_dev.db`, `infra/stacks/impulse_stack.py`, `ImpulseDeveloper`/`ImpulseAdministrator` permission sets. Added a README note explaining the old name. |
| 12 | 2026-10-23 18:09 | Reported the backend folder was gone and the site showed internal server errors; asked to restore it and reconnect the Gmail and Google Calendar connectors | Nothing was deleted: `backend/` (code, `.venv`, `impulse_dev.db`) was intact and git showed no deletions. The backend **dev server** had stopped, so the frontend's `/api` calls failed. Restarted it on :8000; `/api/health` returns ok directly and through the :5173 proxy. Turned on the Gmail and Google Calendar connectors for the session (their tools load from the next prompt). Unrelated to the code: the `plugin:engineering` versions of Gmail/Calendar show 'No URL configured'. |
| 13 | 2026-10-23 19:01 | Asked why the backend keeps stopping and to keep it running permanently | Cause: the servers were Claude preview servers, tied to this session/preview, so they stop when it restarts (or when Claude restarts them for code changes). Added `start-dosewise.bat` + `scripts/keep-running.bat`: runs backend :8000 and frontend :5173 in minimised windows, restarts each within 10 s if it stops, and skips a port that's already in use. Added a Windows Startup shortcut (`%APPDATA%\...\Startup\DoseWISE servers.lnk`) so it starts at login; delete that shortcut to undo. |
| 14 | 2026-10-23 19:06 | Backend still missing from the Servers panel; asked to fix auto-restart for good | The app had stopped both preview servers and restored only the frontend; the batch launcher only ran at login. Replaced it with `scripts/dev.mjs`, a Node supervisor that restarts any stopped server within about 3 s and never starts duplicates (it checks IPv4 and IPv6; Vite set to `strictPort`). `.claude/launch.json`: 'frontend' now starts backend + frontend, and 'backend' is a separate watcher, so the site works even if only one entry is restored. The Startup shortcut runs the same supervisor. Tested: killed the backend and it came back on its own; site → API OK; no duplicate ports. Removed `scripts/keep-running.bat`. |
| 15 | 2026-10-23 21:42 | Shared `project prompt 2.pdf` (about 20 changes, mostly to the doctor interface): implement them in frontend and backend and push | **Done (backend `0cf4643` + this commit):** 10-digit mobile required; password 8+ chars with upper, lower, number, only `$`/`_` (eye + (i) buttons, live checklist); doctor speciality / Indian council (NMC + State Medical Councils) dropdowns + registration number, validated server-side via `/api/reference`; full project-specific Terms & Privacy shown in a pop-up so the form keeps its data (draft saved, password never stored); 'Active Rx' → 'Active' with explanation on hover; prescription form shortened with frequency presets, follow-up date → end date, auto-calculated quantity, Indian metric units (mcg/mg/g/kg/ml/IU + count units); sign-in: 'trust this device' removed, eye button, forgot password fixed (it rejected `.test` emails; dev shows 'Reset my password now'); modal cut-off fixed (`min-h-0`); doctor dashboard: 'Tasks requiring action' removed, 'Authorised patients' → 'Patients'; preferred name removed for doctors; whole-site language switch (hi/kn/ta/te) via DOM translator + dictionary, clinical text excluded; high contrast and reduce motion removed; Region = India + state list, date format from device, time zone and units removed; Privacy = plain points, close account moved to Account; Blueprint page removed; **dose logging**: 'Log dosage' → 'Logged today at …' only after save, no duplicate logs (stable key + server dedupe), doctor dose history (taken/late>60 min/missed/not logged) with live refresh, server-side authorised; records filter: no dates, doctor/hospital/medication dropdowns from the selected type; toasts 2 s, no stacking; main menu: patient, doctor, guest only (staff at `/login?staff=1`); **Guest Doctor Access** `/guest` → `POST /api/access/guest-view` (read-only, rate-limited, `guest_access_logs` + audit, patient notified); Patient Access ID (`DW-XXXXXX`) on the dashboard with copy and regenerate; doctors open patients by Access ID (90-day grant). Migration `0002` runs automatically on start-up (local DB upgraded in place; backup at `%TEMP%\impulse_dev_backup.db`). Tests: backend 32 pass, frontend 12 pass, typecheck and build OK; checked in the browser: register, Hindi switch, guest view, patient Access ID + Log dosage, doctor dose history (Telugu). **Server fix:** app restarts were killing the supervisor too; it now runs outside the app (and at login), and the panel entries attach to it. Bug fixed: logo 'Dose' was being translated. |
| 16 | 2026-10-23 21:43 | Owner said they pushed from GitHub Desktop; asked to confirm and update this file | **Not all pushed.** The last push this checkout recorded was at 19:03 (`08d00b7`). These 3 commits are still not on `origin/main`: `fb0e67a` (dev-server supervisor), `0cf4643` (backend for prompt 2), `78f7cd5` (frontend for prompt 2), plus the commit that adds this row. (`git fetch` can't run here without a GitHub login, so this is based on the local record of the remote.) |
| 17 | 2026-10-23 21:44 | Owner pushed again from GitHub Desktop; asked to re-check | **Confirmed:** pushed at 21:43; `origin/main` = `8196b91`, matching local `main`. Everything through prompt 2 is on GitHub. Only this row (and its commit) is new and not yet pushed. |
