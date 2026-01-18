from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.appointment import AppointmentLocationType, AppointmentStatus


class UnmappedLegacyAppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    legacy_source: str | None = None
    legacy_id: str | None = None
    legacy_patient_code: str | None = None
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    appointment_type: str | None = None
    clinician: str | None = None
    location: str | None = None
    location_type: AppointmentLocationType
    is_domiciliary: bool
    created_at: datetime
    updated_at: datetime


class UnmappedLegacyAppointmentList(BaseModel):
    items: list[UnmappedLegacyAppointmentOut]
    total: int
    limit: int
    offset: int


class LegacyResolveRequest(BaseModel):
    patient_id: int
    notes: str | None = None


class LegacyResolveResponse(BaseModel):
    id: int
    patient_id: int
    legacy_source: str | None = None
    legacy_id: str | None = None
