"""Appointment booking: speciality -> doctor -> location -> slots -> hold -> review -> confirm."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import serializers as S
from app.core.database import get_db
from app.core.deps import current_user
from app.core.errors import forbidden, not_found
from app.models import Appointment, AvailabilitySlot, DoctorProfile, FollowUpInstruction, SlotHold, User
from app.models.base import utcnow
from app.services import booking
from app.services.permissions import authorize_patient

router = APIRouter(prefix="/api", tags=["appointments"])


@router.get("/specialities")
def specialities(db: Session = Depends(get_db)):
    rows = db.execute(select(DoctorProfile.speciality).where(DoctorProfile.verification_status == "verified")
                      .distinct()).scalars()
    return sorted(rows)


@router.get("/doctors")
def doctors(speciality: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    qy = select(DoctorProfile).where(DoctorProfile.verification_status == "verified")
    if speciality:
        qy = qy.where(DoctorProfile.speciality == speciality)
    return [{"id": d.user_id, "name": d.user.full_name, "speciality": d.speciality, "bio": d.bio,
             "languages": d.languages, "consultation_types": d.consultation_types, "avatar_color": d.user.avatar_color,
             "organization": {"id": d.organization.id, "name": d.organization.name, "address": d.organization.address,
                              "is_demo": d.organization.data_source == "demo"} if d.organization else None}
            for d in db.execute(qy).scalars()]


@router.get("/doctors/{doctor_id}/slots")
def slots(doctor_id: str, day: date, user: User = Depends(current_user), db: Session = Depends(get_db)):
    booking.materialize_slots(db, doctor_id)
    db.commit()
    tz = ZoneInfo("Asia/Kolkata")
    lo = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    rows = db.execute(select(AvailabilitySlot).where(
        AvailabilitySlot.doctor_user_id == doctor_id, AvailabilitySlot.starts_at >= max(lo, utcnow()),
        AvailabilitySlot.starts_at < lo + timedelta(days=1), AvailabilitySlot.status == "open")
        .order_by(AvailabilitySlot.starts_at)).scalars()
    return [{"id": s.id, "starts_at": s.starts_at, "ends_at": s.ends_at, "consultation_type": s.consultation_type,
             "available": s.booked_count < s.capacity,
             "location": s.organization.name if s.organization else None} for s in rows]


class HoldIn(BaseModel):
    patient_id: str
    slot_id: str


def _booking_access(db, user, patient_id):
    if user.role not in ("patient", "caregiver"):
        raise forbidden("Only patients or authorised caregivers can book")
    return authorize_patient(db, user, patient_id, "appointments.book" if user.role == "caregiver" else "medications.view")


@router.post("/appointments/hold")
def hold(body: HoldIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = _booking_access(db, user, body.patient_id)
    h = booking.hold(db, user, acc.patient, body.slot_id)
    db.commit()
    slot = db.get(AvailabilitySlot, h.slot_id)
    doctor = db.get(User, slot.doctor_user_id)
    return {"hold_id": h.id, "expires_at": h.expires_at, "cancellation_policy": booking.CANCELLATION_POLICY,
            "slot": {"starts_at": slot.starts_at, "ends_at": slot.ends_at, "consultation_type": slot.consultation_type,
                     "doctor": S.person(doctor),
                     "location": {"name": slot.organization.name, "address": slot.organization.address}
                     if slot.organization else None}}


class ConfirmIn(BaseModel):
    patient_id: str
    hold_id: str
    reason: str | None = Field(default=None, max_length=300)
    follow_up_id: str | None = None
    reschedule_appointment_id: str | None = None


@router.post("/appointments/confirm")
def confirm(body: ConfirmIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = _booking_access(db, user, body.patient_id)
    old = None
    if body.reschedule_appointment_id:
        old = db.get(Appointment, body.reschedule_appointment_id)
        if not old or old.patient_id != acc.patient.id:
            raise not_found("Appointment")
    appt = booking.confirm(db, user, acc.patient, body.hold_id, body.reason or (old.reason if old else None),
                           body.follow_up_id, rescheduled_from=old)
    if old:
        booking.cancel(db, user, old, "Rescheduled")
        old.status = "rescheduled"
    if body.follow_up_id:
        f = db.get(FollowUpInstruction, body.follow_up_id)
        if f and f.patient_id == acc.patient.id:
            f.appointment_id = appt.id
    db.commit()
    return S.appointment(appt)


@router.delete("/appointments/hold/{hold_id}")
def release(hold_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    h = db.get(SlotHold, hold_id)
    if h and h.user_id == user.id and h.status == "held":
        h.status = "released"
        booking._release(db, h.slot_id)
        db.commit()
    return {"status": "released"}


@router.get("/patients/{patient_id}/appointments")
def patient_appointments(patient_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "appointments.view")
    rows = db.execute(select(Appointment).where(Appointment.patient_id == patient_id)
                      .order_by(Appointment.starts_at.desc())).scalars()
    now = utcnow()
    out = {"upcoming": [], "past": []}
    for a in rows:
        (out["upcoming"] if a.starts_at >= now and a.status == "confirmed" else out["past"]).append(S.appointment(a))
    out["upcoming"].reverse()
    follow = db.execute(select(FollowUpInstruction).where(FollowUpInstruction.patient_id == patient_id,
                                                          FollowUpInstruction.kind == "follow_up",
                                                          FollowUpInstruction.status == "open")).scalars()
    out["recommended_follow_ups"] = [S.instruction(f) for f in follow]
    out["cancellation_policy"] = booking.CANCELLATION_POLICY
    return out


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/appointments/{appt_id}/cancel")
def cancel(appt_id: str, body: CancelIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Appointment, appt_id)
    if not a:
        raise not_found("Appointment")
    if user.role == "doctor":
        if a.doctor_user_id != user.id:
            raise forbidden()
    else:
        _booking_access(db, user, a.patient_id)
    booking.cancel(db, user, a, body.reason)
    db.commit()
    return S.appointment(a)
