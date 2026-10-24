from datetime import timedelta

from conftest import make_doctor, register

from app.models import AvailabilitySlot, Notification
from app.models.base import utcnow


def test_close_account_needs_only_the_word_close():
    api, me = register("patient")
    assert api.post("/api/account/close", {"confirm": "nope"}).status_code == 400
    r = api.post("/api/account/close", {"confirm": "close"})
    assert r.status_code == 200
    assert api.get("/api/auth/me").status_code == 401  # signed out everywhere


def test_region_save_requires_a_state():
    api, _ = register("patient")
    assert api.patch("/api/account/preferences", {"country": "India", "state": "Kerala"}).status_code == 200
    assert api.patch("/api/account/preferences", {"country": "India"}).status_code == 400


def test_reschedule_links_old_booking_and_notifies(db):
    p_api, patient = register("patient")
    d_api, doc = make_doctor()
    now = utcnow()
    slots = [AvailabilitySlot(doctor_user_id=doc["id"], starts_at=now + timedelta(days=d, hours=2),
                              ends_at=now + timedelta(days=d, hours=2, minutes=20), capacity=1, booked_count=0)
             for d in (3, 4)]
    db.add_all(slots)
    db.commit()
    pid = patient["patient_id"]
    h = p_api.post("/api/appointments/hold", {"patient_id": pid, "slot_id": slots[0].id}).json()
    first = p_api.post("/api/appointments/confirm", {"patient_id": pid, "hold_id": h["hold_id"]}).json()
    h2 = p_api.post("/api/appointments/hold", {"patient_id": pid, "slot_id": slots[1].id}).json()
    second = p_api.post("/api/appointments/confirm", {"patient_id": pid, "hold_id": h2["hold_id"],
                                                      "reschedule_appointment_id": first["id"]}).json()
    appts = p_api.get(f"/api/patients/{pid}/appointments").json()
    old = next(a for a in appts["upcoming"] + appts["past"] if a["id"] == first["id"])
    assert old["status"] == "rescheduled" and old["rescheduled_to"]["id"] == second["id"]
    titles = [n.title for n in db.query(Notification).filter(Notification.user_id == patient["id"])]
    assert "Appointment rescheduled" in titles
    # cancelling notifies both sides, including the person who cancelled
    assert p_api.post(f"/api/appointments/{second['id']}/cancel", {"reason": "Travelling"}).status_code == 200
    db.expire_all()
    assert db.query(Notification).filter(Notification.user_id == patient["id"],
                                         Notification.title == "Appointment cancelled").count() >= 1
    assert db.query(Notification).filter(Notification.user_id == doc["id"],
                                         Notification.title == "Appointment cancelled").count() >= 1


def test_guest_view_is_one_time_and_rotates_the_access_id():
    from conftest import Api

    p_api, patient = register("patient")
    first_id = p_api.get("/api/me/access-id").json()["access_id"]
    r = Api().post("/api/access/guest-view", {"access_id": first_id, "doctor_name": "Dr Guest"})
    assert r.status_code == 200
    s = r.json()["session"]
    assert s["minutes"] == 15 and s["expires_at"] and s["access_id"] == first_id
    new_id = p_api.get("/api/me/access-id").json()["access_id"]
    assert new_id != first_id  # rotated automatically
    assert Api().post("/api/access/guest-view", {"access_id": first_id}).status_code == 404  # old one is dead
    assert Api().post("/api/access/guest-view", {"access_id": new_id}).status_code == 200


def test_body_measurements_and_bmi():
    api, me = register("patient")
    pid = me["patient_id"]
    url = f"/api/patients/{pid}/health/self-reported"
    assert api.patch(url, {"date_of_birth": "1990-05-20", "sex": "Female", "height_cm": 160, "weight_kg": 64}).status_code == 200
    d = api.get(f"/api/patients/{pid}/health").json()["demographics"]
    assert d["bmi"] == 25.0 and d["bmi_category"] == "Overweight" and d["age"] >= 36 and d["sex"] == "Female"
    assert api.patch(url, {"height_cm": 900}).status_code == 422  # impossible values are refused
