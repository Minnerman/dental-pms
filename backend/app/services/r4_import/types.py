from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class R4Patient(BaseModel):
    patient_code: int = Field(..., ge=1)
    first_name: str
    last_name: str
    date_of_birth: date | None = None


class R4Appointment(BaseModel):
    appointment_id: str | None = None
    patient_code: int | None = None
    starts_at: datetime
    ends_at: datetime
    clinician: str | None = None
    location: str | None = None
    location_type: str | None = None
    appointment_type: str | None = None
    status: str | None = None
