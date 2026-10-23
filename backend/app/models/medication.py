"""Medicines, prescriptions (versioned), schedules, dose occurrences and append-only dose events."""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, UTCDateTime


class MedicationCatalogue(IdMixin, TimestampMixin, Base):
    __tablename__ = "medication_catalogue"
    __table_args__ = (UniqueConstraint("generic_name", "strength", "dosage_form", name="uq_catalogue_entry"),)

    generic_name: Mapped[str] = mapped_column(String(160), index=True)
    brand_names: Mapped[list] = mapped_column(JSON, default=list)
    strength: Mapped[str] = mapped_column(String(40))
    dosage_form: Mapped[str] = mapped_column(String(40))  # tablet | capsule | syrup | injection | inhaler ...
    routes: Mapped[list] = mapped_column(JSON, default=lambda: ["oral"])
    ingredients: Mapped[list] = mapped_column(JSON, default=list)  # normalised lower-case actives
    rxnorm_code: Mapped[str | None] = mapped_column(String(32))
    # Patient education. Only filled from a reviewed, attributable source; empty means the UI
    # says "reliable information is not available" instead of generating any.
    education: Mapped[dict] = mapped_column(JSON, default=dict)
    education_source: Mapped[str | None] = mapped_column(String(200))
    education_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    data_source: Mapped[str] = mapped_column(String(40), default="demo")


class Prescription(IdMixin, TimestampMixin, Base):
    """A prescribing event (one order sheet). Each medicine on it is a PrescriptionItem."""

    __tablename__ = "prescriptions"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    prescriber_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id"))
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("healthcare_organizations.id"))
    # impulse | external_provider | ocr_verified
    source: Mapped[str] = mapped_column(String(24), default="impulse")
    notes: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    items: Mapped[list["PrescriptionItem"]] = relationship(back_populates="prescription")
    prescriber = relationship("User", foreign_keys=[prescriber_user_id])


ITEM_STATUSES = (
    "draft",
    "pending_verification",
    "scheduled",
    "active",
    "on_hold",
    "completed",
    "discontinued",
    "superseded",
)

# Validated status transitions (anything not listed is rejected).
ITEM_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_verification", "active", "scheduled", "discontinued"},
    "pending_verification": {"active", "scheduled", "discontinued"},
    "scheduled": {"active", "discontinued", "on_hold"},
    "active": {"on_hold", "completed", "discontinued", "superseded"},
    "on_hold": {"active", "discontinued"},
    "completed": set(),
    "discontinued": set(),
    "superseded": set(),
}


