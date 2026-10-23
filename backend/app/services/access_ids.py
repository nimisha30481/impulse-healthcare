"""Patient Access IDs: short codes a patient shares so a doctor can open their record.

Format "DW-XXXXXX": 6 characters from a 31-symbol alphabet without look-alikes (0/O, 1/I/L),
about 887 million combinations. Guessing is limited by per-IP rate limits on every lookup endpoint.
Regenerating the ID immediately invalidates the old one (that is how a patient revokes it).
"""
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PatientProfile
from app.models.base import utcnow

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
VALID_DAYS = 365


def new_access_id(db: Session) -> str:
    while True:
        code = "DW-" + "".join(secrets.choice(ALPHABET) for _ in range(6))
        if not db.execute(select(PatientProfile.id).where(PatientProfile.access_id == code)).first():
            return code


def normalize(raw: str) -> str:
    s = "".join(ch for ch in raw.upper() if ch.isalnum())
    if s.startswith("DW"):
        s = s[2:]
    return f"DW-{s}"


def expires_at(p: PatientProfile):
    return (p.access_id_created_at or utcnow()) + timedelta(days=VALID_DAYS)


def lookup(db: Session, raw: str) -> tuple[PatientProfile | None, str]:
    """Returns (patient, outcome) where outcome is granted | invalid | expired."""
    code = normalize(raw or "")
    if len(code) != 9:
        return None, "invalid"
    p = db.execute(select(PatientProfile).where(PatientProfile.access_id == code)).scalar_one_or_none()
    if not p or not p.user.is_active or p.user.closed_at:
        return None, "invalid"
    if expires_at(p) <= utcnow():
        return p, "expired"
    return p, "granted"
