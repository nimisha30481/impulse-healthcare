# DoseWISE AWS setup guide

This guide covers DynamoDB, Cognito, Bedrock, SNS and Location Service. The code for all five is
already in the backend. Each one stays switched off until its settings are added to `backend/.env`.

**Fast path (about 10 minutes):** do Step 0, then run one script. It creates every resource and
writes the settings for you. Steps 1–5 explain what it does, and how to do it by hand if you prefer.

**Where to type the commands:** in a terminal opened in the project folder. In VS Code use
**Terminal → New Terminal**, or open PowerShell and run:
```bash
cd C:\Users\nimis\OneDrive\Documents\GitHub\impulse-healthcare
```

---

## Update the AWS user's permissions (once, about 2 minutes)

The `DoseWISE` IAM user needs the permissions in [aws-iam-policy.json](aws-iam-policy.json) for SMS
testing and the extra services. The file is too long for an inline policy, so create a normal one:

1. AWS console → **IAM → Policies → Create policy → JSON**.
2. Delete what's there and paste the whole contents of `docs/aws-iam-policy.json`.
3. Choose **Next**, name it `DoseWISE-app`, then **Create policy**.
4. **IAM → Users → DoseWISE → Add permissions → Attach policies directly**. Tick `DoseWISE-app`,
   then **Add permissions**. You can remove the older DoseWISE policy afterwards.

## Turn on the remaining services (one command)

```bash
backend\.venv\Scripts\python.exe scripts\aws_setup.py --extras --ses-email you@gmail.com
```

This turns on:

| Service | What it does |
|---|---|
| S3 + KMS | Private, encrypted document storage |
| EventBridge | Domain events |
| Step Functions | Records each interaction-check workflow |
| AppSync Events | Real-time updates |
| SES | DoseWISE emails, sent from your address |

AWS emails a link to the SES address; click it. Until SES leaves its sandbox, emails only go to
verified addresses.

Some services stay off on purpose, and Platform status says why:

| Service | Why it's off |
|---|---|
| HealthLake, OpenSearch, Timestream | Billed every hour they exist |
| Comprehend Medical | Not offered in the Mumbai region |
| API Gateway, Lambda | Only exist in a full AWS deployment (`infra/`) |
| Drug-interaction database | Needs a licence (Bedrock AI screening covers the gap meanwhile) |

## Step 0. Sign in to AWS once (on this PC)

1. Create an AWS account at <https://aws.amazon.com> if you don't have one.
2. Install the AWS CLI v2:
   ```bash
   winget install Amazon.AWSCLI
   ```
   Close the terminal and open a new one.
3. In the AWS console, open **IAM → Users → Create user** (e.g. `dosewise-dev`).
   - Attach the policy in [aws-iam-policy.json](aws-iam-policy.json) (Create policy → JSON → paste it).
   - Open the user, go to **Security credentials → Create access key → "Local code"**.
4. Run this command and paste in the key, the secret, region `ap-south-1` and output `json`:
   ```bash
   aws configure
   ```
   The keys are saved in `%USERPROFILE%\.aws`, outside the project. Never put them in code or `.env`.

## The one command

```bash
backend\.venv\Scripts\python.exe scripts\aws_setup.py
```

The script:
- creates the DynamoDB table, the SNS topic, the Location place index, and a Bedrock model that works;
- writes everything into `backend/.env`;
- is safe to re-run.

Useful extras:

| Add this | What it does |
|---|---|
| `--verify-phone 9876543210` | Texts a code to that number and asks you for it. This lets the SMS sandbox send to that phone (Step 4). |
| `--cognito` | Creates the Cognito user pool, app client and sign-in domain, and switches login to Cognito (Step 2). |
| `--bedrock-model <id>` | Use a specific Bedrock model instead of letting the script pick one. |

Then **restart the backend**: close the backend window, and the DoseWISE supervisor restarts it.

**Check it worked:** sign in, then open **Settings → Platform status**. Each service should now show
**Configured**.

---

## Step 1. Amazon DynamoDB: medication-event store

DynamoDB **works alongside** the main SQL database. It does not replace it. Patients, prescriptions
and audit stay in SQL (PostgreSQL/RDS in AWS). Every dose event is also mirrored to DynamoDB, and
duplicates are refused by a conditional write.

By hand:
1. Console → **DynamoDB → Create table**. Name `dosewise-medication-events`, partition key `pk`
   (String), sort key `sk` (String).
2. Under table settings choose **Customize → On-demand**, then create the table.
3. Add `DYNAMODB_EVENTS_TABLE=dosewise-medication-events` to `backend/.env`.

**Test:** log a dose. In the table, choose **Explore items** and you should see `PATIENT#…` / `EVENT#…`.

## Step 2. Amazon Cognito: user sign-in

1. Console → **Cognito → Create user pool**. Choose **Traditional web application**, sign-in with
   **Email**, name `dosewise-users`.
   - Return URL: `http://localhost:8000/api/auth/cognito/callback`
2. Open the pool and go to **Sign-in → MFA**. Choose **Optional** and **Authenticator apps**.
3. Under **App clients**, open the client. Copy the **Client ID** and **Client secret**.
   - Under **Login pages**, check that the scopes are `openid email phone profile`.
4. Under **Domain**, copy the domain. It looks like `xxxx.auth.ap-south-1.amazoncognito.com`.
5. Add these lines to `backend/.env`:
   ```
   AUTH_PROVIDER=cognito
   COGNITO_REGION=ap-south-1
   COGNITO_USER_POOL_ID=ap-south-1_XXXX
   COGNITO_CLIENT_ID=...
   COGNITO_CLIENT_SECRET=...
   COGNITO_DOMAIN=xxxx.auth.ap-south-1.amazoncognito.com
   ```

