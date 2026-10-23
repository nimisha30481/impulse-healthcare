"""Background engine: one idempotent `tick()` run every minute (an asyncio loop locally; an
EventBridge Scheduler rule invoking the worker Lambda in AWS). Safe to run twice: every send is
guarded by a unique dedupe key or a status check."""
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    CareRelationship,
    DoctorPatientAccess,
    DoseOccurrence,
    MedicationEvent,
    PatientProfile,
    PrescriptionItem,
    SlotHold,
    AvailabilitySlot,
)
from app.models.base import utcnow
from app.services import escalation, medication_schedule, notifications, realtime
from app.services.permissions import users_with_access

log = logging.getLogger("impulse.jobs")


def _in_quiet_hours(policy, tzname: str, now) -> bool:
    q = policy.quiet_hours or {}
    if not q.get("start") or not q.get("end"):
        return False
    local = now.astimezone(ZoneInfo(tzname)).strftime("%H:%M")
    start, end = q["start"], q["end"]
    return (start <= local or local < end) if start > end else (start <= local < end)


def lifecycle(db: Session, now) -> None:
    for item in db.execute(select(PrescriptionItem).where(PrescriptionItem.status.in_(("scheduled", "active")))).scalars():
        cur = next((v for v in item.versions if v.version_no == item.current_version_no), None)
        if not cur:
            continue
        if item.status == "scheduled" and cur.effective_from <= now:
            item.status = "active"
        # promote future-dated versions once effective
        for v in item.versions:
            if v.status == "scheduled" and v.effective_from <= now:
                for old in item.versions:
                    if old.status == "current":
                        old.status = "superseded"
                v.status = "current"
                item.current_version_no = v.version_no
        cur = next((v for v in item.versions if v.version_no == item.current_version_no), cur)
        if item.status == "active" and cur.end_date and now.astimezone(ZoneInfo("Asia/Kolkata")).date() > cur.end_date:
            item.status = "completed"
        if item.status == "active" and item.discontinue_effective and item.discontinue_effective <= now:
            item.status = "discontinued"


def expire_grants(db: Session, now) -> None:
    for model in (CareRelationship, DoctorPatientAccess):
        for g in db.execute(select(model).where(model.status == "active", model.expires_at.is_not(None))).scalars():
            if g.expires_at <= now:
                g.status = "expired"
                realtime.queue(db, [g.patient.user_id], "permissions", g.patient_id)


def run_reminders(db: Session, now) -> None:
    for item in db.execute(select(PrescriptionItem).where(PrescriptionItem.status == "active")).scalars():
        medication_schedule.materialize_item(db, item, now)
    db.flush()

    due = db.execute(
        select(DoseOccurrence).where(
            DoseOccurrence.status.in_(("upcoming", "snoozed", "due", "awaiting_confirmation")),
            DoseOccurrence.scheduled_at <= now,
        )
    ).scalars().all()
    touched_patients = set()
    for occ in due:
        item = occ.item
        if item.status != "active":
            continue
        policy = escalation.policy_for(db, occ.patient_id)
        user = db.get(PatientProfile, occ.patient_id).user
        name = occ.version.brand_name or occ.version.generic_name

        if occ.status == "upcoming":
            occ.status = "due"
            notifications.notify(db, user, category="medication_reminder", title=f"Time for {name}",
                                 body=f"{occ.version.dose_amount:g} {occ.version.dose_unit} · {occ.version.route}",
                                 patient_id=occ.patient_id, link="/patient", priority="high",
                                 dedupe_key=f"reminder:{occ.id}")
            occ.reminder_sent_at = now
            db.add(MedicationEvent(occurrence_id=occ.id, item_id=occ.item_id, version_id=occ.version_id,
                                   patient_id=occ.patient_id, kind="reminder_sent", source="system"))
            touched_patients.add(occ.patient_id)
        elif occ.status == "snoozed" and occ.snoozed_until and occ.snoozed_until <= now:
            occ.status = "due"
            notifications.notify(db, user, category="medication_reminder", title=f"Reminder: {name}",
                                 body="Your snoozed reminder is due.", patient_id=occ.patient_id, link="/patient",
                                 dedupe_key=f"reminder:{occ.id}:snooze:{occ.snoozed_until.isoformat()}")
            touched_patients.add(occ.patient_id)
        elif occ.status == "due" and not occ.followup_sent_at and \
                now - occ.scheduled_at >= timedelta(minutes=policy.follow_up_after_minutes):
            if not _in_quiet_hours(policy, occ.version.schedule.timezone if occ.version.schedule else "Asia/Kolkata", now):
                notifications.notify(db, user, category="medication_reminder", title=f"Did you take {name}?",
                                     body="Let us know so your care record stays accurate.",
                                     patient_id=occ.patient_id, link="/patient", dedupe_key=f"followup:{occ.id}")
                db.add(MedicationEvent(occurrence_id=occ.id, item_id=occ.item_id, version_id=occ.version_id,
                                       patient_id=occ.patient_id, kind="followup_sent", source="system"))
            occ.followup_sent_at = now
            occ.status = "awaiting_confirmation"
            touched_patients.add(occ.patient_id)
        elif occ.status in ("due", "awaiting_confirmation") and \
                now - occ.scheduled_at >= timedelta(minutes=policy.unconfirmed_after_minutes):
            occ.status = "unconfirmed"
            db.add(MedicationEvent(occurrence_id=occ.id, item_id=occ.item_id, version_id=occ.version_id,
                                   patient_id=occ.patient_id, kind="marked_unconfirmed", source="system"))
            touched_patients.add(occ.patient_id)
            db.flush()
            escalation.evaluate(db, occ.patient_id)
    for pid in touched_patients:
        realtime.queue(db, [u.id for u in users_with_access(db, pid, "medications.view")], "doses", pid)


def appointment_reminders(db: Session, now) -> None:
    soon = db.execute(
        select(Appointment).where(
            Appointment.status == "confirmed",
            Appointment.starts_at > now,
            Appointment.starts_at <= now + timedelta(hours=24),
        )
    ).scalars()
    for appt in soon:
        notifications.notify(db, appt.patient.user, category="appointment_reminder", title="Appointment tomorrow",
                             body=f"With {appt.doctor.full_name}", patient_id=appt.patient_id,
                             link="/patient/appointments", dedupe_key=f"appt-reminder:{appt.id}")


def release_holds(db: Session, now) -> None:
    for hold in db.execute(select(SlotHold).where(SlotHold.status == "held", SlotHold.expires_at <= now)).scalars():
        hold.status = "expired"
        slot = db.get(AvailabilitySlot, hold.slot_id)
        if slot and slot.booked_count > 0:
            slot.booked_count -= 1


def tick(db: Session) -> None:
    now = utcnow()
    for step in (lifecycle, expire_grants, release_holds, run_reminders, appointment_reminders):
        try:
            step(db, now)
            db.commit()
        except Exception:  # noqa: BLE001 - one failing step must not stop the others
            db.rollback()
            log.exception("background step %s failed", step.__name__)
    try:
        notifications.retry_failed(db)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("notification retry failed")
