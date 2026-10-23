import re
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

DOSE_UNITS = ("tablet", "capsule", "mcg", "mg", "g", "kg", "ml", "IU", "drop", "puff", "unit", "patch", "sachet",
              "application")
ROUTES = ("oral", "sublingual", "topical", "inhaled", "nasal", "ophthalmic", "otic", "subcutaneous",
          "intramuscular", "intravenous", "rectal", "transdermal")
FORMS = ("tablet", "capsule", "syrup", "suspension", "injection", "inhaler", "drops", "cream", "ointment",
         "patch", "powder", "solution", "spray")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class MedicationOrder(BaseModel):
    catalogue_id: str | None = None
    generic_name: str = Field(min_length=2, max_length=160)
    brand_name: str | None = Field(default=None, max_length=160)
    strength: str = Field(min_length=1, max_length=40)
    dosage_form: str
    dose_amount: float = Field(gt=0, le=10000)
    dose_unit: str
    route: str
    frequency_label: str = Field(min_length=2, max_length=80)
    times_of_day: list[str] = Field(default_factory=list, max_length=8)
    days_of_week: list[int] | None = None
    interval_days: int = Field(default=1, ge=1, le=30)
    timezone: str = "Asia/Kolkata"
    is_prn: bool = False
    indication: str | None = Field(default=None, max_length=200)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    start_date: date
    end_date: date | None = None
    quantity: str | None = Field(default=None, max_length=40)
    refills_allowed: int = Field(default=0, ge=0, le=12)
    refill_instructions: str | None = Field(default=None, max_length=300)
    food_instructions: str | None = Field(default=None, max_length=200)
    special_instructions: str | None = Field(default=None, max_length=2000)
    missed_dose_guidance: str | None = Field(default=None, max_length=1000)

    @field_validator("dosage_form")
    @classmethod
    def _form(cls, v):
        if v not in FORMS:
            raise ValueError(f"Choose a dosage form from: {', '.join(FORMS)}")
        return v

    @field_validator("dose_unit")
    @classmethod
    def _unit(cls, v):
        if v not in DOSE_UNITS:
            raise ValueError(f"Unsupported dose unit. Use one of: {', '.join(DOSE_UNITS)}")
        return v

    @field_validator("route")
    @classmethod
    def _route(cls, v):
        if v not in ROUTES:
            raise ValueError(f"Unsupported route. Use one of: {', '.join(ROUTES)}")
        return v

    @field_validator("times_of_day")
    @classmethod
    def _times(cls, v):
        for t in v:
            if not _HHMM.match(t):
                raise ValueError(f"'{t}' is not a valid 24-hour time (HH:MM)")
        if len(set(v)) != len(v):
            raise ValueError("Dose times must be unique")
        return sorted(v)

    @field_validator("days_of_week")
    @classmethod
    def _days(cls, v):
        if v is not None and (not v or any(d < 0 or d > 6 for d in v)):
            raise ValueError("Days of week must be between 0 (Mon) and 6 (Sun)")
        return sorted(set(v)) if v else v

    @model_validator(mode="after")
    def _consistency(self):
        if not self.is_prn and not self.times_of_day:
            raise ValueError("Scheduled medicines need at least one dose time (or mark as 'as needed')")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class PrescriptionCreate(BaseModel):
    patient_id: str
    items: list[MedicationOrder] = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)
    publish: bool = True


class PrescriptionEdit(BaseModel):
    order: MedicationOrder
    change_reason: str = Field(min_length=3, max_length=300)
    expected_lock_version: int
    effective_from: datetime | None = None


class Discontinue(BaseModel):
    effective_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=300)
    special_instructions: str | None = Field(default=None, max_length=2000)
    follow_up: str | None = Field(default=None, max_length=1000)
    expected_lock_version: int


class StatusChange(BaseModel):
    status: str
    reason: str = Field(min_length=3, max_length=300)
    expected_lock_version: int
