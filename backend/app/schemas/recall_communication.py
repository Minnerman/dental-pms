from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.patient_recall_communication import (
    PatientRecallCommunicationChannel,
    PatientRecallCommunicationDirection,
    PatientRecallCommunicationStatus,
)


class RecallCommunicationCreate(BaseModel):
    channel: PatientRecallCommunicationChannel
    notes: str | None = Field(default=None, max_length=2000)
    outcome: str | None = Field(default=None, max_length=250)
    contacted_at: datetime | None = None
    other_detail: str | None = Field(default=None, max_length=120)

    @field_validator("notes", "outcome", "other_detail", mode="before")
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
        if self.channel == PatientRecallCommunicationChannel.other:
            if not self.other_detail:
                raise ValueError("Other detail is required when channel is other.")
        elif self.other_detail is not None:
            raise ValueError("Other detail is only allowed when channel is other.")
        return self


class RecallCommunicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    recall_id: int
    channel: PatientRecallCommunicationChannel
    direction: PatientRecallCommunicationDirection
    status: PatientRecallCommunicationStatus
    notes: str | None = None
    other_detail: str | None = None
    outcome: str | None = None
    contacted_at: datetime | None = None
    created_at: datetime
    created_by_user_id: int | None = None
