from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.patient_recall_communication import (
    PatientRecallCommunicationChannel,
    PatientRecallCommunicationDirection,
    PatientRecallCommunicationStatus,
)


class RecallCommunicationCreate(BaseModel):
    channel: PatientRecallCommunicationChannel
    notes: str | None = None


class RecallCommunicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    recall_id: int
    channel: PatientRecallCommunicationChannel
    direction: PatientRecallCommunicationDirection
    status: PatientRecallCommunicationStatus
    notes: str | None = None
    created_at: datetime
    created_by_user_id: int | None = None
