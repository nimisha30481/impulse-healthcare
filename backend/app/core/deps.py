from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CSRF_HEADER, SESSION_COOKIE, hash_token
from app.models import User, UserSession
from app.models.base import utcnow

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class AuthContext:
    user: User
    session: UserSession


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def get_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    sess = db.execute(select(UserSession).where(UserSession.token_hash == hash_token(token))).scalar_one_or_none()
    now = utcnow()
    if not sess or sess.revoked_at or sess.expires_at < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active or user.closed_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account unavailable")
    # CSRF: double-submit token bound to the server-side session
    if request.method in UNSAFE_METHODS and request.headers.get(CSRF_HEADER) != sess.csrf_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token")
    if not sess.last_seen_at or (now - sess.last_seen_at).total_seconds() > 300:
        sess.last_seen_at = now
        db.commit()
    return AuthContext(user=user, session=sess)


def get_partial_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    """Session that may still be waiting for its MFA step."""
    return get_auth(request, db)


def current_user(ctx: AuthContext = Depends(get_auth)) -> User:
    if ctx.user.mfa_enabled and not ctx.session.mfa_passed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA verification required")
    return ctx.user


def require_roles(*roles: str):
    def _dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This area is not available for your account type")
        if user.role == "doctor" and (not user.doctor_profile or user.doctor_profile.verification_status != "verified"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Your doctor account isn't active yet. Please contact DoseWISE support."
            )
        return user

    return _dep
