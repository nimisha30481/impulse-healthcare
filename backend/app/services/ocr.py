"""Prescription upload -> validate -> quality check -> OCR -> medication identification ->
patient review -> doctor verification -> structured prescription -> schedule activation.

Everything before doctor verification is labelled UNVERIFIED and can never create reminders.
"""
import io

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations import aws_services
from app.models import OCRExtraction, PrescriptionItem, UploadedDocument
from app.models.base import utcnow

FIELDS = ("patient_name", "doctor_name", "date", "instructions")
MED_FIELDS = ("name", "strength", "dose", "route", "frequency", "duration")


def quality_check(data: bytes, mime: str) -> dict:
    if mime == "application/pdf":
        return {"kind": "pdf", "warnings": []}
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        w, h = img.size
    except Exception:  # noqa: BLE001
        return {"kind": "image", "warnings": ["The image could not be read"], "readable": False}
    warnings = []
    if min(w, h) < 600:
        warnings.append("Low resolution - text may be misread. A clearer photo is recommended.")
    gray = img.convert("L").resize((64, 64))
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    if mean < 60:
        warnings.append("The photo looks very dark.")
    if max(pixels) - min(pixels) < 60:
        warnings.append("Low contrast - the text may be faint or blurred.")
    return {"kind": "image", "width": w, "height": h, "warnings": warnings, "readable": True}


def extract(db: Session, doc: UploadedDocument, data: bytes) -> OCRExtraction:
    quality = quality_check(data, doc.mime_type)
    ext = OCRExtraction(document_id=doc.id, patient_id=doc.patient_id, quality=quality, engine="manual",
                        extracted={"medications": []}, uncertain_fields=[], history=[])
    text_res = aws_services.textract_text(data) if quality.get("readable", True) else aws_services.Result("failed")
    if text_res.state == "ok":
        ext.raw_text = text_res.data
        ext.engine = "textract"
        ext.confidence = text_res.meta.get("confidence")
        meds_res = aws_services.comprehend_medications(text_res.data)
        if meds_res.state == "ok":
            ext.engine = "textract+comprehend_medical"
            ext.extracted = {"medications": meds_res.data}
            ext.uncertain_fields = [
                f"medications[{i}].{k}" for i, m in enumerate(meds_res.data) for k in MED_FIELDS
                if m.get(f"{k}_confidence", m.get("confidence", 0)) < 0.8 or k not in m
            ]
    else:
        ext.history.append({"at": utcnow().isoformat(), "event": "ocr_unavailable",
                            "detail": "Automatic reading is not configured. Please type the prescription details."})
    ext.history = [*ext.history, {"at": utcnow().isoformat(), "event": "extracted", "engine": ext.engine}]
    ext.possible_duplicates = find_duplicates(db, doc)
    db.add(ext)
    db.flush()
    return ext


def find_duplicates(db: Session, doc: UploadedDocument) -> list[dict]:
    same = db.execute(
        select(UploadedDocument).where(
            UploadedDocument.patient_id == doc.patient_id,
            UploadedDocument.sha256 == doc.sha256,
            UploadedDocument.id != doc.id,
        )
    ).scalars().all()
    return [{"kind": "same_file", "document_id": d.id, "title": d.title, "uploaded_at": d.created_at.isoformat()}
            for d in same]


def medication_duplicates(db: Session, patient_id: str, names: list[str]) -> list[dict]:
    out = []
    active = db.execute(
        select(PrescriptionItem).where(PrescriptionItem.patient_id == patient_id,
                                       PrescriptionItem.status.in_(("active", "scheduled", "on_hold")))
    ).scalars()
    lower = {n.lower().strip() for n in names if n}
    for it in active:
        v = next((v for v in it.versions if v.version_no == it.current_version_no), None)
        if v and v.generic_name.lower() in lower:
            out.append({"kind": "already_active", "item_id": it.id, "name": v.generic_name})
    return out
