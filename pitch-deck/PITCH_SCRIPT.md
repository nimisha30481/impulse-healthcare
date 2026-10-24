# DoseWISE — 2-minute pitch (≈300 words)

**Hook (15 s)**
An elderly patient sees a cardiologist, an endocrinologist and a GP. Three prescriptions, three hospitals, and nobody sees the full list. The WHO estimates only about half of patients with chronic disease take their medicines as prescribed. The result: duplicated drugs, missed doses, dangerous interactions.

**Solution (20 s)**
DoseWISE is one shared, versioned medication record that follows the patient. Doctors prescribe, change or stop a medicine, and every version is kept. Patients get reminders and log each dose as taken, late or missed. Caregivers see only what the patient allows. In an emergency, any doctor can open a read-only chart with the patient's Access ID.

**Live demo moments (30 s)**
- Dr. Mehra prescribes. Duplicate therapy, allergies and an **Amazon Bedrock** AI interaction screen run instantly, clearly marked unverified until a licensed drug database confirms it.
- Ananya logs her dose. Her doctor's adherence view updates in real time through **AWS AppSync**.
- A guest doctor opens her chart for 15 minutes. That Access ID then dies automatically and a new one is issued.

**AWS architecture (35 s)**
Eleven AWS services are live in Mumbai, ap-south-1, and each one is tested:
- **Cognito** signs users in, with email verification codes and two-step verification (MFA).
- **DynamoDB** keeps an idempotent mirror of every dose event.
- Uploaded documents go to **S3**, encrypted with **KMS**.
- **EventBridge** carries domain events, and **Step Functions** records every interaction-check workflow.
- **SNS** and **SES** send alerts and email; they replace Pinpoint, which reaches end of support on 30 October 2026.
- **Location Service** finds nearby pharmacies and hospitals.
- **Bedrock** also translates the whole interface into Hindi, Kannada, Tamil and Telugu.
- Every access is audited in a tamper-evident, hash-chained log, alongside CloudTrail.

**Honest scope (10 s)**
- HealthLake, Timestream and OpenSearch are designed in and switch on at scale.
- API Gateway and Lambda deploy from our CDK stack.
- Comprehend Medical isn't offered in Mumbai, so we keep health data in India.

**Proof and impact (10 s)**
45 backend and 12 frontend automated tests pass. Every page across 5 roles opens with zero errors. A 1,000-patient pilot is estimated to cost about 70 to 95 dollars a month.

**Close (5 s)**
DoseWISE: better medication management, more connected care. Thank you.
