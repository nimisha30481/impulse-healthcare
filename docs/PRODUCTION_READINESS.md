# DoseWISE — Production Readiness Checklist

Legend: ✅ done in repo · ⬜ not done.

## Product & safety
- ✅ Required user flows 1–17 implemented end to end locally (flows 1–17 in the brief)
- ✅ Unverified OCR never activates prescriptions; unconfirmed ≠ missed; no fabricated interactions
- ⬜ Clinical safety review (clinical safety officer) of all patient-facing wording
- ⬜ Licensed drug-interaction knowledge source contracted and connected
- ⬜ Reviewed medication-education source connected
- ⬜ Professional translation review (kn, hi, te, ta)
- ⬜ Staffed support hours defined and shown in-product

## Security
- ✅ Server-side authorisation on every patient endpoint; denials audited
- ✅ Argon2, MFA, lockout, CSRF, secure cookies, upload validation, security headers
- ✅ Hash-chained audit log
- ⬜ External penetration test
- ⬜ WAF on CloudFront (rate rules, bot control)
- ⬜ Audit log export to immutable storage
- ⬜ Secrets rotation schedule (RDS secret, provider keys)
- ⬜ GuardDuty + Malware Protection for S3 + Security Hub enabled

## AWS integration tests (all ⬜ — require an AWS account)
1 Cognito authentication · 2 API Gateway authorisation/throttling · 3 Lambda prescription workflows ·
4 HealthLake store/retrieve · 5 DynamoDB event handling (duplicates) · 6 S3 upload/presigned access ·
7 Step Functions execution (retry, timeout, failure alert) · 8 Bedrock summary (citation validation) ·
9 Comprehend Medical extraction · 10 Interaction source (success, timeout, error) · 11 AppSync authorised
updates · 12 Timestream for InfluxDB writes · 13 SNS ops alerts · 14 SES + End User Messaging (Pinpoint
replacement) delivery receipts · 15 EventBridge processing + DLQ · 16 Location search · 17 OpenSearch
indexing · 18 KMS encryption/key policy · 19 CloudTrail validation · 20 Identity Center access.
Each with: service failure, missing credentials, expired session, unauthorised request, duplicate event,
concurrent update, retry, failed notification, wrong permission, permission revocation, sync failure.

## Operations
- ✅ IaC (CDK), alarms → SNS, budget alert, environment separation by stack name
- ⬜ `cdk synth/deploy` validated in a real account; separate AWS accounts per environment
- ⬜ CI pipeline (tests, typecheck, build, cdk synth, dependency scanning)
- ⬜ Backup restore drill performed and recorded
- ⬜ Load test of booking and reminder tick
- ⬜ On-call runbooks

## Legal & compliance
- ⬜ Privacy policy, terms and consent text reviewed by counsel
- ⬜ DPDP assessment (and HIPAA BAA if applicable); data-residency decision for Comprehend Medical/Bedrock
- ⬜ Retention schedule confirmed per jurisdiction
- ⬜ Clinician-verification procedure with medical councils documented
