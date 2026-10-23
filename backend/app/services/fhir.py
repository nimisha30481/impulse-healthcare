"""FHIR R4 mapping + one-way sync to Amazon HealthLake.

Source of truth: the SQL database. HealthLake is a downstream replica for interoperability.
Direction: SQL -> HealthLake only. Conflicts: SQL wins; a changed content hash re-sends.
Failures stay in fhir_sync_records with status=failed and are retried (max 5) by the sync job.
"""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations import aws_services
from app.models import Allergy, Diagnosis, FhirSyncRecord, PatientProfile, PrescriptionItem

PROVENANCE_TAG = "https://impulse.example/fhir/provenance"


def _meta(provenance: str) -> dict:
    return {"tag": [{"system": PROVENANCE_TAG, "code": provenance}]}


def patient_resource(p: PatientProfile) -> dict:
    return {
        "resourceType": "Patient",
        "id": p.id,
        "identifier": [{"system": "https://impulse.example/mrn", "value": p.mrn}],
        "name": [{"text": p.user.full_name}],
        "birthDate": p.date_of_birth.isoformat() if p.date_of_birth else None,
        "meta": _meta("clinician_verified"),
    }


def medication_request(item: PrescriptionItem) -> dict:
    v = next(v for v in item.versions if v.version_no == item.current_version_no)
    status = {"active": "active", "on_hold": "on-hold", "completed": "completed", "discontinued": "stopped",
              "draft": "draft", "scheduled": "active", "pending_verification": "draft",
              "superseded": "cancelled"}[item.status]
    return {
        "resourceType": "MedicationRequest",
        "id": item.id,
        "status": status,
        "intent": "order",
        "subject": {"reference": f"Patient/{item.patient_id}"},
        "medicationCodeableConcept": {"text": f"{v.generic_name} {v.strength}"},
        "authoredOn": v.created_at.isoformat(),
        "dosageInstruction": [{
            "text": f"{v.dose_amount:g} {v.dose_unit} {v.route} {v.frequency_label}",
            "route": {"text": v.route},
            "timing": {"repeat": {"timeOfDay": [f"{t}:00" for t in (v.schedule.times_of_day if v.schedule else [])]}},
        }],
        "note": [{"text": f"DoseWISE version {v.version_no}"}],
        "meta": _meta("clinician_verified"),
    }


def allergy_resource(a: Allergy) -> dict:
    return {
        "resourceType": "AllergyIntolerance",
        "id": a.id,
        "patient": {"reference": f"Patient/{a.patient_id}"},
        "code": {"text": a.substance},
        "reaction": [{"description": a.reaction}] if a.reaction else [],
        "clinicalStatus": {"coding": [{"code": "active" if a.status == "active" else "inactive"}]},
        "meta": _meta(a.provenance),
    }


def condition_resource(d: Diagnosis) -> dict:
    return {
        "resourceType": "Condition",
        "id": d.id,
        "subject": {"reference": f"Patient/{d.patient_id}"},
        "code": {"text": d.name, **({"coding": [{"code": d.code}]} if d.code else {})},
        "clinicalStatus": {"coding": [{"code": "active" if d.status == "active" else "resolved"}]},
        "meta": _meta(d.provenance),
    }


def resources_for(db: Session, patient: PatientProfile) -> list[dict]:
    out = [patient_resource(patient)]
    out += [medication_request(i) for i in db.execute(
        select(PrescriptionItem).where(PrescriptionItem.patient_id == patient.id)).scalars() if i.versions]
    out += [allergy_resource(a) for a in db.execute(select(Allergy).where(Allergy.patient_id == patient.id)).scalars()]
    out += [condition_resource(d) for d in db.execute(select(Diagnosis).where(Diagnosis.patient_id == patient.id)).scalars()]
    return out


def sync_patient(db: Session, patient: PatientProfile) -> dict:
    summary = {"synced": 0, "unchanged": 0, "failed": 0, "not_configured": 0}
    for res in resources_for(db, patient):
        res = {k: v for k, v in res.items() if v is not None}
        h = hashlib.sha256(json.dumps(res, sort_keys=True, default=str).encode()).hexdigest()
        rec = db.execute(select(FhirSyncRecord).where(
            FhirSyncRecord.resource_type == res["resourceType"], FhirSyncRecord.local_id == res["id"])).scalar_one_or_none()
        if rec and rec.content_hash == h and rec.status == "synced":
            summary["unchanged"] += 1
            continue
        if not rec:
            rec = FhirSyncRecord(patient_id=patient.id, resource_type=res["resourceType"], local_id=res["id"],
                                 content_hash=h)
            db.add(rec)
        if rec.attempts >= 5 and rec.status == "failed" and rec.content_hash == h:
            summary["failed"] += 1
            continue
        rec.content_hash = h
        rec.attempts += 1
        result = aws_services.healthlake_put(res)
        rec.status = {"ok": "synced", "not_configured": "not_configured"}.get(result.state, "failed")
        rec.last_error = result.error
        if result.state == "ok":
            rec.fhir_id = result.data or res["id"]
        summary[{"synced": "synced", "not_configured": "not_configured"}.get(rec.status, "failed")] += 1
    return summary
