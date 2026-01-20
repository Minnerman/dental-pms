from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class R4Patient(BaseModel):
    patient_code: int = Field(..., ge=1)
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    title: str | None = None
    sex: str | None = None
    mobile_no: str | None = None
    email: str | None = None


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


class R4Treatment(BaseModel):
    treatment_code: int = Field(..., ge=1)
    description: str | None = None
    short_code: str | None = None
    default_time_minutes: int | None = None
    exam: bool = False
    patient_required: bool = False


class R4TreatmentPlan(BaseModel):
    patient_code: int = Field(..., ge=1)
    tp_number: int = Field(..., ge=1)
    plan_index: int | None = None
    is_master: bool = False
    is_current: bool = False
    is_accepted: bool = False
    creation_date: datetime | None = None
    acceptance_date: datetime | None = None
    completion_date: datetime | None = None
    status_code: int | None = None
    reason_id: int | None = None
    tp_group: int | None = None


class R4TreatmentPlanItem(BaseModel):
    patient_code: int = Field(..., ge=1)
    tp_number: int = Field(..., ge=1)
    tp_item: int = Field(..., ge=0)
    tp_item_key: int | None = None
    code_id: int | None = None
    tooth: int | None = None
    surface: int | None = None
    appointment_need_id: int | None = None
    completed: bool = False
    completed_date: datetime | None = None
    patient_cost: float | None = None
    dpb_cost: float | None = None
    discretionary_cost: float | None = None
    material: str | None = None
    arch_code: int | None = None


class R4TreatmentPlanReview(BaseModel):
    patient_code: int = Field(..., ge=1)
    tp_number: int = Field(..., ge=1)
    temporary_note: str | None = None
    reviewed: bool = False
    last_edit_user: str | None = None
    last_edit_date: datetime | None = None
