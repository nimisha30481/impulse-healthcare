"""Human care-coordination: assigned cases, contact attempts, notes, resolution, escalation.
Staff see only the minimum necessary patient details for the cases assigned to them."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import serializers as S
from app.core import audit
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.errors import bad_request, forbidden, not_found
from app.integrations import aws_services
from app.models import (
    CareRelationship,
    CaseNote,
    ContactAttempt,
    DoseOccurrence,
    EscalationCase,
    SupportCase,
    User,
)
from app.models.base import utcnow

router = APIRouter(prefix="/api/support", tags=["support"])
Staff = require_roles("support")

OPERATIONAL_NOTE = ("Cases are reviewed by people during staffed hours. IMPULSE does not provide real-time or "
                    "24/7 monitoring and does not dispatch emergency services.")


def _case_summary(c: SupportCase) -> dict:
    return {"id": c.id, "case_type": c.case_type, "priority": c.priority, "status": c.status, "reason": c.reason,
            "created_at": c.created_at, "updated_at": c.updated_at, "patient_name": c.patient.user.full_name,
            "patient_id": c.patient_id, "assigned_to": S.person(c.assignee)}


@router.get("/cases")
def cases(status: str | None = None, user: User = Depends(Staff), db: Session = Depends(get_db)):
    qy = select(SupportCase).where(SupportCase.assigned_to == user.id)
    if status:
        qy = qy.where(SupportCase.status == status)
    rows = db.execute(qy.order_by(SupportCase.created_at.desc())).scalars().all()
    order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    rows.sort(key=lambda c: (c.status == "resolved", order.get(c.priority, 9)))
    return {"cases": [_case_summary(c) for c in rows], "operational_note": OPERATIONAL_NOTE}


def _own_case(db, user, case_id) -> SupportCase:
    c = db.get(SupportCase, case_id)
    if not c:
        raise not_found("Case")
    if c.assigned_to != user.id:
        audit.record(db, action="support_case_access_denied", resource_type="support_case", resource_id=case_id,
                     patient_id=c.patient_id, user=user, outcome="denied", commit=True)
        raise forbidden("This case is not assigned to you")
    return c


@router.get("/cases/{case_id}")
def case_detail(case_id: str, user: User = Depends(Staff), db: Session = Depends(get_db)):
    c = _own_case(db, user, case_id)
    p = c.patient
    caregivers = db.execute(select(CareRelationship).where(CareRelationship.patient_id == p.id,
                                                           CareRelationship.status == "active")).scalars()
    checkins = db.execute(select(DoseOccurrence).where(DoseOccurrence.patient_id == p.id,
                                                       DoseOccurrence.scheduled_at <= utcnow())
                          .order_by(DoseOccurrence.scheduled_at.desc()).limit(12)).scalars()
    esc = db.execute(select(EscalationCase).where(EscalationCase.support_case_id == c.id)).scalar_one_or_none()
    audit.record(db, action="support_case_access", resource_type="support_case", resource_id=c.id,
                 patient_id=p.id, user=user, auth_context="support_case")
    db.commit()
    return {
        **_case_summary(c),
        "resolution": c.resolution, "history": c.history,
        # minimum necessary: contact details + check-in status, not the medical record
        "patient_contact": {"name": p.user.full_name, "preferred_name": p.user.preferred_name, "phone": p.user.phone,
                            "email": p.user.email, "timezone": p.timezone,
                            "emergency_contact": {"name": p.emergency_contact_name, "phone": p.emergency_contact_phone,
                                                  "relation": p.emergency_contact_relation}},
        "caregivers": [{"name": r.caregiver.full_name, "phone": r.caregiver.phone, "email": r.caregiver.email,
                        "relationship": r.relationship_label, "can_be_notified": "adherence.notify" in r.scopes}
                       for r in caregivers if r.caregiver],
        "checkin_history": [{"scheduled_at": o.scheduled_at, "status": o.status} for o in checkins],
        "escalation": {"stage": esc.stage, "history": esc.history} if esc else None,
        "attempts": [{"id": a.id, "at": a.created_at, "method": a.method, "target": a.target, "outcome": a.outcome,
                      "note": a.note} for a in c.attempts],
        "notes": [{"id": n.id, "at": n.created_at, "author": n.author.full_name, "body": n.body} for n in c.notes],
        "operational_note": OPERATIONAL_NOTE,
    }


class AttemptIn(BaseModel):
    method: str = Field(pattern="^(phone|sms|email|in_app)$")
    target: str = Field(pattern="^(patient|caregiver|emergency_contact)$")
    outcome: str = Field(pattern="^(reached|no_answer|voicemail|wrong_number|message_sent)$")
    note: str | None = Field(default=None, max_length=2000)


@router.post("/cases/{case_id}/attempts")
def add_attempt(case_id: str, body: AttemptIn, user: User = Depends(Staff), db: Session = Depends(get_db)):
    c = _own_case(db, user, case_id)
    db.add(ContactAttempt(case_id=c.id, user_id=user.id, **body.model_dump()))
    if c.status == "open":
        c.status = "in_progress"
    c.history = [*c.history, {"at": utcnow().isoformat(), "event": f"contact {body.target} via {body.method}: {body.outcome}",
                              "by": user.id}]
    audit.record(db, action="support_contact_attempt", resource_type="support_case", resource_id=c.id,
                 patient_id=c.patient_id, user=user, reason=body.outcome)
    db.commit()
    return {"status": c.status}


class NoteIn(BaseModel):
    body: str = Field(min_length=2, max_length=4000)


@router.post("/cases/{case_id}/notes")
def add_note(case_id: str, body: NoteIn, user: User = Depends(Staff), db: Session = Depends(get_db)):
    c = _own_case(db, user, case_id)
    db.add(CaseNote(case_id=c.id, author_user_id=user.id, body=body.body))
    audit.record(db, action="support_case_note", resource_type="support_case", resource_id=c.id,
                 patient_id=c.patient_id, user=user)
    db.commit()
    return {"status": "added"}


class ResolveIn(BaseModel):
    resolution: str = Field(min_length=5, max_length=4000)


@router.post("/cases/{case_id}/resolve")
def resolve(case_id: str, body: ResolveIn, user: User = Depends(Staff), db: Session = Depends(get_db)):
    c = _own_case(db, user, case_id)
    if c.status == "resolved":
        raise bad_request("Already resolved")
    c.status, c.resolution, c.resolved_at = "resolved", body.resolution, utcnow()
    c.history = [*c.history, {"at": utcnow().isoformat(), "event": "resolved", "by": user.id}]
    esc = db.execute(select(EscalationCase).where(EscalationCase.support_case_id == c.id)).scalar_one_or_none()
    if esc:
        esc.status = "resolved"
    audit.record(db, action="support_case_resolved", resource_type="support_case", resource_id=c.id,
                 patient_id=c.patient_id, user=user)
    db.commit()
    return {"status": "resolved"}


class EscalateIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)
    priority: str = Field(default="urgent", pattern="^(high|urgent)$")


@router.post("/cases/{case_id}/escalate")
def escalate(case_id: str, body: EscalateIn, user: User = Depends(Staff), db: Session = Depends(get_db)):
    """Stage 6: escalate per documented operational procedure (supervisor review)."""
    c = _own_case(db, user, case_id)
    c.status, c.priority = "escalated", body.priority
    c.history = [*c.history, {"at": utcnow().isoformat(), "event": f"escalated: {body.reason}", "by": user.id}]
    res = aws_services.ops_alert(f"IMPULSE case escalated ({body.priority})", f"Case {c.id}: {body.reason[:500]}")
    audit.record(db, action="support_case_escalated", resource_type="support_case", resource_id=c.id,
                 patient_id=c.patient_id, user=user, reason=body.reason[:300])
    db.commit()
    return {"status": "escalated", "supervisor_alert": res.state}