class PrescriptionItem(IdMixin, TimestampMixin, Base):
    """One medicine for one patient. Its clinical content lives in immutable versions."""

    __tablename__ = "prescription_items"

    prescription_id: Mapped[str] = mapped_column(ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    catalogue_id: Mapped[str | None] = mapped_column(ForeignKey("medication_catalogue.id"))
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    current_version_no: Mapped[int] = mapped_column(Integer, default=1)
    # optimistic concurrency: edits must quote the version they were based on
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
    discontinued_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    discontinue_reason: Mapped[str | None] = mapped_column(String(300))
    discontinue_effective: Mapped[datetime | None] = mapped_column(UTCDateTime())
    discontinue_instructions: Mapped[str | None] = mapped_column(Text)
    discontinue_follow_up: Mapped[str | None] = mapped_column(Text)
    hold_reason: Mapped[str | None] = mapped_column(String(300))
    replaced_by_item_id: Mapped[str | None] = mapped_column(ForeignKey("prescription_items.id"))

    prescription: Mapped[Prescription] = relationship(back_populates="items")
    catalogue: Mapped[MedicationCatalogue | None] = relationship()
    versions: Mapped[list["PrescriptionVersion"]] = relationship(
        back_populates="item", order_by="PrescriptionVersion.version_no", foreign_keys="PrescriptionVersion.item_id"
    )


class PrescriptionVersion(IdMixin, TimestampMixin, Base):
    """Immutable. Editing a prescription publishes a new version; old ones are kept forever."""

    __tablename__ = "prescription_versions"
    __table_args__ = (UniqueConstraint("item_id", "version_no", name="uq_item_version"),)

    item_id: Mapped[str] = mapped_column(ForeignKey("prescription_items.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="current")  # current | superseded | scheduled
    generic_name: Mapped[str] = mapped_column(String(160))
    brand_name: Mapped[str | None] = mapped_column(String(160))
    strength: Mapped[str] = mapped_column(String(40))
    dosage_form: Mapped[str] = mapped_column(String(40))
    dose_amount: Mapped[float] = mapped_column(Float)
    dose_unit: Mapped[str] = mapped_column(String(24))
    route: Mapped[str] = mapped_column(String(24))
    frequency_label: Mapped[str] = mapped_column(String(80))  # human readable, e.g. "Twice daily"
    indication: Mapped[str | None] = mapped_column(String(200))  # documented reason, never inferred
    duration_days: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[str | None] = mapped_column(String(40))
    refills_allowed: Mapped[int] = mapped_column(Integer, default=0)
    refill_instructions: Mapped[str | None] = mapped_column(String(300))
    food_instructions: Mapped[str | None] = mapped_column(String(200))
    special_instructions: Mapped[str | None] = mapped_column(Text)
    missed_dose_guidance: Mapped[str | None] = mapped_column(Text)  # only from prescriber/verified source
    effective_from: Mapped[datetime] = mapped_column(UTCDateTime())
    change_reason: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    is_prn: Mapped[bool] = mapped_column(Boolean, default=False)  # as-needed: no reminders

    item: Mapped[PrescriptionItem] = relationship(back_populates="versions", foreign_keys=[item_id])
    schedule: Mapped["MedicationSchedule | None"] = relationship(back_populates="version", uselist=False)
    author = relationship("User", foreign_keys=[created_by])


class MedicationSchedule(IdMixin, TimestampMixin, Base):
    """When doses are due for one prescription version. Supports multiple times per day,
    specific weekdays, and every-N-days patterns."""

    __tablename__ = "medication_schedules"

    version_id: Mapped[str] = mapped_column(ForeignKey("prescription_versions.id", ondelete="CASCADE"), unique=True)
    times_of_day: Mapped[list] = mapped_column(JSON, default=list)  # ["08:00", "20:00"] local time
    days_of_week: Mapped[list | None] = mapped_column(JSON)  # [0..6] Mon=0; null = every day
    interval_days: Mapped[int] = mapped_column(Integer, default=1)  # 1 = daily, 2 = alternate days
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")

    version: Mapped[PrescriptionVersion] = relationship(back_populates="schedule")


DOSE_STATUSES = (
    "upcoming",
    "due",
    "taken_reported",
    "missed_reported",
    "snoozed",
    "skipped",
    "unconfirmed",
    "awaiting_confirmation",
    "cancelled",
)


class DoseOccurrence(IdMixin, TimestampMixin, Base):
    __tablename__ = "dose_occurrences"
    __table_args__ = (UniqueConstraint("item_id", "scheduled_at", name="uq_dose_slot"),)

    item_id: Mapped[str] = mapped_column(ForeignKey("prescription_items.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("prescription_versions.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    status: Mapped[str] = mapped_column(String(24), default="upcoming", index=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reminder_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    followup_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    responded_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    escalation_evaluated: Mapped[bool] = mapped_column(Boolean, default=False)

    item: Mapped[PrescriptionItem] = relationship()
    version: Mapped[PrescriptionVersion] = relationship()


class MedicationEvent(IdMixin, TimestampMixin, Base):
    """Append-only dose history. Rows are never updated or deleted."""

    __tablename__ = "medication_events"

    occurrence_id: Mapped[str | None] = mapped_column(ForeignKey("dose_occurrences.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("prescription_items.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str | None] = mapped_column(ForeignKey("prescription_versions.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    # reminder_sent | followup_sent | taken_reported | missed_reported | snoozed | skipped |
    # cant_take | marked_unconfirmed | cancelled_by_change | caregiver_checkin
    kind: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(String(40))  # unwell | unavailable | forgot | side_effects | cost | other
    note: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    source: Mapped[str] = mapped_column(String(24), default="patient_app")


class InteractionAssessment(IdMixin, TimestampMixin, Base):
    __tablename__ = "interaction_assessments"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("prescription_items.id"))
    version_id: Mapped[str | None] = mapped_column(ForeignKey("prescription_versions.id"))
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    # completed | unavailable | failed | partial
    status: Mapped[str] = mapped_column(String(16))
    knowledge_source: Mapped[str | None] = mapped_column(String(120))
    knowledge_source_version: Mapped[str | None] = mapped_column(String(80))
    checks_performed: Mapped[list] = mapped_column(JSON, default=list)
    checks_unavailable: Mapped[list] = mapped_column(JSON, default=list)
    medications_considered: Mapped[list] = mapped_column(JSON, default=list)
    orchestrator: Mapped[str] = mapped_column(String(24), default="local")  # local | step_functions
    execution_ref: Mapped[str | None] = mapped_column(String(300))
    error: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    review_decision: Mapped[str | None] = mapped_column(String(40))  # acknowledged | will_modify | override
    review_note: Mapped[str | None] = mapped_column(Text)

    alerts: Mapped[list["InteractionAlert"]] = relationship(back_populates="assessment")


class InteractionAlert(IdMixin, TimestampMixin, Base):
    __tablename__ = "interaction_alerts"

    assessment_id: Mapped[str] = mapped_column(ForeignKey("interaction_assessments.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # drug_drug | duplicate_therapy | allergy
    severity: Mapped[str] = mapped_column(String(16))  # major | moderate | minor | info
    medicines: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    consequences: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(160))
    source_updated_at: Mapped[str | None] = mapped_column(String(40))
    review_guidance: Mapped[str | None] = mapped_column(Text)

    assessment: Mapped[InteractionAssessment] = relationship(back_populates="alerts")


class RefillRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "refill_requests"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("prescription_items.id"))
    pharmacy_id: Mapped[str | None] = mapped_column(ForeignKey("healthcare_organizations.id"))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    # requested -> approved | declined -> (sent_to_pharmacy) -> fulfilled
    status: Mapped[str] = mapped_column(String(20), default="requested")
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    review_note: Mapped[str | None] = mapped_column(Text)
