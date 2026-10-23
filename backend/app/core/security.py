import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

_ph = PasswordHasher()

SESSION_COOKIE = "impulse_session"
CSRF_COOKIE = "impulse_csrf"
CSRF_HEADER = "X-CSRF-Token"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Tokens are stored only as keyed hashes, so a database leak does not leak live sessions."""
    return hmac.new(get_settings().secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


PASSWORD_SPECIALS = "$_"
PASSWORD_RULES = (
    "At least 8 characters, with at least one upper-case letter, one lower-case letter, one number "
    "and one special character. Only $ and _ are allowed as special characters."
)


def validate_password_strength(password: str) -> str | None:
    """Same rules as the frontend (lib/schemas.ts `password`)."""
    if len(password) < 8:
        return "Use at least 8 characters."
    if any(not (c.isascii() and (c.isalnum() or c in PASSWORD_SPECIALS)) for c in password):
        return "Only letters, numbers, $ and _ are allowed."
    for test, msg in ((str.isupper, "an upper-case letter"), (str.islower, "a lower-case letter"),
                      (str.isdigit, "a number")):
        if not any(test(c) for c in password):
            return f"Add {msg}."
    if not any(c in PASSWORD_SPECIALS for c in password):
        return "Add a special character ($ or _)."
    return None
