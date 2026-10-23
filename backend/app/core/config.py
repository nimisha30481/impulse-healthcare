"""Application settings, loaded from environment variables (see backend/.env.example).

Every AWS integration is optional. When its settings are empty the integration reports
itself as "not configured" and the app falls back to a documented local behaviour; it never
pretends the AWS service ran.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]  # paths work whatever the working directory is


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # --- core ---
    environment: str = "development"  # development | test | staging | production
    app_name: str = "DoseWISE"
    # SQLite keeps local setup to zero dependencies. Use PostgreSQL everywhere else:
    # postgresql+psycopg://user:pass@host:5432/impulse
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'impulse_dev.db').as_posix()}"
    database_secret_arn: str = ""  # AWS: build database_url from the RDS-generated secret
    secret_key: str = "dev-only-change-me"  # used for CSRF/HMAC; must be set outside development
    frontend_origin: str = "http://localhost:5173"
    session_hours: int = 12
    cookie_secure: bool = False
    enable_demo_login: bool = True  # forced off outside development (see is_demo_allowed)
    run_background_jobs: bool = True
    background_tick_seconds: int = 60
    local_storage_dir: str = str(BACKEND_DIR / "private_storage")
    max_upload_mb: int = 10
    default_timezone: str = "Asia/Kolkata"

    # --- authentication ---
    auth_provider: str = "local"  # local | cognito
    cognito_region: str = ""
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_client_secret: str = ""
    cognito_domain: str = ""  # e.g. impulse-dev.auth.ap-south-1.amazoncognito.com
    cognito_redirect_uri: str = "http://localhost:8000/api/auth/cognito/callback"

    # --- AWS (all optional) ---
    aws_region: str = "ap-south-1"
    s3_documents_bucket: str = ""
    kms_key_id: str = ""
    dynamodb_events_table: str = ""
    dynamodb_idempotency_table: str = ""
    eventbridge_bus_name: str = ""
    sfn_interaction_state_machine_arn: str = ""
    sns_ops_topic_arn: str = ""
    ses_from_address: str = ""
    sms_origination_identity: str = ""  # AWS End User Messaging SMS phone pool / sender id
    healthlake_datastore_endpoint: str = ""
    healthlake_region: str = ""
    comprehend_medical_region: str = ""
    textract_enabled: bool = False
    bedrock_model_id: str = ""
    bedrock_region: str = ""
    appsync_events_http_endpoint: str = ""
    appsync_events_api_key: str = ""
    timestream_influx_url: str = ""
    timestream_influx_token: str = ""
    location_place_index: str = ""
    location_map_name: str = ""
    location_api_key: str = ""
    opensearch_endpoint: str = ""

    # --- drug interaction knowledge source ---
    # none = pairwise interaction checking is unavailable (the honest default).
    # http = a licensed provider exposing the contract in app/services/interactions.py
    interaction_source: str = "none"
    interaction_source_url: str = ""
    interaction_source_api_key: str = ""
    interaction_source_name: str = ""

    @property
    def is_dev(self) -> bool:
        return self.environment in ("development", "test")

    @property
    def is_demo_allowed(self) -> bool:
        return self.is_dev and self.enable_demo_login


def _database_url_from_secret(arn: str, region: str) -> str:
    """In AWS the RDS credentials live in Secrets Manager (rotatable), never in env vars."""
    import json

    import boto3

    sec = json.loads(boto3.client("secretsmanager", region_name=region).get_secret_value(SecretId=arn)["SecretString"])
    return (f"postgresql+psycopg://{sec['username']}:{sec['password']}@{sec['host']}:{sec.get('port', 5432)}"
            f"/{sec.get('dbname', 'impulse')}?sslmode=require")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.database_secret_arn:
        s.database_url = _database_url_from_secret(s.database_secret_arn, s.aws_region)
    if not s.is_dev and s.secret_key == "dev-only-change-me":
        raise RuntimeError("SECRET_KEY must be set outside development")
    return s
