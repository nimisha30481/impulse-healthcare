"""Account settings: profile, preferences (language/theme/region/notifications), password, MFA,
backup codes, sessions, login history, data export, account closure."""
import json
import secrets

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.database import get_db
from app.core.deps import AuthContext, current_user, get_auth
from app.core.security import hash_password, validate_password_strength, verify_password
from app.models import (
    ConsentRecord,
    MedicalRecord,
    PatientProfile,
    PrescriptionItem,
    SecurityEvent,
    User,
    UserSession,
)
from app.models.base import utcnow
from app.api.auth import user_out

router = APIRouter(prefix="/api/account", tags=["account"])

LANGUAGES = ("en", "kn", "hi", "te", "ta")


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    preferred_name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=32)
    avatar_color: str | None = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")


@router.patch("/profile")
def update_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    audit.record(db, action="profile_updated", resource_type="user", resource_id=user.id, user=user)
    db.commit()
    return user_out(user)


class PreferencesIn(BaseModel):
    language: str | None = None
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    text_size: str | None = Field(default=None, pattern="^(normal|large|x-large)$")
    reduced_motion: bool | None = None
    high_contrast: bool | None = None
    country: str | None = Field(default=None, max_length=60)
    state: str | None = Field(default=None, max_length=60)
    timezone: str | None = Field(default=None, max_length=64)
    date_format: str | None = Field(default=None, pattern="^(DD/MM/YYYY|MM/DD/YYYY|YYYY-MM-DD)$")
    units: str | None = Field(default=None, pattern="^(metric|imperial)$")
    notifications: dict | None = None
    data_sharing: dict | None = None


