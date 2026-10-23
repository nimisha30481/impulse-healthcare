"""Central, server-side, resource-level authorisation for patient data.

Every patient-scoped endpoint calls `authorize_patient`. Frontend role checks are cosmetic only.
"""
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.errors import forbidden, not_found
from app.models import (
    BreakGlassAccess,
    CareRelationship,
    DoctorPatientAccess,
    PatientProfile,
    SupportCase,
    User,
)
from app.models.base import utcnow

# Scopes a doctor's "clinical.read" covers
READ_SCOPES = {
    "medications.view",
    "records.view",
    "appointments.view",
    "instructions.view",
    "adherence.view",
    "careteam.view",
}
WRITE_SCOPES = {"clinical.write", "prescribe", "instructions.write", "messages.patient", "appointments.book"}


@dataclass
class Access:
    patient: PatientProfile
    kind: str  # owner | caregiver_grant | doctor_access | break_glass | support_case
    grant_id: str | None = None


def patient_of(db: Session, user: User) -> PatientProfile:
    p = db.execute(select(PatientProfile).where(PatientProfile.user_id == user.id)).scalar_one_or_none()
    if not p:
        raise forbidden("No patient profile for this account")
    return p


def _active(grant, now) -> bool:
    if grant.status != "active":
        return False
    if grant.starts_at and grant.starts_at > now:
        return False
    if grant.expires_at and grant.expires_at <= now:
        grant.status = "expired"  # automatic expiry, persisted by the caller's commit
        return False
    return True


def active_caregiver_grant(db: Session, caregiver: User, patient_id: str) -> CareRelationship | None:
    now = utcnow()
    for rel in db.execute(
        select(CareRelationship).where(
            CareRelationship.patient_id == patient_id,
            CareRelationship.caregiver_user_id == caregiver.id,
            CareRelationship.status == "active",
        )
    ).scalars():
        if _active(rel, now):
            return rel
    return None


def active_doctor_access(db: Session, doctor: User, patient_id: str) -> DoctorPatientAccess | None:
    now = utcnow()
    for acc in db.execute(
        select(DoctorPatientAccess).where(
            DoctorPatientAccess.patient_id == patient_id,
            DoctorPatientAccess.doctor_user_id == doctor.id,
            DoctorPatientAccess.status == "active",
        )
    ).scalars():
        if _active(acc, now):
            return acc
    return None


def _break_glass(db: Session, user: User, patient_id: str) -> BreakGlassAccess | None:
    return db.execute(
        select(BreakGlassAccess).where(
            BreakGlassAccess.patient_id == patient_id,
            BreakGlassAccess.user_id == user.id,
            BreakGlassAccess.expires_at > utcnow(),
        )
    ).scalar_one_or_none()


def check_patient_access(db: Session, user: User, patient_id: str, scope: str) -> Access | None:
    patient = db.get(PatientProfile, patient_id)
    if not patient:
        return None
    if user.role == "patient":
        return Access(patient, "owner") if patient.user_id == user.id else None
    if user.role == "caregiver":
        rel = active_caregiver_grant(db, user, patient_id)
        if rel and scope in (rel.scopes or []):
            return Access(patient, "caregiver_grant", rel.id)
        return None
    if user.role == "doctor":
        if not user.doctor_profile or user.doctor_profile.verification_status != "verified":
            return None
        acc = active_doctor_access(db, user, patient_id)
        if acc:
            scopes = set(acc.scopes or [])
            if scope in READ_SCOPES and "clinical.read" in scopes:
                return Access(patient, "doctor_access", acc.id)
            if scope in scopes or (scope in WRITE_SCOPES and "clinical.write" in scopes and scope != "prescribe"):
                return Access(patient, "doctor_access", acc.id)
        bg = _break_glass(db, user, patient_id)
        if bg and scope in READ_SCOPES:
            return Access(patient, "break_glass", bg.id)
        return None
    if user.role == "support":
        # minimum necessary: support staff only see patients on cases assigned to them
        case = db.execute(
            select(SupportCase).where(
                SupportCase.patient_id == patient_id,
                SupportCase.assigned_to == user.id,
                SupportCase.status != "resolved",
            )
        ).first()
        if case and scope in {"case.contact", "careteam.view"}:
            return Access(patient, "support_case")
        return None
    return None  # admins get no clinical access by role alone


def authorize_patient(db: Session, user: User, patient_id: str, scope: str, *, audit_read: bool = False) -> Access:
    access = check_patient_access(db, user, patient_id, scope)
    if access is None:
        if not db.get(PatientProfile, patient_id):
            raise not_found("Patient")
        audit.record(
            db,
            action="access_denied",
            resource_type="patient",
            resource_id=patient_id,
            patient_id=patient_id,
            user=user,
            reason=scope,
            outcome="denied",
            commit=True,
        )
        raise forbidden()
    if audit_read:
        audit.record(
            db,
            action=f"read:{scope}",
            resource_type="patient",
            resource_id=patient_id,
            patient_id=patient_id,
            user=user,
            auth_context=access.kind,
        )
        db.commit()
    return access


def patients_visible_to(db: Session, user: User) -> list[str]:
    """Patient ids this user can currently reach - used for lists and real-time fan-out."""
    if user.role == "patient":
        p = db.execute(select(PatientProfile.id).where(PatientProfile.user_id == user.id)).scalar_one_or_none()
        return [p] if p else []
    now = utcnow()
    if user.role == "caregiver":
        rels = db.execute(
            select(CareRelationship).where(
                CareRelationship.caregiver_user_id == user.id, CareRelationship.status == "active"
            )
        ).scalars()
        return [r.patient_id for r in rels if _active(r, now)]
    if user.role == "doctor":
        accs = db.execute(
            select(DoctorPatientAccess).where(
                DoctorPatientAccess.doctor_user_id == user.id, DoctorPatientAccess.status == "active"
            )
        ).scalars()
        return [a.patient_id for a in accs if _active(a, now)]
    if user.role == "support":
        rows = db.execute(
            select(SupportCase.patient_id).where(
                SupportCase.assigned_to == user.id, or_(SupportCase.status != "resolved")
            )
        ).scalars()
        return list(set(rows))
    return []


def users_with_access(db: Session, patient_id: str, scope: str) -> list[User]:
    """Everyone who should receive updates about this patient for a given scope."""
    out: list[User] = []
    patient = db.get(PatientProfile, patient_id)
    if patient:
        out.append(patient.user)
    now = utcnow()
    for rel in db.execute(
        select(CareRelationship).where(CareRelationship.patient_id == patient_id, CareRelationship.status == "active")
    ).scalars():
        if _active(rel, now) and scope in (rel.scopes or []) and rel.caregiver:
            out.append(rel.caregiver)
    for acc in db.execute(
        select(DoctorPatientAccess).where(
            DoctorPatientAccess.patient_id == patient_id, DoctorPatientAccess.status == "active"
        )
    ).scalars():
        if _active(acc, now):
            out.append(acc.doctor)
    return out
