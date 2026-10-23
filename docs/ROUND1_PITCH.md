# DoseWISE — Round 1 pitch notes (Mentoring + Judging, 70 marks)

The public page **/blueprint** on the website covers every criterion below, in the same order. Use it
as the presentation backbone. Replace "Member 1–4" with real names, and make sure each person can
answer the questions for their own part without notes.

| # | Criterion (marks) | Where it is shown | One-line answer |
|---|---|---|---|
| 1 | Problem & use case (10) | /blueprint#problem, landing "Problem" | Adults on several long-term medicines from several doctors; there's no shared, versioned medication record, and missed doses go unnoticed. WHO estimates adherence at about 50% (figure disputed; we validate with a pilot). It needs the cloud because the record must be shared across people and places and reminders must fire when apps are closed. |
| 2 | AWS selection (15) | /blueprint#aws, docs/AWS_ARCHITECTURE.md | 12 MVP services, each with one job. 9 more are added only at a named trigger. Pinpoint (end of support) and Timestream LiveAnalytics (closed to new customers) are replaced. |
| 3 | Architecture & security (15) | /blueprint#architecture, docs/SECURITY.md | One domain → API Gateway → Lambda, where every request is checked against the patient's grants → RDS/S3/DynamoDB. EventBridge/Step Functions handle follow-ups. KMS encrypts everything. IAM roles mean no keys in code; the DB password lives in Secrets Manager. |
| 4 | Feature plan & scope (10) | /blueprint#mvp | MoSCoW list; the Must list is the brief's 8 MVP points and already works with demo data. 8-week path to a 30-patient pilot. |
| 5 | Scalability & cost (10) | /blueprint#scale | Pilot: 1k patients, ~4k doses/day. Breaks first: DB connections (→ RDS Proxy), then the reminder tick (→ SQS sharding), then live updates (→ AppSync). About $70–95/month for a pilot and $360–720/month at 50k patients, with SMS and optional services off. |
| 6 | Innovation (5) | /blueprint#innovation | Honest adherence states, doctor-verified OCR, safety checks that say "unavailable", a source-linked clinical brief, consent-scoped caregivers, human escalation. |
| 7 | Team & pitch (5) | /blueprint#pitch | Each member owns one area (table below) and demos it. |

## Ownership

| Member | Owns | Demo moment |
|---|---|---|
| 1 — Product | problem, users, scope, pilot | Landing page → Blueprint §1 and §4 |
| 2 — Backend | prescriptions, reminders, permissions, booking | Doctor edits a prescription (version 2 appears; a stale edit is rejected) |
| 3 — Cloud & security | AWS services, CDK, IAM/KMS, cost | Blueprint §2, §3 and §5; `infra/stacks/impulse_stack.py` |
| 4 — Frontend & UX | portals, accessibility | Patient dashboard → caregiver view → dark mode / large text |

## Demo script (3 minutes)

1. Landing → "Healthcare shouldn't feel disconnected" plus the WHO evidence (30 s).
2. Log in as **Doctor** (demo login) → Prescription Verification → approve the uploaded prescription.
   Then open Ananya → Prescriptions → Edit → Check safety. It shows "Drug interaction checking is
   currently unavailable" and a duplicate-therapy alert (60 s).
3. Log in as **Patient** → the new medicine appears with versions and history; log in as **Caregiver** → scoped view (30 s).
4. Blueprint §3 diagram + data flow A (45 s).
5. Cost and what breaks first (15 s).

## Questions to rehearse (answer from facts, never guess)

- **"Has it run on AWS?"** Not yet. The CDK stack synthesizes (106 resources). Live deployment and 20 integration tests are the next milestone. Locally, every AWS feature has a tested fallback, and the Platform status page shows which are configured.
- **"Why so many services?"** The MVP needs 12. The others are listed with the trigger that would justify them, and none is deployed before that.
- **"Why PostgreSQL and DynamoDB?"** Relational integrity and transactions for prescriptions, consent and bookings. DynamoDB only for idempotent event writes.
- **"How do you stop a caregiver seeing everything?"** Server-side `authorize_patient` checks an active, unexpired grant with the exact scope on every request. Revocation applies on the next request, and denials are audited.
- **"Where are the AWS keys?"** There are none. Lambdas use IAM roles; the RDS secret is in Secrets Manager; `.env` is git-ignored.
- **"Is the 50% adherence figure solid?"** It's the WHO's estimate and widely cited, but a 2012 paper questions its evidence base, so the pilot measures our own baseline.
- **"Compliance?"** We claim none. The controls exist, and a DPDP/HIPAA legal review is a planned step.
- **"What if the AI is wrong?"** AI (Bedrock) only rewords verified facts, and any output that cites something not in its input is discarded. It never diagnoses, prescribes or detects interactions.

Sources: [WHO 2003 press release](https://www.who.int/news/item/01-07-2003-failure-to-take-prescribed-medicine-for-chronic-diseases-is-a-massive-world-wide-problem) ·
[Critique of the 50% figure (PMC3525884)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3525884) ·
[Pinpoint end of support](https://docs.aws.amazon.com/pinpoint/latest/userguide/migrate.html) ·
[Timestream LiveAnalytics availability](https://docs.aws.amazon.com/timestream/latest/developerguide/AmazonTimestreamForLiveAnalytics-availability-change.html)
