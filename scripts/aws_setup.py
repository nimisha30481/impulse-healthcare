"""One-command AWS setup for DoseWISE. Creates (or reuses) the AWS resources and writes their
names into backend/.env, then the dev supervisor's backend restart picks them up.

Run from the repo root after signing in to AWS (`aws configure` or `aws configure sso`):

    backend\\.venv\\Scripts\\python.exe scripts\\aws_setup.py
    backend\\.venv\\Scripts\\python.exe scripts\\aws_setup.py --cognito          # also switch sign-in to Cognito
    backend\\.venv\\Scripts\\python.exe scripts\\aws_setup.py --verify-phone 9876543210   # SNS SMS sandbox

Safe to re-run: every step reuses what already exists. No secret is printed.
"""
import argparse
import sys
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
    pool_name = f"{NAME}-users"
    pool = next((p["Id"] for p in idp.list_user_pools(MaxResults=60)["UserPools"] if p["Name"] == pool_name), None)
    if not pool:
        pool = idp.create_user_pool(
            PoolName=pool_name,
            UsernameAttributes=["email"],
            AutoVerifiedAttributes=["email"],
            Policies={"PasswordPolicy": {"MinimumLength": 10, "RequireUppercase": True, "RequireLowercase": True,
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
        )["UserPoolClient"]["ClientId"]
        ok("Cognito app client created")
    secret = idp.describe_user_pool_client(UserPoolId=pool, ClientId=client_id)["UserPoolClient"]["ClientSecret"]
    prefix = f"{NAME}-{account[-6:]}"
    domain = idp.describe_user_pool(UserPoolId=pool)["UserPool"].get("Domain")
    if not domain:
        idp.create_user_pool_domain(Domain=prefix, UserPoolId=pool)
        domain = prefix
        ok("Cognito hosted sign-in domain created")
    env.update(AUTH_PROVIDER="cognito", COGNITO_REGION=region, COGNITO_USER_POOL_ID=pool,
               COGNITO_CLIENT_ID=client_id, COGNITO_CLIENT_SECRET=secret,
               COGNITO_DOMAIN=f"{domain}.auth.{region}.amazoncognito.com", COGNITO_REDIRECT_URI=CALLBACK)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--profile", help="AWS CLI profile name (default: your default profile)")
    ap.add_argument("--cognito", action="store_true", help="create Cognito and switch sign-in to it")
    ap.add_argument("--verify-phone", help="Indian mobile number to verify for the SNS SMS sandbox")
    ap.add_argument("--bedrock-model", help="use this Bedrock model/inference-profile ID instead of auto-picking")
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
    failed = []
    for name, step in steps:
        print(f"\n{name}")
        try:
            step()
        except ClientError as e:
            print(f"  [fail] {code(e)}: {e.response.get('Error', {}).get('Message', '')}")
            failed.append(name)

    write_env(env)
    print(f"\nWrote {len(env)} settings to backend/.env. Restart the backend to load them "
          "(the DoseWISE supervisor restarts it automatically if you stop it).")
    if failed:
        sys.exit(f"Not set up: {', '.join(failed)}. Fix the error above (usually a missing IAM permission) and re-run.")


if __name__ == "__main__":
    main()
