# Impulse Healthcare: Project Context

> This is the living record for the project. It is updated after every prompt in a Claude session,
> so the latest state, decisions, and history are always here. Newest timeline entries go at the bottom.

**Last updated:** 2026-10-23
**Repository:** https://github.com/nimisha30481/impulse-healthcare (branch `main`)
**Source brief:** `Healthcare_Medication_Coordination_Tabular.pdf` (2 pages, on the owner's Desktop)

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

| File | Purpose |
|---|---|
| `README.md` | Placeholder title only (`# impulse-healthcare`). |
| `.gitignore` | Default ignore rules from repo creation. |
| `index.html` | Minimal "Hello World" page (placeholder; no app code yet). |
| `PROJECT_CONTEXT.md` | This file: project context, history, and timeline. |
| `CLAUDE.md` | Tells Claude to keep this file updated after every prompt. |

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
- [ ] Choose the application stack and scaffold the project (frontend + AWS backend).
- [ ] Replace the placeholder `index.html` and expand `README.md`.

---

## 7. Timeline / History

| # | Date & time (IST) | Prompt / event | Outcome |
|---|---|---|---|
| 1 | 2026-10-23 10:46 | Repository created on GitHub | Commit `ad93761` "Initial commit" (`README.md`, `.gitignore`). |
| 2 | 2026-10-23 10:55 | Asked: create a Hello World `index.html`, then stage, commit, and push | `index.html` created and committed as `b81248d`. **Push failed** because a GitHub login was needed; the user must push manually. |
| 3 | 2026-10-23 ~10:57 | Shared the project brief PDF and asked for a `.md` file that keeps the full project context, history, and timeline, updated after every prompt | Created `PROJECT_CONTEXT.md` (this file) from the PDF, plus `CLAUDE.md` with the standing rule to update it after each prompt. Not yet committed. |
| 4 | 2026-10-23 11:01 | New session: re-sent the brief (as a screenshot) with the same request for a context/history/timeline `.md` updated after every prompt | Checked `PROJECT_CONTEXT.md`: it already exists and sections 1–4 match the screenshot word for word, so it was kept, not recreated. Added this row. `CLAUDE.md` and `PROJECT_CONTEXT.md` are still untracked (not committed). `main` is 1 commit ahead of `origin`. |
| 5 | 2026-10-23 11:03 | Asked: commit `PROJECT_CONTEXT.md` and `CLAUDE.md` to `main` | Both files committed together with this row in the commit "Add project context and Claude instructions" (run `git log` for the hash; a commit can't contain its own hash). `main` is now 2 commits ahead of `origin`, not pushed. |
