from datetime import timedelta

from conftest import Api, make_doctor, order, register

from app.models import DoseOccurrence, GuestAccessLog, PrescriptionItem
from app.models.base import utcnow


def test_doctor_registration_requires_indian_council_and_speciality():
    api = Api()
    base = {"role": "doctor", "full_name": "Dr X", "email": "drx@example.com", "phone": "9876543210",
            "password": "Str0ng_Pass", "accept_terms": True, "registration_number": "KMC-123"}
    assert api.post("/api/auth/register", {**base, "speciality": "Wizardry",
                                           "registration_council": "Karnataka Medical Council"}).status_code == 400
    assert api.post("/api/auth/register", {**base, "speciality": "Cardiology",
                                           "registration_council": "Some Council"}).status_code == 400
    assert api.post("/api/auth/register", {**base, "speciality": "Cardiology",
                                           "registration_council": "Karnataka Medical Council"}).status_code == 200


def test_patient_access_id_view_copy_regenerate():
    p_api, patient = register("patient")
    first = p_api.get("/api/me/access-id").json()["access_id"]
    assert first.startswith("DW-") and len(first) == 9
    second = p_api.post("/api/me/access-id/regenerate").json()["access_id"]
    assert second != first
    guest = Api()
    assert guest.post("/api/access/guest-view", {"access_id": first}).status_code == 404  # old ID revoked


def test_guest_view_read_only_and_logged(db):
    p_api, patient = register("patient")
    code = p_api.get("/api/me/access-id").json()["access_id"]
    guest = Api()
    r = guest.post("/api/access/guest-view", {"access_id": code.lower().replace("-", ""), "doctor_name": "Dr Guest",
                                              "hospital": "City ER"})
    assert r.status_code == 200, r.text
    assert r.json()["patient"]["name"] == "Test Patient"
    bad = guest.post("/api/access/guest-view", {"access_id": "DW-ZZZZZZ"})
    assert bad.status_code == 404 and "wasn't recognised" in bad.json()["detail"]
    outcomes = sorted(x.outcome for x in db.query(GuestAccessLog).all())
    assert outcomes == ["granted", "invalid"]
    # a guest has no session: no write endpoint is reachable
    assert guest.get(f"/api/patients/{patient['patient_id']}/records").status_code == 401


def test_guest_lookup_is_rate_limited():
    guest = Api()
    codes = [guest.post("/api/access/guest-view", {"access_id": f"DW-AAAA{i:02d}"}).status_code for i in range(11)]
    assert codes[-1] == 429


def test_doctor_opens_patient_with_access_id():
    p_api, patient = register("patient")
    d_api, doc = make_doctor()
    pid = patient["patient_id"]
    assert d_api.get(f"/api/doctor/patients/{pid}").status_code == 403
    code = p_api.get("/api/me/access-id").json()["access_id"]
    r = d_api.post("/api/doctor/access-id", {"access_id": code})
    assert r.status_code == 200 and r.json()["patient_id"] == pid
    assert d_api.get(f"/api/doctor/patients/{pid}").status_code == 200


def test_dose_log_taken_late_no_duplicates_and_authorised_only(db):
    p_api, patient = register("patient")
    d_api, doc = make_doctor()
    other_doc_api, _ = make_doctor()
    pid = patient["patient_id"]
    code = p_api.get("/api/me/access-id").json()["access_id"]
    d_api.post("/api/doctor/access-id", {"access_id": code})
    item = d_api.post("/api/doctor/prescriptions", {"patient_id": pid, "items": [order()]}).json()["items"][0]
    it = db.get(PrescriptionItem, item["id"])
    on_time = DoseOccurrence(item_id=it.id, version_id=it.versions[0].id, patient_id=pid, scheduled_at=utcnow() - timedelta(minutes=5))
    late = DoseOccurrence(item_id=it.id, version_id=it.versions[0].id, patient_id=pid, scheduled_at=utcnow() - timedelta(hours=3))
    db.add_all([on_time, late])
    db.commit()
    r1 = p_api.post(f"/api/patients/{pid}/doses/{on_time.id}/respond", {"kind": "taken_reported", "idempotency_key": "a"})
    r2 = p_api.post(f"/api/patients/{pid}/doses/{on_time.id}/respond", {"kind": "taken_reported", "idempotency_key": "b"})
    assert r1.json()["event_id"] == r2.json()["event_id"]  # second log returns the saved one, no duplicate
    p_api.post(f"/api/patients/{pid}/doses/{late.id}/respond", {"kind": "taken_reported"})
    log = d_api.get(f"/api/doctor/patients/{pid}/dose-log").json()
    states = {r["id"]: r["state"] for r in log["rows"]}
    assert states[on_time.id] == "taken" and states[late.id] == "late"
    assert all(r["logged_at"] for r in log["rows"] if r["state"] in ("taken", "late"))
    assert other_doc_api.get(f"/api/doctor/patients/{pid}/dose-log").status_code == 403
