"""Doctor availability, bookable slots, temporary holds and appointments."""
from datetime import date, datetime

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, UTCDateTime


class DoctorAvailability(IdMixin, TimestampMixin, Base):
    """Recurring weekly working hours. Slots are materialised from these rules."""

    __tablename__ = "doctor_availability"

    doctor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("healthcare_organizations.id"))
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = Monday
    start_time: Mapped[str] = mapped_column(String(5))  # "09:00" local
    end_time: Mapped[str] = mapped_column(String(5))
    slot_minutes: Mapped[int] = mapped_column(Integer, default=20)
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    consultation_type: Mapped[str] = mapped_column(String(16), default="in_person")  # in_person | video
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")


class DoctorLeave(IdMixin, TimestampMixin, Base):
    __tablename__ = "doctor_leave"

    doctor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(200))


class AvailabilitySlot(IdMixin, TimestampMixin, Base):
    __tablename__ = "availability_slots"
    __table_args__ = (UniqueConstraint("doctor_user_id", "starts_at", name="uq_doctor_slot"),)

    doctor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("healthcare_organizations.id"))
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime())
    consultation_type: Mapped[str] = mapped_column(String(16), default="in_person")
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    # booked + held must never exceed capacity; enforced with a conditional UPDATE
    booked_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | blocked
    block_reason: Mapped[str | None] = mapped_column(String(200))

    organization = relationship("HealthcareOrganization")


class SlotHold(IdMixin, TimestampMixin, Base):
    __tablename__ = "slot_holds"

    slot_id: Mapped[str] = mapped_column(ForeignKey("availability_slots.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id"))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(16), default="held")  # held | converted | released | expired


class Appointment(IdMixin, TimestampMixin, Base):
    __tablename__ = "appointments"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    doctor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    slot_id: Mapped[str | None] = mapped_column(ForeignKey("availability_slots.id"))
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("healthcare_organizations.id"))
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime())
    consultation_type: Mapped[str] = mapped_column(String(16), default="in_person")
    # confirmed | cancelled | completed | no_show | rescheduled
    status: Mapped[str] = mapped_column(String(16), default="confirmed", index=True)
    reason: Mapped[str | None] = mapped_column(String(300))
    booked_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    cancelled_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    rescheduled_from_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"))
    follow_up_id: Mapped[str | None] = mapped_column(ForeignKey("follow_up_instructions.id"))
    history: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)

    doctor = relationship("User", foreign_keys=[doctor_user_id])
    organization = relationship("HealthcareOrganization")
    patient = relationship("PatientProfile")
