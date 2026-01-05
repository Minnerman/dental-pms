from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.appointment import AppointmentStatus
from app.schemas.actor import ActorOut
from app.schemas.patient import PatientSummary


class AppointmentCreate(BaseModel):
    patient_id: int
    clinician_user_id: Optional[int] = None
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus = AppointmentStatus.booked
    appointment_type: Optional[str] = None
    clinician: Optional[str] = None
    location: Optional[str] = None
    is_domiciliary: bool = False
    visit_address: Optional[str] = None


class AppointmentUpdate(BaseModel):
    clinician_user_id: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    appointment_type: Optional[str] = None
    clinician: Optional[str] = None
    location: Optional[str] = None
    is_domiciliary: Optional[bool] = None
    visit_address: Optional[str] = None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient: PatientSummary
    patient_has_alerts: bool = False
    clinician_user_id: Optional[int] = None
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    appointment_type: Optional[str] = None
    clinician: Optional[str] = None
    location: Optional[str] = None
    is_domiciliary: bool
    visit_address: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[ActorOut] = None
