"""Turns prescription versions + schedules into concrete dose occurrences, and records patient
responses as append-only events.

Rules that matter for safety:
* doses are only generated for `active` items, inside start/end dates, never after a
  discontinuation's effective time, and from the version effective at that instant;
* changing or discontinuing a prescription cancels future, unanswered doses of the old version;
* an unanswered dose becomes `unconfirmed` - never assumed taken and never assumed missed.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict
from app.integrations import aws_services
from app.models import DoseOccurrence, MedicationEvent, PrescriptionItem, PrescriptionVersion
from app.models.base import utcnow

OPEN_STATUSES = ("upcoming", "due", "snoozed", "awaiting_confirmation")
RESPONSE_KINDS = {
    "taken_reported": "taken_reported",
    "missed_reported": "missed_reported",
    "skipped": "skipped",
    "snoozed": "snoozed",
    "cant_take": "missed_reported",
}
CANT_TAKE_REASONS = ("unwell", "unavailable", "forgot", "side_effects", "cost", "other")


def _version_at(versions: list[PrescriptionVersion], t: datetime) -> PrescriptionVersion | None:
    eligible = [v for v in versions if v.effective_from <= t and v.status in ("current", "superseded", "scheduled")]
    return max(eligible, key=lambda v: v.version_no) if eligible else None


def _dose_times_for_day(v: PrescriptionVersion, day: date) -> list[datetime]:
    sched = v.schedule
    if not sched or v.is_prn or not sched.times_of_day:
        return []
    if day < v.start_date or (v.end_date and day > v.end_date):
        return []
    if sched.days_of_week is not None and day.weekday() not in sched.days_of_week:
        return []
    if (day - v.start_date).days % max(sched.interval_days, 1) != 0:
        return []
    tz = ZoneInfo(sched.timezone)
    out = []
    for hhmm in sched.times_of_day:
        h, m = (int(x) for x in hhmm.split(":"))
        out.append(datetime.combine(day, time(h, m), tzinfo=tz).astimezone(ZoneInfo("UTC")))
    return out


def materialize_item(db: Session, item: PrescriptionItem, now: datetime | None = None, horizon_hours: int = 36) -> int:
    if item.status != "active":
        return 0
    now = now or utcnow()
    versions = list(item.versions)
    if not versions:
        return 0
    tzname = (versions[-1].schedule.timezone if versions[-1].schedule else "Asia/Kolkata")
    local_today = now.astimezone(ZoneInfo(tzname)).date()
    window_start = now - timedelta(hours=2)
    window_end = now + timedelta(hours=horizon_hours)
    created = 0
    for offset in range(-1, horizon_hours // 24 + 2):
        day = local_today + timedelta(days=offset)
        candidates = set()
        for v in versions:
            candidates.update(_dose_times_for_day(v, day))
        for t in sorted(candidates):
            if not (window_start <= t <= window_end):
                continue
            if item.discontinue_effective and t >= item.discontinue_effective:
                continue
            v = _version_at(versions, t)
            if v is None or t not in _dose_times_for_day(v, day):
                continue
            if t < item.created_at - timedelta(minutes=1):
                continue  # never backfill doses from before the prescription existed
            occ = DoseOccurrence(item_id=item.id, version_id=v.id, patient_id=item.patient_id, scheduled_at=t)
            try:
                with db.begin_nested():
                    db.add(occ)
                    db.flush()
                created += 1
            except IntegrityError:
                pass
    return created


def cancel_future_doses(db: Session, item: PrescriptionItem, from_time: datetime, reason: str, actor_id: str | None) -> int:
    n = 0
    for occ in db.execute(
        select(DoseOccurrence).where(
            DoseOccurrence.item_id == item.id,
            DoseOccurrence.scheduled_at >= from_time,
            DoseOccurrence.status.in_(OPEN_STATUSES),
        )
    ).scalars():
        occ.status = "cancelled"
        db.add(MedicationEvent(
            occurrence_id=occ.id, item_id=item.id, version_id=occ.version_id, patient_id=item.patient_id,
            actor_user_id=actor_id, kind="cancelled_by_change", note=reason, source="system",
        ))
        n += 1
    return n


def record_response(
    db: Session,
    occ: DoseOccurrence,
    *,
    kind: str,
    actor_id: str,
    reason: str | None = None,
    note: str | None = None,
    snooze_minutes: int | None = None,
    idempotency_key: str | None = None,
    source: str = "patient_app",
) -> MedicationEvent:
    if kind not in RESPONSE_KINDS:
        raise bad_request("Unknown response")
    if kind == "cant_take" and reason not in CANT_TAKE_REASONS:
        raise bad_request("Please choose a reason")
    if idempotency_key:
        existing = db.execute(
            select(MedicationEvent).where(MedicationEvent.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing:
            return existing  # retried request: same result, no duplicate event
    if occ.status == "cancelled":
        raise conflict("This dose was cancelled because the prescription changed")
    now = utcnow()
    if occ.scheduled_at - now > timedelta(hours=2):
        raise bad_request("You can respond to a dose up to 2 hours before it is due")
    if kind == "snoozed":
        minutes = snooze_minutes or 15
        if not 5 <= minutes <= 120:
            raise bad_request("Snooze between 5 and 120 minutes")
        occ.snoozed_until = now + timedelta(minutes=minutes)
        occ.status = "snoozed"
    else:
        occ.status = RESPONSE_KINDS[kind]
        occ.responded_at = now
    ev = MedicationEvent(
        occurrence_id=occ.id, item_id=occ.item_id, version_id=occ.version_id, patient_id=occ.patient_id,
        actor_user_id=actor_id, kind=kind, reason=reason, note=note, idempotency_key=idempotency_key, source=source,
    )
    db.add(ev)
    db.flush()
    aws_services.mirror_medication_event({
        "pk": f"PATIENT#{occ.patient_id}",
        "sk": f"EVENT#{ev.created_at.isoformat()}#{ev.id}",
        "kind": kind,
        "occurrence_id": occ.id,
        "prescription_version_id": occ.version_id,
        "scheduled_at": occ.scheduled_at.isoformat(),
    })
    aws_services.write_adherence_point(occ.patient_id, kind, ev.created_at.isoformat())
    return ev


def adherence_summary(db: Session, patient_id: str, days: int = 7) -> dict:
    """Transparent method (shown to users):
    - scheduled: doses whose time has passed in the window (cancelled doses excluded)
    - reported_taken: the patient (or caregiver) said it was taken - not independently verified
    - reported_missed: someone reported it missed/couldn't take; skipped counted separately
    - unconfirmed: nobody responded - unknown, NOT counted as missed
    - rate = reported_taken / (reported_taken + reported_missed + skipped); shown with
      'responses received' so a high rate built on few responses is not misleading.
    """
    now = utcnow()
    since = now - timedelta(days=days)
    occs = db.execute(
        select(DoseOccurrence).where(
            DoseOccurrence.patient_id == patient_id,
            DoseOccurrence.scheduled_at >= since,
            DoseOccurrence.scheduled_at <= now,
            DoseOccurrence.status != "cancelled",
        )
    ).scalars().all()
    counts = {k: 0 for k in ("taken_reported", "missed_reported", "skipped", "unconfirmed", "pending")}
    by_day: dict[str, dict] = {}
    for o in occs:
        key = o.status if o.status in counts else "pending"
        counts[key] += 1
        d = o.scheduled_at.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
        bucket = by_day.setdefault(d, {"date": d, "taken_reported": 0, "missed_reported": 0, "skipped": 0,
                                       "unconfirmed": 0, "pending": 0})
        bucket[key] += 1
    responded = counts["taken_reported"] + counts["missed_reported"] + counts["skipped"]
    return {
        "window_days": days,
        "scheduled": len(occs),
        **counts,
        "responses_received": responded,
        "response_coverage": round(responded / len(occs), 3) if occs else None,
        "reported_rate": round(counts["taken_reported"] / responded, 3) if responded else None,
        "trend": sorted(by_day.values(), key=lambda b: b["date"]),
        "method": "Reported rate = doses reported taken ÷ doses with any response. Unconfirmed doses are "
                  "shown separately and are not counted as missed or taken. 'Taken' is self-reported and "
                  "not independently verified.",
    }
