"""Authentication: registration, email verification, login, TOTP MFA, sessions, password reset,
demo login (development only) and the Cognito hosted-UI callback (when AUTH_PROVIDER=cognito).

Sessions are opaque random tokens in an HttpOnly cookie; only a keyed hash is stored server-side.
Nothing sensitive is put in localStorage.
"""
import re
import time
from collections import defaultdict, deque
from typing import Annotated
from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import AuthContext, client_ip, current_user, get_auth
from app.core.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    hash_password,
    hash_token,
    new_token,
    validate_password_strength,
    verify_password,
)
from app.integrations import aws_services
from app.models import (
    AuthToken,
    CaregiverProfile,
    DoctorProfile,
    PatientProfile,
    SecurityEvent,
    User,
    UserSession,
)
from app.core.india import COUNCILS, SPECIALITIES
from app.models.base import utcnow
from app.services import notifications
from app.services.access_ids import new_access_id

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Sign-in and recovery accept any well-formed address (EmailStr rejects reserved domains such as
# the demo accounts' "@impulse.test"); registration still uses strict EmailStr.
Email = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]

# --- simple in-process rate limiter (API Gateway throttling covers this in AWS) ---
_attempts: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str, limit: int = 10, window: int = 300) -> None:
    now = time.monotonic()
    q = _attempts[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")
    q.append(now)


def user_out(u: User) -> dict:
    prof = {}
    if u.role == "patient" and u.patient_profile:
        prof = {"patient_id": u.patient_profile.id, "mrn": u.patient_profile.mrn}
    if u.role == "doctor" and u.doctor_profile:
        prof = {"speciality": u.doctor_profile.speciality, "verification_status": u.doctor_profile.verification_status}
    return {
        "id": u.id, "email": u.email, "phone": u.phone, "role": u.role, "full_name": u.full_name,
        "preferred_name": u.preferred_name, "avatar_color": u.avatar_color, "email_verified": u.email_verified,
        "mfa_enabled": u.mfa_enabled, "is_demo": u.is_demo, "preferences": u.preferences or {}, **prof,
    }


def _sec_event(db: Session, request: Request, kind: str, user: User | None = None, email: str | None = None,
               **detail) -> None:
    db.add(SecurityEvent(user_id=getattr(user, "id", None), email=email or getattr(user, "email", None), kind=kind,
                         ip_address=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300],
                         detail=detail))


def _start_session(db: Session, response: Response, request: Request, user: User, mfa_passed: bool) -> UserSession:
    s = get_settings()
    token = new_token()
    sess = UserSession(user_id=user.id, token_hash=hash_token(token), csrf_token=new_token(24),
                       expires_at=utcnow() + timedelta(hours=s.session_hours), mfa_passed=mfa_passed,
                       user_agent=(request.headers.get("user-agent") or "")[:300], ip_address=client_ip(request),
                       last_seen_at=utcnow())
    db.add(sess)
    db.flush()
    cookie = dict(httponly=True, secure=s.cookie_secure, samesite="lax", max_age=s.session_hours * 3600, path="/")
    response.set_cookie(SESSION_COOKIE, token, **cookie)
    response.set_cookie(CSRF_COOKIE, sess.csrf_token, **{**cookie, "httponly": False})
    return sess


def _issue_token(db: Session, user: User, purpose: str, hours: int) -> str:
    token = new_token()
    db.add(AuthToken(user_id=user.id, purpose=purpose, token_hash=hash_token(token),
                     expires_at=utcnow() + timedelta(hours=hours)))
    return token


def _consume_token(db: Session, token: str, purpose: str) -> AuthToken:
    t = db.execute(select(AuthToken).where(AuthToken.token_hash == hash_token(token),
                                           AuthToken.purpose == purpose)).scalar_one_or_none()
    if not t or t.used_at or t.expires_at < utcnow():
        raise HTTPException(400, "This link is invalid or has expired. Request a new one.")
    t.used_at = utcnow()
    return t


def _send_link(db: Session, user: User, purpose: str, token: str) -> dict:
    """Emails the link through SES. In development, if SES is not configured, the link is
    returned in the response (clearly labelled) so the flow can be completed locally."""
    path = {"verify_email": "/verify-email", "reset_password": "/reset-password"}[purpose]
    link = f"{get_settings().frontend_origin}{path}?token={token}"
    res = aws_services.send_email(user.email, "DoseWISE account", f"Use this link within 24 hours: {link}")
    out = {"email_delivery": res.state if res.state != "ok" else "sent"}
    if res.state != "ok" and get_settings().is_dev:
        out["dev_link"] = link
    return out


# ---------------- registration ----------------
class RegisterIn(BaseModel):
    # caregiver accounts are only created through a patient's invitation link
    role: str = Field(pattern="^(patient|caregiver|doctor)$")
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(pattern=r"^\d{10}$", description="10-digit mobile number")
    password: str = Field(min_length=8, max_length=200)
    accept_terms: bool
    # doctor onboarding (verified by staff before any clinical access)
    speciality: str | None = None
    registration_number: str | None = Field(default=None, max_length=40)
    registration_council: str | None = None


