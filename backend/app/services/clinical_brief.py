"""Automatic clinical brief: a deterministic, source-linked summary of what is documented.

Every statement carries the ids of the records it came from. Missing and conflicting information
is listed explicitly. An optional Bedrock narrative is stored separately, labelled as
AI-generated and unverified, and is discarded if it cites anything not in the inputs.
The brief never diagnoses, prescribes or changes treatment.
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.integrations import aws_services
from app.models import (
    Allergy,
    Appointment,
    ClinicalBrief,
    Diagnosis,
    FollowUpInstruction,
    MedicalRecord,
    PatientProfile,
    PrescriptionItem,
    PrescriptionVersion,
    User,
)
from app.models.base import utcnow
from app.services.medication_schedule import adherence_summary


def generate(db: Session, doctor: User, patient: PatientProfile, appointment_id: str | None = None) -> ClinicalBrief:
    now = utcnow()
    sections: dict[str, dict] = {}
    missing: list[str] = []
    conflicts: list[dict] = []

    reason = None
    if appointment_id:
        appt = db.get(Appointment, appointment_id)
        if appt and appt.patient_id == patient.id and appt.reason:
            reason = {"text": appt.reason, "sources": [{"type": "appointment", "id": appt.id}]}
    if not reason:
        missing.append("Reason for visit was not documented")
    sections["reason_for_visit"] = {"title": "Reason for visit", "items": [reason] if reason else []}

    dx = db.execute(select(Diagnosis).where(Diagnosis.patient_id == patient.id)).scalars().all()
    sections["conditions"] = {"title": "Documented conditions", "items": [
        {"text": f"{d.name}" + (f" ({d.code})" if d.code else "") + f" — {d.status}",
         "provenance": d.provenance, "sources": [{"type": "diagnosis", "id": d.id}]} for d in dx]}
    if not dx:
        missing.append("No conditions documented" if patient.condition_status != "none_known"
                       else "Patient reports no known conditions")

    allergies = db.execute(select(Allergy).where(Allergy.patient_id == patient.id, Allergy.status == "active")).scalars().all()
    sections["allergies"] = {"title": "Known allergies", "items": [
        {"text": f"{a.substance}" + (f" — {a.reaction}" if a.reaction else "") + (f" ({a.severity})" if a.severity else ""),
         "provenance": a.provenance, "sources": [{"type": "allergy", "id": a.id}]} for a in allergies],
        "status": patient.allergy_status}
    if patient.allergy_status == "unknown":
        missing.append("Allergy status unknown — not the same as 'no allergies'")
    if patient.allergy_status == "none_known" and allergies:
        conflicts.append({"text": "Allergy status says 'none known' but allergy records exist",
                          "sources": [{"type": "allergy", "id": a.id} for a in allergies]})

    items = db.execute(select(PrescriptionItem).where(
        PrescriptionItem.patient_id == patient.id,
        PrescriptionItem.status.in_(("active", "on_hold", "scheduled")))).scalars().all()
    meds = []
    by_name: dict[str, list] = {}
    for it in items:
        v = next(v for v in it.versions if v.version_no == it.current_version_no)
        prescriber = it.prescription.prescriber.full_name if it.prescription.prescriber else "External provider"
        meds.append({"text": f"{v.generic_name} {v.strength} — {v.dose_amount:g} {v.dose_unit} {v.route}, "
                             f"{v.frequency_label} ({it.status.replace('_', ' ')}; prescriber: {prescriber})",
                     "sources": [{"type": "prescription_item", "id": it.id}]})
        by_name.setdefault(v.generic_name.lower(), []).append((it, prescriber))
    for name, group in by_name.items():
        if len(group) > 1:
            conflicts.append({"text": f"{name} is active on {len(group)} prescriptions "
                                      f"({', '.join(p for _, p in group)})",
                              "sources": [{"type": "prescription_item", "id": it.id} for it, _ in group]})
    sections["current_medications"] = {"title": "Current medications", "items": meds}
    if not meds:
        missing.append("No current medications recorded in DoseWISE")

    since = now - timedelta(days=90)
    changes = db.execute(select(PrescriptionVersion).join(PrescriptionItem).where(
        PrescriptionItem.patient_id == patient.id, PrescriptionVersion.created_at >= since,
        PrescriptionVersion.version_no > 1)).scalars().all()
    stopped = [it for it in db.execute(select(PrescriptionItem).where(
        PrescriptionItem.patient_id == patient.id, PrescriptionItem.status == "discontinued")).scalars()
        if it.discontinued_at and it.discontinued_at >= since]
    sections["recent_medication_changes"] = {"title": "Medication changes (90 days)", "items": [
        {"text": f"{v.generic_name}: version {v.version_no} — {v.change_reason}",
         "sources": [{"type": "prescription_item", "id": v.item_id}]} for v in changes] + [
        {"text": f"Discontinued: {next(v for v in it.versions if v.version_no == it.current_version_no).generic_name}"
                 f" — {it.discontinue_reason}", "sources": [{"type": "prescription_item", "id": it.id}]}
        for it in stopped]}

    records = db.execute(select(MedicalRecord).where(
        MedicalRecord.patient_id == patient.id, MedicalRecord.status == "current").order_by(
        MedicalRecord.occurred_at.desc())).scalars().all()
    consults = [r for r in records if r.record_type in ("consultation", "hospital_visit", "discharge_summary")][:5]
    labs = [r for r in records if r.record_type == "lab_report"][:5]
    history = [r for r in records if r.record_type in ("procedure", "diagnosis")][:5]
    fmt = lambda r: {"text": f"{r.occurred_at.date().isoformat()} · {r.title}" + (f" — {r.summary}" if r.summary else ""),  # noqa: E731
                     "provenance": r.provenance, "sources": [{"type": "medical_record", "id": r.id}]}
    sections["recent_consultations"] = {"title": "Recent consultations & visits", "items": [fmt(r) for r in consults]}
    sections["lab_findings"] = {"title": "Relevant lab reports", "items": [fmt(r) for r in labs]}
    sections["medical_history"] = {"title": "Relevant medical history", "items": [fmt(r) for r in history]}
    if not labs:
        missing.append("No lab reports on file")

    fus = db.execute(select(FollowUpInstruction).where(
        FollowUpInstruction.patient_id == patient.id, FollowUpInstruction.status == "open")).scalars().all()
    sections["outstanding_follow_ups"] = {"title": "Outstanding follow-ups", "items": [
        {"text": f"{f.title}" + (f" (due {f.due_date})" if f.due_date else "") +
                 (" — booked" if f.appointment_id else " — not yet booked" if f.kind == "follow_up" else ""),
         "sources": [{"type": "follow_up", "id": f.id}]} for f in fus]}

    adh = adherence_summary(db, patient.id, 30)
    adh_text = (f"30 days: {adh['scheduled']} scheduled · {adh['taken_reported']} reported taken · "
                f"{adh['missed_reported']} reported missed · {adh['unconfirmed']} unconfirmed (no response)")
    sections["adherence"] = {"title": "Adherence (self-reported)", "items": [
        {"text": adh_text, "sources": [{"type": "adherence_summary", "id": patient.id}]}]}
    if adh["scheduled"] and (adh["response_coverage"] or 0) < 0.5:
        missing.append("Fewer than half of scheduled doses have a response — adherence data is incomplete")

    content = {
        "generated_at": now.isoformat(),
        "label": "Automatically assembled from DoseWISE records. Verify against source records before clinical use.",
        "sections": sections,
        "missing_information": missing,
        "conflicts": conflicts,
        "uncertainty": [
            "Patient-reported and OCR-extracted items are marked by provenance and are not doctor-verified.",
            "Records held outside DoseWISE are not included.",
        ],
    }
    brief = ClinicalBrief(patient_id=patient.id, generated_for=doctor.id, appointment_id=appointment_id,
                          content=content)
    facts = [{"id": s["sources"][0]["id"], "section": key, "fact": s["text"]}
             for key, sec in sections.items() for s in sec["items"] if s.get("sources")]
    ai = aws_services.bedrock_summarize(facts) if facts else aws_services.Result("not_configured")
    brief.ai_status = ai.state
    if ai.state == "ok":
        brief.ai_summary = ai.data
    db.add(brief)
    db.flush()
    audit.record(db, action="clinical_brief_generated", resource_type="clinical_brief", resource_id=brief.id,
                 patient_id=patient.id, user=doctor, auth_context="doctor_access")
    return brief
