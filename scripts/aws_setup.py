"""One-command AWS setup for DoseWISE. Creates (or reuses) the AWS resources and writes their
names into backend/.env, then the dev supervisor's backend restart picks them up.

Run from the repo root after signing in to AWS (`aws configure` or `aws configure sso`):

    backend\\.venv\\Scripts\\python.exe scripts\\aws_setup.py
    backend\\.venv\\Scripts\\python.exe scripts\\aws_setup.py --cognito          # also switch sign-in to Cognito
    backend\\.venv\\Scripts\\python.exe scripts\\aws_setup.py --verify-phone 9876543210   # SNS SMS sandbox

Safe to re-run: every step reuses what already exists. No secret is printed.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "backend" / ".env"
NAME = "dosewise"
CALLBACK = "http://localhost:8000/api/auth/cognito/callback"
# Tried in order; the first one this account can actually call is used.
BEDROCK_PREFERENCES = ["nova-lite", "nova-micro", "nova-pro", "claude"]


def ok(msg):
    print(f"  [ok]   {msg}")


def warn(msg):
    print(f"  [skip] {msg}")


def code(e: ClientError) -> str:
    return e.response.get("Error", {}).get("Code", "")


def current_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    pairs = (l.split("=", 1) for l in ENV_FILE.read_text(encoding="utf-8").splitlines() if "=" in l and not l.startswith("#"))
    return {k.strip(): v.strip() for k, v in pairs if v.strip()}


def write_env(values: dict[str, str]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else [
        "# Written by scripts/aws_setup.py. Never commit this file."
    ]
    pending = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    lines += [f"{k}={v}" for k, v in pending.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dynamodb(s, env):
    db = s.client("dynamodb")
    table = f"{NAME}-medication-events"
    try:
        db.create_table(
            TableName=table,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            SSESpecification={"Enabled": True},
        )
        db.get_waiter("table_exists").wait(TableName=table)
        ok(f"DynamoDB table {table} created")
    except ClientError as e:
        if code(e) != "ResourceInUseException":
            raise
        ok(f"DynamoDB table {table} already exists")
    env["DYNAMODB_EVENTS_TABLE"] = table


def sns(s, env, verify_phone):
    topic = s.client("sns").create_topic(Name=f"{NAME}-ops-alerts")["TopicArn"]  # idempotent
    ok("SNS ops-alert topic ready")
    env["SNS_OPS_TOPIC_ARN"] = topic
    env["SNS_SMS_ENABLED"] = "true"
    if verify_phone:
        digits = "".join(c for c in verify_phone if c.isdigit())[-10:]
        phone = f"+91{digits}"
        client = s.client("sns")
        try:
            client.create_sms_sandbox_phone_number(PhoneNumber=phone, LanguageCode="en-US")
        except ClientError as e:
            if code(e) not in ("OptedOutException",):
                print(f"  [warn] could not send verification code: {e}")
                return
        otp = input(f"  Enter the code AWS just texted to {phone}: ").strip()
        client.verify_sms_sandbox_phone_number(PhoneNumber=phone, OneTimePassword=otp)
        ok(f"{phone} verified for the SMS sandbox")


def location(s, env):
    loc = s.client("location")
    index = f"{NAME}-places"
    try:
        loc.create_place_index(IndexName=index, DataSource="Esri",
                               DataSourceConfiguration={"IntendedUse": "SingleUse"},
                               Description="DoseWISE Find Care geocoding")
        ok(f"Location place index {index} created")
    except ClientError as e:
        if code(e) != "ConflictException":
            raise
        ok(f"Location place index {index} already exists")
    env["LOCATION_PLACE_INDEX"] = index


def bedrock(s, env, region, wanted):
    candidates = [wanted] if wanted else []
    if not wanted:
        br = s.client("bedrock", region_name=region)
        ids = [p["inferenceProfileId"] for p in br.list_inference_profiles().get("inferenceProfileSummaries", [])]
        ids += [m["modelId"] for m in br.list_foundation_models(byOutputModality="TEXT")["modelSummaries"]
                if "ON_DEMAND" in m.get("inferenceTypesSupported", [])]
        for pref in BEDROCK_PREFERENCES:
            candidates += [i for i in ids if pref in i and i not in candidates]
    rt = s.client("bedrock-runtime", region_name=region)
    for model in candidates:
        try:
            rt.converse(modelId=model, messages=[{"role": "user", "content": [{"text": "Reply OK"}]}],
                        inferenceConfig={"maxTokens": 5})
        except ClientError:
            continue
        ok(f"Bedrock model {model} answered")
        env.update(BEDROCK_MODEL_ID=model, BEDROCK_REGION=region, BEDROCK_INTERACTION_SCREENING="true")
        return
    warn("no Bedrock model could be called. Open the Bedrock console > Model catalog, open a model "
         "(e.g. Amazon Nova Lite), accept access, then re-run this script.")


def cognito(s, env, region, account):
    idp = s.client("cognito-idp")
    # Matches DoseWISE's own password rule (8+ chars, upper, lower, number), so the app's sign-up form
    # and Cognito never disagree. Supersedes the earlier "dosewise-users" pool (10-char minimum).
    pool_name = f"{NAME}-accounts"
    pool = next((p["Id"] for p in idp.list_user_pools(MaxResults=60)["UserPools"] if p["Name"] == pool_name), None)
    if not pool:
        pool = idp.create_user_pool(
            PoolName=pool_name,
            UsernameAttributes=["email"],
            AutoVerifiedAttributes=["email"],
            Policies={"PasswordPolicy": {"MinimumLength": 8, "RequireUppercase": True, "RequireLowercase": True,
                                         "RequireNumbers": True, "RequireSymbols": False}},
            AccountRecoverySetting={"RecoveryMechanisms": [{"Priority": 1, "Name": "verified_email"}]},
        )["UserPool"]["Id"]
        idp.set_user_pool_mfa_config(UserPoolId=pool, MfaConfiguration="OPTIONAL",
                                     SoftwareTokenMfaConfiguration={"Enabled": True})
        ok(f"Cognito user pool {pool_name} created (email sign-in, TOTP MFA optional)")
    else:
        ok(f"Cognito user pool {pool_name} already exists")
    clients = idp.list_user_pool_clients(UserPoolId=pool, MaxResults=60)["UserPoolClients"]
    client_id = next((c["ClientId"] for c in clients if c["ClientName"] == f"{NAME}-web"), None)
    if not client_id:
        client_id = idp.create_user_pool_client(
            UserPoolId=pool, ClientName=f"{NAME}-web", GenerateSecret=True,
            AllowedOAuthFlows=["code"], AllowedOAuthFlowsUserPoolClient=True,
            AllowedOAuthScopes=["openid", "email", "phone", "profile"],
            CallbackURLs=[CALLBACK], SupportedIdentityProviders=["COGNITO"],
            # DoseWISE's own sign-in form sends the password to Cognito server-side
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
            PreventUserExistenceErrors="ENABLED",
        )["UserPoolClient"]["ClientId"]
        ok("Cognito app client created")
    secret = idp.describe_user_pool_client(UserPoolId=pool, ClientId=client_id)["UserPoolClient"]["ClientSecret"]
    prefix = f"{NAME}-login-{account[-6:]}"
    domain = idp.describe_user_pool(UserPoolId=pool)["UserPool"].get("Domain")
    if not domain:
        idp.create_user_pool_domain(Domain=prefix, UserPoolId=pool)
        domain = prefix
        ok("Cognito hosted sign-in domain created")
    env.update(AUTH_PROVIDER="cognito", COGNITO_REGION=region, COGNITO_USER_POOL_ID=pool,
               COGNITO_CLIENT_ID=client_id, COGNITO_CLIENT_SECRET=secret,
               COGNITO_DOMAIN=f"{domain}.auth.{region}.amazoncognito.com", COGNITO_REDIRECT_URI=CALLBACK)


# ---------------- extras (--extras): needs the wider policy in docs/aws-iam-policy.json ----------------
def kms_and_s3(s, env, region, account):
    kms = s.client("kms")
    alias = f"alias/{NAME}-documents"
    try:
        key = kms.describe_key(KeyId=alias)["KeyMetadata"]["Arn"]
        ok("KMS key already exists")
    except ClientError as e:
        if code(e) != "NotFoundException":
            raise
        key = kms.create_key(Description="DoseWISE private documents (S3 SSE-KMS)")["KeyMetadata"]["Arn"]
        kms.create_alias(AliasName=alias, TargetKeyId=key)
        kms.enable_key_rotation(KeyId=key)
        ok("KMS key created (yearly rotation on)")
    env["KMS_KEY_ID"] = key
    s3 = s.client("s3")
    bucket = f"{NAME}-documents-{account}-{region}"
    try:
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": region})
        ok(f"S3 bucket {bucket} created")
    except ClientError as e:
        if code(e) not in ("BucketAlreadyOwnedByYou",):
            raise
        ok(f"S3 bucket {bucket} already exists")
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={"Rules": [{
        "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms", "KMSMasterKeyID": key}, "BucketKeyEnabled": True}]})
    s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    ok("S3: public access blocked, KMS encryption and versioning on")
    env["S3_DOCUMENTS_BUCKET"] = bucket


def eventbridge(s, env):
    ev = s.client("events")
    bus = f"{NAME}-events"
    try:
        ev.create_event_bus(Name=bus)
        ok(f"EventBridge bus {bus} created")
    except ClientError as e:
        if code(e) != "ResourceAlreadyExistsException":
            raise
        ok(f"EventBridge bus {bus} already exists")
    env["EVENTBRIDGE_BUS_NAME"] = bus


def step_functions(s, env, account):
    iam = s.client("iam")
    role = f"{NAME}-sfn-role"
    try:
        role_arn = iam.get_role(RoleName=role)["Role"]["Arn"]
    except ClientError as e:
        if code(e) != "NoSuchEntity":
            raise
        role_arn = iam.create_role(RoleName=role, AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "states.amazonaws.com"},
                                                    "Action": "sts:AssumeRole"}]}))["Role"]["Arn"]
        time.sleep(10)  # new roles take a moment to become usable
    # Records each interaction assessment as an auditable workflow run. The clinical checks themselves
    # run in the API; in a full AWS deployment (infra/) this machine also drives the Lambda follow-up.
    definition = {"Comment": "DoseWISE interaction assessment", "StartAt": "RecordAssessment", "States": {
        "RecordAssessment": {"Type": "Pass", "Parameters": {"assessment_id.$": "$.assessment_id",
                                                            "patient_id.$": "$.patient_id", "status": "recorded"},
                             "Next": "Done"},
        "Done": {"Type": "Succeed"}}}
    sfn = s.client("stepfunctions")
    name = f"{NAME}-interaction-assessment"
    arn = f"arn:aws:states:{s.region_name}:{account}:stateMachine:{name}"
    try:
        sfn.describe_state_machine(stateMachineArn=arn)
        ok("Step Functions state machine already exists")
    except ClientError as e:
        if code(e) != "StateMachineDoesNotExist":
            raise
        arn = sfn.create_state_machine(name=name, roleArn=role_arn, definition=json.dumps(definition))["stateMachineArn"]
        ok("Step Functions state machine created")
    env["SFN_INTERACTION_STATE_MACHINE_ARN"] = arn


def ses(s, env, email):
    if not email:
        warn("SES: pass --ses-email you@example.com to send DoseWISE emails from that address")
        return
    sv = s.client("sesv2")
    try:
        sv.create_email_identity(EmailIdentity=email)
        ok(f"SES: AWS emailed a verification link to {email}. Click it, then emails start working")
    except ClientError as e:
        if code(e) != "AlreadyExistsException":
            raise
        status = sv.get_email_identity(EmailIdentity=email).get("VerificationStatus")
        ok(f"SES identity {email} already added (status: {status})")
    env["SES_FROM_ADDRESS"] = email


def appsync(s, env):
    saved = current_env()
    if saved.get("APPSYNC_EVENTS_HTTP_ENDPOINT") and saved.get("APPSYNC_EVENTS_API_KEY"):
        ok("AppSync Events already linked (endpoint and key in backend/.env)")
        return
    a = s.client("appsync")
    name = f"{NAME}-events"
    api = next((x for x in a.list_apis().get("apis", []) if x["name"] == name), None)
    if not api:
        mode = [{"authType": "API_KEY"}]
        api = a.create_api(name=name, eventConfig={"authProviders": mode, "connectionAuthModes": mode,
                                                   "defaultPublishAuthModes": mode, "defaultSubscribeAuthModes": mode})["api"]
        a.create_channel_namespace(apiId=api["apiId"], name="users")  # app publishes to /users/<id>
        ok("AppSync Events API created")
    else:
        api = a.get_api(apiId=api["apiId"])["api"]  # the list summary has no "dns" endpoints
        ok("AppSync Events API already exists")
    key = current_env().get("APPSYNC_EVENTS_API_KEY")  # reuse, so re-runs don't pile up keys
    if not key:
        key = a.create_api_key(apiId=api["apiId"], description="DoseWISE backend",
                               expires=int(time.time()) + 360 * 86400)["apiKey"]["id"]
    env.update(APPSYNC_EVENTS_HTTP_ENDPOINT=f"https://{api['dns']['HTTP']}", APPSYNC_EVENTS_API_KEY=key)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--profile", help="AWS CLI profile name (default: your default profile)")
    ap.add_argument("--cognito", action="store_true", help="create Cognito and switch sign-in to it")
    ap.add_argument("--verify-phone", help="Indian mobile number to verify for the SNS SMS sandbox")
    ap.add_argument("--bedrock-model", help="use this Bedrock model/inference-profile ID instead of auto-picking")
    ap.add_argument("--extras", action="store_true",
                    help="also set up S3+KMS, EventBridge, Step Functions, AppSync (and SES with --ses-email)")
    ap.add_argument("--ses-email", help="email address DoseWISE sends from (AWS emails it a verification link)")
    a = ap.parse_args()

    try:
        s = boto3.Session(profile_name=a.profile, region_name=a.region)
        account = s.client("sts").get_caller_identity()["Account"]
    except (NoCredentialsError, ProfileNotFound, ClientError) as e:
        sys.exit(f"Not signed in to AWS ({e.__class__.__name__}). Run `aws configure` first; see docs/AWS_SETUP_GUIDE.md.")
    print(f"AWS account ...{account[-4:]}, region {a.region}")

    env = {"AWS_REGION": a.region}
    steps = [("DynamoDB", lambda: dynamodb(s, env)),
             ("SNS", lambda: sns(s, env, a.verify_phone)),
             ("Location Service", lambda: location(s, env)),
             ("Bedrock", lambda: bedrock(s, env, a.region, a.bedrock_model))]
    if a.cognito:
        steps.append(("Cognito", lambda: cognito(s, env, a.region, account)))
    if a.extras or a.ses_email:
        steps.append(("SES email", lambda: ses(s, env, a.ses_email)))
    if a.extras:
        steps += [("S3 + KMS", lambda: kms_and_s3(s, env, a.region, account)),
                  ("EventBridge", lambda: eventbridge(s, env)),
                  ("Step Functions", lambda: step_functions(s, env, account)),
                  ("AppSync Events", lambda: appsync(s, env))]
    failed = []
    for name, step in steps:
        print(f"\n{name}")
        try:
            step()
        except ClientError as e:
            print(f"  [fail] {code(e)}: {e.response.get('Error', {}).get('Message', '')}")
            if code(e) == "SubscriptionRequiredException":
                print("         Not a DoseWISE or permission problem: AWS hasn't activated this service on the account yet.\n"
                      "         This usually clears within 24 hours of account sign-up; re-run this command later.")
            failed.append(name)
        except Exception as e:  # noqa: BLE001 - one service's problem must not stop the others or the .env write
            print(f"  [fail] {type(e).__name__}: {e}")
            failed.append(name)

    write_env(env)
    print(f"\nWrote {len(env)} settings to backend/.env.")
    restart_backend()
    if failed:
        sys.exit(f"Not set up: {', '.join(failed)}. See the reason above, then re-run this command.")


def restart_backend():
    """Stops the backend on :8000; the DoseWISE supervisor starts it again with the new settings."""
    import subprocess

    bat = ROOT / "restart-backend.bat"
    if sys.platform == "win32" and bat.exists():
        subprocess.run(["cmd", "/c", str(bat)], check=False, capture_output=True)
        print("Restarted the backend: it's back with the new settings in about 10 seconds.")
    else:
        print("Restart the backend to load them.")


if __name__ == "__main__":
    main()
