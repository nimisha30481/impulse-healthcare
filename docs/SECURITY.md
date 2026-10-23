# DoseWISE — Security, Authentication & Authorisation

## 1. Authentication

| Mode | How |
|---|---|
| `AUTH_PROVIDER=local` (dev/default) | Argon2id password hashes; strength rule (10+ chars, 3 classes); email verification via single-use hashed tokens (24 h); lockout 15 min after 5 failures; per-IP/per-email rate limits; TOTP MFA (pyotp) with 8 argon2-hashed one-time backup codes; MFA mandatory to disable-protect for doctor/support/admin. |
| `AUTH_PROVIDER=cognito` | Hosted UI authorization-code flow; the backend exchanges the code with the client secret, verifies the ID token signature (JWKS), issuer, audience and `token_use`, then opens an DoseWISE session. First Cognito sign-in creates a **patient** account only. |

Sessions: 256-bit random token in an `HttpOnly`, `SameSite=Lax`, `Secure` (in AWS) cookie; only an
HMAC of it is stored. Server-side expiry (12 h), revocation, "sign out everywhere", session list with
device/IP, login history. Password reset revokes all sessions. Nothing sensitive is kept in
`localStorage` (only the theme name before sign-in). The query cache is cleared on sign-out.

CSRF: double-submit token bound to the server session; every POST/PUT/PATCH/DELETE must send
`X-CSRF-Token`.

Demo login: only when `ENVIRONMENT in (development, test)` **and** `ENABLE_DEMO_LOGIN=true`; returns 404
otherwise; only accounts flagged `is_demo`.

## 2. Authorisation

- Roles: patient, caregiver, doctor, support, admin. Registration allows patient/caregiver/doctor only;
  doctors start `pending` and get no clinical access until staff verify registration; support accounts
  are created by admins; admins have **no** clinical access by role.
- Every patient-scoped endpoint calls `services/permissions.authorize_patient(user, patient_id, scope)`:
  - patient → own record only;
  - caregiver → active, unexpired `CareRelationship` containing the scope (no scope exists for
    prescribing, editing records/diagnoses or granting permissions);
  - doctor → verified **and** active, unexpired `DoctorPatientAccess` (patient grant, appointment
    booking — 90 days — or referral), or a live break-glass grant for read scopes;
  - support → only patients on cases assigned to them, contact scope only.
- Denials are audited (`access_denied`). Doctor patient lists contain only authorised patients; search
  never reveals others.
- Break-glass: justification ≥ 20 chars, read-only, 1 hour, patient notified, ops alert, admin review.
- Revocation is effective on the next request everywhere (API, SSE refetch, download links issued
  afterwards). Presigned S3 links live 5 minutes. Already-downloaded data cannot be recalled (stated in UI).

## 3. Application security controls

Input validation (Pydantic, Zod), output encoding (React), parameterised SQL (SQLAlchemy), upload
validation by magic bytes/size/script-bearing PDFs, private storage with path-traversal guard,
security headers (`nosniff`, `DENY` framing, referrer policy, `no-store` on API), CORS locked to the
frontend origin, rate limiting (in-process locally; API Gateway throttling in AWS), optimistic locking
on prescriptions, idempotency keys on dose responses, generic text on SMS/email.

## 4. Audit

`audit_logs` rows hold identifiers and context only (no record contents, secrets or tokens), chained
by SHA-256 (`prev_hash` → `hash`). `GET /api/admin/audit` verifies the chain and is itself audited.
Logged: logins/failures, record reads/uploads/downloads/exports, prescription create/change/
discontinue, permission grant/revoke, emergency access, clinical brief generation, support case
access, OCR verification, interaction reviews. CloudTrail covers AWS API activity.

Production hardening: stream audit rows to an append-only store (S3 Object Lock / CloudTrail Lake) so
a database administrator cannot rewrite the whole chain.

## 5. AWS security configuration

- KMS CMK with rotation for S3, DynamoDB, RDS, SNS, Step Functions logs, CloudTrail. Key policy grants
  only the stack roles and the CloudTrail/Logs services.
- S3: Block Public Access, TLS-only policy, versioning, access logging, owner-enforced; GuardDuty
  Malware Protection recommended.
- RDS: private isolated subnets, SG only from Lambda SG, encrypted, IAM auth enabled, Multi-AZ + 35-day
  backups in prod, deletion protection.
- Lambda: least-privilege grants per resource; secrets read from Secrets Manager at start-up.
- IAM Identity Center permission sets: `ImpulseDeveloper` (read-only infra, no data-plane access),
  `ImpulseAdministrator` (break-glass admin, MFA, short sessions). Separate accounts for dev / test /
  staging / prod via AWS Organizations. Developers never get production patient data.
- Encryption is not authorisation: application checks remain mandatory.

## 6. Compliance position

HIPAA applies only where DoseWISE operates as/for a covered entity or business associate. For an Indian
launch, assess the Digital Personal Data Protection Act 2023 and its Rules (consent, notice, data
principal rights, breach notification, cross-border transfer), Telemedicine Practice Guidelines,
applicable state rules and CERT-In directions. Privacy, consent and retention settings are
configurable for legal review. **DoseWISE claims no compliance or certification.**

## 7. Incident response (outline)

1. Detect (CloudWatch alarms → SNS, GuardDuty, audit-chain verification failure, user report).
2. Contain: revoke sessions (`user_sessions`), disable accounts, rotate KMS grants/secrets, block IPs at CloudFront/WAF.
3. Assess scope from audit log + CloudTrail; preserve evidence (snapshot, log export).
4. Notify per jurisdiction (e.g. CERT-In within 6 hours; Data Protection Board and affected data principals under DPDP) — legal to confirm.
5. Recover from backups (see DATA_GOVERNANCE.md), post-incident review, update controls.
