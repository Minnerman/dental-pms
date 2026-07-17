from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.patient_recall import PatientRecallKind, PatientRecallStatus
from app.models.patient_recall_communication import PatientRecallCommunicationChannel


class RecallDashboardRow(BaseModel):
    id: int
    patient_id: int
    first_name: str
    last_name: str
    recall_kind: PatientRecallKind
    due_date: date
    status: PatientRecallStatus
    notes: str | None = None
    completed_at: datetime | None = None
    last_contacted_at: datetime | None = None
    last_contact_channel: PatientRecallCommunicationChannel | None = None
    last_contact_method: PatientRecallCommunicationChannel | None = None
    last_contact_note: str | None = None
    last_contact_other_detail: str | None = None
    last_contact_outcome: str | None = None


class RecallContactCreate(BaseModel):
    method: PatientRecallCommunicationChannel
    outcome: str | None = Field(default=None, max_length=250)
    note: str | None = Field(default=None, max_length=2000)
    contacted_at: datetime | None = None
    other_detail: str | None = Field(default=None, max_length=120)

    @field_validator("outcome", "note", "other_detail", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("contacted_at")
    @classmethod
    def reject_future_contact(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if normalized > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Contact time cannot be in the future.")
        return normalized

    @model_validator(mode="after")
    def validate_other_detail(self):
        if self.method == PatientRecallCommunicationChannel.other:
            if not self.other_detail:
                raise ValueError("Other detail is required when method is other.")
        elif self.other_detail is not None:
            raise ValueError("Other detail is only allowed when method is other.")
        return self


class RecallKpiRange(BaseModel):
    from_date: date
    to_date: date


class RecallKpiCounts(BaseModel):
    due: int
    overdue: int
    contacted: int
    booked: int
    declined: int


class RecallKpiRates(BaseModel):
    contacted_rate: float
    booked_rate: float


class RecallKpiOut(BaseModel):
    range: RecallKpiRange
    counts: RecallKpiCounts
    rates: RecallKpiRates
