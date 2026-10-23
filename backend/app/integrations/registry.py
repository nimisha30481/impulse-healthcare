"""Single place that reports which AWS integrations are configured.

States:
  configured      - settings present; the adapter will call AWS. Not proof it works: see
                    docs/AWS_ARCHITECTURE.md "Integration test results".
  not_configured  - settings missing; the documented local fallback is used.
  infrastructure  - provisioned by IaC only; no application calls (e.g. CloudTrail, KMS on S3).
"""
from functools import lru_cache

import boto3

from app.core.config import get_settings


@lru_cache
def client(service: str, region: str | None = None):
    return boto3.client(service, region_name=region or get_settings().aws_region)


def integration_status() -> list[dict]:
    s = get_settings()

    def row(service, module, configured, fallback, phase, note="", off_state="not_configured"):
        """off_state says *why* a service is off: not_configured (turn on with scripts/aws_setup.py --extras),
        deploy_only (only exists in a full AWS deployment), optional_cost (left off: fixed monthly cost),
        unavailable_region (not offered in ap-south-1), licence_required, covered (another service does the job)."""
        return {
            "service": service,
            "module": module,
            "state": "configured" if configured else off_state,
            "fallback": fallback,
            "phase": phase,
            "note": note,
        }

    return [
        row("Amazon Cognito", "Authentication", s.auth_provider == "cognito" and bool(s.cognito_user_pool_id),
            "Local argon2 password auth + TOTP MFA with server-side sessions", 1),
        row("Amazon API Gateway", "API entry point", False,
            "On this computer requests go straight to the DoseWISE server; API Gateway fronts it once deployed to AWS", 1,
            "Created by the infra/ CDK deployment", off_state="deploy_only"),
        row("AWS Lambda", "Backend compute", False,
            "On this computer the DoseWISE server runs as a normal process; in AWS the same code runs on Lambda", 1,
            "Created by the infra/ CDK deployment", off_state="deploy_only"),
        row("Amazon DynamoDB", "Idempotency + medication event mirror",
            bool(s.dynamodb_events_table or s.dynamodb_idempotency_table),
            "Idempotency and event history kept in the SQL database only", 1),
        row("Amazon S3", "Private document storage", bool(s.s3_documents_bucket),
            f"Files written to the private local directory {s.local_storage_dir}", 1),
        row("AWS KMS", "Encryption keys", bool(s.kms_key_id),
            "No KMS: local files are not encrypted at rest (development only)", 1,
            "Used for S3 SSE-KMS when configured; RDS/DynamoDB encryption set in infra/"),
        {"service": "AWS CloudTrail", "module": "AWS API auditing", "state": "infrastructure",
         "fallback": "Application-level hash-chained audit log is always on", "phase": 1,
         "note": "Trail defined in infra/; complements, never replaces, the clinical audit log"},
        row("Amazon HealthLake", "FHIR R4 replica", bool(s.healthlake_datastore_endpoint),
            "FHIR resources are generated and queued (fhir_sync_records), ready to send", 2,
            "A data store bills every hour it exists (roughly US$200/month), so it is left off until needed",
            off_state="optional_cost"),
        row("AWS AppSync (Events API)", "Real-time updates", bool(s.appsync_events_http_endpoint),
            "Server-sent events from FastAPI to signed-in browsers", 2),
        row("Amazon EventBridge", "Domain events", bool(s.eventbridge_bus_name),
            "Events dispatched to in-process handlers", 2),
        row("AWS Step Functions", "Interaction assessment workflow", bool(s.sfn_interaction_state_machine_arn),
            "Same workflow steps run in-process (orchestrator=local) and are recorded", 2),
        row("Amazon SNS", "Patient/doctor SMS alerts + ops alerts", bool(s.sns_ops_topic_arn or s.sns_sms_enabled),
            "SMS marked not_configured (nothing sent); ops alerts logged to server log", 2,
            "SMS to Indian numbers needs TRAI DLT registration (entity + template IDs)"),
        row("Amazon SES (email)", "Email notifications", bool(s.ses_from_address),
            "Email marked not_configured (nothing sent); visible in-app", 2,
            "Replaces Amazon Pinpoint email - see docs/AWS_ARCHITECTURE.md"),
        row("AWS End User Messaging SMS", "SMS notifications", bool(s.sms_origination_identity),
            "SMS goes through Amazon SNS instead" if s.sns_sms_enabled else
            "SMS goes through Amazon SNS once SMS is activated on the AWS account (SNS_SMS_ENABLED=true); "
            "until then patients get in-app and email notifications", 2,
            "Replaces Amazon Pinpoint SMS (Pinpoint end of support: 30 Oct 2026)", off_state="covered"),
        {"service": "Amazon Pinpoint", "module": "Messaging (requested)", "state": "replaced",
         "fallback": "SES + End User Messaging SMS behind app/services/notifications.py", "phase": 2,
         "note": "Pinpoint stopped accepting new customers May 2025; end of support 30 Oct 2026"},
        row("Amazon Comprehend Medical", "Medication entity extraction", bool(s.comprehend_medical_region),
            "No entity extraction; manual transcription", 3,
            "Not offered in Asia Pacific (Mumbai); using another region would send health text outside India",
            off_state="unavailable_region"),
        row("Amazon Bedrock", "Brief summaries + AI drug-drug screening (unverified, doctor review)", bool(s.bedrock_model_id),
            "No AI summary or screening; duplicate-ingredient and allergy checks still run", 3,
            "AI screening is an extra signal only, never shown as 'no interactions'"),
        row("Drug interaction knowledge source", "Pairwise drug-drug interactions",
            s.interaction_source == "http" and bool(s.interaction_source_url),
            "Pairwise interaction checking shown as UNAVAILABLE; duplicate-ingredient and documented-allergy "
            "checks still run on DoseWISE data", 3,
            "Requires a licensed clinical knowledge provider"
            + ("; meanwhile Amazon Bedrock AI screening (unverified) is on" if s.bedrock_interaction_screening else ""),
            off_state="licence_required"),
        row("Amazon Timestream for InfluxDB", "Adherence time-series analytics", bool(s.timestream_influx_url),
            "Adherence trends computed in SQL from medication events", 3,
            "Runs a database instance billed for every hour it runs, so it is left off until needed",
            off_state="optional_cost"),
        row("Amazon OpenSearch Service", "Directory search", bool(s.opensearch_endpoint),
            "SQL LIKE search over the directory tables", 3,
            "A search domain bills every hour (from roughly US$25/month), so it is left off until needed",
            off_state="optional_cost"),
        row("Amazon Location Service", "Maps, geocoding, distance", bool(s.location_place_index or s.location_api_key),
            "Distance computed locally (haversine) when the user shares or types a location; no map tiles", 3),
        {"service": "AWS IAM Identity Center", "module": "Workforce access", "state": "infrastructure",
         "fallback": "n/a - not used for patient sign-in", "phase": 1,
         "note": "Permission sets for developers/admins/support documented in docs/SECURITY.md"},
    ]
