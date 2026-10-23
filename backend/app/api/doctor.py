"""Doctor portal: dashboard, patient list/profile, prescriptions, interaction review, clinical
briefs, instructions & follow-ups, prescription verification (OCR), availability."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import serializers as S
from app.api.patients import ocr_out
from app.core import audit
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.errors import bad_request, not_found
from app.models import (
    Appointment,
    AvailabilitySlot,
    ClinicalBrief,
    DoctorAvailability,
    DoctorPatientAccess,
    EscalationCase,
    FollowUpInstruction,
    InteractionAssessment,
    MedicalRecord,
    OCRExtraction,
    PatientProfile,
    PrescriptionItem,
    RecordCorrectionRequest,
    RefillRequest,
    User,
)
from app.models.base import utcnow
from app.schemas.prescriptions import Discontinue, MedicationOrder, PrescriptionCreate, PrescriptionEdit, StatusChange
from app.services import booking, clinical_brief, interactions, notifications, prescriptions, realtime
from app.services.medication_schedule import adherence_summary
from app.services.permissions import authorize_patient, patients_visible_to, users_with_access

router = APIRouter(prefix="/api/doctor", tags=["doctor"])
Doctor = require_roles("doctor")


@router.get("/dashboard")
def dashboard(user: User = Depends(Doctor), db: Session = Depends(get_db)):
    now = utcnow()
    end_of_day = now.replace(hour=23, minute=59)
    pids = patients_visible_to(db, user)
    appts = db.execute(select(Appointment).where(Appointment.doctor_user_id == user.id,
                                                 Appointment.status == "confirmed", Appointment.starts_at >= now - timedelta(hours=1))
                       .order_by(Appointment.starts_at).limit(20)).scalars().all()
    today = [S.appointment(a) for a in appts if a.starts_at <= end_of_day + timedelta(hours=6)]
    upcoming = [S.appointment(a) for a in appts if a not in today][:8]
    follow = db.execute(select(FollowUpInstruction).where(FollowUpInstruction.author_user_id == user.id,
                                                          FollowUpInstruction.kind == "follow_up",
                                                          FollowUpInstruction.status == "open")).scalars().all()
    esc = db.execute(select(EscalationCase).where(EscalationCase.patient_id.in_(pids),
                                                  EscalationCase.status == "open")).scalars().all() if pids else []
    verif = db.execute(select(OCRExtraction).where(OCRExtraction.patient_id.in_(pids),
                                                   OCRExtraction.status == "patient_reviewed")).scalars().all() if pids else []
    refills = db.execute(select(RefillRequest).where(RefillRequest.patient_id.in_(pids),
                                                     RefillRequest.status == "requested")).scalars().all() if pids else []
    corrections = db.execute(select(RecordCorrectionRequest).where(RecordCorrectionRequest.patient_id.in_(pids),
                                                                   RecordCorrectionRequest.status == "open")).scalars().all() if pids else []
    unreviewed = db.execute(select(InteractionAssessment).where(
        InteractionAssessment.requested_by == user.id, InteractionAssessment.reviewed_at.is_(None))).scalars().all()
    unreviewed = [a for a in unreviewed if a.alerts]
    names = {p.id: p.user.full_name for p in db.execute(select(PatientProfile).where(PatientProfile.id.in_(pids))).scalars()} if pids else {}
    tasks = (
        [{"kind": "verification", "title": f"Verify uploaded prescription — {names.get(v.patient_id)}",
          "link": "/doctor/verification", "priority": "high"} for v in verif]
        + [{"kind": "interaction_review", "title": f"Review safety alert — {names.get(a.patient_id)}",
            "link": f"/doctor/patients/{a.patient_id}", "priority": "high"} for a in unreviewed]
        + [{"kind": "refill", "title": f"Refill request — {names.get(r.patient_id)}",
            "link": f"/doctor/patients/{r.patient_id}", "priority": "normal", "id": r.id} for r in refills]
        + [{"kind": "correction", "title": f"Record correction request — {names.get(c.patient_id)}",
            "link": f"/doctor/patients/{c.patient_id}", "priority": "normal", "id": c.id} for c in corrections]
    )
    return {
        "today_appointments": today,
        "upcoming": upcoming,
        "follow_ups": [{**S.instruction(f), "patient_name": names.get(f.patient_id)} for f in follow],
        "adherence_alerts": [{"patient_id": e.patient_id, "patient_name": names.get(e.patient_id), "stage": e.stage,
                              "consecutive_unconfirmed": e.consecutive_unconfirmed, "since": e.created_at}
                             for e in esc],
        "pending_verifications": len(verif),
        "tasks": tasks,
        "patient_count": len(pids),
    }


@router.get("/patients")
def patient_list(q: str | None = None, filter: str | None = None, user: User = Depends(Doctor),
                 db: Session = Depends(get_db)):
    """Only patients this doctor is authorised for. Searching never reveals other patients."""
    pids = patients_visible_to(db, user)
    db.commit()
    if not pids:
        return []
    now = utcnow()
    out = []
    for p in db.execute(select(PatientProfile).where(PatientProfile.id.in_(pids))).scalars():
        if q and q.lower() not in p.user.full_name.lower() and q.lower() not in p.mrn.lower():
            continue
        last = db.execute(select(func.max(Appointment.starts_at)).where(
            Appointment.patient_id == p.id, Appointment.doctor_user_id == user.id, Appointment.starts_at < now,
            Appointment.status.in_(("completed", "confirmed")))).scalar()
        nxt = db.execute(select(func.min(Appointment.starts_at)).where(
            Appointment.patient_id == p.id, Appointment.doctor_user_id == user.id, Appointment.starts_at >= now,
            Appointment.status == "confirmed")).scalar()
        esc = db.execute(select(EscalationCase).where(EscalationCase.patient_id == p.id,
                                                      EscalationCase.status == "open")).first()
        fu = db.execute(select(FollowUpInstruction).where(FollowUpInstruction.patient_id == p.id,
                                                          FollowUpInstruction.kind == "follow_up",
                                                          FollowUpInstruction.status == "open")).first()
        active = db.execute(select(func.count(PrescriptionItem.id)).where(
            PrescriptionItem.patient_id == p.id, PrescriptionItem.status == "active")).scalar()
        acc = db.execute(select(DoctorPatientAccess).where(DoctorPatientAccess.patient_id == p.id,
                                                           DoctorPatientAccess.doctor_user_id == user.id,
                                                           DoctorPatientAccess.status == "active")).scalars().first()
        flags = {
            "upcoming_appointment": bool(nxt), "requires_follow_up": bool(fu),
            "new_patient": bool(acc and acc.created_at > now - timedelta(days=14)),
            "adherence_concern": bool(esc), "active_treatment": bool(active),
        }
        if filter and not flags.get(filter):
            continue
        out.append({"id": p.id, "name": p.user.full_name, "mrn": p.mrn, "avatar_color": p.user.avatar_color,
                    "last_consultation": last, "next_appointment": nxt, "flags": flags,
                    "permission": {"status": acc.status if acc else "break_glass_only",
                                   "expires_at": acc.expires_at if acc else None,
                                   "authority": acc.granting_authority if acc else None}})
    return sorted(out, key=lambda r: r["name"])


@router.get("/patients/{patient_id}")
def patient_profile(patient_id: str, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view", audit_read=True)
    p = acc.patient
    items = db.execute(select(PrescriptionItem).where(PrescriptionItem.patient_id == p.id)
                       .order_by(PrescriptionItem.updated_at.desc())).scalars().all()
    encounters = db.execute(select(MedicalRecord).where(MedicalRecord.patient_id == p.id)
                            .order_by(MedicalRecord.occurred_at.desc()).limit(8)).scalars()
    fus = db.execute(select(FollowUpInstruction).where(FollowUpInstruction.patient_id == p.id)
                     .order_by(FollowUpInstruction.created_at.desc())).scalars()
    assessments = db.execute(select(InteractionAssessment).where(InteractionAssessment.patient_id == p.id)
                             .order_by(InteractionAssessment.created_at.desc()).limit(5)).scalars()
    from app.models import MedicationEvent

    barriers = db.execute(select(MedicationEvent).where(MedicationEvent.patient_id == p.id,
                                                       MedicationEvent.kind == "cant_take")
                          .order_by(MedicationEvent.created_at.desc()).limit(10)).scalars()
    corrections = db.execute(select(RecordCorrectionRequest).where(RecordCorrectionRequest.patient_id == p.id,
                                                                   RecordCorrectionRequest.status == "open")).scalars()
    refills = db.execute(select(RefillRequest).where(RefillRequest.patient_id == p.id,
                                                     RefillRequest.status == "requested")).scalars()
    team = users_with_access(db, p.id, "messages.patient")
    return {
        "access": acc.kind,
        "patient": {"id": p.id, "name": p.user.full_name, "mrn": p.mrn, "dob": p.date_of_birth, "sex": p.sex,
                    "blood_group": p.blood_group, "avatar_color": p.user.avatar_color, "user_id": p.user_id,
                    "allergy_status": p.allergy_status, "timezone": p.timezone},
        "prescriptions": [S.item(i) for i in items if i.versions],
        "recent_encounters": [S.record(r) for r in encounters],
        "follow_ups": [S.instruction(f) for f in fus],
        "adherence": {"week": adherence_summary(db, p.id, 7), "month": adherence_summary(db, p.id, 30),
                      "barriers": [{"at": b.created_at, "reason": b.reason, "note": b.note} for b in barriers]},
        "assessments": [interactions.serialize(a) for a in assessments],
        "corrections": [{"id": c.id, "record_id": c.record_id, "description": c.description, "created_at": c.created_at}
                        for c in corrections],
        "refills": [{"id": r.id, "item_id": r.item_id, "note": r.note, "created_at": r.created_at} for r in refills],
        "care_team": [S.person(u) for u in team if u.id != user.id],
    }


# ---------------- prescriptions ----------------
@router.post("/prescriptions")
def create_prescription(body: PrescriptionCreate, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, body.patient_id, "prescribe")
    rx, assessments = prescriptions.create(db, user, acc.patient, body.items, body.notes, body.publish)
    db.commit()
    return {"prescription_id": rx.id, "items": [S.item(i) for i in rx.items],
            "assessments": [interactions.serialize(a) for a in assessments]}


def _item_for(db, user, item_id, scope="prescribe") -> PrescriptionItem:
    it = db.get(PrescriptionItem, item_id)
    if not it:
        raise not_found("Prescription")
    authorize_patient(db, user, it.patient_id, scope)
    return it


@router.get("/prescription-items/{item_id}")
def get_item(item_id: str, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    it = _item_for(db, user, item_id, "medications.view")
    out = S.item(it, full=True)
    out["assessments"] = [interactions.serialize(a) for a in db.execute(
        select(InteractionAssessment).where(InteractionAssessment.item_id == it.id)
        .order_by(InteractionAssessment.created_at.desc())).scalars()]
    out["external"] = it.prescription.source != "impulse" or it.prescription.prescriber_user_id != user.id
    return out


@router.put("/prescription-items/{item_id}")
def edit_item(item_id: str, body: PrescriptionEdit, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    it = _item_for(db, user, item_id)
    v, assessment = prescriptions.edit(db, user, it, body.order, body.change_reason, body.expected_lock_version,
                                       body.effective_from)
    db.commit()
    return {"item": S.item(it, full=True), "assessment": interactions.serialize(assessment)}


@router.post("/prescription-items/{item_id}/discontinue")
def discontinue(item_id: str, body: Discontinue, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    it = _item_for(db, user, item_id)
    prescriptions.discontinue(db, user, it, effective_at=body.effective_at, reason=body.reason,
                              instructions=body.special_instructions, follow_up=body.follow_up,
                              expected_lock=body.expected_lock_version)
    db.commit()
    return S.item(it, full=True)


@router.post("/prescription-items/{item_id}/status")
def change_status(item_id: str, body: StatusChange, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    it = _item_for(db, user, item_id)
    prescriptions.set_status(db, user, it, body.status, body.reason, body.expected_lock_version)
    db.commit()
    return S.item(it, full=True)


@router.post("/prescription-items/{item_id}/interaction-check")
def recheck(item_id: str, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    it = _item_for(db, user, item_id, "medications.view")
    a = interactions.assess(db, it.patient_id, new_item=it, user=user)
    db.commit()
    return interactions.serialize(a)


class PreviewIn(BaseModel):
    patient_id: str
    order: MedicationOrder


@router.post("/interaction-preview")
def preview(body: PreviewIn, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    """Runs the safety checks on a draft before it is saved. Nothing is persisted; the checks
    run again (and are recorded) when the prescription is actually created."""
    acc = authorize_patient(db, user, body.patient_id, "prescribe")
    rx, assessments = prescriptions.create(db, user, acc.patient, [body.order], "draft preview", publish=False)
    out = interactions.serialize(assessments[0])
    db.rollback()  # discard the draft; preview is advisory only
    return out


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(acknowledged|will_modify|override)$")
    note: str | None = Field(default=None, max_length=1000)


@router.post("/interaction-assessments/{assessment_id}/review")
def review_assessment(assessment_id: str, body: ReviewIn, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    a = db.get(InteractionAssessment, assessment_id)
    if not a:
        raise not_found("Assessment")
    authorize_patient(db, user, a.patient_id, "prescribe")
    if body.decision == "override" and not body.note:
        raise bad_request("Please document the clinical reason for proceeding")
    a.reviewed_by, a.reviewed_at, a.review_decision, a.review_note = user.id, utcnow(), body.decision, body.note
    audit.record(db, action="interaction_reviewed", resource_type="interaction_assessment", resource_id=a.id,
                 patient_id=a.patient_id, user=user, reason=body.decision)
    db.commit()
    return interactions.serialize(a)


class RefillDecision(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


@router.post("/refills/{refill_id}")
def decide_refill(refill_id: str, body: RefillDecision, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    r = db.get(RefillRequest, refill_id)
    if not r:
        raise not_found("Refill")
    authorize_patient(db, user, r.patient_id, "prescribe")
    if r.status != "requested":
        raise bad_request("Already decided")
    r.status = "approved" if body.approve else "declined"
    r.reviewed_by, r.reviewed_at, r.review_note = user.id, utcnow(), body.note
    p = db.get(PatientProfile, r.patient_id)
    notifications.notify(db, p.user, category="prescription_change", title=f"Refill {r.status}",
                         body=body.note or "Open DoseWISE for details.", patient_id=p.id, link="/patient/medicines")
    audit.record(db, action=f"refill_{r.status}", resource_type="refill", resource_id=r.id, patient_id=p.id, user=user)
    db.commit()
    return {"status": r.status}


class CorrectionDecision(BaseModel):
    accept: bool
    note: str = Field(min_length=3, max_length=1000)
    amended_summary: str | None = Field(default=None, max_length=4000)


@router.post("/corrections/{correction_id}")
def decide_correction(correction_id: str, body: CorrectionDecision, user: User = Depends(Doctor),
                      db: Session = Depends(get_db)):
    c = db.get(RecordCorrectionRequest, correction_id)
    if not c:
        raise not_found("Correction request")
    authorize_patient(db, user, c.patient_id, "clinical.write")
    if c.status != "open":
        raise bad_request("Already decided")
    c.status = "accepted" if body.accept else "declined"
    c.reviewer_user_id, c.reviewer_note, c.resolved_at = user.id, body.note, utcnow()
    if body.accept:
        orig = db.get(MedicalRecord, c.record_id)
        amended = MedicalRecord(patient_id=orig.patient_id, record_type=orig.record_type,
                                title=f"{orig.title} (amended)", summary=body.amended_summary or orig.summary,
                                occurred_at=orig.occurred_at, doctor_user_id=orig.doctor_user_id,
                                organization_id=orig.organization_id, document_id=orig.document_id,
                                medication_names=orig.medication_names, data=orig.data,
                                provenance="clinician_verified", amends_id=orig.id, created_by=user.id)
        orig.status = "amended"  # original kept unchanged and still viewable
        db.add(amended)
        db.flush()
        c.amendment_record_id = amended.id
    p = db.get(PatientProfile, c.patient_id)
    notifications.notify(db, p.user, category="important_alert", title=f"Correction {c.status}", body=body.note,
                         patient_id=p.id, link="/patient/records")
    audit.record(db, action=f"record_correction_{c.status}", resource_type="medical_record", resource_id=c.record_id,
                 patient_id=p.id, user=user)
    db.commit()
    return {"status": c.status}


# ---------------- clinical briefs ----------------
class BriefIn(BaseModel):
    appointment_id: str | None = None


@router.post("/patients/{patient_id}/brief")
def make_brief(patient_id: str, body: BriefIn, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view")
    b = clinical_brief.generate(db, user, acc.patient, body.appointment_id)
    db.commit()
    return {"id": b.id, "created_at": b.created_at, "content": b.content, "ai_summary": b.ai_summary,
            "ai_status": b.ai_status}


@router.get("/briefs")
def list_briefs(user: User = Depends(Doctor), db: Session = Depends(get_db)):
    pids = set(patients_visible_to(db, user))
    rows = db.execute(select(ClinicalBrief).where(ClinicalBrief.generated_for == user.id)
                      .order_by(ClinicalBrief.created_at.desc()).limit(50)).scalars()
    return [{"id": b.id, "patient_id": b.patient_id, "patient_name": db.get(PatientProfile, b.patient_id).user.full_name,
             "created_at": b.created_at, "ai_status": b.ai_status,
             "missing": len(b.content.get("missing_information", [])), "conflicts": len(b.content.get("conflicts", []))}
            for b in rows if b.patient_id in pids]


@router.get("/briefs/{brief_id}")
def get_brief(brief_id: str, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    b = db.get(ClinicalBrief, brief_id)
    if not b:
        raise not_found("Brief")
    authorize_patient(db, user, b.patient_id, "records.view")
    audit.record(db, action="read:clinical_brief", resource_type="clinical_brief", resource_id=b.id,
                 patient_id=b.patient_id, user=user)
    db.commit()
    return {"id": b.id, "patient_id": b.patient_id, "created_at": b.created_at, "content": b.content,
            "ai_summary": b.ai_summary, "ai_status": b.ai_status}


# ---------------- instructions & follow-ups ----------------
class InstructionIn(BaseModel):
    patient_id: str
    kind: str = Field(default="instruction", pattern="^(instruction|follow_up)$")
    audience: str = Field(default="patient", pattern="^(patient|caregiver|both)$")
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")
    expires_on: date | None = None
    requires_ack: bool = False
    due_date: date | None = None
    timeframe: str | None = Field(default=None, max_length=60)
    appointment_request: bool = False
    linked_instruction_ids: list[str] = []
    attachments: list[str] = []


@router.post("/instructions")
def create_instruction(body: InstructionIn, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, body.patient_id, "instructions.write")
    f = FollowUpInstruction(author_user_id=user.id, **body.model_dump())
    db.add(f)
    db.flush()
    recipients = []
    if body.audience in ("patient", "both"):
        recipients.append(acc.patient.user)
    if body.audience in ("caregiver", "both"):
        recipients += [u for u in users_with_access(db, body.patient_id, "instructions.view") if u.role == "caregiver"]
    if not recipients:
        f.delivery_status = "no_recipient"
    for u in recipients:
        notifications.notify(db, u, category="doctor_instruction",
                             title="New follow-up recommendation" if body.kind == "follow_up" else "New instruction from your doctor",
                             body=body.title, patient_id=body.patient_id, priority=body.priority,
                             link="/patient" if u.role == "patient" else f"/caregiver/patients/{body.patient_id}",
                             dedupe_key=f"ins:{f.id}:{u.id}")
    audit.record(db, action=f"{body.kind}_created", resource_type="follow_up_instruction", resource_id=f.id,
                 patient_id=body.patient_id, user=user)
    realtime.queue(db, [u.id for u in recipients], "instructions", body.patient_id, f.id)
    db.commit()
    return S.instruction(f)


@router.get("/follow-ups")
def follow_ups(status: str = "open", user: User = Depends(Doctor), db: Session = Depends(get_db)):
    pids = patients_visible_to(db, user)
    rows = db.execute(select(FollowUpInstruction).where(FollowUpInstruction.author_user_id == user.id,
                                                        FollowUpInstruction.status == status)
                      .order_by(FollowUpInstruction.due_date)).scalars()
    return [{**S.instruction(f), "patient_name": db.get(PatientProfile, f.patient_id).user.full_name}
            for f in rows if f.patient_id in pids]


@router.post("/follow-ups/{fid}/complete")
def complete_follow_up(fid: str, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    f = db.get(FollowUpInstruction, fid)
    if not f or f.author_user_id != user.id:
        raise not_found("Follow-up")
    authorize_patient(db, user, f.patient_id, "instructions.write")
    f.status, f.completed_at = "completed", utcnow()
    db.commit()
    return S.instruction(f)


# ---------------- prescription verification (OCR) ----------------
@router.get("/verifications")
def verifications(user: User = Depends(Doctor), db: Session = Depends(get_db)):
    pids = patients_visible_to(db, user)
    if not pids:
        return []
    rows = db.execute(select(OCRExtraction).where(OCRExtraction.patient_id.in_(pids),
                                                  OCRExtraction.status.in_(("patient_reviewed", "extracted")))
                      .order_by(OCRExtraction.created_at.desc())).scalars()
    return [{**ocr_out(e), "patient_id": e.patient_id, "patient_name": db.get(PatientProfile, e.patient_id).user.full_name,
             "document": S.document(e.document)} for e in rows]


class VerifyIn(BaseModel):
    approve: bool
    note: str = Field(min_length=3, max_length=1000)
    items: list[MedicationOrder] = []


@router.post("/verifications/{ext_id}")
def verify(ext_id: str, body: VerifyIn, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    e = db.get(OCRExtraction, ext_id)
    if not e:
        raise not_found("Extraction")
    acc = authorize_patient(db, user, e.patient_id, "prescribe")
    if e.status != "patient_reviewed":
        raise bad_request("The patient must review the extracted details before verification")
    e.verified_by, e.verified_at, e.verification_note = user.id, utcnow(), body.note
    if body.approve:
        if not body.items:
            raise bad_request("Enter the structured medication details you are approving")
        rx, _ = prescriptions.create(db, user, acc.patient, body.items, f"Verified from uploaded document: {body.note}",
                                     publish=True, source="ocr_verified")
        rx.notes = f"Source document {e.document_id}"
        e.resulting_prescription_id = rx.id
        e.status = "verified"
    else:
        e.status = "rejected"
        notifications.notify(db, acc.patient.user, category="important_alert", title="Uploaded prescription not approved",
                             body=body.note, patient_id=e.patient_id, link="/patient/records")
    e.history = [*e.history, {"at": utcnow().isoformat(), "event": e.status, "by": user.id, "note": body.note}]
    audit.record(db, action=f"ocr_{e.status}", resource_type="ocr_extraction", resource_id=e.id,
                 patient_id=e.patient_id, user=user)
    db.commit()
    return ocr_out(e)


# ---------------- appointments & availability ----------------
@router.get("/appointments")
def doctor_appointments(scope: str = Query("upcoming", pattern="^(upcoming|past|all)$"), user: User = Depends(Doctor),
                        db: Session = Depends(get_db)):
    qy = select(Appointment).where(Appointment.doctor_user_id == user.id)
    now = utcnow()
    if scope == "upcoming":
        qy = qy.where(Appointment.starts_at >= now - timedelta(hours=2)).order_by(Appointment.starts_at)
    elif scope == "past":
        qy = qy.where(Appointment.starts_at < now).order_by(Appointment.starts_at.desc())
    return [S.appointment(a) for a in db.execute(qy.limit(100)).scalars()]


class ApptStatus(BaseModel):
    status: str = Field(pattern="^(completed|no_show)$")


@router.post("/appointments/{appt_id}/status")
def appointment_status(appt_id: str, body: ApptStatus, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    a = db.get(Appointment, appt_id)
    if not a or a.doctor_user_id != user.id:
        raise not_found("Appointment")
    if a.status != "confirmed":
        raise bad_request("Only confirmed appointments can be updated")
    a.status = body.status
    a.history = [*a.history, {"at": utcnow().isoformat(), "event": body.status, "by": user.id}]
    if body.status == "completed":
        db.add(MedicalRecord(patient_id=a.patient_id, record_type="consultation", title=f"Consultation with {user.full_name}",
                             occurred_at=a.starts_at, doctor_user_id=user.id, organization_id=a.organization_id,
                             created_by=user.id, provenance="clinician_verified"))
    db.commit()
    return S.appointment(a)


@router.get("/availability")
def get_availability(user: User = Depends(Doctor), db: Session = Depends(get_db)):
    rules = db.execute(select(DoctorAvailability).where(DoctorAvailability.doctor_user_id == user.id)
                       .order_by(DoctorAvailability.weekday, DoctorAvailability.start_time)).scalars()
    from app.models import DoctorLeave

    leave = db.execute(select(DoctorLeave).where(DoctorLeave.doctor_user_id == user.id)).scalars()
    return {"rules": [{"id": r.id, "weekday": r.weekday, "start_time": r.start_time, "end_time": r.end_time,
                       "slot_minutes": r.slot_minutes, "capacity": r.capacity,
                       "consultation_type": r.consultation_type, "organization_id": r.organization_id} for r in rules],
            "leave": [{"id": lv.id, "start_date": lv.start_date, "end_date": lv.end_date, "reason": lv.reason} for lv in leave]}


class RuleIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    slot_minutes: int = Field(ge=10, le=120)
    capacity: int = Field(default=1, ge=1, le=10)
    consultation_type: str = Field(default="in_person", pattern="^(in_person|video)$")


class AvailabilityIn(BaseModel):
    rules: list[RuleIn]


@router.put("/availability")
def set_availability(body: AvailabilityIn, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    for r in body.rules:
        if r.end_time <= r.start_time:
            raise bad_request("End time must be after start time")
    org = user.doctor_profile.organization_id
    for r in db.execute(select(DoctorAvailability).where(DoctorAvailability.doctor_user_id == user.id)).scalars():
        db.delete(r)
    for r in body.rules:
        db.add(DoctorAvailability(doctor_user_id=user.id, organization_id=org, **r.model_dump()))
    # drop future empty slots and regenerate; booked slots are kept untouched
    for s in db.execute(select(AvailabilitySlot).where(AvailabilitySlot.doctor_user_id == user.id,
                                                       AvailabilitySlot.starts_at > utcnow(),
                                                       AvailabilitySlot.booked_count == 0)).scalars():
        db.delete(s)
    db.flush()
    n = booking.materialize_slots(db, user.id)
    db.commit()
    return {"slots_created": n}


class LeaveIn(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=200)


@router.post("/leave")
def add_leave(body: LeaveIn, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    if body.end_date < body.start_date:
        raise bad_request("End date must be on or after start date")
    n = booking.apply_leave(db, user.id, body.start_date, body.end_date, body.reason)
    db.commit()
    return {"slots_blocked": n, "note": "Existing bookings in this period were not cancelled; please reschedule them."}


class BlockIn(BaseModel):
    blocked: bool
    reason: str | None = None


@router.post("/slots/{slot_id}/block")
def block_slot(slot_id: str, body: BlockIn, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    s = db.get(AvailabilitySlot, slot_id)
    if not s or s.doctor_user_id != user.id:
        raise not_found("Slot")
    if body.blocked and s.booked_count:
        raise bad_request("This slot has a booking; cancel or reschedule it first")
    s.status, s.block_reason = ("blocked", body.reason) if body.blocked else ("open", None)
    db.commit()
    return {"status": s.status}


@router.get("/slots")
def my_slots(day: date, user: User = Depends(Doctor), db: Session = Depends(get_db)):
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Kolkata")
    lo = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    rows = db.execute(select(AvailabilitySlot).where(AvailabilitySlot.doctor_user_id == user.id,
                                                     AvailabilitySlot.starts_at >= lo,
                                                     AvailabilitySlot.starts_at < lo + timedelta(days=1))
                      .order_by(AvailabilitySlot.starts_at)).scalars()
    return [{"id": s.id, "starts_at": s.starts_at, "ends_at": s.ends_at, "status": s.status,
             "booked": s.booked_count, "capacity": s.capacity, "block_reason": s.block_reason} for s in rows]
