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
