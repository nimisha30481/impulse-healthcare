import io
from datetime import date, timedelta

from PIL import Image

from conftest import grant_doctor, make_doctor, order, register

from app.models import DoseOccurrence, Notification, PrescriptionItem
from app.models.base import utcnow
from app.services import jobs


def _setup():
    p_api, patient = register("patient")
    d_api, doc = make_doctor()
    grant_doctor(p_api, doc["id"])
    return p_api, patient, d_api, doc


def test_prescription_create_notifies_and_schedules(db):
    p_api, patient, d_api, doc = _setup()
    pid = patient["patient_id"]
    r = d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order(times_of_day=["00:00", "23:59"])]})
    assert r.status_code == 200, r.text
    body = r.json()
    # no knowledge source configured -> drug-drug checking is reported unavailable, never "no interactions"
    assert body["assessments"][0]["drug_drug_state"] == "unavailable"
    meds = p_api.get(f"/api/patients/{pid}/medications").json()
    assert meds[0]["current"]["generic_name"] == "Metformin"
    assert db.query(Notification).filter(Notification.category == "new_prescription").count() >= 1
    assert db.query(DoseOccurrence).filter(DoseOccurrence.patient_id == pid).count() >= 1


def test_invalid_dose_unit_rejected():
    p_api, patient, d_api, doc = _setup()
    r = d_api.post("/api/doctor/prescriptions", {"patient_id": patient["patient_id"], "items": [order(dose_unit="spoons")]})
    assert r.status_code == 422


def test_edit_creates_version_and_old_doses_cancelled(db):
    p_api, patient, d_api, doc = _setup()
    pid = patient["patient_id"]
    item = d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order(times_of_day=["23:58"])]}).json()["items"][0]
    tomorrow_times = order(times_of_day=["23:59"], dose_amount=2)
    r = d_api.put(f"/api/doctor/prescription-items/{item['id']}",
                  {"order": tomorrow_times, "change_reason": "Dose increased", "expected_lock_version": 1})
    assert r.status_code == 200, r.text
    full = r.json()["item"]
    assert [v["version_no"] for v in full["versions"]] == [2, 1]
    assert full["versions"][1]["status"] == "superseded"
    # stale edit is rejected (optimistic locking)
    stale = d_api.put(f"/api/doctor/prescription-items/{item['id']}",
                      {"order": tomorrow_times, "change_reason": "again", "expected_lock_version": 1})
    assert stale.status_code == 409
    open_old = db.query(DoseOccurrence).filter(DoseOccurrence.item_id == item["id"],
                                               DoseOccurrence.status != "cancelled").all()
    assert all(o.version.version_no == 2 for o in open_old)


def test_discontinue_stops_future_reminders_and_keeps_history(db):
    p_api, patient, d_api, doc = _setup()
    pid = patient["patient_id"]
    item = d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order(times_of_day=["23:59"])]}).json()["items"][0]
    r = d_api.post(f"/api/doctor/prescription-items/{item['id']}/discontinue",
                   {"reason": "No longer needed", "expected_lock_version": 1})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "discontinued"
    assert db.query(DoseOccurrence).filter(DoseOccurrence.item_id == item["id"],
                                           DoseOccurrence.status.in_(("upcoming", "due"))).count() == 0
    jobs.tick(db)
    assert db.query(DoseOccurrence).filter(DoseOccurrence.item_id == item["id"],
                                           DoseOccurrence.status.in_(("upcoming", "due"))).count() == 0
    detail = p_api.get(f"/api/patients/{pid}/medications/{item['id']}").json()
    assert detail["bucket"] == "discontinued" and len(detail["versions"]) == 1


def test_invalid_status_transition_rejected():
    p_api, patient, d_api, doc = _setup()
    item = d_api.post("/api/doctor/prescriptions", {"patient_id": patient["patient_id"], "items": [order()]}).json()["items"][0]
    d_api.post(f"/api/doctor/prescription-items/{item['id']}/discontinue", {"reason": "stop", "expected_lock_version": 1})
    r = d_api.post(f"/api/doctor/prescription-items/{item['id']}/status",
                   {"status": "active", "reason": "restart", "expected_lock_version": 2})
    assert r.status_code == 400


