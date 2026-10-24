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


def e164(phone: str) -> str | None:
    """Indian 10-digit mobile -> +91XXXXXXXXXX; numbers already in +E.164 pass through."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if phone.strip().startswith("+") and 8 <= len(digits) <= 15:
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    return None


def send_sms(phone: str, text: str) -> Result:
    s = get_settings()
    number = e164(phone or "")
    if s.sns_sms_enabled and not s.sms_origination_identity:
        if not number:
            return Result("failed", error="Invalid mobile number")
        attrs = {"AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}}
        for key, val in (("AWS.SNS.SMS.SenderID", s.sns_sms_sender_id), ("AWS.MM.SMS.EntityId", s.sns_dlt_entity_id),
                         ("AWS.MM.SMS.TemplateId", s.sns_dlt_template_id)):
            if val:
                attrs[key] = {"DataType": "String", "StringValue": val}
        try:
            resp = client("sns").publish(PhoneNumber=number, Message=text, MessageAttributes=attrs)
            return Result("ok", data=resp["MessageId"])
        except Exception as e:  # noqa: BLE001
            return Result("failed", error=str(e)[:300])
    if not s.sms_origination_identity:
        return Result("not_configured")
    try:
        resp = client("pinpoint-sms-voice-v2").send_text_message(
            DestinationPhoneNumber=number or phone,
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


# ---------------- Bedrock ----------------
BEDROCK_SYSTEM = (
    "You rewrite verified clinical facts into a short, neutral summary for a doctor. "
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


INTERACTION_SYSTEM = (
    "You are a medication-safety screening assistant for doctors. Given a patient's medicine list, list "
    "only clinically recognised drug-drug interactions between medicines IN THE LIST. Respond with JSON only: "
    '{"interactions":[{"medicines":["<name from list>","<name from list>"],"severity":"major|moderate|minor",'
    '"explanation":"<one sentence>","consequences":"<one sentence>"}]}. If you are not confident, leave it out. '
    "Never give dosing advice, never recommend stopping or changing a medicine."
)


def bedrock_interaction_screen(medicines: list[dict]) -> Result:
    """AI screening only. Output is validated (names must come from the input list, severity from a fixed
    set) and is always presented as unverified. An empty result is NOT evidence of safety."""
    s = get_settings()
    if not (s.bedrock_model_id and s.bedrock_interaction_screening):
        return Result("not_configured")
    names = {m["name"].lower(): m["name"] for m in medicines}
    try:
        resp = client("bedrock-runtime", s.bedrock_region or s.aws_region).converse(
            modelId=s.bedrock_model_id,
            system=[{"text": INTERACTION_SYSTEM}],
            messages=[{"role": "user", "content": [{"text": json.dumps(
                [{"name": m["name"], "strength": m.get("strength"), "route": m.get("route"),
                  "ingredients": m.get("ingredients")} for m in medicines])}]}],
            inferenceConfig={"maxTokens": 800, "temperature": 0},
        )
        text = resp["output"]["message"]["content"][0]["text"]
        raw = json.loads(text[text.find("{"): text.rfind("}") + 1])
        found = []
        for hit in raw.get("interactions", [])[:10]:
            meds = [names.get(str(n).lower()) for n in hit.get("medicines", [])]
            if len(meds) < 2 or None in meds or hit.get("severity") not in ("major", "moderate", "minor"):
                continue  # discard anything that doesn't refer to the actual list
            found.append({"medicines": meds, "severity": hit["severity"],
                          "explanation": str(hit.get("explanation", ""))[:400],
                          "consequences": str(hit.get("consequences", ""))[:400]})
        return Result("ok", data=found, meta={"model": s.bedrock_model_id})
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
        resp = client("location").search_place_index_for_text(IndexName=s.location_place_index, Text=text,
                                                               MaxResults=5, FilterCountries=["IND"])
        if not resp["Results"]:
            return Result("ok", data=None)
        # Among equally relevant hits prefer the plainest label: "Koramangala, Devanahalli, Bangalore" is a
        # same-named village 40 km away, "Koramangala, Bangalore" is the neighbourhood people mean.
        top = max(r.get("Relevance", 0) for r in resp["Results"])
        best = min((r for r in resp["Results"] if r.get("Relevance", 0) == top),
                   key=lambda r: len((r["Place"].get("Label") or "").split(",")))
        lng, lat = best["Place"]["Geometry"]["Point"]
        return Result("ok", data={"lat": lat, "lng": lng, "label": best["Place"].get("Label")})
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
