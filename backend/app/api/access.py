"""Reference data, Patient Access IDs, guest (unregistered) doctor access, doctor access by ID,
and the doctor-facing dose log."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import rate_limit
from app.core import audit
from app.core.database import get_db
from app.core.deps import client_ip, current_user, require_roles
from app.core.india import COUNCILS, SPECIALITIES, STATES
from app.models import (
    Allergy,
    Diagnosis,
    DoctorPatientAccess,
    DoseOccurrence,
    GuestAccessLog,
    MedicalRecord,
    PrescriptionItem,
    User,
)
from app.models.base import utcnow
from app.services import access_ids, notifications
from app.services.medication_schedule import adherence_summary
from app.services.permissions import authorize_patient, patient_of

router = APIRouter(prefix="/api", tags=["access"])

LATE_AFTER_MINUTES = 60  # a dose logged more than this long after its scheduled time is "late"

GENERIC_ERROR = "That Patient Access ID wasn't recognised. Check the code with the patient and try again."
EXPIRED_ERROR = "This Patient Access ID has expired. Ask the patient to generate a new one from their dashboard."


@router.get("/reference")
def reference():
    return {"specialities": SPECIALITIES, "councils": COUNCILS, "states": STATES}


# ---------------- patient: their own Access ID ----------------
def _access_out(p):
    return {"access_id": p.access_id, "created_at": p.access_id_created_at, "expires_at": access_ids.expires_at(p)}


@router.get("/me/access-id")
def my_access_id(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = patient_of(db, user)
    if not p.access_id:
        p.access_id, p.access_id_created_at = access_ids.new_access_id(db), utcnow()
        db.commit()
    return _access_out(p)


@router.post("/me/access-id/regenerate")
def regenerate(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = patient_of(db, user)
    old = p.access_id
    p.access_id, p.access_id_created_at = access_ids.new_access_id(db), utcnow()
    audit.record(db, action="access_id_regenerated", resource_type="patient", resource_id=p.id, patient_id=p.id,
                 user=user, reason=f"replaced {old[:4]}…" if old else None)
    db.commit()
    return _access_out(p)


# ---------------- read-only chart (guest view) ----------------
def read_only_chart(db: Session, p) -> dict:
    now = utcnow()
    items = db.execute(select(PrescriptionItem).where(PrescriptionItem.patient_id == p.id,
                                                      PrescriptionItem.status.in_(("active", "on_hold")))).scalars()
    meds = []
    for it in items:
        v = next((v for v in it.versions if v.version_no == it.current_version_no), None)
        if v:
            meds.append({"name": v.brand_name or v.generic_name, "generic_name": v.generic_name, "strength": v.strength,
                         "dose": f"{v.dose_amount:g} {v.dose_unit}", "route": v.route, "frequency": v.frequency_label,
                         "times": v.schedule.times_of_day if v.schedule else [],
                         "instructions": " · ".join(x for x in (v.food_instructions, v.special_instructions) if x) or None,
                         "prescribed": v.start_date, "status": it.status})
    allergies = [{"substance": a.substance, "reaction": a.reaction, "severity": a.severity, "provenance": a.provenance}
                 for a in db.execute(select(Allergy).where(Allergy.patient_id == p.id, Allergy.status == "active")).scalars()]
    doses = db.execute(select(DoseOccurrence).where(DoseOccurrence.patient_id == p.id,
                                                    DoseOccurrence.scheduled_at <= now,
                                                    DoseOccurrence.status != "cancelled")
                       .order_by(DoseOccurrence.scheduled_at.desc()).limit(20)).scalars()
    records = db.execute(select(MedicalRecord).where(MedicalRecord.patient_id == p.id, MedicalRecord.status == "current")
                         .order_by(MedicalRecord.occurred_at.desc()).limit(15)).scalars()
    dx = db.execute(select(Diagnosis).where(Diagnosis.patient_id == p.id)).scalars()
    adh = adherence_summary(db, p.id, 30)
    return {
        "patient": {"name": p.user.full_name, "access_id": p.access_id, "dob": p.date_of_birth, "sex": p.sex,
                    "blood_group": p.blood_group, "phone": p.user.phone,
                    "emergency_contact": {"name": p.emergency_contact_name, "phone": p.emergency_contact_phone,
                                          "relation": p.emergency_contact_relation}},
        "allergy_status": p.allergy_status,
        "allergies": allergies,
        "conditions": [{"name": d.name, "code": d.code, "status": d.status} for d in dx],
        "active_medications": meds,
        "dose_history": [_dose_row(o) for o in doses],
        "records": [{"type": r.record_type, "title": r.title, "summary": r.summary, "date": r.occurred_at,
                     "provenance": r.provenance} for r in records],
        "adherence": {"reported_rate": adh["reported_rate"], "taken_reported": adh["taken_reported"],
                      "scheduled": adh["scheduled"], "unconfirmed": adh["unconfirmed"], "method": adh["method"]},
        "generated_at": now,
        "notice": "Read-only. Patient-reported and demo data are labelled; verify clinically before acting.",
    }


class GuestIn(BaseModel):
    access_id: str = Field(min_length=4, max_length=32)
    doctor_name: str | None = Field(default=None, max_length=160)
    doctor_license: str | None = Field(default=None, max_length=80)
    hospital: str | None = Field(default=None, max_length=200)


@router.post("/access/guest-view")
def guest_view(body: GuestIn, request: Request, db: Session = Depends(get_db)):
    """Unauthenticated, read-only lookup. The Access ID is the patient's consent; every attempt is logged."""
    ip = client_ip(request)
    log = GuestAccessLog(ip_address=ip, user_agent=(request.headers.get("user-agent") or "")[:300],
                         access_id_entered=body.access_id.strip()[:32], doctor_name=body.doctor_name,
                         doctor_license=body.doctor_license, hospital=body.hospital, outcome="invalid")
    db.add(log)
    try:
        rate_limit(f"guest:{ip}", 10, 900)  # brute-force protection: 10 lookups / 15 min / IP
    except HTTPException:
        log.outcome = "rate_limited"
        db.commit()
        raise
    p, outcome = access_ids.lookup(db, body.access_id)
    log.outcome = outcome
    log.patient_id = p.id if p else None
    if outcome != "granted":
        audit.record(db, action="guest_access_denied", resource_type="patient", resource_id=p.id if p else None,
                     patient_id=p.id if p else None, reason=outcome, outcome="denied", source="guest", ip_address=ip)
        db.commit()
        raise HTTPException(410 if outcome == "expired" else 404, EXPIRED_ERROR if outcome == "expired" else GENERIC_ERROR)
    who = ", ".join(x for x in (body.doctor_name, body.doctor_license, body.hospital) if x) or "an unnamed guest doctor"
    audit.record(db, action="guest_record_view", resource_type="patient", resource_id=p.id, patient_id=p.id,
                 reason=who[:300], auth_context="patient_access_id", source="guest", ip_address=ip)
    notifications.notify(db, p.user, category="security", title="Your record was viewed with your Access ID",
                         body=f"Viewed by {who}. If you didn't share your Access ID, regenerate it now.",
                         patient_id=p.id, link="/patient", priority="high")
    out = read_only_chart(db, p)
    out["session"] = {"viewer": who, "access_id": p.access_id}
    db.commit()
    return out