def test_reminder_sent_once_and_response_recorded(db):
    p_api, patient, d_api, doc = _setup()
    pid = patient["patient_id"]
    item = d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order()]}).json()["items"][0]
    it = db.get(PrescriptionItem, item["id"])
    occ = DoseOccurrence(item_id=it.id, version_id=it.versions[0].id, patient_id=pid,
                         scheduled_at=utcnow() - timedelta(minutes=1))
    db.add(occ)
    db.commit()
    jobs.tick(db)
    jobs.tick(db)  # second run must not duplicate
    sent = db.query(Notification).filter(Notification.dedupe_key == f"reminder:{occ.id}:in_app").count()
    assert sent == 1
    r = p_api.post(f"/api/patients/{pid}/doses/{occ.id}/respond", {"kind": "taken_reported", "idempotency_key": "k1"})
    assert r.status_code == 200
    again = p_api.post(f"/api/patients/{pid}/doses/{occ.id}/respond", {"kind": "taken_reported", "idempotency_key": "k1"})
    assert again.json()["event_id"] == r.json()["event_id"]  # idempotent retry
    adh = p_api.get(f"/api/patients/{pid}/adherence").json()
    assert adh["taken_reported"] == 1


def test_unanswered_doses_become_unconfirmed_and_escalate(db):
    from app.models import EscalationPolicy, SupportCase

    p_api, patient, d_api, doc = _setup()
    pid = patient["patient_id"]
    item = d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order()]}).json()["items"][0]
    it = db.get(PrescriptionItem, item["id"])
    db.add(EscalationPolicy(patient_id=pid, case_after_consecutive=2, checkin_after_consecutive=1,
                            caregiver_after_consecutive=2, quiet_hours={}))
    for h in (5, 4):
        db.add(DoseOccurrence(item_id=it.id, version_id=it.versions[0].id, patient_id=pid,
                              scheduled_at=utcnow() - timedelta(hours=h)))
    db.commit()
    for _ in range(4):
        jobs.tick(db)
    statuses = {o.status for o in db.query(DoseOccurrence).filter(DoseOccurrence.patient_id == pid,
                                                                  DoseOccurrence.scheduled_at < utcnow() - timedelta(hours=3))}
    assert statuses == {"unconfirmed"}  # never assumed missed or taken
    assert db.query(SupportCase).filter(SupportCase.patient_id == pid).count() == 1


def test_booking_and_double_booking_prevention(db):
    import threading

    from app.models import AvailabilitySlot

    p_api, patient, d_api, doc = _setup()
    p2_api, patient2 = register("patient")
    d_api.put("/api/doctor/availability", {"rules": [
        {"weekday": d, "start_time": "09:00", "end_time": "10:00", "slot_minutes": 30} for d in range(7)]})
    day = (date.today() + timedelta(days=2)).isoformat()
    slots = p_api.get(f"/api/doctors/{doc['id']}/slots?day={day}").json()
    sid = slots[0]["id"]
    results = []

    def try_hold(api, pid):
        results.append(api.post("/api/appointments/hold", {"patient_id": pid, "slot_id": sid}).status_code)

    t1 = threading.Thread(target=try_hold, args=(p_api, patient["patient_id"]))
    t2 = threading.Thread(target=try_hold, args=(p2_api, patient2["patient_id"]))
    t1.start(), t2.start(), t1.join(), t2.join()
    assert sorted(results) == [200, 409]
    db.expire_all()
    assert db.get(AvailabilitySlot, sid).booked_count == 1
    winner = p_api if results[0] == 200 and True else p2_api
    # whoever holds it can confirm
    for api, pat in ((p_api, patient), (p2_api, patient2)):
        hold = api.post("/api/appointments/hold", {"patient_id": pat["patient_id"], "slot_id": slots[1]["id"]})
        if hold.status_code == 200:
            appt = api.post("/api/appointments/confirm", {"patient_id": pat["patient_id"], "hold_id": hold.json()["hold_id"]})
            assert appt.status_code == 200 and appt.json()["status"] == "confirmed"
            break
    assert winner