@router.patch("/preferences")
def update_preferences(body: PreferencesIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.language and body.language not in LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    if body.timezone:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(body.timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(400, "Unknown time zone")
        if user.patient_profile:
            user.patient_profile.timezone = body.timezone
    prefs = dict(user.preferences or {})
    changes = body.model_dump(exclude_none=True)
    if "data_sharing" in changes and user.patient_profile:
        db.add(ConsentRecord(patient_id=user.patient_profile.id, actor_user_id=user.id, action="preference_change",
                             resource="data_sharing", note=json.dumps(changes["data_sharing"])))
    prefs.update(changes)
    user.preferences = prefs
    db.commit()
    return {"preferences": user.preferences}


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


@router.post("/password")
def change_password(body: PasswordIn, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    user = ctx.user
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if err := validate_password_strength(body.new_password):
        raise HTTPException(400, err)
    user.password_hash = hash_password(body.new_password)
    for s in db.execute(select(UserSession).where(UserSession.user_id == user.id, UserSession.id != ctx.session.id,
                                                  UserSession.revoked_at.is_(None))).scalars():
        s.revoked_at = utcnow()
    db.add(SecurityEvent(user_id=user.id, kind="password_changed"))
    audit.record(db, action="password_changed", resource_type="user", resource_id=user.id, user=user)
    db.commit()
    return {"status": "updated", "other_sessions_signed_out": True}


@router.post("/mfa/setup")
def mfa_setup(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.mfa_enabled:
        raise HTTPException(400, "MFA is already on")
    user.mfa_secret = pyotp.random_base32()
    db.commit()
    return {"secret": user.mfa_secret,
            "otpauth_uri": pyotp.TOTP(user.mfa_secret).provisioning_uri(name=user.email, issuer_name="IMPULSE")}


class CodeIn(BaseModel):
    code: str


@router.post("/mfa/enable")
def mfa_enable(body: CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.mfa_secret or not pyotp.TOTP(user.mfa_secret).verify(body.code.strip(), valid_window=1):
        raise HTTPException(400, "That code didn't match. Check the time on your phone and try again.")
    codes = [secrets.token_hex(4).upper() for _ in range(8)]
    user.backup_codes = [hash_password(c) for c in codes]
    user.mfa_enabled = True
    db.add(SecurityEvent(user_id=user.id, kind="mfa_enabled"))
    audit.record(db, action="mfa_enabled", resource_type="user", resource_id=user.id, user=user)
    db.commit()
    return {"status": "enabled", "backup_codes": codes}


class DisableMfaIn(BaseModel):
    password: str


@router.post("/mfa/disable")
def mfa_disable(body: DisableMfaIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "Password is incorrect")
    if user.role in ("doctor", "support", "admin"):
        raise HTTPException(400, "MFA is required for clinical and staff accounts")
    user.mfa_enabled, user.mfa_secret, user.backup_codes = False, None, None
    db.add(SecurityEvent(user_id=user.id, kind="mfa_disabled"))
    audit.record(db, action="mfa_disabled", resource_type="user", resource_id=user.id, user=user)
    db.commit()
    return {"status": "disabled"}


@router.get("/sessions")
def sessions(ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    rows = db.execute(select(UserSession).where(UserSession.user_id == ctx.user.id, UserSession.revoked_at.is_(None),
                                                UserSession.expires_at > utcnow())
                      .order_by(UserSession.created_at.desc())).scalars()
    return [{"id": s.id, "created_at": s.created_at, "last_seen_at": s.last_seen_at, "user_agent": s.user_agent,
             "ip_address": s.ip_address, "current": s.id == ctx.session.id, "trusted_device": s.trusted_device}
            for s in rows]


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: str, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    s = db.get(UserSession, session_id)
    if not s or s.user_id != ctx.user.id:
        raise HTTPException(404, "Session not found")
    s.revoked_at = utcnow()
    db.commit()
    return {"status": "revoked"}


@router.post("/sessions/revoke-all")
def revoke_all(response: Response, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    for s in db.execute(select(UserSession).where(UserSession.user_id == ctx.user.id,
                                                  UserSession.revoked_at.is_(None))).scalars():
        s.revoked_at = utcnow()
    db.add(SecurityEvent(user_id=ctx.user.id, kind="signed_out_everywhere"))
    db.commit()
    return {"status": "all_sessions_revoked"}


@router.get("/login-history")
def login_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(SecurityEvent).where(SecurityEvent.user_id == user.id)
                      .order_by(SecurityEvent.created_at.desc()).limit(50)).scalars()
    return [{"at": e.created_at, "kind": e.kind, "ip_address": e.ip_address, "user_agent": e.user_agent} for e in rows]


@router.get("/export")
def export_data(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Downloadable copy of the user's own data (patients: profile, medicines, records)."""
    data: dict = {"account": user_out(user), "exported_at": utcnow().isoformat()}
    p = db.execute(select(PatientProfile).where(PatientProfile.user_id == user.id)).scalar_one_or_none()
    if p:
        data["medications"] = [
            {"status": it.status, "versions": [
                {"version": v.version_no, "medicine": v.generic_name, "strength": v.strength,
                 "dose": f"{v.dose_amount:g} {v.dose_unit}", "route": v.route, "frequency": v.frequency_label,
                 "start": v.start_date, "end": v.end_date, "change_reason": v.change_reason} for v in it.versions]}
            for it in db.execute(select(PrescriptionItem).where(PrescriptionItem.patient_id == p.id)).scalars()]
        data["records"] = [{"type": r.record_type, "title": r.title, "date": r.occurred_at, "summary": r.summary,
                            "provenance": r.provenance, "status": r.status}
                           for r in db.execute(select(MedicalRecord).where(MedicalRecord.patient_id == p.id)).scalars()]
        data["consent_history"] = [{"at": c.created_at, "action": c.action, "resource": c.resource, "scopes": c.scopes}
                                   for c in db.execute(select(ConsentRecord).where(ConsentRecord.patient_id == p.id)).scalars()]
    audit.record(db, action="record_export", resource_type="user", resource_id=user.id, user=user,
                 patient_id=p.id if p else None)
    db.commit()
    return Response(json.dumps(data, default=str, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="impulse-export.json"'})


class CloseIn(BaseModel):
    password: str
    confirm: str


@router.post("/close")
def close_account(body: CloseIn, response: Response, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    """Closes sign-in immediately. Clinical records are retained for the configured legal retention
    period (see docs/DATA_GOVERNANCE.md) and are not deleted by this action."""
    if body.confirm != "CLOSE" or not verify_password(body.password, ctx.user.password_hash):
        raise HTTPException(400, "Type CLOSE and enter your password to confirm")
    ctx.user.closed_at = utcnow()
    ctx.user.is_active = False
    for s in db.execute(select(UserSession).where(UserSession.user_id == ctx.user.id)).scalars():
        s.revoked_at = utcnow()
    audit.record(db, action="account_closed", resource_type="user", resource_id=ctx.user.id, user=ctx.user)
    db.commit()
    return {"status": "closed",
            "retention_note": "Medical records are retained as required by law and then deleted per policy."}
