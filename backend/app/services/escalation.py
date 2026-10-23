"""Structured follow-up when a patient repeatedly does not respond.

Stage 1 reminder -> 2 gentle follow-up -> 3 extra check-in -> 4 notify authorised caregiver
(only if the patient approved that criterion) -> 5 human care-coordinator case -> 6 staff escalate
per documented procedure (manual). Silence is treated as "unknown", never as an emergency.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import audit
from app.integrations import aws_services
from app.models import (
    CareRelationship,
    DoseOccurrence,
    EscalationCase,
    EscalationPolicy,
    PatientProfile,
    SupportCase,
    SupportProfile,
    User,
)
from app.models.base import utcnow
from app.services import notifications, realtime


def policy_for(db: Session, patient_id: str) -> EscalationPolicy:
    p = db.execute(select(EscalationPolicy).where(EscalationPolicy.patient_id == patient_id)).scalar_one_or_none()
    if p:
        return p
    default = db.execute(select(EscalationPolicy).where(EscalationPolicy.patient_id.is_(None))).scalar_one_or_none()
    if not default:
        default = EscalationPolicy(patient_id=None)
        db.add(default)
        db.flush()
    return default


def consecutive_unanswered(db: Session, patient_id: str) -> int:
    recent = db.execute(
        select(DoseOccurrence)
        .where(
            DoseOccurrence.patient_id == patient_id,
            DoseOccurrence.status.in_(("taken_reported", "missed_reported", "skipped", "unconfirmed")),
        )
        .order_by(DoseOccurrence.scheduled_at.desc())
        .limit(20)
    ).scalars()
    n = 0
    for o in recent:
        if o.status != "unconfirmed":
            break  # any response (even "missed") means the patient is reachable
        n += 1
    return n


def _log(case: EscalationCase, stage: int, text: str) -> None:
    case.history = [*(case.history or []), {"at": utcnow().isoformat(), "stage": stage, "event": text}]


def assign_support_user(db: Session) -> str | None:
    """Least-loaded on-duty coordinator."""
    rows = db.execute(
        select(User.id, func.count(SupportCase.id))
        .join(SupportProfile, SupportProfile.user_id == User.id)
        .outerjoin(SupportCase, (SupportCase.assigned_to == User.id) & (SupportCase.status != "resolved"))
        .where(User.role == "support", User.is_active.is_(True), SupportProfile.on_duty.is_(True))
        .group_by(User.id)
        .order_by(func.count(SupportCase.id))
    ).all()
    return rows[0][0] if rows else None


def open_support_case(db: Session, patient_id: str, case_type: str, reason: str, priority: str = "normal",
                      created_by: str | None = None) -> SupportCase:
    case = SupportCase(
        patient_id=patient_id, case_type=case_type, priority=priority, reason=reason,
        assigned_to=assign_support_user(db), created_by=created_by,
        history=[{"at": utcnow().isoformat(), "event": "created", "by": created_by or "system"}],
    )
    db.add(case)
    db.flush()
    if case.assigned_to:
        assignee = db.get(User, case.assigned_to)
        notifications.notify(db, assignee, category="important_alert", title="New case assigned",
                             body=f"A {case_type.replace('_', ' ')} case was assigned to you.",
                             link=f"/support/cases/{case.id}", priority="high", dedupe_key=f"case-assign:{case.id}")
        realtime.queue(db, [assignee.id], "support_cases", patient_id, case.id)
    else:
        aws_services.ops_alert("Unassigned IMPULSE support case", f"Case {case.id} has no on-duty coordinator")
    audit.record(db, action="support_case_created", resource_type="support_case", resource_id=case.id,
                 patient_id=patient_id, reason=case_type, source="escalation" if not created_by else "api")
    return case


def evaluate(db: Session, patient_id: str) -> EscalationCase | None:
    policy = policy_for(db, patient_id)
    streak = consecutive_unanswered(db, patient_id)
    case = db.execute(
        select(EscalationCase).where(
            EscalationCase.patient_id == patient_id,
            EscalationCase.trigger == "missed_medication",
            EscalationCase.status == "open",
        )
    ).scalar_one_or_none()
    if streak == 0:
        if case:
            case.status = "resolved"
            _log(case, case.stage, "patient responded; escalation closed")
        return case
    if not case:
        case = EscalationCase(patient_id=patient_id, trigger="missed_medication", stage=2, history=[])
        db.add(case)
        db.flush()
        _log(case, 2, "unconfirmed dose(s) after reminder and follow-up")
    case.consecutive_unconfirmed = streak
    patient = db.get(PatientProfile, patient_id)

    if streak >= policy.checkin_after_consecutive and case.stage < 3:
        case.stage = 3
        notifications.notify(db, patient.user, category="important_alert", title="Quick check-in",
                             body="We haven't heard back about your recent doses. Tap to let us know how you are.",
                             patient_id=patient_id, link="/patient", dedupe_key=f"esc:{case.id}:3")
        _log(case, 3, "check-in sent to patient")

    if streak >= policy.caregiver_after_consecutive and case.stage < 4:
        if policy.notify_caregiver_approved:
            rels = db.execute(select(CareRelationship).where(
                CareRelationship.patient_id == patient_id, CareRelationship.status == "active")).scalars().all()
            notified = 0
            for rel in rels:
                if "adherence.notify" in (rel.scopes or []) and rel.caregiver:
                    notifications.notify(db, rel.caregiver, category="caregiver_update",
                                         title="Check-in needed",
                                         body=f"{patient.user.preferred_name or patient.user.full_name} has not "
                                              f"responded to {streak} recent medication reminders.",
                                         patient_id=patient_id, link=f"/caregiver/patients/{patient_id}",
                                         priority="high", dedupe_key=f"esc:{case.id}:4:{rel.id}")
                    notified += 1
            _log(case, 4, f"{notified} authorised caregiver(s) notified")
        else:
            _log(case, 4, "caregiver notification skipped: patient has not approved this criterion")
        case.stage = 4

    if streak >= policy.case_after_consecutive and case.stage < 5 and policy.create_case_enabled:
        sc = open_support_case(db, patient_id, "missed_medication",
                               f"{streak} consecutive unconfirmed doses after reminders, follow-ups and check-in.")
        case.support_case_id = sc.id
        case.stage = 5
        _log(case, 5, "care-coordinator case created")
    return case
