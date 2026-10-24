"""Application audit log with a hash chain so edits or deletions of past rows are detectable.

CloudTrail records AWS API activity; it does not replace these clinical-application records.

Sequence numbers are assigned at commit time, not when the entry is created: two requests that
each wrote an audit entry used to pick the same "next" number and the second one failed with a
server error. Entries now get a temporary negative number, and just before the transaction commits
(after this session holds the database write lock, and under a process lock for PostgreSQL) they
receive their real number and hash.
"""
import hashlib
import json
import secrets
import threading

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models.base import new_id, utcnow

_lock = threading.Lock()
GENESIS = "0" * 64
_PENDING = "pending_audit"
_HELD = "audit_lock_held"


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
    entry = AuditLog(
        id=new_id(),
        seq=-(secrets.randbits(52) + 1),  # placeholder; the real number is assigned at commit
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
        prev_hash=GENESIS,
        hash="",
    )
    db.add(entry)
    db.info.setdefault(_PENDING, []).append(entry)
    if commit:
        db.commit()
    return entry


@event.listens_for(Session, "before_commit")
def _assign_sequence(session: Session) -> None:
    pending = session.info.get(_PENDING)
    if not pending:
        return
    session.flush()  # takes the database write lock first (SQLite allows one writer at a time)
    if not session.info.get(_HELD):
        _lock.acquire()
        session.info[_HELD] = True
    last = session.execute(select(AuditLog).where(AuditLog.seq > 0).order_by(AuditLog.seq.desc()).limit(1)
                           ).scalar_one_or_none()
    seq, prev = (last.seq, last.hash) if last else (0, GENESIS)
    for entry in pending:
        seq += 1
        entry.seq, entry.prev_hash = seq, prev
        entry.hash = _digest(_row_fields(entry), prev)
        prev = entry.hash
    session.info[_PENDING] = []
    session.flush()


@event.listens_for(Session, "after_transaction_end")
def _release(session: Session, transaction) -> None:
    if transaction.parent is not None:
        return  # a savepoint ended; the outer transaction is still open
    if session.info.pop(_HELD, False):
        _lock.release()
    # committed entries were already numbered; after a rollback they were never written
    session.info[_PENDING] = []


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = db.scalar(select(func.count()).select_from(AuditLog)) or 0
    for entry in db.execute(select(AuditLog).where(AuditLog.seq > 0).order_by(AuditLog.seq)).scalars():
        fields = _row_fields(entry)
        if entry.prev_hash != prev or _digest(fields, prev) != entry.hash:
            return {"valid": False, "broken_at_seq": entry.seq, "entries": count}
        prev = entry.hash
    return {"valid": True, "broken_at_seq": None, "entries": count}
