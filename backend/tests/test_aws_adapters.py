import json

from conftest import grant_doctor, make_doctor, order, register

from app.core.config import get_settings
from app.integrations import aws_services


class FakeClient:
    def __init__(self, reply=None):
        self.reply, self.calls = reply, []

    def converse(self, **kw):
        self.calls.append(kw)
        return {"output": {"message": {"content": [{"text": self.reply}]}}}

    def publish(self, **kw):
        self.calls.append(kw)
        return {"MessageId": "m-1"}


def test_e164_formatting():
    assert aws_services.e164("9876543210") == "+919876543210"
    assert aws_services.e164("+91 98765 43210") == "+919876543210"
    assert aws_services.e164("12345") is None


def test_sns_sms_uses_india_number_and_dlt_ids(monkeypatch):
    s = get_settings()
    fake = FakeClient()
    monkeypatch.setattr(s, "sns_sms_enabled", True)
    monkeypatch.setattr(s, "sns_dlt_entity_id", "1101")
    monkeypatch.setattr(s, "sns_dlt_template_id", "1107")
    monkeypatch.setattr(aws_services, "client", lambda *a, **k: fake)
    r = aws_services.send_sms("9876543210", "DoseWISE: you have a medication reminder.")
    assert r.state == "ok"
    sent = fake.calls[0]
    assert sent["PhoneNumber"] == "+919876543210"
    assert sent["MessageAttributes"]["AWS.MM.SMS.EntityId"]["StringValue"] == "1101"
    assert sent["MessageAttributes"]["AWS.SNS.SMS.SMSType"]["StringValue"] == "Transactional"


def test_bedrock_screening_is_labelled_validated_and_never_a_safety_result(monkeypatch):
    s = get_settings()
    reply = json.dumps({"interactions": [
        {"medicines": ["Warfarin", "Aspirin"], "severity": "major", "explanation": "Bleeding risk.", "consequences": "Bleeding."},
        {"medicines": ["Warfarin", "Imaginary drug"], "severity": "major", "explanation": "x"},  # not on list: dropped
    ]})
    monkeypatch.setattr(s, "bedrock_model_id", "test-model")
    monkeypatch.setattr(s, "bedrock_interaction_screening", True)
    monkeypatch.setattr(aws_services, "client", lambda *a, **k: FakeClient(reply))
    p_api, patient = register("patient")
    d_api, doc = make_doctor()
    grant_doctor(p_api, doc["id"])
    pid = patient["patient_id"]
    d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order(generic_name="Warfarin", strength="5 mg")]})
    r = d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order(generic_name="Aspirin", strength="75 mg")]})
    a = r.json()["assessments"][0]
    ai = [x for x in a["alerts"] if x["kind"] == "ai_screening"]
    assert len(ai) == 1 and set(ai[0]["medicines"]) == {"Warfarin", "Aspirin"}
    assert "unverified" in ai[0]["source"]
    assert "ai_screening" in a["checks_performed"]
    assert a["drug_drug_state"] == "unavailable"  # AI never counts as a licensed interaction check
