from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.models.appointment import AppointmentLocationType, AppointmentStatus
from app.schemas.actor import ActorOut
from app.schemas.patient import PatientSummary


class AppointmentCreate(BaseModel):
    patient_id: int
    clinician_user_id: Optional[int] = None
    starts_at: datetime
    ends_at: datetime
    allow_outside_hours: Optional[bool] = False
    status: AppointmentStatus = AppointmentStatus.booked
    appointment_type: Optional[str] = None
    clinician: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[AppointmentLocationType] = None
    location_text: Optional[str] = None
    is_domiciliary: Optional[bool] = None
    visit_address: Optional[str] = None


class AppointmentUpdate(BaseModel):
    clinician_user_id: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    allow_outside_hours: Optional[bool] = False
    status: Optional[AppointmentStatus] = None
    appointment_type: Optional[str] = None
    clinician: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[AppointmentLocationType] = None
    location_text: Optional[str] = None
    is_domiciliary: Optional[bool] = None
    visit_address: Optional[str] = None
    cancel_reason: Optional[str] = None


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
    location_type: AppointmentLocationType
    location_text: Optional[str] = None
    is_domiciliary: bool
    visit_address: Optional[str] = None
    cancel_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[ActorOut] = None


class DiarySnapshotColumnOut(BaseModel):
    key: str
    label: str
    kind: Literal["chair", "clinician"]
    appointment_count: int
    clinician_user_id: Optional[int] = None
    location: Optional[str] = None
    location_type: Optional[AppointmentLocationType] = None


class DiarySnapshotFlagsOut(BaseModel):
    has_notes: bool = False
    has_patient_alerts: bool = False
    has_cancel_reason: bool = False


class DiarySnapshotAppointmentOut(BaseModel):
    id: int
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    status: AppointmentStatus
    appointment_type: Optional[str] = None
    patient_id: Optional[int] = None
    patient_display_name: str
    clinician_user_id: Optional[int] = None
    clinician_label: Optional[str] = None
    location: Optional[str] = None
    location_type: AppointmentLocationType
    is_domiciliary: bool = False
    column_key: str
    flags: DiarySnapshotFlagsOut


class DiarySnapshotOut(BaseModel):
    date: date
    view: Literal["day", "week"]
    range_start: date
    range_end: date
    columns: list[DiarySnapshotColumnOut]
    time_blocks: list[str]
    appointments: list[DiarySnapshotAppointmentOut]
    summary: dict[str, int]
