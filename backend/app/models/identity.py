from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, UTCDateTime

ROLES = ("patient", "doctor", "caregiver", "support", "admin")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    password_hash: Mapped[str | None] = mapped_column(String(255))  # null for Cognito-managed users
    cognito_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(16), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    preferred_name: Mapped[str | None] = mapped_column(String(80))
    avatar_color: Mapped[str] = mapped_column(String(16), default="#0f766e")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes: Mapped[list | None] = mapped_column(JSON)  # argon2 hashes
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # language, theme, text_size, timezone, country, state, date_format, units, notification prefs
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    patient_profile: Mapped["PatientProfile | None"] = relationship(back_populates="user", uselist=False)
    doctor_profile: Mapped["DoctorProfile | None"] = relationship(
        back_populates="user", uselist=False, foreign_keys="DoctorProfile.user_id"
    )
    caregiver_profile: Mapped["CaregiverProfile | None"] = relationship(back_populates="user", uselist=False)
    support_profile: Mapped["SupportProfile | None"] = relationship(back_populates="user", uselist=False)


class PatientProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "patient_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    mrn: Mapped[str] = mapped_column(String(32), unique=True)  # DoseWISE patient identifier
    # Shareable Patient Access ID (services/access_ids.py); regenerating it revokes the old one.
    access_id: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)
    access_id_created_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(24))
    blood_group: Mapped[str | None] = mapped_column(String(8))
    # Allergy knowledge state: unknown | none_known | has_allergies. Missing data is NOT "no allergies".
    allergy_status: Mapped[str] = mapped_column(String(16), default="unknown")
    condition_status: Mapped[str] = mapped_column(String(16), default="unknown")
    emergency_contact_name: Mapped[str | None] = mapped_column(String(160))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(32))
    emergency_contact_relation: Mapped[str | None] = mapped_column(String(60))
    emergency_info_shareable: Mapped[bool] = mapped_column(Boolean, default=False)
    patient_reported_notes: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")

    user: Mapped[User] = relationship(back_populates="patient_profile")


class DoctorProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    speciality: Mapped[str] = mapped_column(String(80))
    registration_number: Mapped[str] = mapped_column(String(64))
    registration_council: Mapped[str | None] = mapped_column(String(120))
    # pending | verified | rejected. Only verified doctors may use clinical endpoints.
    verification_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("healthcare_organizations.id"))
    bio: Mapped[str | None] = mapped_column(Text)
    consultation_types: Mapped[list] = mapped_column(JSON, default=lambda: ["in_person"])
    languages: Mapped[list] = mapped_column(JSON, default=lambda: ["English"])

    user: Mapped[User] = relationship(back_populates="doctor_profile", foreign_keys=[user_id])
    organization: Mapped["HealthcareOrganization | None"] = relationship()


class CaregiverProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "caregiver_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    relationship_note: Mapped[str | None] = mapped_column(String(120))

    user: Mapped[User] = relationship(back_populates="caregiver_profile")


class SupportProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "support_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    team: Mapped[str] = mapped_column(String(80), default="Care coordination")
    on_duty: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="support_profile")


class HealthcareOrganization(IdMixin, TimestampMixin, Base):
    __tablename__ = "healthcare_organizations"
    __table_args__ = (Index("ix_org_kind_city", "kind", "city"),)

    kind: Mapped[str] = mapped_column(String(16))  # hospital | clinic | pharmacy | laboratory
    name: Mapped[str] = mapped_column(String(200), index=True)
    address: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(32))
    opening_hours: Mapped[str | None] = mapped_column(String(160))
    departments: Mapped[list] = mapped_column(JSON, default=list)
    services: Mapped[list] = mapped_column(JSON, default=list)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    # verified directory data vs. demonstration content
    data_source: Mapped[str] = mapped_column(String(32), default="demo")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class UserSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    mfa_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    trusted_device: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthToken(IdMixin, TimestampMixin, Base):
    """Single-use tokens for email verification, password reset and caregiver invitations."""

    __tablename__ = "auth_tokens"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(24))  # verify_email | reset_password
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class SecurityEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "security_events"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(40))  # login_success | login_failed | mfa_enabled | ...
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
