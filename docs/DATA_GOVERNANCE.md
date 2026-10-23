# IMPULSE — Data Governance, Privacy, Backup & Recovery

## 1. Classification

| Class | Examples | Controls |
|---|---|---|
| Restricted health data | prescriptions, records, documents, adherence events, allergies, diagnoses | KMS encryption, per-patient authorisation, audit on access, no-store caching, never in logs/notifications |
| Confidential personal data | name, email, phone, emergency contact | authorisation, minimum-necessary views (support sees contact only) |
| Security data | password hashes, session/token hashes, MFA secrets, audit log | never returned by APIs; audit log admin-only and audited |
| Public / demo | directory demo entries, marketing content | labelled DEMO |

## 2. Ownership & sources of truth

The patient is the data principal; IMPULSE (operator) is the custodian; clinicians own the clinical
accuracy of what they record. Source-of-truth table: [ARCHITECTURE.md §4](ARCHITECTURE.md#source-of-truth).

## 3. Consent & permissions

Every grant, scope change, acceptance, revocation, expiry and data-sharing preference change writes a
`consent_records` row. Patients see consent history and access history (who accessed what, when,
under which authority). Permissions expire automatically. Caregiver missed-dose alerts require the
patient's explicit opt-in.

## 4. Patient transparency (in-product)

What is stored → Records/Medicines/Settings → Download my data · Who can access it → Care Team ·
Why it's accessed → access history shows the authority (owner, caregiver grant, doctor access,
break-glass, support case) · How to revoke → Care Team → Revoke · Request records → Download my data ·
Corrections → Records → Request a correction (original kept, amendment trail) · Privacy requests →
Help & Support.

## 5. Retention & deletion (configure after legal review)

| Data | Default retention | Notes |
|---|---|---|
| Clinical records, prescriptions, versions, medication events | per applicable medical-records law (placeholder: 7+ years after last activity) | account closure stops access, does not delete |
| Audit logs | ≥ 7 years | append-only |
| Notifications, sessions, auth tokens | 1 year / on expiry | |
| Uploaded documents (S3) | same as clinical records; non-current versions 365 days | |
| Backups | 35 days (prod) | |
| Demo data | deletable any time (`python -m app.seed --reset`, dev only) | |

## 6. Backup & recovery

| Component | Mechanism | RPO | RTO (target) |
|---|---|---|---|
| RDS PostgreSQL | automated backups + PITR (35 days prod), Multi-AZ, KMS | ≤ 5 min | ≤ 4 h |
| S3 documents | versioning, KMS; optional cross-region replication for DR | ~0 (versions) | ≤ 4 h |
| DynamoDB | PITR (35 days) | ≤ 5 min | ≤ 2 h |
| Audit evidence | CloudTrail (validated) + DB backups | — | — |
| Infrastructure | CDK in git | — | ≤ 2 h redeploy |

Consistency between documents and metadata: object keys are deterministic
(`patients/<patient_id>/<document_id>`) and the DB stores the SHA-256, so a restore is verified by
reconciling `uploaded_documents` against S3 (missing/extra objects, hash mismatch) — run after every
restore. Restore to the **same point in time** for RDS and use S3 versions at that timestamp.

Backup access is restricted to the administrator permission set; backups are encrypted with the CMK.
CloudWatch/AWS Backup failure notifications go to the SNS ops topic.

**A backup is not reliable until a restore has been tested.** Quarterly drill: restore RDS to a new
instance at T, restore S3 versions at T, run the reconciliation, run the API smoke tests, record the
result in PROJECT_CONTEXT.md.

## 7. Minimum necessary

Support sees contact details, caregiver contacts and check-in statuses — not the medical record.
Events and real-time messages carry only identifiers. SMS/email carry no clinical content. Logs contain
no record contents.
