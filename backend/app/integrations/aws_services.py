"""Thin adapters for the remaining AWS services. Each one returns a result that says plainly
whether AWS was actually called; callers record that state and never assume success."""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings
from app.integrations.registry import client

log = logging.getLogger("impulse.aws")


@dataclass
class Result:
    state: str  # ok | not_configured | failed
    data: Any = None
    error: str | None = None
    meta: dict = field(default_factory=dict)


# ---------------- EventBridge ----------------
def publish_event(detail_type: str, detail: dict) -> Result:
    """Minimal payloads only: identifiers + event type, never clinical content."""
    s = get_settings()
    if not s.eventbridge_bus_name:
        return Result("not_configured")
    try:
        resp = client("events").put_events(
            Entries=[{
                "EventBusName": s.eventbridge_bus_name,
                "Source": "impulse.app",
                "DetailType": detail_type,
                "Detail": json.dumps(detail, default=str),
            }]
        )
        if resp.get("FailedEntryCount"):
            return Result("failed", error=str(resp["Entries"]))
        return Result("ok", data=resp["Entries"][0].get("EventId"))
    except Exception as e:  # noqa: BLE001
        log.warning("EventBridge publish failed: %s", e)
        return Result("failed", error=str(e)[:300])


# ---------------- DynamoDB ----------------
def mirror_medication_event(item: dict) -> Result:
    """Writes the medication event to DynamoDB with a conditional put so retries never create
    duplicates. pk=PATIENT#<id>, sk=EVENT#<iso-ts>#<event-id>."""
    s = get_settings()
    if not s.dynamodb_events_table:
        return Result("not_configured")
    try:
        client("dynamodb").put_item(
            TableName=s.dynamodb_events_table,
            Item={k: {"S": str(v)} for k, v in item.items() if v is not None},
            ConditionExpression="attribute_not_exists(pk)",
        )
        return Result("ok")
    except client("dynamodb").exceptions.ConditionalCheckFailedException:
        return Result("ok", meta={"duplicate": True})
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- Step Functions ----------------
def start_interaction_workflow(assessment_id: str, patient_id: str) -> Result:
    s = get_settings()
    if not s.sfn_interaction_state_machine_arn:
        return Result("not_configured")
    try:
        resp = client("stepfunctions").start_execution(
            stateMachineArn=s.sfn_interaction_state_machine_arn,
            name=f"assess-{assessment_id}",  # execution name = idempotency key
            input=json.dumps({"assessment_id": assessment_id, "patient_id": patient_id}),
        )
        return Result("ok", data=resp["executionArn"])
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- SNS (ops alerts) ----------------
def ops_alert(subject: str, message: str) -> Result:
    s = get_settings()
    if not s.sns_ops_topic_arn:
        log.warning("OPS ALERT (SNS not configured): %s - %s", subject, message)
        return Result("not_configured")
    try:
        resp = client("sns").publish(TopicArn=s.sns_ops_topic_arn, Subject=subject[:100], Message=message)
        return Result("ok", data=resp["MessageId"])
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- SES / End User Messaging SMS ----------------
def send_email(to: str, subject: str, text: str) -> Result:
    s = get_settings()
    if not s.ses_from_address:
        return Result("not_configured")
    try:
        resp = client("sesv2").send_email(
            FromEmailAddress=s.ses_from_address,
            Destination={"ToAddresses": [to]},
            Content={"Simple": {"Subject": {"Data": subject}, "Body": {"Text": {"Data": text}}}},
        )
        return Result("ok", data=resp["MessageId"])
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


def send_sms(phone: str, text: str) -> Result:
    s = get_settings()
    if not s.sms_origination_identity:
        return Result("not_configured")
    try:
        resp = client("pinpoint-sms-voice-v2").send_text_message(
            DestinationPhoneNumber=phone,
            OriginationIdentity=s.sms_origination_identity,
            MessageBody=text,
            MessageType="TRANSACTIONAL",
        )
        return Result("ok", data=resp["MessageId"])
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- AppSync Events (real-time fan-out) ----------------
def appsync_publish(channel: str, event: dict) -> Result:
    s = get_settings()
    if not s.appsync_events_http_endpoint:
        return Result("not_configured")
    try:
        r = httpx.post(
            f"{s.appsync_events_http_endpoint}/event",
            headers={"x-api-key": s.appsync_events_api_key, "content-type": "application/json"},
            json={"channel": channel, "events": [json.dumps(event)]},
            timeout=5,
        )
        r.raise_for_status()
        return Result("ok")
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- Textract + Comprehend Medical ----------------
def textract_text(data: bytes) -> Result:
    s = get_settings()
    if not s.textract_enabled:
        return Result("not_configured")
    try:
        resp = client("textract").detect_document_text(Document={"Bytes": data})
        lines = [b for b in resp["Blocks"] if b["BlockType"] == "LINE"]
        text = "\n".join(b["Text"] for b in lines)
        conf = sum(b.get("Confidence", 0) for b in lines) / max(len(lines), 1) / 100
        return Result("ok", data=text, meta={"confidence": round(conf, 3)})
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


