"""Appointment booking with double-booking prevention.

Capacity is enforced by a single conditional UPDATE (`booked_count < capacity`), which is atomic
on both PostgreSQL and SQLite, so two concurrent requests for the last place cannot both win.
A short slot hold (5 minutes) reserves the place while the patient reviews the details.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import audit
from app.core.errors import bad_request, conflict, not_found
from app.integrations import aws_services
from app.models import (
    Appointment,
    AvailabilitySlot,
    DoctorAvailability,
    DoctorLeave,
    DoctorPatientAccess,
    PatientProfile,
    SlotHold,
    User,
)
from app.models.base import utcnow
from app.services import notifications, realtime

HOLD_MINUTES = 5
CANCELLATION_POLICY = "Free cancellation or rescheduling up to 2 hours before the appointment."


def materialize_slots(db: Session, doctor_id: str, days: int = 21) -> int:
    rules = db.execute(select(DoctorAvailability).where(DoctorAvailability.doctor_user_id == doctor_id)).scalars().all()
    leave = db.execute(select(DoctorLeave).where(DoctorLeave.doctor_user_id == doctor_id)).scalars().all()
    created = 0
    today = utcnow().astimezone(ZoneInfo("Asia/Kolkata")).date()
    for offset in range(days):
        day = today + timedelta(days=offset)
        if any(lv.start_date <= day <= lv.end_date for lv in leave):
            continue
        for r in rules:
            if r.weekday != day.weekday():
                continue
            tz = ZoneInfo(r.timezone)
            cur = datetime.combine(day, time.fromisoformat(r.start_time), tzinfo=tz)
            end = datetime.combine(day, time.fromisoformat(r.end_time), tzinfo=tz)
            while cur + timedelta(minutes=r.slot_minutes) <= end:
                starts = cur.astimezone(ZoneInfo("UTC"))
                if starts > utcnow():
                    try:
                        with db.begin_nested():
                            db.add(AvailabilitySlot(doctor_user_id=doctor_id, organization_id=r.organization_id,
                                                    starts_at=starts, ends_at=starts + timedelta(minutes=r.slot_minutes),
                                                    capacity=r.capacity, consultation_type=r.consultation_type))
                            db.flush()
                        created += 1
                    except IntegrityError:
                        pass
                cur += timedelta(minutes=r.slot_minutes)
    return created


def apply_leave(db: Session, doctor_id: str, start: date, end: date, reason: str | None) -> int:
    """Blocks open, unbooked slots in the leave window. Booked appointments are left for the
    doctor to reschedule explicitly - they are never silently cancelled."""
    db.add(DoctorLeave(doctor_user_id=doctor_id, start_date=start, end_date=end, reason=reason))
    n = 0
    tz = ZoneInfo("Asia/Kolkata")
    lo = datetime.combine(start, time.min, tzinfo=tz)
    hi = datetime.combine(end, time.max, tzinfo=tz)
    for s in db.execute(select(AvailabilitySlot).where(
            AvailabilitySlot.doctor_user_id == doctor_id, AvailabilitySlot.starts_at >= lo,
            AvailabilitySlot.starts_at <= hi, AvailabilitySlot.booked_count == 0)).scalars():
        s.status, s.block_reason = "blocked", reason or "Leave"
        n += 1
    return n


def _claim(db: Session, slot_id: str) -> bool:
    res = db.execute(
        update(AvailabilitySlot)
        .where(AvailabilitySlot.id == slot_id, AvailabilitySlot.status == "open",
               AvailabilitySlot.booked_count < AvailabilitySlot.capacity, AvailabilitySlot.starts_at > utcnow())
        .values(booked_count=AvailabilitySlot.booked_count + 1)
    )
    return res.rowcount == 1


def _release(db: Session, slot_id: str) -> None:
    db.execute(update(AvailabilitySlot).where(AvailabilitySlot.id == slot_id, AvailabilitySlot.booked_count > 0)
               .values(booked_count=AvailabilitySlot.booked_count - 1))


def hold(db: Session, user: User, patient: PatientProfile, slot_id: str) -> SlotHold:
    if not db.get(AvailabilitySlot, slot_id):
        raise not_found("Slot")
    # one active hold per patient: release any previous one
    for h in db.execute(select(SlotHold).where(SlotHold.patient_id == patient.id, SlotHold.status == "held")).scalars():
        h.status = "released"
        _release(db, h.slot_id)
    if not _claim(db, slot_id):
        raise conflict("Sorry, that time was just taken. Please choose another slot.")
    h = SlotHold(slot_id=slot_id, user_id=user.id, patient_id=patient.id,
                 expires_at=utcnow() + timedelta(minutes=HOLD_MINUTES))
    db.add(h)
    db.flush()
    return h


def confirm(db: Session, user: User, patient: PatientProfile, hold_id: str, reason: str | None,
            follow_up_id: str | None = None, rescheduled_from: Appointment | None = None) -> Appointment:
    h = db.get(SlotHold, hold_id)
    if not h or h.patient_id != patient.id or h.status != "held":
        raise conflict("Your hold on this slot expired. Please choose the time again.")
    if h.expires_at <= utcnow():
        h.status = "expired"
        _release(db, h.slot_id)
        raise conflict("Your hold on this slot expired. Please choose the time again.")
    slot = db.get(AvailabilitySlot, h.slot_id)
    h.status = "converted"
    appt = Appointment(
        patient_id=patient.id, doctor_user_id=slot.doctor_user_id, slot_id=slot.id,
        organization_id=slot.organization_id, starts_at=slot.starts_at, ends_at=slot.ends_at,
        consultation_type=slot.consultation_type, reason=reason, booked_by=user.id, follow_up_id=follow_up_id,
        rescheduled_from_id=rescheduled_from.id if rescheduled_from else None,
        history=[{"at": utcnow().isoformat(), "event": "booked", "by": user.id}],
    )
    db.add(appt)
    db.flush()
    _ensure_doctor_access(db, patient.id, slot.doctor_user_id, user.id)
    doctor = db.get(User, slot.doctor_user_id)
    local = _local(slot.starts_at)
    if rescheduled_from:
        moved = f"moved from {_local(rescheduled_from.starts_at)} to {local}"
        notifications.notify(db, patient.user, category="appointment_reminder", title="Appointment rescheduled",
                             body=f"{doctor.full_name} · {moved}", patient_id=patient.id, link="/patient/appointments",
                             dedupe_key=f"appt-resched:{appt.id}")
        notifications.notify(db, doctor, category="appointment_reminder", title="Appointment rescheduled",
                             body=f"{patient.user.full_name} · {moved}", patient_id=patient.id,
                             link="/doctor/appointments", dedupe_key=f"appt-resched-doc:{appt.id}")
    else:
        notifications.notify(db, patient.user, category="appointment_reminder", title="Appointment confirmed",
                             body=f"{doctor.full_name} · {local}", patient_id=patient.id, link="/patient/appointments",
                             dedupe_key=f"appt-confirm:{appt.id}")
        notifications.notify(db, doctor, category="appointment_reminder", title="New appointment booked",
                             body=f"{patient.user.full_name} · {local}", patient_id=patient.id,
                             link="/doctor/appointments", dedupe_key=f"appt-new:{appt.id}")
    audit.record(db, action="appointment_booked", resource_type="appointment", resource_id=appt.id,
                 patient_id=patient.id, user=user)
    aws_services.publish_event("AppointmentBooked", {"appointment_id": appt.id})
    realtime.queue(db, [patient.user_id, doctor.id], "appointments", patient.id, appt.id)
    return appt


def _ensure_doctor_access(db: Session, patient_id: str, doctor_id: str, granted_by: str) -> None:
    """Booking with a doctor grants that doctor clinical access for the consultation (recorded
    as granting_authority=appointment, expiring 90 days later). Patients can revoke it."""
    existing = db.execute(select(DoctorPatientAccess).where(
        DoctorPatientAccess.patient_id == patient_id, DoctorPatientAccess.doctor_user_id == doctor_id,
        DoctorPatientAccess.status == "active")).scalar_one_or_none()
    if not existing:
        db.add(DoctorPatientAccess(patient_id=patient_id, doctor_user_id=doctor_id,
                                   scopes=["clinical.read", "clinical.write", "prescribe"],
                                   purpose="Consultation booked through DoseWISE", granting_authority="appointment",
                                   granted_by=granted_by, starts_at=utcnow(), expires_at=utcnow() + timedelta(days=90)))


def _local(dt) -> str:
    return dt.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%a %d %b, %I:%M %p")


def cancel(db: Session, user: User, appt: Appointment, reason: str, notify: bool = True) -> None:
    """notify=False when the cancellation is part of a reschedule (that sends its own message)."""
    if appt.status != "confirmed":
        raise bad_request("Only confirmed appointments can be cancelled")
    if user.role != "doctor" and appt.starts_at - utcnow() < timedelta(hours=2):
        raise bad_request("Appointments can't be cancelled online within 2 hours. Please contact the clinic.")
    appt.status = "cancelled"
    appt.cancelled_by = user.id
    appt.cancel_reason = reason
    appt.history = [*appt.history, {"at": utcnow().isoformat(), "event": "cancelled", "by": user.id, "reason": reason}]
    if appt.slot_id:
        _release(db, appt.slot_id)
    if notify:  # both sides see it in their notifications, including whoever cancelled
        when = _local(appt.starts_at)
        for who, name, link in ((appt.patient.user, appt.doctor.full_name, "/patient/appointments"),
                                (appt.doctor, appt.patient.user.full_name, "/doctor/appointments")):
            notifications.notify(db, who, category="appointment_reminder", title="Appointment cancelled",
                                 body=f"{name} · {when} · {reason[:100]}", patient_id=appt.patient_id, link=link,
                                 dedupe_key=f"appt-cancel:{appt.id}:{who.id}")
    audit.record(db, action="appointment_cancelled", resource_type="appointment", resource_id=appt.id,
                 patient_id=appt.patient_id, user=user, reason=reason)
    realtime.queue(db, [appt.patient.user_id, appt.doctor_user_id], "appointments", appt.patient_id, appt.id)
