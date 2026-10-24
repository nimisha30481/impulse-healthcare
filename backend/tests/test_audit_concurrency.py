import threading

from app.core import audit
from app.core.database import SessionLocal


def test_parallel_requests_never_collide_on_audit_sequence():
    """Before the fix, two requests writing audit entries at once could pick the same sequence number
    and one failed with a server error."""
    errors = []

    def worker(i):
        db = SessionLocal()
        try:
            for j in range(5):
                audit.record(db, action="concurrency_check", resource_type="test", resource_id=f"{i}-{j}")
                audit.record(db, action="concurrency_check", resource_type="test", resource_id=f"{i}-{j}b")
                db.commit()
        except Exception as e:  # noqa: BLE001
            errors.append(e)
        finally:
            db.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors[:1]
    db = SessionLocal()
    try:
        result = audit.verify_chain(db)
        assert result["valid"] and result["entries"] >= 80
    finally:
        db.close()


def test_rolled_back_entries_do_not_break_the_chain():
    db = SessionLocal()
    try:
        audit.record(db, action="kept", resource_type="test")
        db.commit()
        audit.record(db, action="discarded", resource_type="test")
        db.rollback()
        audit.record(db, action="kept_again", resource_type="test")
        db.commit()
        assert audit.verify_chain(db)["valid"]
    finally:
        db.close()