def comprehend_medications(text: str) -> Result:
    """Returns medication mentions with attributes. Mentions are NOT prescriptions."""
    s = get_settings()
    if not s.comprehend_medical_region:
        return Result("not_configured")
    try:
        resp = client("comprehendmedical", s.comprehend_medical_region).detect_entities_v2(Text=text[:20000])
        meds = []
        for ent in resp["Entities"]:
            if ent["Category"] != "MEDICATION":
                continue
            m = {"name": ent["Text"], "confidence": round(ent["Score"], 3)}
            for a in ent.get("Attributes", []):
                key = {"STRENGTH": "strength", "DOSAGE": "dose", "ROUTE_OR_MODE": "route",
                       "FREQUENCY": "frequency", "DURATION": "duration", "FORM": "form"}.get(a["Type"])
                if key:
                    m[key] = a["Text"]
                    m[f"{key}_confidence"] = round(a["Score"], 3)
            meds.append(m)
        return Result("ok", data=meds)
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- Bedrock ----------------
BEDROCK_SYSTEM = (
    "You rewrite verified clinical facts into a short, neutral summary for a clinician. "
    "Use ONLY the facts provided. Do not add diagnoses, interactions, dosing advice or recommendations. "
    "If a fact is marked missing or conflicting, say so. Cite fact ids in square brackets."
)


def bedrock_summarize(facts: list[dict]) -> Result:
    s = get_settings()
    if not s.bedrock_model_id:
        return Result("not_configured")
    try:
        resp = client("bedrock-runtime", s.bedrock_region or s.aws_region).converse(
            modelId=s.bedrock_model_id,
            system=[{"text": BEDROCK_SYSTEM}],
            messages=[{"role": "user", "content": [{"text": json.dumps(facts, default=str)[:30000]}]}],
            inferenceConfig={"maxTokens": 600, "temperature": 0},
        )
        text = resp["output"]["message"]["content"][0]["text"]
        # output validation: every cited id must exist in the input facts
        known = {str(f.get("id")) for f in facts}
        cited = set(re.findall(r"\[([^\]]+)\]", text))
        if cited - known:
            return Result("failed", error="Summary cited sources that were not provided; discarded")
        return Result("ok", data=text)
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- HealthLake ----------------
def healthlake_put(resource: dict) -> Result:
    s = get_settings()
    if not s.healthlake_datastore_endpoint:
        return Result("not_configured")
    try:
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        import boto3

        url = f"{s.healthlake_datastore_endpoint.rstrip('/')}/{resource['resourceType']}/{resource['id']}"
        body = json.dumps(resource)
        req = AWSRequest(method="PUT", url=url, data=body, headers={"Content-Type": "application/fhir+json"})
        creds = boto3.Session().get_credentials()
        SigV4Auth(creds, "healthlake", s.healthlake_region or s.aws_region).add_auth(req)
        r = httpx.put(url, content=body, headers=dict(req.headers), timeout=15)
        r.raise_for_status()
        return Result("ok", data=r.json().get("id"))
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- Timestream for InfluxDB ----------------
def write_adherence_point(patient_id: str, kind: str, ts_iso: str) -> Result:
    s = get_settings()
    if not s.timestream_influx_url:
        return Result("not_configured")
    try:
        line = f"dose_event,patient={patient_id},kind={kind} value=1i"
        r = httpx.post(
            f"{s.timestream_influx_url}/api/v2/write?org=impulse&bucket=adherence&precision=s",
            headers={"Authorization": f"Token {s.timestream_influx_token}"},
            content=line,
            timeout=5,
        )
        r.raise_for_status()
        return Result("ok")
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- Location Service ----------------
def geocode(text: str) -> Result:
    s = get_settings()
    if not s.location_place_index:
        return Result("not_configured")
    try:
        resp = client("location").search_place_index_for_text(IndexName=s.location_place_index, Text=text, MaxResults=1)
        if not resp["Results"]:
            return Result("ok", data=None)
        lng, lat = resp["Results"][0]["Place"]["Geometry"]["Point"]
        return Result("ok", data={"lat": lat, "lng": lng, "label": resp["Results"][0]["Place"].get("Label")})
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])


# ---------------- OpenSearch ----------------
def opensearch_query(q: str, kind: str | None) -> Result:
    s = get_settings()
    if not s.opensearch_endpoint:
        return Result("not_configured")
    try:
        must: list[dict] = [{"multi_match": {"query": q, "fields": ["name^3", "services", "departments", "city"]}}]
        if kind:
            must.append({"term": {"kind": kind}})
        r = httpx.post(f"{s.opensearch_endpoint}/directory/_search", json={"query": {"bool": {"must": must}}}, timeout=5)
        r.raise_for_status()
        return Result("ok", data=[h["_id"] for h in r.json()["hits"]["hits"]])
    except Exception as e:  # noqa: BLE001
        return Result("failed", error=str(e)[:300])
