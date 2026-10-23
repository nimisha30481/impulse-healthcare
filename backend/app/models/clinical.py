"""Medical history: encounters, diagnoses, allergies, timeline records, documents, OCR."""
from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, UTCDateTime

# Provenance of every clinical fact. Shown in the UI so imported/extracted/patient-reported data
# is never mistaken for clinician-verified data.
PROVENANCE = ("clinician_verified", "imported", "ocr_extracted", "patient_reported", "demo")


class Encounter(IdMixin, TimestampMixin, Base):
    __tablename__ = "encounters"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    doctor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("healthcare_organizations.id"))
    kind: Mapped[str] = mapped_column(String(24))  # consultation | hospital_visit | procedure | discharge
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    reason: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String(24), default="clinician_verified")


class Diagnosis(IdMixin, TimestampMixin, Base):
    __tablename__ = "diagnoses"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id"))
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(32))  # e.g. ICD-10 when documented
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | resolved | historical
    onset_date: Mapped[date | None] = mapped_column(Date)
    recorded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    provenance: Mapped[str] = mapped_column(String(24), default="clinician_verified")


class Allergy(IdMixin, TimestampMixin, Base):
    __tablename__ = "allergies"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    substance: Mapped[str] = mapped_column(String(120))
    substance_ingredient: Mapped[str | None] = mapped_column(String(120))  # normalised, lower-case
    reaction: Mapped[str | None] = mapped_column(String(200))
    severity: Mapped[str | None] = mapped_column(String(16))  # mild | moderate | severe | unknown
    status: Mapped[str] = mapped_column(String(16), default="active")
    recorded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    provenance: Mapped[str] = mapped_column(String(24), default="clinician_verified")


class MedicalRecord(IdMixin, TimestampMixin, Base):
    """One entry on the patient's chronological timeline. Never overwritten: corrections create
    an amendment that points back at the original via `amends_id`."""

    __tablename__ = "medical_records"
    __table_args__ = (Index("ix_record_patient_date", "patient_id", "occurred_at"),)

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"))
    # consultation | hospital_visit | diagnosis | prescription | lab_report | procedure |
    # discharge_summary | follow_up
    record_type: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    doctor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("healthcare_organizations.id"))
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id"))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("uploaded_documents.id"))
    medication_names: Mapped[list] = mapped_column(JSON, default=list)
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # structured values, e.g. lab results
    provenance: Mapped[str] = mapped_column(String(24), default="clinician_verified")
    status: Mapped[str] = mapped_column(String(16), default="current")  # current | amended | entered_in_error
    amends_id: Mapped[str | None] = mapped_column(ForeignKey("medical_records.id"))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    fhir_resource_id: Mapped[str | None] = mapped_column(String(64))

    doctor = relationship("User", foreign_keys=[doctor_user_id])
    organization = relationship("HealthcareOrganization")


class RecordCorrectionRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "record_correction_requests"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("medical_records.id"))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | accepted | declined
    reviewer_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    amendment_record_id: Mapped[str | None] = mapped_column(ForeignKey("medical_records.id"))


class UploadedDocument(IdMixin, TimestampMixin, Base):
    """Metadata only. File bytes live in private object storage (S3 or local private dir)."""

    __tablename__ = "uploaded_documents"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(24))  # prescription | lab_report | discharge_summary | other
    title: Mapped[str] = mapped_column(String(200))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_backend: Mapped[str] = mapped_column(String(8))  # s3 | local
    storage_key: Mapped[str] = mapped_column(String(400))
    scan_status: Mapped[str] = mapped_column(String(24), default="validated")  # validated | rejected | scan_pending
    is_demo: Mapped[bool] = mapped_column(default=False)


class OCRExtraction(IdMixin, TimestampMixin, Base):
    """Unverified output from OCR/medical NLP or manual transcription. Never activates a
    prescription by itself: a verified clinician must approve it first."""

    __tablename__ = "ocr_extractions"

    document_id: Mapped[str] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    engine: Mapped[str] = mapped_column(String(40))  # manual | demo
    quality: Mapped[dict] = mapped_column(JSON, default=dict)  # width, height, warnings
    raw_text: Mapped[str | None] = mapped_column(Text)
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)  # header fields + medications list
    confidence: Mapped[float | None] = mapped_column(Float)
    uncertain_fields: Mapped[list] = mapped_column(JSON, default=list)
    possible_duplicates: Mapped[list] = mapped_column(JSON, default=list)
    # extracted -> patient_reviewed -> verified | rejected
    status: Mapped[str] = mapped_column(String(20), default="extracted", index=True)
    patient_corrected: Mapped[dict | None] = mapped_column(JSON)
    reviewed_by_patient_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verification_note: Mapped[str | None] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSON, default=list)
    resulting_prescription_id: Mapped[str | None] = mapped_column(ForeignKey("prescriptions.id"))

    document: Mapped[UploadedDocument] = relationship()