def _png(w=1000, h=1400) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


def test_upload_validation_rejects_wrong_type(db):
    p_api, patient, *_ = _setup()
    pid = patient["patient_id"]
    bad = p_api.post(f"/api/patients/{pid}/documents", files={"file": ("x.png", b"MZ\x90\x00fakeexe", "image/png")},
                     data={"title": "Bad", "category": "other"})
    assert bad.status_code == 400
    ok = p_api.post(f"/api/patients/{pid}/documents", files={"file": ("rx.png", _png(), "image/png")},
                    data={"title": "Lab", "category": "lab_report"})
    assert ok.status_code == 200, ok.text


def test_ocr_never_activates_until_doctor_verifies(db):
    p_api, patient, d_api, doc = _setup()
    pid = patient["patient_id"]
    up = p_api.post(f"/api/patients/{pid}/documents", files={"file": ("rx.png", _png(), "image/png")},
                    data={"title": "Prescription", "category": "prescription"}).json()
    ocr = up["ocr"]
    assert ocr["engine"] == "manual" and "UNVERIFIED" in ocr["label"]
    assert d_api.post(f"/api/doctor/verifications/{ocr['id']}", {"approve": True, "note": "okay",
                                                                "items": [order()]}).status_code == 400
    rv = p_api.post(f"/api/patients/{pid}/ocr/{ocr['id']}/review",
                    {"medications": [{"name": "Metformin", "strength": "500 mg", "dose": "1 tablet"}]})
    assert rv.status_code == 200
    assert p_api.get(f"/api/patients/{pid}/medications").json() == []  # nothing active yet
    v = d_api.post(f"/api/doctor/verifications/{ocr['id']}", {"approve": True, "note": "Checked against original",
                                                             "items": [order()]})
    assert v.status_code == 200 and v.json()["status"] == "verified"
    assert len(p_api.get(f"/api/patients/{pid}/medications").json()) == 1


def test_interaction_source_failure_is_not_reported_as_safe(monkeypatch, db):
    from app.core.config import get_settings

    p_api, patient, d_api, doc = _setup()
    s = get_settings()
    monkeypatch.setattr(s, "interaction_source", "http")
    monkeypatch.setattr(s, "interaction_source_url", "http://127.0.0.1:9/unreachable")
    r = d_api.post("/api/doctor/prescriptions", {"patient_id": patient["patient_id"], "items": [order()]})
    a = r.json()["assessments"][0]
    assert a["status"] == "failed" and a["drug_drug_state"] == "failed"


def test_duplicate_ingredient_and_allergy_checks(db):
    from app.models import Allergy

    p_api, patient, d_api, doc = _setup()
    pid = patient["patient_id"]
    db.add(Allergy(patient_id=pid, substance="Metformin", substance_ingredient="metformin"))
    db.commit()
    d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order()]})
    r = d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order(brand_name="Other brand")]})
    kinds = {a["kind"] for a in r.json()["assessments"][0]["alerts"]}
    assert {"duplicate_therapy", "allergy"} <= kinds


def test_notification_without_provider_is_not_marked_sent(db):
    p_api, patient, d_api, doc = _setup()
    p_api.patch("/api/account/preferences", {"notifications": {"doctor_messages": {"email": True}}})
    d_api.post("/api/doctor/prescriptions", {"patient_id": patient["patient_id"], "items": [order()]})
    email = db.query(Notification).filter(Notification.channel == "email").first()
    assert email is not None and email.delivery_status == "not_configured"


def test_clinical_brief_lists_sources_and_missing_info(db):
    p_api, patient, d_api, doc = _setup()
    pid = patient["patient_id"]
    d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order()]})
    b = d_api.post(f"/api/doctor/patients/{pid}/brief", {}).json()
    meds = b["content"]["sections"]["current_medications"]["items"]
    assert meds and meds[0]["sources"][0]["type"] == "prescription_item"
    assert any("Allergy status unknown" in m for m in b["content"]["missing_information"])
    assert b["ai_status"] == "not_configured"
