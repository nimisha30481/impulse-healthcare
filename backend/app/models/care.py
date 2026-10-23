"""Who may see or act on which patient's data: caregiver links, doctor access, consent, break-glass."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, UTCDateTime
from app.models.identity import PatientProfile, User

# Scopes a patient can grant to a caregiver. Caregivers can never prescribe, discontinue,
# edit diagnoses or clinical records, or grant permissions - there is no scope for those.
CAREGIVER_SCOPES = (
    "medications.view",
    "records.view",
    "adherence.notify",
    "appointments.view",
    "appointments.book",
    "checkin.submit",
    "concerns.report",
    "instructions.view",
    "messages.patient",
    "careteam.contact",
)

DOCTOR_SCOPES = ("clinical.read", "clinical.write", "prescribe")


class CareRelationship(IdMixin, TimestampMixin, Base):
    __tablename__ = "care_relationships"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    caregiver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    invite_contact: Mapped[str] = mapped_column(String(255))  # email or phone used for the invitation
    invite_token_hash: Mapped[str | None] = mapped_column(String(128), unique=True)
    relationship_label: Mapped[str] = mapped_column(String(60), default="Family member")
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    purpose: Mapped[str] = mapped_column(String(200), default="Support with medication and appointments")
    # invited -> accepted (identity confirmed, awaiting patient final authorisation) -> active
    # any -> revoked | expired | declined
    status: Mapped[str] = mapped_column(String(16), default="invited", index=True)
    is_legal_representative: Mapped[bool] = mapped_column(Boolean, default=False)  # future LAR workflow
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    authorized_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    revocation_reason: Mapped[str | None] = mapped_column(String(300))
    granted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    patient: Mapped[PatientProfile] = relationship()
    caregiver: Mapped[User | None] = relationship(foreign_keys=[caregiver_user_id])


class DoctorPatientAccess(IdMixin, TimestampMixin, Base):
    __tablename__ = "doctor_patient_access"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    doctor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scopes: Mapped[list] = mapped_column(JSON, default=lambda: list(DOCTOR_SCOPES))
    purpose: Mapped[str] = mapped_column(String(200), default="Ongoing treatment")
    # patient_grant | appointment | referral | organization
    granting_authority: Mapped[str] = mapped_column(String(32), default="patient_grant")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active | revoked | expired
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    revocation_reason: Mapped[str | None] = mapped_column(String(300))
    granted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    patient: Mapped[PatientProfile] = relationship()
    doctor: Mapped[User] = relationship(foreign_keys=[doctor_user_id])


class ConsentRecord(IdMixin, TimestampMixin, Base):
    """Append-only history of consent decisions (grants, revocations, data-sharing preferences)."""

    __tablename__ = "consent_records"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    subject_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))  # grant | revoke | expire | preference_change
    resource: Mapped[str] = mapped_column(String(40))  # care_relationship | doctor_access | data_sharing
    resource_id: Mapped[str | None] = mapped_column(String(36))
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text)


class BreakGlassAccess(IdMixin, TimestampMixin, Base):
    """Emergency access outside normal grants: justified, time-boxed, audited, reviewed afterwards."""

    __tablename__ = "break_glass_access"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    justification: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(40), default="clinical.read")
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    review_outcome: Mapped[str | None] = mapped_column(String(200))


class EscalationPolicy(IdMixin, TimestampMixin, Base):
    """Configurable follow-up rules. patient_id null = platform default."""

    __tablename__ = "escalation_policies"

    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), unique=True)
    follow_up_after_minutes: Mapped[int] = mapped_column(Integer, default=30)  # stage 2
    unconfirmed_after_minutes: Mapped[int] = mapped_column(Integer, default=120)
    checkin_after_consecutive: Mapped[int] = mapped_column(Integer, default=2)  # stage 3
    caregiver_after_consecutive: Mapped[int] = mapped_column(Integer, default=3)  # stage 4 (needs consent)
    case_after_consecutive: Mapped[int] = mapped_column(Integer, default=4)  # stage 5
    notify_caregiver_approved: Mapped[bool] = mapped_column(Boolean, default=False)  # patient-approved criterion
    create_case_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours: Mapped[dict] = mapped_column(JSON, default=lambda: {"start": "22:00", "end": "07:00"})
