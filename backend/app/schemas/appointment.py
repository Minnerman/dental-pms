from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.appointment import AppointmentStatus
from app.schemas.actor import ActorOut
from app.schemas.patient import PatientSummary


class AppointmentCreate(BaseModel):
    patient_id: int
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus = AppointmentStatus.booked
    clinician: Optional[str] = None
    location: Optional[str] = None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient: PatientSummary
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    clinician: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[ActorOut] = None