How it works once switched on:
- DoseWISE's **own** sign-up and sign-in forms stay, with every field the brief requires (mobile,
  doctor council and registration number, and so on). Behind them, Cognito stores the account and
  the password.
- New users get a **6-digit code by email** to verify. "Forgot password" also emails a code.
- The app client must allow `ALLOW_USER_PASSWORD_AUTH`, and the pool's minimum password length
  must be **8** to match DoseWISE's rule. The script sets both (pool `dosewise-accounts`).
- Accounts made before the switch, and the demo logins, keep working with their local passwords.
- Two-step verification (TOTP) and doctor verification still run in DoseWISE as before.
- Cognito's built-in email sender allows about 50 emails a day. For more, connect Amazon SES in
  the pool's **Messaging** settings.
- To go back to local login, set `AUTH_PROVIDER=local`.

## Step 3. Amazon Bedrock: AI drug–drug interaction screening

1. Console → region **Asia Pacific (Mumbai)** → **Bedrock → Model catalog**. Open a model such as
   **Amazon Nova Lite**.
   - If it asks, request or accept access. Anthropic models ask a one-time use-case question.
2. Copy the model ID or the inference-profile ID (e.g. `apac.amazon.nova-lite-v1:0`).
3. Add these lines to `backend/.env`:
   ```
   BEDROCK_MODEL_ID=<the id>
   BEDROCK_REGION=ap-south-1
   BEDROCK_INTERACTION_SCREENING=true
   ```

How it shows up:
- When a doctor prescribes two or more medicines, the safety check adds **"AI screening"** results.
- Every AI result is labelled *AI-generated, unverified*.
- Medicines the AI invents that aren't on the list are discarded.
- **An empty AI result is never shown as "no interactions".** A licensed drug-interaction source
  (`INTERACTION_SOURCE`) is still needed before the check counts as complete.

**Test:** as a doctor, prescribe Warfarin and then Aspirin to the same patient. You should see an
"Ai Screening" alert.

## Step 4. Amazon SNS: SMS alerts

New AWS accounts are in the **SMS sandbox**, which can only text phone numbers you verify. To get
a test SMS:

1. **Verify your phone.** Choose one:
   - **Console:** **SNS → Text messaging (SMS) → Sandbox destination phone numbers → Add phone
     number**. Enter `+91` and your 10 digits, then type the code AWS texts you.
   - **Terminal:** run the command below (replace the number). It texts you a code and waits for
     you to type it in. This needs the updated permissions above.
     ```bash
     backend\.venv\Scripts\python.exe scripts\aws_setup.py --verify-phone 9XXXXXXXXX
     ```
2. **Spend limit:** on the same SNS page, open **Text messaging preferences → Edit**. The account
   limit starts at USD 1/month. Raising it above USD 1 needs a quick request in **Service quotas**
   or **Support**.
3. `SNS_SMS_ENABLED=true` is already in `backend/.env` (the script set it).
4. **In DoseWISE:** add your mobile number to your profile. Then turn on **Settings →
   Notifications → SMS** for the reminders you want.

**Sending to Indian numbers (required by TRAI):** register on a DLT portal (Jio, Airtel, Vi and so on).
1. Register an entity ID, a 6-letter sender ID (e.g. `DOSEWS`), and one transactional template.
   The template text is:
   `DoseWISE: you have a new {#var#}. Open the app to view it.`
2. Add these lines to `backend/.env`:
   ```
   SNS_SMS_SENDER_ID=DOSEWS
   SNS_DLT_ENTITY_ID=<entity id>
   SNS_DLT_TEMPLATE_ID=<template id>
   ```
3. When ready to text anyone, request **production access** (exit the sandbox) in the SNS console.

SMS texts are generic on purpose. Medicine names never go over SMS.
`SNS_OPS_TOPIC_ARN`, which the script fills in, is for server alerts to the team. Subscribe your
email to that topic in the console.

## Step 5. Amazon Location Service: pharmacies and hospitals near you

1. Console → **Amazon Location → Place indexes → Create**. Name `dosewise-places`, data provider
   **Esri** (or HERE), intended use **Single use**.
2. Add `LOCATION_PLACE_INDEX=dosewise-places` to `backend/.env`.

**Test:** open **Find Care** and type a place in **Near…** (e.g. "Koramangala, Bengaluru"). Results
are then sorted by real distance.

---

## Costs (rough, for development use)

| Service | Cost |
|---|---|
| DynamoDB on-demand, Location, Cognito (≤ 10k users) | Usually ₹0 to a few rupees a month at this scale |
| Bedrock | Paid per token. Nova Lite is fractions of a rupee per check |
| SNS SMS to India | Paid per message |

Set an **AWS Budget** alert (Billing → Budgets), for example USD 5.

## Troubleshooting

| What you see | Fix |
|---|---|
| `Not signed in to AWS` | Run `aws configure` again (Step 0) |
| `AccessDenied…` | The IAM user is missing a permission. Attach [aws-iam-policy.json](aws-iam-policy.json) |
| Bedrock "no model could be called" | Accept model access in the console (Step 3) and re-run |
| Platform status still "Not configured" | Restart the backend after editing `.env` |
| SMS shows "failed" | The number isn't verified in the sandbox, or DLT IDs are missing for India |
