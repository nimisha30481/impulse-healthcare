"""Notification abstraction. The frontend never talks to a provider directly.

Delivery truthfulness: a row is only marked `sent` when the provider accepted it; `delivered`
only when a provider receipt confirms it. With no provider configured the status is
`not_configured`, which the UI shows as "not sent".
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations import aws_services
from app.models import Notification, User
from app.services import realtime

# Insecure channels get a generic message; details are only visible after signing in.
GENERIC_TEXT = {
    "medication_reminder": "DoseWISE: you have a medication reminder. Open the app to view it.",
    "appointment_reminder": "DoseWISE: you have an upcoming appointment. Open the app for details.",
    "default": "DoseWISE: you have a new update. Sign in to view it.",
}

PREF_KEYS = {
    "medication_reminder": "medication_reminders",
    "appointment_reminder": "appointment_reminders",
    "doctor_instruction": "doctor_messages",
    "new_prescription": "doctor_messages",
    "prescription_change": "doctor_messages",
    "caregiver_update": "caregiver_notifications",
    "security": "security_alerts",
    "emergency": "emergency_notifications",
}


def _channels_for(user: User, category: str) -> list[str]:
    prefs = (user.preferences or {}).get("notifications", {})
    key = PREF_KEYS.get(category)
    chosen = prefs.get(key, {}) if key else {}
    channels = ["in_app"]
    if category in ("security", "emergency"):
        chosen = {"email": True, "sms": True, **chosen}  # safety-relevant: default on
    if chosen.get("email"):
        channels.append("email")
    if chosen.get("sms") and user.phone:
        channels.append("sms")
    return channels


def notify(
    db: Session,
    user: User,
    *,
    category: str,
    title: str,
    body: str,
    patient_id: str | None = None,
    link: str | None = None,
    priority: str = "normal",
    dedupe_key: str | None = None,
) -> list[Notification]:
    """Create one notification per enabled channel. Duplicate dedupe keys are skipped silently,
    which is what prevents duplicate reminders when the engine runs twice."""
    created = []
    for channel in _channels_for(user, category):
        key = f"{dedupe_key}:{channel}" if dedupe_key else None
        n = Notification(
            user_id=user.id,
            patient_id=patient_id,
            category=category,
            title=title,
            body=body,
            link=link,
            channel=channel,
            priority=priority,
            dedupe_key=key,
        )
        try:
            with db.begin_nested():
                db.add(n)
                db.flush()
        except IntegrityError:
            continue
        _deliver(n, user)
        created.append(n)
    if created:
        realtime.queue(db, [user.id], "notifications", patient_id)
    return created


def _deliver(n: Notification, user: User) -> None:
    n.attempts += 1
    if n.channel == "in_app":
        n.delivery_status = "delivered"  # stored and visible in the app inbox
        return
    text = GENERIC_TEXT.get(n.category, GENERIC_TEXT["default"])
    if n.channel == "email":
        res = aws_services.send_email(user.email, "DoseWISE update", text)
    elif n.channel == "sms":
        res = aws_services.send_sms(user.phone or "", text)
    else:
        res = aws_services.Result("not_configured")
    if res.state == "ok":
        n.delivery_status = "sent"
        n.provider_message_id = res.data
    elif res.state == "not_configured":
        n.delivery_status = "not_configured"
    else:
        n.delivery_status = "failed"
        n.last_error = res.error


def retry_failed(db: Session, max_attempts: int = 3) -> int:
    from sqlalchemy import select

    count = 0
    for n in db.execute(
        select(Notification).where(Notification.delivery_status == "failed", Notification.attempts < max_attempts)
    ).scalars():
        _deliver(n, db.get(User, n.user_id))
        count += 1
    return count
