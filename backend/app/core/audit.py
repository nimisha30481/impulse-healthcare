"""Application audit log with a hash chain so edits or deletions of past rows are detectable.

CloudTrail records AWS API activity; it does not replace these clinical-application records.
"""
import hashlib
import json
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models.base import new_id, utcnow

_lock = threading.Lock()
GENESIS = "0" * 64


def _digest(row: dict, prev_hash: str) -> str:
    payload = json.dumps(row, sort_keys=True, default=str) + prev_hash
    return hashlib.sha256(payload.encode()).hexdigest()


def _row_fields(entry: AuditLog) -> dict:
    return {
        "seq": entry.seq,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "user_id": entry.user_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "patient_id": entry.patient_id,
        "version_ref": entry.version_ref,
        "reason": entry.reason,
        "auth_context": entry.auth_context,
        "outcome": entry.outcome,
    }


def record(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    user=None,
    patient_id: str | None = None,
    version_ref: str | None = None,
    reason: str | None = None,
    auth_context: str | None = None,
    outcome: str = "success",
    source: str = "api",
    ip_address: str | None = None,
    commit: bool = False,
) -> AuditLog:
    """Append an audit entry in the caller's transaction (so the audit row commits or rolls back
    together with the change it describes)."""
    with _lock:
        last = db.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)).scalar_one_or_none()
        seq = (last.seq + 1) if last else 1
        prev_hash = last.hash if last else GENESIS
        entry = AuditLog(
            id=new_id(),
            seq=seq,
            created_at=utcnow().replace(microsecond=0),
            user_id=getattr(user, "id", None),
            user_role=getattr(user, "role", None),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_id=patient_id,
            version_ref=version_ref,
            reason=reason,
            auth_context=auth_context,
            outcome=outcome,
            source=source,
            ip_address=ip_address,
            prev_hash=prev_hash,
        )
        entry.hash = _digest(_row_fields(entry), prev_hash)
        db.add(entry)
        db.flush()
    if commit:
        db.commit()
    return entry


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = db.scalar(select(func.count()).select_from(AuditLog)) or 0
    for entry in db.execute(select(AuditLog).order_by(AuditLog.seq)).scalars():
        fields = _row_fields(entry)
        if entry.prev_hash != prev or _digest(fields, prev) != entry.hash:
            return {"valid": False, "broken_at_seq": entry.seq, "entries": count}
        prev = entry.hash
    return {"valid": True, "broken_at_seq": None, "entries": count}
