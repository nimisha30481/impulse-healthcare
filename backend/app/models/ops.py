"""Notifications, follow-ups, messages, escalation & support cases, emergencies, audit, sync."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, UTCDateTime


class Notification(IdMixin, TimestampMixin, Base):
    """One message to one user on one channel. `dedupe_key` is unique so the reminder engine
    can never send the same reminder twice. Bodies must not contain sensitive clinical detail
    for insecure channels (SMS/email) - those get a generic text and a link into the app."""

    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"))
    # new_prescription | prescription_change | appointment_reminder | doctor_instruction |
    # record_uploaded | caregiver_update | important_alert | medication_reminder | security | emergency
    category: Mapped[str] = mapped_column(String(32), index=True)
    priority: Mapped[str] = mapped_column(String(12), default="normal")  # low | normal | high | emergency
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    channel: Mapped[str] = mapped_column(String(12), default="in_app")  # in_app | email | sms | push
    dedupe_key: Mapped[str | None] = mapped_column(String(160), unique=True)
    # created | sent | delivered | failed | not_configured (provider missing; nothing was sent)
    delivery_status: Mapped[str] = mapped_column(String(16), default="created")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300))
    provider_message_id: Mapped[str | None] = mapped_column(String(120))
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class FollowUpInstruction(IdMixin, TimestampMixin, Base):
    """Doctor instructions and follow-up recommendations. A recommended follow-up is NOT an
    appointment; `appointment_id` is only set once something is actually booked."""

    __tablename__ = "follow_up_instructions"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="instruction")  # instruction | follow_up
    audience: Mapped[str] = mapped_column(String(16), default="patient")  # patient | caregiver | both
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(12), default="normal")
    attachments: Mapped[list] = mapped_column(JSON, default=list)  # uploaded_document ids
    expires_on: Mapped[date | None] = mapped_column(Date)
    requires_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    delivery_status: Mapped[str] = mapped_column(String(16), default="delivered_in_app")
    due_date: Mapped[date | None] = mapped_column(Date)  # follow-ups: recommended date
    timeframe: Mapped[str | None] = mapped_column(String(60))  # follow-ups: "in 2 weeks"
    appointment_request: Mapped[bool] = mapped_column(Boolean, default=False)
    appointment_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | completed | cancelled
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    linked_instruction_ids: Mapped[list] = mapped_column(JSON, default=list)

    author = relationship("User", foreign_keys=[author_user_id])


class Message(IdMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # message | consultation_note | follow_up_note | report_request | appointment_reminder
    kind: Mapped[str] = mapped_column(String(24), default="message")
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    sender = relationship("User", foreign_keys=[sender_user_id])


class EscalationCase(IdMixin, TimestampMixin, Base):
    """Automated escalation trail for one patient + trigger. Moves through the stages of the
    configured EscalationPolicy. Silence is never treated as an emergency."""

    __tablename__ = "escalation_cases"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    # missed_medication | missed_checkin | concerning_symptoms | emergency_alert
    trigger: Mapped[str] = mapped_column(String(24))
    stage: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | resolved
    consecutive_unconfirmed: Mapped[int] = mapped_column(Integer, default=0)
    history: Mapped[list] = mapped_column(JSON, default=list)
    support_case_id: Mapped[str | None] = mapped_column(ForeignKey("support_cases.id"))


class SupportCase(IdMixin, TimestampMixin, Base):
    __tablename__ = "support_cases"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    # missed_medication | missed_checkin | concerning_symptoms | emergency_alert |
    # affordability | medicine_unavailable | refill_difficulty | general
    case_type: Mapped[str] = mapped_column(String(24), index=True)
    priority: Mapped[str] = mapped_column(String(12), default="normal")  # low | normal | high | urgent
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open | in_progress | escalated | resolved
    reason: Mapped[str] = mapped_column(Text)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    history: Mapped[list] = mapped_column(JSON, default=list)

    attempts: Mapped[list["ContactAttempt"]] = relationship(back_populates="case", order_by="ContactAttempt.created_at")
    notes: Mapped[list["CaseNote"]] = relationship(back_populates="case", order_by="CaseNote.created_at")
    patient = relationship("PatientProfile")
    assignee = relationship("User", foreign_keys=[assigned_to])


class ContactAttempt(IdMixin, TimestampMixin, Base):
    __tablename__ = "contact_attempts"

    case_id: Mapped[str] = mapped_column(ForeignKey("support_cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    method: Mapped[str] = mapped_column(String(16))  # phone | sms | email | in_app
    target: Mapped[str] = mapped_column(String(24))  # patient | caregiver | emergency_contact
    outcome: Mapped[str] = mapped_column(String(24))  # reached | no_answer | voicemail | wrong_number
    note: Mapped[str | None] = mapped_column(Text)

    case: Mapped[SupportCase] = relationship(back_populates="attempts")


class CaseNote(IdMixin, TimestampMixin, Base):
    __tablename__ = "case_notes"

    case_id: Mapped[str] = mapped_column(ForeignKey("support_cases.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)

    case: Mapped[SupportCase] = relationship(back_populates="notes")
    author = relationship("User")


class EmergencyAlert(IdMixin, TimestampMixin, Base):
    __tablename__ = "emergency_alerts"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    triggered_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    alert_type: Mapped[str] = mapped_column(String(24))  # call_services | emergency_contact | care_team
    recipients: Mapped[list] = mapped_column(JSON, default=list)  # [{who, channel, delivery_status}]
    location_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[dict | None] = mapped_column(JSON)
    info_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    actions: Mapped[list] = mapped_column(JSON, default=list)


class ClinicalBrief(IdMixin, TimestampMixin, Base):
    __tablename__ = "clinical_briefs"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    generated_for: Mapped[str] = mapped_column(ForeignKey("users.id"))
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"))
    content: Mapped[dict] = mapped_column(JSON)  # sections, each with source record ids
    ai_summary: Mapped[str | None] = mapped_column(Text)  # Bedrock narrative, labelled unverified
    ai_status: Mapped[str] = mapped_column(String(24), default="not_configured")


class AuditLog(IdMixin, Base):
    """Tamper-evident: each row stores the hash of the previous row (hash chain).
    Contains identifiers and context only - never full medical records or secrets."""

    __tablename__ = "audit_logs"

    seq: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    user_role: Mapped[str | None] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(48), index=True)
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    patient_id: Mapped[str | None] = mapped_column(String(36), index=True)
    version_ref: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(String(300))
    auth_context: Mapped[str | None] = mapped_column(String(80))  # e.g. owner | caregiver_grant | doctor_access | break_glass
    source: Mapped[str] = mapped_column(String(24), default="api")
    ip_address: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16), default="success")  # success | denied | failed
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class GuestAccessLog(IdMixin, TimestampMixin, Base):
    """Every guest (unregistered) doctor lookup by Patient Access ID, granted or not."""

    __tablename__ = "guest_access_logs"

    ip_address: Mapped[str | None] = mapped_column(String(64), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(300))
    access_id_entered: Mapped[str] = mapped_column(String(32))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patient_profiles.id", ondelete="SET NULL"), index=True)
    doctor_name: Mapped[str | None] = mapped_column(String(160))
    doctor_license: Mapped[str | None] = mapped_column(String(80))
    hospital: Mapped[str | None] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(String(16))  # granted | invalid | expired | rate_limited


class FhirSyncRecord(IdMixin, TimestampMixin, Base):
    """Tracks PostgreSQL -> HealthLake synchronisation. PostgreSQL is the source of truth;
    HealthLake is a one-way FHIR replica for interoperability."""

    __tablename__ = "fhir_sync_records"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(40))
    local_id: Mapped[str] = mapped_column(String(36))
    fhir_id: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | synced | failed | not_configured
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300))


class IdempotencyRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(120), unique=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    response: Mapped[dict] = mapped_column(JSON, default=dict)
