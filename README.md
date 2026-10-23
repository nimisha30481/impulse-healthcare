# DoseWISE — Smart Healthcare & Medication Management

> Better medication management. More connected care.

DoseWISE connects **patients, doctors, caregivers and care coordinators** around one trustworthy medication
record: versioned prescriptions, dose reminders with honest adherence tracking, appointment booking,
medical records, caregiver permissions, human escalation, and an AWS cloud architecture behind it.

All demo data is **fictional**. DoseWISE makes **no regulatory compliance claims**.

> DoseWISE was previously called IMPULSE. Technical identifiers keep the old name so nothing breaks:
> the repository, cookies (`impulse_session`, `impulse_csrf`), the local database file, demo emails
> (`*@impulse.test`) and AWS stack/permission-set names.

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript (Vite), Tailwind CSS, Framer Motion, Lucide, Recharts, Zod, TanStack Query |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | PostgreSQL in AWS (RDS); SQLite for zero-setup local development |
| Cloud | AWS — Cognito, API Gateway, Lambda, DynamoDB, S3, KMS, CloudTrail, EventBridge, Step Functions, SNS, SES, End User Messaging, HealthLake, AppSync, Bedrock, Timestream for InfluxDB, OpenSearch, Location Service, IAM Identity Center (see [docs/AWS_ARCHITECTURE.md](docs/AWS_ARCHITECTURE.md)) |
| IaC | AWS CDK v2 (Python) in [`infra/`](infra/) |

## Quick start (local, ~5 minutes)

Prerequisites: Python 3.11+, Node 20+.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed --reset        # creates backend/impulse_dev.db with fictional demo data
uvicorn app.main:app --reload --port 8000
```

```bash
# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173  (proxies /api to :8000)
```

**Or just double-click `start-dosewise.bat`** (it also starts automatically at Windows login). It runs
both servers and restarts either one within seconds if it stops. The backend upgrades the database
schema itself on start-up (Alembic), so no manual migration step is needed.

Open http://localhost:5173. The main menu has three ways in: **Patient**, **Doctor** (Log In → demo
persona, development only, no password) and **Guest Doctor Access** (no account needed).

| Way in | Shows |
|---|---|
| Patient — Ananya (Access ID `DW-ANANYA`) | Access ID card, Log dosage → "Logged today", adherence, appointment, records |
| Patient — Rahul (`DW-RAHULV`) | unconfirmed doses → escalation |
| Doctor — Dr. Mehra | open a patient by Access ID, prescribe (frequency presets, quantity autofill), dose history (taken / late / missed / not logged), verification, briefs |
| Guest Doctor Access (`/guest`) | read-only chart for an Access ID; every attempt logged, patient notified |
| Staff personas | caregiver, coordinator, admin: `/login?staff=1` |

Account rules: mobile number required (10 digits); password at least 8 characters with an upper-case
letter, a lower-case letter, a number and `$` or `_` (no other symbols); doctors choose a speciality
and an Indian medical council (NMC or a State Medical Council) and enter their registration number.
Interface languages: English, Hindi, Kannada, Tamil, Telugu (header selector; clinical text is never translated).

Without AWS credentials every integration uses a documented local fallback and **says so** in the
UI (Settings → Platform status). Email/SMS show as "not sent (provider not configured)"; drug–drug
interaction checking shows as **unavailable** rather than "no interactions found".

Optional: copy `backend/.env.example` to `backend/.env` to use PostgreSQL or enable AWS services.

## Tests

```bash
cd backend && .venv\Scripts\python -m pytest -q      # 32 API/integration tests
cd frontend && npm test && npm run typecheck && npm run build
```

Covered: registration, login + lockout, CSRF, MFA, role escalation prevention, unverified doctors,
unauthorised record access (+ audit of denials), caregiver invite/accept/authorise/scope/revoke,
prescription create/edit (versioning, optimistic locking)/discontinue/invalid transitions,
reminders (no duplicates, idempotent responses), unconfirmed → escalation → support case,
concurrent booking (double-booking prevention), upload validation, OCR never auto-activates,
interaction-source failure is not reported as safe, duplicate-therapy & allergy checks,
notification without provider not marked sent, clinical brief sources & missing info, audit tamper detection.

## Repository layout

```
backend/   FastAPI app (app/api, app/services, app/models, app/integrations), tests, Alembic migrations, Dockerfile
frontend/  React app (src/pages per portal, src/features shared workflows, src/components design system)
infra/     AWS CDK stack
docs/      Architecture, AWS, security, data governance, API, production readiness
PROJECT_CONTEXT.md   living project record (updated every prompt)
```

## Documentation

- [Application architecture & database](docs/ARCHITECTURE.md)
- [AWS architecture, service matrix, deployment, costs, limitations](docs/AWS_ARCHITECTURE.md)
- [Security, authentication & authorisation design](docs/SECURITY.md)
- [Data governance, privacy, backup & recovery](docs/DATA_GOVERNANCE.md)
- [API reference](docs/API.md) — live OpenAPI at http://localhost:8000/api/docs
- [Production readiness checklist](docs/PRODUCTION_READINESS.md)

## Important limitations

DoseWISE is a development build. It is not a certified medical device, does not dispatch emergency
services (call **112** in India), does not provide 24/7 monitoring, and does not contain a drug
interaction database — a licensed clinical knowledge source must be connected for drug–drug checks.
