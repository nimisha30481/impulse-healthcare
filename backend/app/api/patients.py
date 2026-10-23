"""Patient-scoped data. Used by patients for themselves and by caregivers/doctors/support for
patients they are authorised for - every route calls authorize_patient with a specific scope."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api import serializers as S
from app.core import audit
from app.core.database import get_db
from app.core.deps import client_ip, current_user
from app.core.errors import bad_request, forbidden, not_found
from app.integrations import storage
from app.models import (
    Allergy,
    Appointment,
    CareRelationship,
    Diagnosis,
    DoctorPatientAccess,
    DoseOccurrence,
    EmergencyAlert,
    FollowUpInstruction,
    InteractionAssessment,
    MedicalRecord,
    MedicationEvent,
    Message,
    Notification,
    OCRExtraction,
    PatientProfile,
    PrescriptionItem,
    RecordCorrectionRequest,
    RefillRequest,
    UploadedDocument,
    User,
)
from app.models.base import new_id, utcnow
from app.services import escalation, interactions, medication_schedule, notifications, ocr, realtime
from app.services.permissions import authorize_patient, users_with_access

router = APIRouter(prefix="/api/patients/{patient_id}", tags=["patients"])


# ---------------- dashboard ----------------
@router.get("/overview")
def overview(patient_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "medications.view")
    p = acc.patient
    tz = ZoneInfo(p.timezone)
    today = utcnow().astimezone(tz).date()
    lo = datetime.combine(today, time.min, tzinfo=tz)
    for it in db.execute(select(PrescriptionItem).where(PrescriptionItem.patient_id == p.id,
                                                        PrescriptionItem.status == "active")).scalars():
        medication_schedule.materialize_item(db, it)
    db.commit()
    doses = db.execute(select(DoseOccurrence).where(
        DoseOccurrence.patient_id == p.id, DoseOccurrence.scheduled_at >= lo,
        DoseOccurrence.scheduled_at < lo + timedelta(days=1), DoseOccurrence.status != "cancelled")
        .order_by(DoseOccurrence.scheduled_at)).scalars().all()
    nxt = None
    if acc.kind in ("owner", "doctor_access") or authorize_ok(db, user, p.id, "appointments.view"):
        a = db.execute(select(Appointment).where(Appointment.patient_id == p.id, Appointment.status == "confirmed",
                                                 Appointment.starts_at > utcnow())
                       .order_by(Appointment.starts_at).limit(1)).scalar_one_or_none()
        nxt = S.appointment(a) if a else None
    return {
        "patient": {"id": p.id, "name": p.user.full_name, "preferred_name": p.user.preferred_name or p.user.full_name.split()[0],
                    "mrn": p.mrn, "avatar_color": p.user.avatar_color, "timezone": p.timezone},
        "access": acc.kind,
        "today": [S.dose(o) for o in doses],
        "adherence": medication_schedule.adherence_summary(db, p.id, 7),
        "next_appointment": nxt,
        "care_team": care_team(db, p) if acc.kind == "owner" else None,
    }


def authorize_ok(db, user, pid, scope) -> bool:
    from app.services.permissions import check_patient_access

    return check_patient_access(db, user, pid, scope) is not None


def care_team(db: Session, p: PatientProfile) -> dict:
    rels = db.execute(select(CareRelationship).where(CareRelationship.patient_id == p.id,
                                                     CareRelationship.status.in_(("invited", "accepted", "active"))))
    docs = db.execute(select(DoctorPatientAccess).where(DoctorPatientAccess.patient_id == p.id,
                                                        DoctorPatientAccess.status == "active")).scalars()
    return {
        "caregivers": [{"id": r.id, "status": r.status, "contact": r.invite_contact, "label": r.relationship_label,
                        "scopes": r.scopes, "expires_at": r.expires_at, "caregiver": S.person(r.caregiver),
                        "authorized_at": r.authorized_at} for r in rels.scalars()],
        "doctors": [{"access_id": d.id, "doctor": S.person(d.doctor), "purpose": d.purpose, "scopes": d.scopes,
                     "granting_authority": d.granting_authority, "expires_at": d.expires_at,
                     "phone": d.doctor.phone} for d in docs],
    }


@router.get("/care-team")
def get_care_team(patient_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "careteam.view" if user.role != "caregiver" else "careteam.contact")
    team = care_team(db, acc.patient)
    team["patient"] = S.person(acc.patient.user)
    if acc.kind != "owner":  # others see names/roles, not other people's grant details
        team["caregivers"] = [{"label": c["label"], "caregiver": c["caregiver"], "status": c["status"]}
                              for c in team["caregivers"] if c["status"] == "active"]
    recent = db.execute(select(Notification).where(
        Notification.user_id == user.id, Notification.patient_id == patient_id, Notification.channel == "in_app",
        Notification.category.in_(("caregiver_update", "prescription_change", "doctor_instruction", "new_prescription")))
        .order_by(Notification.created_at.desc()).limit(8)).scalars()
    team["recent_updates"] = [S.notification(n) for n in recent]
    return team


# ---------------- medicines ----------------
@router.get("/medications")
def medications(patient_id: str, q: str | None = None, bucket: str | None = None,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "medications.view")
    items = db.execute(select(PrescriptionItem).where(PrescriptionItem.patient_id == patient_id)
                       .order_by(PrescriptionItem.updated_at.desc())).scalars().all()
    out = [S.item(it) for it in items if it.versions and it.status != "draft"]
    if q:
        ql = q.lower()
        out = [m for m in out if ql in m["current"]["generic_name"].lower()
               or ql in (m["current"]["brand_name"] or "").lower()]
    if bucket:
        out = [m for m in out if m["bucket"] == bucket]
    return out


@router.get("/medications/{item_id}")
def medication_detail(patient_id: str, item_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "medications.view")
    it = db.get(PrescriptionItem, item_id)
    if not it or it.patient_id != patient_id:
        raise not_found("Medicine")
    out = S.item(it, full=True)
    events = db.execute(select(MedicationEvent).where(MedicationEvent.item_id == it.id)
                        .order_by(MedicationEvent.created_at.desc()).limit(60)).scalars()
    out["events"] = [{"id": e.id, "kind": e.kind, "reason": e.reason, "note": e.note, "at": e.created_at,
                      "source": e.source} for e in events]
    a = db.execute(select(InteractionAssessment).where(InteractionAssessment.item_id == it.id)
                   .order_by(InteractionAssessment.created_at.desc()).limit(1)).scalar_one_or_none()
    out["interaction"] = interactions.serialize(a, "doctor" if user.role == "doctor" else "patient") if a else None
    audit.record(db, action="read:medication", resource_type="prescription_item", resource_id=it.id,
                 patient_id=patient_id, user=user, auth_context=acc.kind)
    db.commit()
    return out


@router.get("/doses")
def doses(patient_id: str, day: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "medications.view")
    tz = ZoneInfo(acc.patient.timezone)
    d = datetime.fromisoformat(day).date() if day else utcnow().astimezone(tz).date()
    lo = datetime.combine(d, time.min, tzinfo=tz)
    rows = db.execute(select(DoseOccurrence).where(
        DoseOccurrence.patient_id == patient_id, DoseOccurrence.scheduled_at >= lo,
        DoseOccurrence.scheduled_at < lo + timedelta(days=1)).order_by(DoseOccurrence.scheduled_at)).scalars()
    return [S.dose(o) for o in rows]


class DoseResponse(BaseModel):
    kind: str = Field(pattern="^(taken_reported|missed_reported|skipped|snoozed|cant_take)$")
    reason: str | None = None
    note: str | None = Field(default=None, max_length=500)
    snooze_minutes: int | None = None
    idempotency_key: str | None = Field(default=None, max_length=80)


@router.post("/doses/{occ_id}/respond")
def respond(patient_id: str, occ_id: str, body: DoseResponse, user: User = Depends(current_user),
            db: Session = Depends(get_db)):
    scope = "medications.view" if user.role == "patient" else "checkin.submit"
    if user.role not in ("patient", "caregiver"):
        raise forbidden("Only the patient or an authorised caregiver can respond to a dose")
    acc = authorize_patient(db, user, patient_id, scope)
    occ = db.get(DoseOccurrence, occ_id)
    if not occ or occ.patient_id != patient_id:
        raise not_found("Dose")
    ev = medication_schedule.record_response(
        db, occ, kind=body.kind, actor_id=user.id, reason=body.reason, note=body.note,
        snooze_minutes=body.snooze_minutes, idempotency_key=body.idempotency_key,
        source="patient_app" if acc.kind == "owner" else "caregiver_checkin")
    escalation.evaluate(db, patient_id)
    if body.kind == "cant_take" and body.reason in ("cost", "unavailable"):
        escalation.open_support_case(db, patient_id, "affordability" if body.reason == "cost" else "medicine_unavailable",
                                     f"Patient could not take {occ.version.generic_name}: {body.reason}"
                                     + (f" — {body.note}" if body.note else ""), created_by=user.id)
    realtime.queue(db, [u.id for u in users_with_access(db, patient_id, "medications.view")], "doses", patient_id, occ.id)
    db.commit()
    return {"event_id": ev.id, "dose": S.dose(occ)}


@router.get("/adherence")
def adherence(patient_id: str, days: int = Query(7, ge=1, le=90), user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "medications.view")
    return medication_schedule.adherence_summary(db, patient_id, days)


# ---------------- health overview & records ----------------
@router.get("/health")
def health(patient_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view", audit_read=True)
    p = acc.patient
    dx = db.execute(select(Diagnosis).where(Diagnosis.patient_id == p.id)).scalars()
    al = db.execute(select(Allergy).where(Allergy.patient_id == p.id)).scalars()
    current = [S.item(i) for i in db.execute(select(PrescriptionItem).where(
        PrescriptionItem.patient_id == p.id, PrescriptionItem.status.in_(("active", "on_hold")))).scalars()]
    return {
        "conditions": {"status": p.condition_status, "items": [
            {"id": d.id, "name": d.name, "code": d.code, "status": d.status, "onset_date": d.onset_date,
             "provenance": d.provenance} for d in dx]},
        "allergies": {"status": p.allergy_status, "items": [
            {"id": a.id, "substance": a.substance, "reaction": a.reaction, "severity": a.severity,
             "status": a.status, "provenance": a.provenance} for a in al]},
        "current_medicines": current,
        "emergency": {"contact_name": p.emergency_contact_name, "contact_phone": p.emergency_contact_phone,
                      "relation": p.emergency_contact_relation, "blood_group": p.blood_group,
                      "shareable": p.emergency_info_shareable},
        "demographics": {"date_of_birth": p.date_of_birth, "sex": p.sex, "mrn": p.mrn},
        "patient_reported": p.patient_reported_notes,
    }


class SelfReported(BaseModel):
    patient_reported_notes: str | None = Field(default=None, max_length=2000)
    allergy_status: str | None = Field(default=None, pattern="^(unknown|none_known|has_allergies)$")
    emergency_contact_name: str | None = Field(default=None, max_length=160)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)
    emergency_contact_relation: str | None = Field(default=None, max_length=60)
    emergency_info_shareable: bool | None = None
    blood_group: str | None = Field(default=None, max_length=8)
    new_allergy: str | None = Field(default=None, max_length=120)
    new_allergy_reaction: str | None = Field(default=None, max_length=200)


@router.patch("/health/self-reported")
def update_self_reported(patient_id: str, body: SelfReported, user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view")
    if acc.kind != "owner":
        raise forbidden("Only the patient can update self-reported details")
    p = acc.patient
    data = body.model_dump(exclude_none=True)
    if body.new_allergy:
        db.add(Allergy(patient_id=p.id, substance=body.new_allergy, substance_ingredient=body.new_allergy.lower(),
                       reaction=body.new_allergy_reaction, severity="unknown", provenance="patient_reported",
                       recorded_by=user.id))
        p.allergy_status = "has_allergies"
    for k in ("new_allergy", "new_allergy_reaction"):
        data.pop(k, None)
    for k, v in data.items():
        setattr(p, k, v)
    audit.record(db, action="self_reported_update", resource_type="patient", resource_id=p.id, patient_id=p.id,
                 user=user, auth_context="owner")
    db.commit()
    return {"status": "saved"}


@router.get("/records")
def records(patient_id: str, record_type: str | None = None, doctor_id: str | None = None,
            organization: str | None = None, medication: str | None = None, date_from: str | None = None,
            date_to: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view", audit_read=True)
    qy = select(MedicalRecord).where(MedicalRecord.patient_id == patient_id)
    if record_type:
        qy = qy.where(MedicalRecord.record_type == record_type)
    if doctor_id:
        qy = qy.where(MedicalRecord.doctor_user_id == doctor_id)
    if date_from:
        qy = qy.where(MedicalRecord.occurred_at >= datetime.fromisoformat(date_from).replace(tzinfo=ZoneInfo("UTC")))
    if date_to:
        qy = qy.where(MedicalRecord.occurred_at < datetime.fromisoformat(date_to).replace(tzinfo=ZoneInfo("UTC")) + timedelta(days=1))
    rows = [S.record(r) for r in db.execute(qy.order_by(MedicalRecord.occurred_at.desc())).scalars()]
    if organization:
        rows = [r for r in rows if r["organization"] and organization.lower() in r["organization"].lower()]
    if medication:
        rows = [r for r in rows if any(medication.lower() in m.lower() for m in r["medication_names"])]
    corrections = db.execute(select(RecordCorrectionRequest).where(RecordCorrectionRequest.patient_id == patient_id)).scalars()
    return {"records": rows, "access": acc.kind,
            "corrections": [{"id": c.id, "record_id": c.record_id, "status": c.status, "description": c.description,
                             "reviewer_note": c.reviewer_note, "created_at": c.created_at} for c in corrections]}


class CorrectionIn(BaseModel):
    description: str = Field(min_length=10, max_length=2000)


@router.post("/records/{record_id}/correction")
def request_correction(patient_id: str, record_id: str, body: CorrectionIn, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view")
    if acc.kind != "owner":
        raise forbidden("Only the patient can request a correction")
    rec = db.get(MedicalRecord, record_id)
    if not rec or rec.patient_id != patient_id:
        raise not_found("Record")
    c = RecordCorrectionRequest(patient_id=patient_id, record_id=record_id, requested_by=user.id,
                                description=body.description)
    db.add(c)
    if rec.doctor_user_id:
        notifications.notify(db, db.get(User, rec.doctor_user_id), category="important_alert",
                             title="Record correction requested", body=f"{acc.patient.user.full_name}: {rec.title}",
                             patient_id=patient_id, link=f"/doctor/patients/{patient_id}")
    audit.record(db, action="record_correction_requested", resource_type="medical_record", resource_id=record_id,
                 patient_id=patient_id, user=user)
    db.commit()
    return {"id": c.id, "status": c.status}


# ---------------- documents ----------------
@router.get("/documents")
def list_documents(patient_id: str, q: str | None = None, category: str | None = None,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "records.view")
    qy = select(UploadedDocument).where(UploadedDocument.patient_id == patient_id)
    if category:
        qy = qy.where(UploadedDocument.category == category)
    if q:
        qy = qy.where(or_(UploadedDocument.title.ilike(f"%{q}%"), UploadedDocument.original_filename.ilike(f"%{q}%")))
    docs = db.execute(qy.order_by(UploadedDocument.created_at.desc())).scalars().all()
    ext = {e.document_id: e for e in db.execute(select(OCRExtraction).where(OCRExtraction.patient_id == patient_id)).scalars()}
    return [{**S.document(d), "ocr_status": ext[d.id].status if d.id in ext else None,
             "ocr_id": ext[d.id].id if d.id in ext else None} for d in docs]


@router.post("/documents")
async def upload_document(patient_id: str, request: Request, file: UploadFile = File(...),
                          title: str = Form(..., min_length=2, max_length=200),
                          category: str = Form(..., pattern="^(prescription|lab_report|discharge_summary|other)$"),
                          user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view")
    if acc.kind not in ("owner", "doctor_access"):
        raise forbidden("Only the patient or their doctor can upload records")
    data = await file.read()
    try:
        mime = storage.validate_upload(data, file.content_type or "")
    except storage.UploadRejected as e:
        audit.record(db, action="record_upload_rejected", resource_type="document", patient_id=patient_id, user=user,
                     reason=str(e), outcome="failed", commit=True)
        raise HTTPException(400, str(e))
    doc_id = new_id()
    key = f"patients/{patient_id}/{doc_id}"
    backend = storage.put(key, data, mime)
    doc = UploadedDocument(id=doc_id, patient_id=patient_id, uploaded_by=user.id, category=category, title=title,
                           original_filename=(file.filename or "upload")[:255], mime_type=mime, size_bytes=len(data),
                           sha256=storage.sha256(data), storage_backend=backend, storage_key=key)
    db.add(doc)
    db.flush()
    extraction = None
    if category == "prescription":
        extraction = ocr.extract(db, doc, data)
    else:
        db.add(MedicalRecord(patient_id=patient_id, record_type="lab_report" if category == "lab_report" else
                             "discharge_summary" if category == "discharge_summary" else "consultation",
                             title=title, occurred_at=utcnow(), document_id=doc.id, created_by=user.id,
                             provenance="patient_reported" if acc.kind == "owner" else "clinician_verified"))
    audit.record(db, action="record_upload", resource_type="document", resource_id=doc.id, patient_id=patient_id,
                 user=user, auth_context=acc.kind, ip_address=client_ip(request))
    for u in users_with_access(db, patient_id, "records.view"):
        if u.id != user.id and u.role != "doctor":
            notifications.notify(db, u, category="record_uploaded", title="New record uploaded", body=title,
                                 patient_id=patient_id, dedupe_key=f"doc:{doc.id}:{u.id}")
    db.commit()
    return {"document": S.document(doc), "ocr": ocr_out(extraction) if extraction else None}


@router.get("/documents/{doc_id}/download")
def download(patient_id: str, doc_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view")
    doc = db.get(UploadedDocument, doc_id)
    if not doc or doc.patient_id != patient_id:
        raise not_found("Document")
    audit.record(db, action="record_download", resource_type="document", resource_id=doc.id, patient_id=patient_id,
                 user=user, auth_context=acc.kind)
    db.commit()
    if doc.storage_backend == "s3":
        return {"url": storage.presigned_url(doc.storage_key, doc.original_filename), "expires_in": 300}
    data = storage.get_bytes(doc.storage_backend, doc.storage_key)
    return Response(data, media_type=doc.mime_type,
                    headers={"Content-Disposition": f'inline; filename="{doc.original_filename}"',
                             "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


# ---------------- OCR review (patient side) ----------------
def ocr_out(e: OCRExtraction) -> dict:
    return {"id": e.id, "document_id": e.document_id, "engine": e.engine, "quality": e.quality,
            "raw_text": e.raw_text, "extracted": e.extracted, "patient_corrected": e.patient_corrected,
            "confidence": e.confidence, "uncertain_fields": e.uncertain_fields,
            "possible_duplicates": e.possible_duplicates, "status": e.status, "history": e.history,
            "verified_at": e.verified_at, "verification_note": e.verification_note,
            "resulting_prescription_id": e.resulting_prescription_id,
            "label": "UNVERIFIED — extracted or typed details must be verified by a doctor before use."}


@router.get("/ocr/{ext_id}")
def get_ocr(patient_id: str, ext_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "records.view")
    e = db.get(OCRExtraction, ext_id)
    if not e or e.patient_id != patient_id:
        raise not_found("Extraction")
    return ocr_out(e)


class OcrReview(BaseModel):
    patient_name: str | None = Field(default=None, max_length=160)
    doctor_name: str | None = Field(default=None, max_length=160)
    date: str | None = Field(default=None, max_length=20)
    instructions: str | None = Field(default=None, max_length=2000)
    medications: list[dict] = Field(min_length=1, max_length=20)
    submit_for_verification: bool = True


@router.post("/ocr/{ext_id}/review")
def review_ocr(patient_id: str, ext_id: str, body: OcrReview, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "records.view")
    if acc.kind != "owner":
        raise forbidden("Only the patient can review their uploaded prescription")
    e = db.get(OCRExtraction, ext_id)
    if not e or e.patient_id != patient_id or e.status not in ("extracted", "patient_reviewed"):
        raise bad_request("This extraction can no longer be edited")
    meds = []
    for m in body.medications:
        clean = {k: str(m.get(k, ""))[:120] for k in ocr.MED_FIELDS}
        if not clean["name"]:
            raise bad_request("Each medicine needs a name")
        meds.append(clean)
    e.patient_corrected = {**body.model_dump(exclude={"medications", "submit_for_verification"}), "medications": meds}
    e.possible_duplicates = ocr.find_duplicates(db, e.document) + ocr.medication_duplicates(db, patient_id,
                                                                                           [m["name"] for m in meds])
    e.reviewed_by_patient_at = utcnow()
    if body.submit_for_verification:
        e.status = "patient_reviewed"
        e.history = [*e.history, {"at": utcnow().isoformat(), "event": "submitted_for_verification", "by": user.id}]
        for u in users_with_access(db, patient_id, "records.view"):
            if u.role == "doctor":
                notifications.notify(db, u, category="important_alert", title="Prescription to verify",
                                     body=f"{acc.patient.user.full_name} uploaded a prescription for verification.",
                                     patient_id=patient_id, link="/doctor/verification", dedupe_key=f"ocr:{e.id}:{u.id}")
    audit.record(db, action="ocr_patient_review", resource_type="ocr_extraction", resource_id=e.id,
                 patient_id=patient_id, user=user)
    db.commit()
    return ocr_out(e)


# ---------------- instructions, messages, refills, concerns ----------------
@router.get("/instructions")
def list_instructions(patient_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "instructions.view")
    rows = db.execute(select(FollowUpInstruction).where(FollowUpInstruction.patient_id == patient_id)
                      .order_by(FollowUpInstruction.created_at.desc())).scalars().all()
    if acc.kind == "caregiver_grant":
        rows = [r for r in rows if r.audience in ("caregiver", "both")]
    elif acc.kind == "owner":
        rows = [r for r in rows if r.audience in ("patient", "both")]
    return [S.instruction(r) for r in rows]


@router.post("/instructions/{ins_id}/acknowledge")
def acknowledge(patient_id: str, ins_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "instructions.view")
    f = db.get(FollowUpInstruction, ins_id)
    if not f or f.patient_id != patient_id:
        raise not_found("Instruction")
    if not f.acknowledged_at:
        f.acknowledged_at, f.acknowledged_by = utcnow(), user.id
        notifications.notify(db, f.author, category="caregiver_update", title="Instruction acknowledged",
                             body=f.title, patient_id=patient_id, dedupe_key=f"ack:{f.id}")
    db.commit()
    return S.instruction(f)


@router.get("/messages")
def list_messages(patient_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "messages.patient" if user.role != "patient" else "medications.view")
    qy = select(Message).where(Message.patient_id == patient_id)
    if acc.kind != "owner":
        qy = qy.where(or_(Message.sender_user_id == user.id, Message.recipient_user_id == user.id))
    rows = db.execute(qy.order_by(Message.created_at)).scalars().all()
    for m in rows:
        if m.recipient_user_id == user.id and not m.read_at:
            m.read_at = utcnow()
    db.commit()
    return [{"id": m.id, "kind": m.kind, "body": m.body, "created_at": m.created_at, "sender": S.person(m.sender),
             "recipient_id": m.recipient_user_id, "read_at": m.read_at} for m in rows]


class MessageIn(BaseModel):
    recipient_id: str
    body: str = Field(min_length=1, max_length=4000)
    kind: str = Field(default="message", pattern="^(message|consultation_note|follow_up_note|report_request|appointment_reminder)$")


@router.post("/messages")
def send_message(patient_id: str, body: MessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "messages.patient" if user.role != "patient" else "medications.view")
    recipient = db.get(User, body.recipient_id)
    allowed = {u.id for u in users_with_access(db, patient_id, "messages.patient")} | {acc.patient.user_id}
    if not recipient or recipient.id not in allowed or recipient.id == user.id:
        raise forbidden("You can only message members of this patient's care team")
    if body.kind != "message" and user.role != "doctor":
        raise forbidden("Only doctors can send clinical notes")
    m = Message(patient_id=patient_id, sender_user_id=user.id, recipient_user_id=recipient.id, body=body.body,
                kind=body.kind)
    db.add(m)
    if body.kind == "consultation_note":
        db.add(MedicalRecord(patient_id=patient_id, record_type="consultation", title="Consultation note",
                             summary=body.body[:2000], occurred_at=utcnow(), doctor_user_id=user.id,
                             created_by=user.id, provenance="clinician_verified"))
    notifications.notify(db, recipient, category="doctor_instruction" if user.role == "doctor" else "caregiver_update",
                         title=f"New message from {user.full_name}", body="Open IMPULSE to read it.",
                         patient_id=patient_id, link="/messages")
    audit.record(db, action=f"message:{body.kind}", resource_type="message", patient_id=patient_id, user=user,
                 auth_context=acc.kind)
    realtime.queue(db, [recipient.id], "messages", patient_id)
    db.commit()
    return {"id": m.id}


class RefillIn(BaseModel):
    item_id: str
    pharmacy_id: str | None = None
    note: str | None = Field(default=None, max_length=500)


@router.get("/refills")
def list_refills(patient_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "medications.view")
    rows = db.execute(select(RefillRequest).where(RefillRequest.patient_id == patient_id)
                      .order_by(RefillRequest.created_at.desc())).scalars()
    return [{"id": r.id, "item_id": r.item_id, "status": r.status, "note": r.note, "pharmacy_id": r.pharmacy_id,
             "created_at": r.created_at, "review_note": r.review_note} for r in rows]


@router.post("/refills")
def request_refill(patient_id: str, body: RefillIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "medications.view")
    if acc.kind not in ("owner", "caregiver_grant"):
        raise forbidden()
    it = db.get(PrescriptionItem, body.item_id)
    if not it or it.patient_id != patient_id or it.status not in ("active", "on_hold"):
        raise bad_request("Refills can only be requested for current medicines")
    r = RefillRequest(patient_id=patient_id, item_id=it.id, pharmacy_id=body.pharmacy_id, requested_by=user.id,
                      note=body.note)
    db.add(r)
    if it.prescription.prescriber:
        notifications.notify(db, it.prescription.prescriber, category="important_alert", title="Refill requested",
                             body=f"{acc.patient.user.full_name} requested a refill.", patient_id=patient_id,
                             link="/doctor/prescriptions")
    audit.record(db, action="refill_requested", resource_type="refill", patient_id=patient_id, user=user)
    db.commit()
    return {"id": r.id, "status": r.status,
            "note": "Your doctor must approve refills. IMPULSE does not authorise refills automatically."}


class ConcernIn(BaseModel):
    kind: str = Field(pattern="^(affordability|medicine_unavailable|refill_difficulty|concerning_symptoms|general)$")
    description: str = Field(min_length=5, max_length=2000)


@router.post("/concerns")
def report_concern(patient_id: str, body: ConcernIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "concerns.report" if user.role == "caregiver" else "medications.view")
    priority = "high" if body.kind == "concerning_symptoms" else "normal"
    case = escalation.open_support_case(db, patient_id, body.kind, body.description, priority, created_by=user.id)
    db.commit()
    return {"case_id": case.id, "assigned": bool(case.assigned_to),
            "message": "Thank you. A care coordinator will review this during support hours. "
                       "If this is an emergency, call 112 now."}


# ---------------- emergency ----------------
class EmergencyIn(BaseModel):
    alert_type: str = Field(pattern="^(call_services|emergency_contact|care_team)$")
    share_info: bool = False
    share_location: bool = False
    location: dict | None = None


@router.post("/emergency")
def emergency(patient_id: str, body: EmergencyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = authorize_patient(db, user, patient_id, "medications.view" if user.role == "patient" else "careteam.contact")
    p = acc.patient
    recipients = []
    if body.alert_type == "call_services":
        recipients.append({"who": "Local emergency services (112)", "channel": "phone_call_by_user",
                           "delivery_status": "user_initiated_call"})
    if body.alert_type in ("emergency_contact", "care_team"):
        for u in users_with_access(db, patient_id, "careteam.contact" if body.alert_type == "care_team" else "adherence.notify"):
            if u.id == user.id or u.role == "patient":
                continue
            ns = notifications.notify(db, u, category="emergency", priority="emergency", title="Emergency alert",
                                      body=f"{p.user.full_name} triggered an emergency alert. Please contact them now.",
                                      patient_id=patient_id, link=f"/emergency/{patient_id}")
            recipients.append({"who": u.full_name, "role": u.role,
                               "channels": [{"channel": n.channel, "delivery_status": n.delivery_status} for n in ns]})
        if body.alert_type == "emergency_contact" and p.emergency_contact_phone:
            from app.integrations import aws_services

            res = aws_services.send_sms(p.emergency_contact_phone, f"IMPULSE emergency alert from {p.user.full_name}. "
                                                                   "Please contact them now.")
            recipients.append({"who": p.emergency_contact_name, "channel": "sms",
                               "delivery_status": {"ok": "sent"}.get(res.state, res.state)})
    alert = EmergencyAlert(patient_id=patient_id, triggered_by=user.id, alert_type=body.alert_type,
                           recipients=recipients, info_shared=body.share_info and p.emergency_info_shareable,
                           location_shared=body.share_location, location=body.location if body.share_location else None,
                           actions=[{"at": utcnow().isoformat(), "action": "triggered", "by": user.id}])
    db.add(alert)
    db.flush()
    if body.alert_type != "call_services":
        escalation.open_support_case(db, patient_id, "emergency_alert", "Emergency alert triggered from the app",
                                     "urgent", created_by=user.id)
    audit.record(db, action="emergency_alert", resource_type="emergency_alert", resource_id=alert.id,
                 patient_id=patient_id, user=user, reason=body.alert_type)
    db.commit()
    return {"id": alert.id, "recipients": recipients,
            "limitations": "IMPULSE does not dispatch emergency responders. For immediate help call 112. "
                           "Care-team alerts are reviewed by people during support hours only."}


@router.post("/emergency/{alert_id}/acknowledge")
def ack_emergency(patient_id: str, alert_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_patient(db, user, patient_id, "careteam.contact" if user.role != "patient" else "medications.view")
    a = db.get(EmergencyAlert, alert_id)
    if not a or a.patient_id != patient_id:
        raise not_found("Alert")
    a.acknowledged_by, a.acknowledged_at = user.id, utcnow()
    a.actions = [*a.actions, {"at": utcnow().isoformat(), "action": "acknowledged", "by": user.id}]
    db.commit()
    return {"status": "acknowledged"}
