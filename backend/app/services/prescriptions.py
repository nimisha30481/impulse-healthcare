"""Prescription workflows: create, edit (new immutable version), discontinue, hold/resume.
Every change is transactional with its dose updates, notifications, timeline entry and audit row."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import audit
from app.core.errors import bad_request, conflict
from app.integrations import aws_services
from app.models import (
    MedicalRecord,
    MedicationSchedule,
    PatientProfile,
    Prescription,
    PrescriptionItem,
    PrescriptionVersion,
    User,
)
from app.models.base import utcnow
from app.models.medication import ITEM_TRANSITIONS
from app.schemas.prescriptions import MedicationOrder
from app.services import interactions, medication_schedule, notifications, realtime
from app.services.permissions import users_with_access


def transition(item: PrescriptionItem, new_status: str) -> None:
    if new_status not in ITEM_TRANSITIONS.get(item.status, set()):
        raise bad_request(f"Cannot change a {item.status.replace('_', ' ')} prescription to {new_status.replace('_', ' ')}")
    item.status = new_status


def current_version(item: PrescriptionItem) -> PrescriptionVersion:
    return next(v for v in item.versions if v.version_no == item.current_version_no)


def _new_version(item: PrescriptionItem, order: MedicationOrder, version_no: int, effective_from: datetime,
                 author: User | None, reason: str | None, status: str) -> PrescriptionVersion:
    data = order.model_dump(exclude={"catalogue_id", "times_of_day", "days_of_week", "interval_days", "timezone"})
    v = PrescriptionVersion(version_no=version_no, effective_from=effective_from,
                            created_by=getattr(author, "id", None), change_reason=reason, status=status, **data)
    v.schedule = MedicationSchedule(times_of_day=order.times_of_day, days_of_week=order.days_of_week,
                                    interval_days=order.interval_days, timezone=order.timezone)
    item.versions.append(v)  # append on the parent so the save cascades (SQLAlchemy 2 has no backref cascade)
    return v


def _start_instant(order: MedicationOrder) -> datetime:
    return datetime.combine(order.start_date, datetime.min.time(), tzinfo=timezone.utc)


def _fanout(db: Session, patient_id: str, topic: str, ref: str) -> None:
    realtime.queue(db, [u.id for u in users_with_access(db, patient_id, "medications.view")], topic, patient_id, ref)


def _notify_patient_and_caregivers(db: Session, patient: PatientProfile, category: str, title: str, body: str,
                                   dedupe: str) -> None:
    notifications.notify(db, patient.user, category=category, title=title, body=body, patient_id=patient.id,
                         link="/patient/medicines", dedupe_key=f"{dedupe}:patient")
    for u in users_with_access(db, patient.id, "medications.view"):
        if u.role == "caregiver":
            notifications.notify(db, u, category="caregiver_update", title=title, body=body, patient_id=patient.id,
                                 link=f"/caregiver/patients/{patient.id}", dedupe_key=f"{dedupe}:{u.id}")


def create(db: Session, doctor: User, patient: PatientProfile, orders: list[MedicationOrder], notes: str | None,
           publish: bool, source: str = "impulse") -> tuple[Prescription, list]:
    now = utcnow()
    rx = Prescription(patient_id=patient.id, prescriber_user_id=doctor.id, notes=notes, source=source,
                      issued_at=now if publish else None,
                      organization_id=doctor.doctor_profile.organization_id if doctor.doctor_profile else None)
    db.add(rx)
    db.flush()
    created_items = []
    for order in orders:
        start = max(_start_instant(order), now) if order.start_date <= now.date() else _start_instant(order)
        status = "draft" if not publish else ("active" if start <= now else "scheduled")
        item = PrescriptionItem(prescription_id=rx.id, patient_id=patient.id, catalogue_id=order.catalogue_id,
                                status=status, current_version_no=1, lock_version=1)
        db.add(item)
        db.flush()
        _new_version(item, order, 1, start, doctor, "Initial prescription", "current")
        db.flush()
        created_items.append(item)
        audit.record(db, action="prescription_created", resource_type="prescription_item", resource_id=item.id,
                     patient_id=patient.id, user=doctor, version_ref="v1", auth_context="doctor_access")
    assessments = []
    for item in created_items:
        assessments.append(interactions.assess(db, patient.id, new_item=item, user=doctor))
    if publish:
        for item in created_items:
            medication_schedule.materialize_item(db, item, now)
        names = ", ".join(current_version(i).generic_name for i in created_items)
        _notify_patient_and_caregivers(db, patient, "new_prescription", "New prescription",
                                       f"{doctor.full_name} prescribed: {names}", f"rx-new:{rx.id}")
        db.add(MedicalRecord(patient_id=patient.id, record_type="prescription", title=f"Prescription: {names}",
                             summary=notes, occurred_at=now, doctor_user_id=doctor.id,
                             organization_id=rx.organization_id, medication_names=[current_version(i).generic_name
                                                                                    for i in created_items],
                             provenance="clinician_verified", created_by=doctor.id))
        aws_services.publish_event("PrescriptionCreated", {"prescription_id": rx.id, "patient_id": patient.id})
        _fanout(db, patient.id, "medications", rx.id)
    return rx, assessments


def edit(db: Session, doctor: User, item: PrescriptionItem, order: MedicationOrder, reason: str,
         expected_lock: int, effective_from: datetime | None):
    if item.lock_version != expected_lock:
        raise conflict("This prescription was changed by someone else. Reload to see the latest version.")
    if item.status not in ("active", "scheduled", "on_hold"):
        raise bad_request(f"A {item.status.replace('_', ' ')} prescription cannot be edited")
    if any(v.status == "scheduled" for v in item.versions):
        raise conflict("A future-dated change is already pending for this prescription")
    now = utcnow()
    eff = effective_from or now
    if eff < now:
        eff = now  # changes cannot be backdated
    old = current_version(item)
    new_no = max(v.version_no for v in item.versions) + 1
    immediate = eff <= now
    new = _new_version(item, order, new_no, eff, doctor, reason, "current" if immediate else "scheduled")
    if immediate:
        old.status = "superseded"
        item.current_version_no = new_no
    item.lock_version += 1
    db.flush()
    medication_schedule.cancel_future_doses(db, item, eff, f"Replaced by version {new_no}", doctor.id)
    medication_schedule.materialize_item(db, item, now)
    assessment = interactions.assess(db, item.patient_id, new_item=item, user=doctor)
    patient = db.get(PatientProfile, item.patient_id)
    when = "now" if immediate else eff.strftime("%d %b %Y %H:%M UTC")
    _notify_patient_and_caregivers(db, patient, "prescription_change", "Prescription updated",
                                   f"{old.generic_name}: your doctor changed this prescription (effective {when}).",
                                   f"rx-edit:{item.id}:{new_no}")
    audit.record(db, action="prescription_changed", resource_type="prescription_item", resource_id=item.id,
                 patient_id=item.patient_id, user=doctor, version_ref=f"v{old.version_no}->v{new_no}",
                 reason=reason, auth_context="doctor_access")
    aws_services.publish_event("PrescriptionUpdated", {"item_id": item.id, "version": new_no})
    _fanout(db, item.patient_id, "medications", item.id)
    return new, assessment


def discontinue(db: Session, doctor: User, item: PrescriptionItem, *, effective_at: datetime | None, reason: str,
                instructions: str | None, follow_up: str | None, expected_lock: int) -> None:
    if item.lock_version != expected_lock:
        raise conflict("This prescription was changed by someone else. Reload to see the latest version.")
    if "discontinued" not in ITEM_TRANSITIONS.get(item.status, set()):
        raise bad_request(f"A {item.status.replace('_', ' ')} prescription cannot be discontinued")
    now = utcnow()
    eff = max(effective_at or now, now)
    item.discontinue_effective = eff
    item.discontinue_reason = reason
    item.discontinue_instructions = instructions
    item.discontinue_follow_up = follow_up
    if eff <= now:
        item.status = "discontinued"
        item.discontinued_at = now
    item.lock_version += 1
    medication_schedule.cancel_future_doses(db, item, eff, "Medication discontinued", doctor.id)
    v = current_version(item)
    patient = db.get(PatientProfile, item.patient_id)
    when = "now" if eff <= now else eff.strftime("%d %b %Y")
    _notify_patient_and_caregivers(db, patient, "prescription_change", "Medicine discontinued",
                                   f"{v.generic_name} is discontinued (effective {when}). Open DoseWISE for "
                                   f"your doctor's instructions.", f"rx-stop:{item.id}")
    db.add(MedicalRecord(patient_id=patient.id, record_type="prescription", title=f"Discontinued: {v.generic_name}",
                         summary=reason, occurred_at=now, doctor_user_id=doctor.id, medication_names=[v.generic_name],
                         provenance="clinician_verified", created_by=doctor.id))
    audit.record(db, action="medication_discontinued", resource_type="prescription_item", resource_id=item.id,
                 patient_id=item.patient_id, user=doctor, version_ref=f"v{v.version_no}", reason=reason,
                 auth_context="doctor_access")
    aws_services.publish_event("MedicationDiscontinued", {"item_id": item.id})
    _fanout(db, item.patient_id, "medications", item.id)


def set_status(db: Session, doctor: User, item: PrescriptionItem, status: str, reason: str, expected_lock: int) -> None:
    if item.lock_version != expected_lock:
        raise conflict("This prescription was changed by someone else. Reload to see the latest version.")
    if status not in ("on_hold", "active", "completed"):
        raise bad_request("Use the discontinue workflow to stop a medicine")
    prev = item.status
    transition(item, status)
    item.lock_version += 1
    now = utcnow()
    if status == "on_hold":
        item.hold_reason = reason
        medication_schedule.cancel_future_doses(db, item, now, "Medication on hold", doctor.id)
    if status == "completed":
        medication_schedule.cancel_future_doses(db, item, now, "Course completed", doctor.id)
    if status == "active":
        item.hold_reason = None
        medication_schedule.materialize_item(db, item, now)
    patient = db.get(PatientProfile, item.patient_id)
    v = current_version(item)
    _notify_patient_and_caregivers(db, patient, "prescription_change", "Prescription status changed",
                                   f"{v.generic_name}: {prev.replace('_', ' ')} → {status.replace('_', ' ')}",
                                   f"rx-status:{item.id}:{item.lock_version}")
    audit.record(db, action="prescription_status_changed", resource_type="prescription_item", resource_id=item.id,
                 patient_id=item.patient_id, user=doctor, reason=f"{prev}->{status}: {reason}",
                 auth_context="doctor_access")
    _fanout(db, item.patient_id, "medications", item.id)
