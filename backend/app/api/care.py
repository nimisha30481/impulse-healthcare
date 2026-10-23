"""Permissions management: caregiver invitations (invite -> accept -> patient authorises ->
active), scope changes, revocation, doctor access grants, access history, break-glass."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import serializers as S
from app.core import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import current_user, require_roles
from app.core.errors import bad_request, forbidden, not_found
from app.core.security import hash_token, new_token
from app.integrations import aws_services
from app.models import (
    AuditLog,
    BreakGlassAccess,
    CareRelationship,
    ConsentRecord,
    DoctorPatientAccess,
    EscalationPolicy,
    PatientProfile,
    User,
)
from app.models.base import utcnow
from app.models.care import CAREGIVER_SCOPES
from app.services import escalation, notifications, realtime
from app.services.permissions import active_caregiver_grant, patient_of
from app.services.medication_schedule import adherence_summary

router = APIRouter(tags=["permissions"])


def _rel_out(r: CareRelationship) -> dict:
    return {"id": r.id, "status": r.status, "contact": r.invite_contact, "label": r.relationship_label,
            "scopes": r.scopes, "purpose": r.purpose, "starts_at": r.starts_at, "expires_at": r.expires_at,
            "accepted_at": r.accepted_at, "authorized_at": r.authorized_at, "revoked_at": r.revoked_at,
            "revocation_reason": r.revocation_reason, "caregiver": S.person(r.caregiver),
            "patient_id": r.patient_id, "patient_name": r.patient.user.full_name}


def _consent(db, patient_id, actor, action, resource, rid, scopes=None, subject=None, note=None):
    db.add(ConsentRecord(patient_id=patient_id, actor_user_id=actor.id, subject_user_id=subject, action=action,
                         resource=resource, resource_id=rid, scopes=scopes or [], note=note))


# ---------------- patient side ----------------
class InviteIn(BaseModel):
    contact: str = Field(min_length=5, max_length=255)  # email or phone
    relationship_label: str = Field(default="Family member", max_length=60)
    scopes: list[str] = Field(min_length=1)
    purpose: str = Field(default="Support with medication and appointments", max_length=200)
    expires_in_days: int | None = Field(default=None, ge=1, le=730)


@router.get("/api/me/permissions")
def my_permissions(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = patient_of(db, user)
    rels = db.execute(select(CareRelationship).where(CareRelationship.patient_id == p.id)
                      .order_by(CareRelationship.created_at.desc())).scalars()
    docs = db.execute(select(DoctorPatientAccess).where(DoctorPatientAccess.patient_id == p.id)
                      .order_by(DoctorPatientAccess.created_at.desc())).scalars()
    history = db.execute(select(ConsentRecord).where(ConsentRecord.patient_id == p.id)
                         .order_by(ConsentRecord.created_at.desc()).limit(50)).scalars()
    access_log = db.execute(select(AuditLog).where(AuditLog.patient_id == p.id, AuditLog.user_id != user.id)
                            .order_by(AuditLog.seq.desc()).limit(50)).scalars().all()
    names = {u.id: (u.full_name, u.role) for u in db.execute(
        select(User).where(User.id.in_({a.user_id for a in access_log if a.user_id}))).scalars()}
    policy = escalation.policy_for(db, p.id)
    db.commit()
    return {
        "caregivers": [_rel_out(r) for r in rels],
        "doctors": [{"id": d.id, "doctor": S.person(d.doctor), "status": d.status, "scopes": d.scopes,
                     "purpose": d.purpose, "granting_authority": d.granting_authority, "starts_at": d.starts_at,
                     "expires_at": d.expires_at, "revoked_at": d.revoked_at} for d in docs],
        "consent_history": [{"id": c.id, "at": c.created_at, "action": c.action, "resource": c.resource,
                             "scopes": c.scopes, "note": c.note} for c in history],
        "access_history": [{"at": a.created_at, "who": names.get(a.user_id, ("System", "system"))[0],
                            "role": names.get(a.user_id, ("", a.user_role or "system"))[1], "action": a.action,
                            "auth_context": a.auth_context, "outcome": a.outcome} for a in access_log],
        "available_scopes": CAREGIVER_SCOPES,
        "escalation_policy": {"notify_caregiver_approved": policy.notify_caregiver_approved,
                              "follow_up_after_minutes": policy.follow_up_after_minutes,
                              "caregiver_after_consecutive": policy.caregiver_after_consecutive,
                              "is_default": policy.patient_id is None},
    }


@router.post("/api/me/caregivers/invite")
def invite(body: InviteIn, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = patient_of(db, user)
    bad = set(body.scopes) - set(CAREGIVER_SCOPES)
    if bad:
        raise bad_request(f"Unknown permission: {', '.join(bad)}")
    contact = body.contact.strip().lower()
    if contact == user.email:
        raise bad_request("You can't invite yourself")
    token = new_token()
    rel = CareRelationship(patient_id=p.id, invite_contact=contact, invite_token_hash=hash_token(token),
                           relationship_label=body.relationship_label, scopes=sorted(set(body.scopes)),
                           purpose=body.purpose, status="invited", granted_by=user.id,
                           expires_at=utcnow() + timedelta(days=body.expires_in_days) if body.expires_in_days else None)
    db.add(rel)
    db.flush()
    link = f"{get_settings().frontend_origin}/caregiver/accept?token={token}"
    sent = aws_services.send_email(contact, "You've been invited to DoseWISE",
                                   f"{user.full_name} invited you to help with their care. Accept: {link}") \
        if "@" in contact else aws_services.send_sms(contact, f"DoseWISE: {user.full_name} invited you. {link}")
    _consent(db, p.id, user, "invite", "care_relationship", rel.id, rel.scopes, note=contact)
    audit.record(db, action="caregiver_invited", resource_type="care_relationship", resource_id=rel.id,
                 patient_id=p.id, user=user)
    db.commit()
    out = {"relationship": _rel_out(rel), "delivery": sent.state if sent.state != "ok" else "sent"}
    if sent.state != "ok" and get_settings().is_dev:
        out["dev_link"] = link
    return out


class AcceptIn(BaseModel):
    token: str


@router.post("/api/caregiver/invitations/accept")
def accept(body: AcceptIn, user: User = Depends(require_roles("caregiver")), db: Session = Depends(get_db)):
    rel = db.execute(select(CareRelationship).where(CareRelationship.invite_token_hash == hash_token(body.token),
                                                    CareRelationship.status == "invited")).scalar_one_or_none()
    if not rel:
        raise bad_request("This invitation is invalid, expired or already used")
    # identity check: the signed-in, email-verified caregiver must own the invited contact
    if rel.invite_contact not in (user.email, (user.phone or "").lower()) or not user.email_verified:
        raise forbidden("This invitation was sent to a different email or phone number")
    rel.caregiver_user_id = user.id
    rel.status = "accepted"
    rel.accepted_at = utcnow()
    rel.invite_token_hash = None
    notifications.notify(db, rel.patient.user, category="caregiver_update", title="Caregiver accepted",
                         body=f"{user.full_name} accepted your invitation. Review and authorise their access.",
                         patient_id=rel.patient_id, link="/patient/care-team", priority="high")
    _consent(db, rel.patient_id, user, "accept", "care_relationship", rel.id, rel.scopes, subject=user.id)
    audit.record(db, action="caregiver_accepted", resource_type="care_relationship", resource_id=rel.id,
                 patient_id=rel.patient_id, user=user)
    db.commit()
    return {"status": "accepted", "message": "The patient must confirm before your access starts.",
            "requested_scopes": rel.scopes, "patient_name": rel.patient.user.full_name}


@router.post("/api/me/caregivers/{rel_id}/authorize")
def authorize(rel_id: str, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = patient_of(db, user)
    rel = db.get(CareRelationship, rel_id)
    if not rel or rel.patient_id != p.id:
        raise not_found("Caregiver link")
    if rel.status != "accepted":
        raise bad_request("The caregiver must accept the invitation first")
    rel.status = "active"
    rel.authorized_at = rel.starts_at = utcnow()
    notifications.notify(db, rel.caregiver, category="caregiver_update", title="Access granted",
                         body=f"{user.full_name} authorised your access.", patient_id=p.id,
                         link=f"/caregiver/patients/{p.id}")
    _consent(db, p.id, user, "grant", "care_relationship", rel.id, rel.scopes, subject=rel.caregiver_user_id)
    audit.record(db, action="permission_granted", resource_type="care_relationship", resource_id=rel.id,
                 patient_id=p.id, user=user, reason=",".join(rel.scopes))
    realtime.queue(db, [rel.caregiver_user_id], "permissions", p.id)
    db.commit()
    return _rel_out(rel)


class ScopesIn(BaseModel):
    scopes: list[str] = Field(min_length=1)
    expires_at: datetime | None = None


@router.put("/api/me/caregivers/{rel_id}")
def update_scopes(rel_id: str, body: ScopesIn, user: User = Depends(require_roles("patient")),
                  db: Session = Depends(get_db)):
    p = patient_of(db, user)
    rel = db.get(CareRelationship, rel_id)
    if not rel or rel.patient_id != p.id or rel.status not in ("invited", "accepted", "active"):
        raise not_found("Caregiver link")
    if set(body.scopes) - set(CAREGIVER_SCOPES):
        raise bad_request("Unknown permission")
    rel.scopes = sorted(set(body.scopes))
    rel.expires_at = body.expires_at
    _consent(db, p.id, user, "scope_change", "care_relationship", rel.id, rel.scopes, subject=rel.caregiver_user_id)
    audit.record(db, action="permission_changed", resource_type="care_relationship", resource_id=rel.id,
                 patient_id=p.id, user=user, reason=",".join(rel.scopes))
    if rel.caregiver_user_id:
        realtime.queue(db, [rel.caregiver_user_id], "permissions", p.id)
    db.commit()
    return _rel_out(rel)


class RevokeIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.post("/api/me/caregivers/{rel_id}/revoke")
def revoke_caregiver(rel_id: str, body: RevokeIn, user: User = Depends(require_roles("patient")),
                     db: Session = Depends(get_db)):
    p = patient_of(db, user)
    rel = db.get(CareRelationship, rel_id)
    if not rel or rel.patient_id != p.id:
        raise not_found("Caregiver link")
    if rel.status in ("revoked", "expired", "declined"):
        raise bad_request("Access is already inactive")
    rel.status, rel.revoked_at, rel.revoked_by = "revoked", utcnow(), user.id
    rel.revocation_reason = body.reason
    rel.invite_token_hash = None
    if rel.caregiver:
        notifications.notify(db, rel.caregiver, category="caregiver_update", title="Access ended",
                             body=f"{user.full_name} ended your access to their information.")
        realtime.queue(db, [rel.caregiver_user_id], "permissions", p.id)
    _consent(db, p.id, user, "revoke", "care_relationship", rel.id, rel.scopes, subject=rel.caregiver_user_id,
             note=body.reason)
    audit.record(db, action="permission_revoked", resource_type="care_relationship", resource_id=rel.id,
                 patient_id=p.id, user=user, reason=body.reason)
    aws_services.publish_event("PermissionRevoked", {"relationship_id": rel.id})
    db.commit()
    return {"status": "revoked", "note": "Access stops immediately for all new requests. Information already "
                                         "downloaded or copied by the caregiver cannot be recalled."}


@router.post("/api/me/doctors/{access_id}/revoke")
def revoke_doctor(access_id: str, body: RevokeIn, user: User = Depends(require_roles("patient")),
                  db: Session = Depends(get_db)):
    p = patient_of(db, user)
    acc = db.get(DoctorPatientAccess, access_id)
    if not acc or acc.patient_id != p.id or acc.status != "active":
        raise not_found("Doctor access")
    acc.status, acc.revoked_at, acc.revoked_by, acc.revocation_reason = "revoked", utcnow(), user.id, body.reason
    _consent(db, p.id, user, "revoke", "doctor_access", acc.id, acc.scopes, subject=acc.doctor_user_id, note=body.reason)
    audit.record(db, action="permission_revoked", resource_type="doctor_access", resource_id=acc.id, patient_id=p.id,
                 user=user, reason=body.reason)
    realtime.queue(db, [acc.doctor_user_id], "permissions", p.id)
    db.commit()
    return {"status": "revoked"}


class GrantDoctorIn(BaseModel):
    doctor_id: str
    purpose: str = Field(default="Ongoing treatment", max_length=200)
    expires_in_days: int | None = Field(default=180, ge=1, le=730)


@router.post("/api/me/doctors/grant")
def grant_doctor(body: GrantDoctorIn, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = patient_of(db, user)
    doc = db.get(User, body.doctor_id)
    if not doc or doc.role != "doctor" or not doc.doctor_profile or doc.doctor_profile.verification_status != "verified":
        raise bad_request("Choose a verified doctor")
    acc = DoctorPatientAccess(patient_id=p.id, doctor_user_id=doc.id, purpose=body.purpose, granted_by=user.id,
                              granting_authority="patient_grant", starts_at=utcnow(),
                              expires_at=utcnow() + timedelta(days=body.expires_in_days) if body.expires_in_days else None)
    db.add(acc)
    db.flush()
    _consent(db, p.id, user, "grant", "doctor_access", acc.id, acc.scopes, subject=doc.id)
    audit.record(db, action="permission_granted", resource_type="doctor_access", resource_id=acc.id, patient_id=p.id,
                 user=user)
    db.commit()
    return {"id": acc.id, "status": acc.status}


class PolicyIn(BaseModel):
    notify_caregiver_approved: bool


@router.put("/api/me/escalation-policy")
def set_policy(body: PolicyIn, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = patient_of(db, user)
    pol = db.execute(select(EscalationPolicy).where(EscalationPolicy.patient_id == p.id)).scalar_one_or_none()
    if not pol:
        base = escalation.policy_for(db, p.id)
        pol = EscalationPolicy(patient_id=p.id, follow_up_after_minutes=base.follow_up_after_minutes,
                               unconfirmed_after_minutes=base.unconfirmed_after_minutes,
                               checkin_after_consecutive=base.checkin_after_consecutive,
                               caregiver_after_consecutive=base.caregiver_after_consecutive,
                               case_after_consecutive=base.case_after_consecutive)
        db.add(pol)
    pol.notify_caregiver_approved = body.notify_caregiver_approved
    _consent(db, p.id, user, "preference_change", "escalation_policy", pol.id,
             note=f"notify_caregiver_approved={body.notify_caregiver_approved}")
    db.commit()
    return {"notify_caregiver_approved": pol.notify_caregiver_approved}


# ---------------- caregiver side ----------------
@router.get("/api/caregiver/patients")
def caregiver_patients(user: User = Depends(require_roles("caregiver")), db: Session = Depends(get_db)):
    rels = db.execute(select(CareRelationship).where(CareRelationship.caregiver_user_id == user.id)
                      .order_by(CareRelationship.created_at.desc())).scalars().all()
    out = []
    for r in rels:
        row = _rel_out(r)
        live = active_caregiver_grant(db, user, r.patient_id)
        if live and live.id == r.id and "medications.view" in r.scopes:
            row["adherence"] = adherence_summary(db, r.patient_id, 7)
        out.append(row)
    db.commit()
    return out


# ---------------- break-glass (doctors) ----------------
class BreakGlassIn(BaseModel):
    patient_mrn: str
    justification: str = Field(min_length=20, max_length=2000)


@router.post("/api/break-glass")
def break_glass(body: BreakGlassIn, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    p = db.execute(select(PatientProfile).where(PatientProfile.mrn == body.patient_mrn)).scalar_one_or_none()
    if not p:
        raise not_found("Patient")
    bg = BreakGlassAccess(patient_id=p.id, user_id=user.id, justification=body.justification,
                          expires_at=utcnow() + timedelta(hours=1))
    db.add(bg)
    db.flush()
    audit.record(db, action="emergency_access", resource_type="break_glass", resource_id=bg.id, patient_id=p.id,
                 user=user, reason=body.justification[:300], auth_context="break_glass")
    notifications.notify(db, p.user, category="security", title="Emergency access to your record",
                         body=f"{user.full_name} used emergency access. It will be reviewed.", patient_id=p.id)
    aws_services.ops_alert("Break-glass access", f"Doctor {user.id} accessed patient {p.id}; review required")
    db.commit()
    return {"patient_id": p.id, "expires_at": bg.expires_at, "scope": "read-only clinical record",
            "note": "This access is logged and will be reviewed."}