# ---------------- registered doctor: open a patient by Access ID ----------------
class DoctorAccessIn(BaseModel):
    access_id: str = Field(min_length=4, max_length=32)


@router.post("/doctor/access-id")
def doctor_access(body: DoctorAccessIn, request: Request, user: User = Depends(require_roles("doctor")),
                  db: Session = Depends(get_db)):
    rate_limit(f"doctor-access:{user.id}", 20, 900)
    p, outcome = access_ids.lookup(db, body.access_id)
    if outcome != "granted":
        audit.record(db, action="doctor_access_id_denied", resource_type="patient", patient_id=p.id if p else None,
                     user=user, reason=outcome, outcome="denied", ip_address=client_ip(request), commit=True)
        raise HTTPException(410 if outcome == "expired" else 404, EXPIRED_ERROR if outcome == "expired" else GENERIC_ERROR)
    now = utcnow()
    acc = db.execute(select(DoctorPatientAccess).where(
        DoctorPatientAccess.patient_id == p.id, DoctorPatientAccess.doctor_user_id == user.id,
        DoctorPatientAccess.status == "active")).scalars().first()
    if acc and acc.expires_at and acc.expires_at <= now:
        acc.status, acc = "expired", None
    if acc:
        acc.expires_at = max(acc.expires_at or now, now + timedelta(days=90))
    else:
        acc = DoctorPatientAccess(patient_id=p.id, doctor_user_id=user.id, purpose="Opened with the patient's Access ID",
                                  granting_authority="access_id", granted_by=p.user_id, starts_at=now,
                                  expires_at=now + timedelta(days=90))
        db.add(acc)
        notifications.notify(db, p.user, category="security", title="A doctor opened your record",
                             body=f"{user.full_name} used your Access ID. You can revoke this in Care Team.",
                             patient_id=p.id, link="/patient/care-team")
    db.flush()
    audit.record(db, action="doctor_access_id_granted", resource_type="doctor_access", resource_id=acc.id,
                 patient_id=p.id, user=user, auth_context="patient_access_id", ip_address=client_ip(request))
    db.commit()
    return {"patient_id": p.id, "name": p.user.full_name, "expires_at": acc.expires_at}


# ---------------- dose log (doctor / care team) ----------------
def _dose_row(o: DoseOccurrence) -> dict:
    v = o.version
    logged = o.responded_at if o.status == "taken_reported" else None
    if o.status == "taken_reported":
        late = logged and (logged - o.scheduled_at) > timedelta(minutes=LATE_AFTER_MINUTES)
        state = "late" if late else "taken"
    elif o.status in ("missed_reported", "skipped"):
        state = "missed"
    elif o.status == "unconfirmed":
        state = "not_logged"
    else:
        state = "pending"
    return {"id": o.id, "medication": v.brand_name or v.generic_name, "strength": v.strength,
            "dose": f"{v.dose_amount:g} {v.dose_unit}", "scheduled_at": o.scheduled_at, "logged_at": logged,
            "responded_at": o.responded_at, "raw_status": o.status, "state": state}


@router.get("/doctor/patients/{patient_id}/dose-log")
def dose_log(patient_id: str, days: int = Query(14, ge=1, le=90), user: User = Depends(current_user),
             db: Session = Depends(get_db)):
    """Server-side authorised: doctors (or care team) only see patients they may access."""
    if user.role not in ("doctor", "caregiver", "patient"):
        raise HTTPException(403, "Not available for your account type")
    authorize_patient(db, user, patient_id, "medications.view")
    now = utcnow()
    rows = db.execute(select(DoseOccurrence).where(
        DoseOccurrence.patient_id == patient_id, DoseOccurrence.scheduled_at >= now - timedelta(days=days),
        DoseOccurrence.scheduled_at <= now + timedelta(hours=2), DoseOccurrence.status != "cancelled")
        .order_by(DoseOccurrence.scheduled_at.desc())).scalars().all()
    out = [_dose_row(o) for o in rows]
    counts = {k: sum(1 for r in out if r["state"] == k) for k in ("taken", "late", "missed", "not_logged", "pending")}
    return {"rows": out, "counts": counts, "late_after_minutes": LATE_AFTER_MINUTES, "generated_at": now}