@router.post("/register")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"register:{client_ip(request)}", 5, 3600)
    if not body.accept_terms:
        raise HTTPException(400, "Please accept the terms to continue")
    if err := validate_password_strength(body.password):
        raise HTTPException(400, err)
    email = body.email.lower()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        # same response as success to avoid account enumeration
        return {"status": "check_email", "message": "If this email can be registered, we've sent a verification link."}
    if get_settings().auth_provider == "cognito":
        raise HTTPException(400, "Registration is handled by the hosted sign-in page")
    user = User(email=email, phone=body.phone, password_hash=hash_password(body.password), role=body.role,
                full_name=body.full_name.strip(), preferences={"language": "en", "theme": "system"})
    db.add(user)
    db.flush()
    if body.role == "patient":
        db.add(PatientProfile(user_id=user.id, mrn=f"IMP-{user.id[:8].upper()}", access_id=new_access_id(db),
                              access_id_created_at=utcnow()))
    elif body.role == "caregiver":
        db.add(CaregiverProfile(user_id=user.id))
    elif body.role == "doctor":
        if body.speciality not in SPECIALITIES:
            raise HTTPException(400, "Choose a speciality from the list")
        if body.registration_council not in COUNCILS:
            raise HTTPException(400, "Choose the medical council you are registered with")
        if not body.registration_number or not re.fullmatch(r"[A-Za-z0-9/\-]{3,40}", body.registration_number.strip()):
            raise HTTPException(400, "Enter your medical registration number (letters, numbers, / or -)")
        db.add(DoctorProfile(user_id=user.id, speciality=body.speciality,
                             registration_number=body.registration_number,
                             registration_council=body.registration_council, verification_status="pending"))
    token = _issue_token(db, user, "verify_email", 24)
    out = _send_link(db, user, "verify_email", token)
    audit.record(db, action="account_registered", resource_type="user", resource_id=user.id, user=user)
    _sec_event(db, request, "registered", user)
    db.commit()
    return {"status": "check_email", "message": "If this email can be registered, we've sent a verification link.",
            **out}


class TokenIn(BaseModel):
    token: str


@router.post("/verify-email")
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    t = _consume_token(db, body.token, "verify_email")
    user = db.get(User, t.user_id)
    user.email_verified = True
    audit.record(db, action="email_verified", resource_type="user", resource_id=user.id, user=user)
    db.commit()
    return {"status": "verified", "role": user.role}


class ResendIn(BaseModel):
    email: Email


@router.post("/resend-verification")
def resend_verification(body: ResendIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"resend:{body.email.lower()}", 3, 3600)
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    out = {}
    if user and not user.email_verified:
        out = _send_link(db, user, "verify_email", _issue_token(db, user, "verify_email", 24))
        db.commit()
    return {"status": "sent_if_exists", **out}


# ---------------- login / MFA / logout ----------------
class LoginIn(BaseModel):
    email: Email
    password: str
    remember_device: bool = False


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    rate_limit(f"login:{client_ip(request)}", 20, 300)
    rate_limit(f"login-email:{email}", 8, 300)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    now = utcnow()
    if user and user.locked_until and user.locked_until > now:
        _sec_event(db, request, "login_locked", user)
        db.commit()
        raise HTTPException(423, "Account temporarily locked after repeated failed attempts. Try again in 15 minutes "
                                 "or reset your password.")
    if not user or not verify_password(body.password, user.password_hash) or not user.is_active or user.closed_at:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_logins = 0
        _sec_event(db, request, "login_failed", user, email=email)
        audit.record(db, action="login_failed", resource_type="user", resource_id=getattr(user, "id", None),
                     outcome="failed", ip_address=client_ip(request))
        db.commit()
        raise HTTPException(401, "Email or password is incorrect")
    if not user.email_verified:
        raise HTTPException(403, "Please verify your email first. Check your inbox for the link.")
    user.failed_logins = 0
    sess = _start_session(db, response, request, user, mfa_passed=not user.mfa_enabled)
    sess.trusted_device = body.remember_device
    _sec_event(db, request, "login_success" if not user.mfa_enabled else "login_password_ok_mfa_pending", user)
    audit.record(db, action="login", resource_type="user", resource_id=user.id, user=user,
                 ip_address=client_ip(request))
    db.commit()
    return {"mfa_required": user.mfa_enabled, "user": user_out(user) if not user.mfa_enabled else None}


class MfaIn(BaseModel):
    code: str = Field(min_length=6, max_length=12)


