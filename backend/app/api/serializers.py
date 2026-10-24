"""Response shapes shared by several routers."""
from app.models import (
    Appointment,
    DoseOccurrence,
    FollowUpInstruction,
    MedicalRecord,
    Notification,
    PrescriptionItem,
    PrescriptionVersion,
    UploadedDocument,
    User,
)

BUCKET = {
    "active": "current", "on_hold": "current", "scheduled": "upcoming", "draft": "upcoming",
    "pending_verification": "upcoming", "completed": "completed", "discontinued": "discontinued",
    "superseded": "discontinued",
}


def person(u: User | None) -> dict | None:
    if not u:
        return None
    out = {"id": u.id, "name": u.full_name, "role": u.role, "avatar_color": u.avatar_color}
    if u.role == "doctor" and u.doctor_profile:
        out["speciality"] = u.doctor_profile.speciality
    return out


def version(v: PrescriptionVersion) -> dict:
    s = v.schedule
    return {
        "id": v.id, "version_no": v.version_no, "status": v.status, "generic_name": v.generic_name,
        "brand_name": v.brand_name, "strength": v.strength, "dosage_form": v.dosage_form,
        "dose_amount": v.dose_amount, "dose_unit": v.dose_unit, "route": v.route,
        "frequency_label": v.frequency_label, "indication": v.indication, "duration_days": v.duration_days,
        "start_date": v.start_date, "end_date": v.end_date, "quantity": v.quantity,
        "refills_allowed": v.refills_allowed, "refill_instructions": v.refill_instructions,
        "food_instructions": v.food_instructions, "special_instructions": v.special_instructions,
        "missed_dose_guidance": v.missed_dose_guidance, "effective_from": v.effective_from,
        "change_reason": v.change_reason, "created_at": v.created_at, "author": person(v.author),
        "is_prn": v.is_prn,
        "schedule": {"times_of_day": s.times_of_day, "days_of_week": s.days_of_week,
                     "interval_days": s.interval_days, "timezone": s.timezone} if s else None,
    }


def item(it: PrescriptionItem, full: bool = False) -> dict:
    cur = next((v for v in it.versions if v.version_no == it.current_version_no), None)
    pending = next((v for v in it.versions if v.status == "scheduled"), None)
    out = {
        "id": it.id, "status": it.status, "bucket": BUCKET.get(it.status, "current"),
        "lock_version": it.lock_version, "prescription_id": it.prescription_id,
        "source": it.prescription.source, "prescriber": person(it.prescription.prescriber),
        "current": version(cur) if cur else None,
        "pending_change": version(pending) if pending else None,
        "discontinue": {"effective": it.discontinue_effective, "reason": it.discontinue_reason,
                        "instructions": it.discontinue_instructions, "follow_up": it.discontinue_follow_up}
        if it.discontinue_reason else None,
        "hold_reason": it.hold_reason,
        "updated_at": it.updated_at,
    }
    if full:
        out["versions"] = [version(v) for v in sorted(it.versions, key=lambda v: v.version_no, reverse=True)]
        cat = it.catalogue
        out["education"] = {
            "available": bool(cat and cat.education),
            "content": cat.education if cat else {},
            "source": cat.education_source if cat else None,
            "reviewed_at": cat.education_reviewed_at if cat else None,
        }
    return out


def dose(o: DoseOccurrence) -> dict:
    v = o.version
    return {
        "id": o.id, "item_id": o.item_id, "scheduled_at": o.scheduled_at, "status": o.status,
        "snoozed_until": o.snoozed_until, "responded_at": o.responded_at,
        "medicine": v.brand_name or v.generic_name, "generic_name": v.generic_name, "strength": v.strength,
        "dose": f"{v.dose_amount:g} {v.dose_unit}", "route": v.route,
        "instructions": " · ".join(x for x in (v.food_instructions, v.special_instructions) if x) or None,
        "version_no": v.version_no,
    }


def appointment(a: Appointment) -> dict:
    nxt = None
    if a.status == "rescheduled":  # point the old booking at its replacement
        from sqlalchemy import select as _select
        from sqlalchemy.orm import object_session

        nxt = object_session(a).execute(_select(Appointment).where(Appointment.rescheduled_from_id == a.id)
                                        .order_by(Appointment.created_at.desc())).scalars().first()
    return {
        "rescheduled_to": {"id": nxt.id, "starts_at": nxt.starts_at, "status": nxt.status} if nxt else None,
        "id": a.id, "patient_id": a.patient_id, "patient_name": a.patient.user.full_name if a.patient else None,
        "doctor": person(a.doctor), "starts_at": a.starts_at, "ends_at": a.ends_at,
        "consultation_type": a.consultation_type, "status": a.status, "reason": a.reason,
        "location": {"name": a.organization.name, "address": a.organization.address} if a.organization else None,
        "history": a.history, "follow_up_id": a.follow_up_id, "rescheduled_from_id": a.rescheduled_from_id,
        "join_available": False,  # video consultations are not implemented yet
    }


def record(r: MedicalRecord) -> dict:
    return {
        "id": r.id, "record_type": r.record_type, "title": r.title, "summary": r.summary,
        "occurred_at": r.occurred_at, "doctor": person(r.doctor),
        "organization": r.organization.name if r.organization else None, "document_id": r.document_id,
        "medication_names": r.medication_names, "data": r.data, "provenance": r.provenance, "status": r.status,
        "amends_id": r.amends_id,
    }


def document(d: UploadedDocument) -> dict:
    return {"id": d.id, "category": d.category, "title": d.title, "filename": d.original_filename,
            "mime_type": d.mime_type, "size_bytes": d.size_bytes, "created_at": d.created_at,
            "scan_status": d.scan_status, "is_demo": d.is_demo, "uploaded_by": d.uploaded_by}


def instruction(f: FollowUpInstruction) -> dict:
    return {
        "id": f.id, "kind": f.kind, "audience": f.audience, "title": f.title, "description": f.description,
        "priority": f.priority, "created_at": f.created_at, "expires_on": f.expires_on,
        "requires_ack": f.requires_ack, "acknowledged_at": f.acknowledged_at, "delivery_status": f.delivery_status,
        "due_date": f.due_date, "timeframe": f.timeframe, "appointment_request": f.appointment_request,
        "appointment_id": f.appointment_id, "status": f.status, "author": person(f.author),
        "patient_id": f.patient_id, "attachments": f.attachments,
    }


def notification(n: Notification) -> dict:
    return {"id": n.id, "category": n.category, "priority": n.priority, "title": n.title, "body": n.body,
            "link": n.link, "channel": n.channel, "delivery_status": n.delivery_status, "created_at": n.created_at,
            "read_at": n.read_at, "acknowledged_at": n.acknowledged_at, "patient_id": n.patient_id}
