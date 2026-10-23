"""Real-time update hints.

Messages carry only {topic, patient_id, resource id}; never clinical content. Clients react by
refetching through the normal authorised APIs, so a revoked permission takes effect on the next
request even if a hint was already queued. Delivered over SSE locally and mirrored to AppSync
Events when configured.
"""
import asyncio
import json
import threading
from collections import defaultdict

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.integrations import aws_services

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def subscribe(user_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    with _lock:
        _subscribers[user_id].add(q)
    return q


def unsubscribe(user_id: str, q: asyncio.Queue) -> None:
    with _lock:
        _subscribers[user_id].discard(q)


def _put(q: asyncio.Queue, msg: str) -> None:
    try:
        q.put_nowait(msg)
    except asyncio.QueueFull:
        pass  # slow client: it will refetch on reconnect anyway


def publish(user_ids, topic: str, patient_id: str | None = None, ref: str | None = None) -> None:
    msg = json.dumps({"topic": topic, "patient_id": patient_id, "ref": ref})
    with _lock:
        targets = [(uid, q) for uid in set(user_ids) for q in _subscribers.get(uid, ())]
    for _, q in targets:
        if _loop and _loop.is_running():
            _loop.call_soon_threadsafe(_put, q, msg)
    for uid in set(user_ids):
        aws_services.appsync_publish(f"/users/{uid}", {"topic": topic, "patient_id": patient_id, "ref": ref})


def queue(db: Session, user_ids, topic: str, patient_id: str | None = None, ref: str | None = None) -> None:
    """Publish only once the surrounding transaction commits, so clients never refetch before
    the change is persisted (and never hear about changes that were rolled back)."""
    db.info.setdefault("realtime", []).append((list(user_ids), topic, patient_id, ref))


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    for args in session.info.pop("realtime", []):
        publish(*args)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop("realtime", None)