@router.post("/mfa/verify")
def mfa_verify(body: MfaIn, request: Request, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    rate_limit(f"mfa:{ctx.user.id}", 6, 300)
    user = ctx.user
    ok = bool(user.mfa_secret) and pyotp.TOTP(user.mfa_secret).verify(body.code.strip(), valid_window=1)
    if not ok and user.backup_codes:
        for i, h in enumerate(user.backup_codes):
            if verify_password(body.code.strip().upper(), h):
                user.backup_codes = user.backup_codes[:i] + user.backup_codes[i + 1:]
                ok = True
                break
    if not ok:
        _sec_event(db, request, "mfa_failed", user)
        db.commit()
        raise HTTPException(401, "That code didn't match. Try the latest code from your authenticator app.")
    ctx.session.mfa_passed = True
    _sec_event(db, request, "login_success", user, mfa=True)
    db.commit()
    return {"user": user_out(user)}


@router.post("/logout")
def logout(response: Response, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    ctx.session.revoked_at = utcnow()
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"status": "signed_out"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.get("/session")
def session_state(request: Request, db: Session = Depends(get_db)):
    """Non-throwing probe the SPA uses on load."""
    try:
        ctx = get_auth(request, db)
    except HTTPException:
        return {"authenticated": False, "demo_enabled": get_settings().is_demo_allowed,
                "auth_provider": get_settings().auth_provider}
    pending = ctx.user.mfa_enabled and not ctx.session.mfa_passed
    return {"authenticated": not pending, "mfa_pending": pending, "user": None if pending else user_out(ctx.user),
            "demo_enabled": get_settings().is_demo_allowed, "auth_provider": get_settings().auth_provider}


# ---------------- password reset ----------------
class ForgotIn(BaseModel):
    email: Email


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"forgot:{client_ip(request)}", 5, 3600)
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    out = {}
    if user and user.password_hash:
        out = _send_link(db, user, "reset_password", _issue_token(db, user, "reset_password", 1))
        _sec_event(db, request, "password_reset_requested", user)
        db.commit()
    return {"status": "sent_if_exists", "message": "If an account exists, a reset link has been sent.", **out}


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=10, max_length=200)


@router.post("/reset-password")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    if err := validate_password_strength(body.password):
        raise HTTPException(400, err)
    t = _consume_token(db, body.token, "reset_password")
    user = db.get(User, t.user_id)
    user.password_hash = hash_password(body.password)
    user.locked_until = None
    for s in db.execute(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))).scalars():
        s.revoked_at = utcnow()  # sign out everywhere after a reset
    _sec_event(db, request, "password_reset", user)
    audit.record(db, action="password_reset", resource_type="user", resource_id=user.id, user=user)
    notifications.notify(db, user, category="security", title="Your password was changed",
                         body="If this wasn't you, contact support immediately.")
    db.commit()
    return {"status": "password_updated"}


# ---------------- demo login (development only) ----------------
class DemoIn(BaseModel):
    persona: str


DEMO_PERSONAS = {
    "patient": "ananya.demo@impulse.test",
    "patient2": "rahul.demo@impulse.test",
    "doctor": "dr.mehra.demo@impulse.test",
    "caregiver": "kavya.demo@impulse.test",
    "support": "support.demo@impulse.test",
    "admin": "admin.demo@impulse.test",
}


@router.post("/demo-login")
def demo_login(body: DemoIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if not get_settings().is_demo_allowed:
        raise HTTPException(404, "Not found")
    email = DEMO_PERSONAS.get(body.persona)
    user = db.execute(select(User).where(User.email == email, User.is_demo.is_(True))).scalar_one_or_none() if email else None
    if not user:
        raise HTTPException(404, "Demo data not loaded. Run: python -m app.seed")
    _start_session(db, response, request, user, mfa_passed=True)
    _sec_event(db, request, "demo_login", user)
    audit.record(db, action="login", resource_type="user", resource_id=user.id, user=user, reason="demo",
                 ip_address=client_ip(request))
    db.commit()
    return {"user": user_out(user)}


# ---------------- Cognito hosted UI (AUTH_PROVIDER=cognito) ----------------
@router.get("/cognito/login")
def cognito_login():
    s = get_settings()
    if s.auth_provider != "cognito":
        raise HTTPException(404, "Cognito is not enabled")
    return RedirectResponse(
        f"https://{s.cognito_domain}/oauth2/authorize?response_type=code&client_id={s.cognito_client_id}"
        f"&redirect_uri={s.cognito_redirect_uri}&scope=openid+email+phone+profile"
    )


@router.get("/cognito/callback")
def cognito_callback(code: str, request: Request, db: Session = Depends(get_db)):
    from app.integrations.cognito import exchange_code_and_verify

    s = get_settings()
    if s.auth_provider != "cognito":
        raise HTTPException(404, "Cognito is not enabled")
    claims = exchange_code_and_verify(code)
    user = db.execute(select(User).where(User.cognito_sub == claims["sub"])).scalar_one_or_none()
    if not user:
        # first sign-in creates a patient account only; other roles need controlled onboarding
        user = User(email=claims["email"].lower(), cognito_sub=claims["sub"], role="patient",
                    full_name=claims.get("name") or claims["email"], email_verified=bool(claims.get("email_verified")))
        db.add(user)
        db.flush()
        db.add(PatientProfile(user_id=user.id, mrn=f"IMP-{user.id[:8].upper()}"))
    response = RedirectResponse(f"{s.frontend_origin}/app")
    _start_session(db, response, request, user, mfa_passed=True)  # MFA enforced by the Cognito pool policy
    _sec_event(db, request, "login_success", user, provider="cognito")
    audit.record(db, action="login", resource_type="user", resource_id=user.id, user=user, reason="cognito")
    db.commit()
    return response
