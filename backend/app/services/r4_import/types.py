from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class R4Patient(BaseModel):
    patient_code: int = Field(..., ge=1)
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    nhs_number: str | None = None
    title: str | None = None
    sex: str | None = None
    phone: str | None = None
    mobile_no: str | None = None
    email: str | None = None
    postcode: str | None = None


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


class R4AppointmentRecord(BaseModel):
    appointment_id: int = Field(..., ge=1)
    patient_code: int | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    duration_minutes: int | None = None
    clinician_code: int | None = None
    status: str | None = None
    cancelled: bool | None = None
    clinic_code: int | None = None
    treatment_code: int | None = None
    appointment_type: str | None = None
    notes: str | None = None
    appt_flag: int | None = None


class R4Treatment(BaseModel):
    treatment_code: int = Field(..., ge=1)
    description: str | None = None
    short_code: str | None = None
    default_time_minutes: int | None = None
    exam: bool = False
    patient_required: bool = False


class R4TreatmentTransaction(BaseModel):
    transaction_id: int = Field(..., ge=1)
    patient_code: int = Field(..., ge=1)
    performed_at: datetime
    treatment_code: int | None = None
    trans_code: int | None = None
    patient_cost: float | None = None
    dpb_cost: float | None = None
    recorded_by: int | None = None
    user_code: int | None = None
    tp_number: int | None = None
    tp_item: int | None = None


class R4User(BaseModel):
    user_code: int = Field(..., ge=1)
    full_name: str | None = None
    title: str | None = None
    forename: str | None = None
    surname: str | None = None
    initials: str | None = None
    is_current: bool = False
    role: str | None = None


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


class R4ToothSystem(BaseModel):
    tooth_system_id: int = Field(..., ge=1)
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_default: bool = False


class R4ToothSurface(BaseModel):
    tooth_id: int = Field(..., ge=1)
    surface_no: int = Field(..., ge=0)
    label: str | None = None
    short_label: str | None = None
    sort_order: int | None = None


class R4ChartHealingAction(BaseModel):
    action_id: int = Field(..., ge=1)
    patient_code: int | None = None
    appointment_need_id: int | None = None
    tp_number: int | None = None
    tp_item: int | None = None
    code_id: int | None = None
    action_date: datetime | None = None
    action_type: str | None = None
    tooth: int | None = None
    surface: int | None = None
    status: str | None = None
    notes: str | None = None
    user_code: int | None = None


class R4BPEEntry(BaseModel):
    bpe_id: int | None = None
    patient_code: int | None = None
    recorded_at: datetime | None = None
    sextant_1: int | None = None
    sextant_2: int | None = None
    sextant_3: int | None = None
    sextant_4: int | None = None
    sextant_5: int | None = None
    sextant_6: int | None = None
    notes: str | None = None
    user_code: int | None = None


class R4BPEFurcation(BaseModel):
    furcation_id: int | None = None
    bpe_id: int | None = None
    patient_code: int | None = None
    tooth: int | None = None
    furcation: int | None = None
    sextant: int | None = None
    recorded_at: datetime | None = None
    notes: str | None = None
    user_code: int | None = None


class R4PerioProbe(BaseModel):
    trans_id: int | None = None
    patient_code: int | None = None
    tooth: int | None = None
    probing_point: int | None = None
    depth: int | None = None
    bleeding: int | None = None
    plaque: int | None = None
    recorded_at: datetime | None = None


class R4PerioPlaque(BaseModel):
    trans_id: int | None = None
    patient_code: int | None = None
    tooth: int | None = None
    plaque: int | None = None
    bleeding: int | None = None
    recorded_at: datetime | None = None


class R4PatientNote(BaseModel):
    patient_code: int | None = None
    note_number: int | None = None
    note_date: datetime | None = None
    note: str | None = None
    tooth: int | None = None
    surface: int | None = None
    category_number: int | None = None
    fixed_note_code: int | None = None
    user_code: int | None = None


class R4FixedNote(BaseModel):
    fixed_note_code: int = Field(..., ge=1)
    category_number: int | None = None
    description: str | None = None
    note: str | None = None
    tooth: int | None = None
    surface: int | None = None


class R4NoteCategory(BaseModel):
    category_number: int = Field(..., ge=0)
    description: str | None = None


class R4TreatmentNote(BaseModel):
    note_id: int = Field(..., ge=1)
    patient_code: int | None = None
    tp_number: int | None = None
    tp_item: int | None = None
    note: str | None = None
    note_date: datetime | None = None
    user_code: int | None = None


class R4TemporaryNote(BaseModel):
    patient_code: int = Field(..., ge=1)
    note: str | None = None
    legacy_updated_at: datetime | None = None
    user_code: int | None = None


class R4OldPatientNote(BaseModel):
    patient_code: int | None = None
    note_number: int | None = None
    note_date: datetime | None = None
    note: str | None = None
    tooth: int | None = None
    surface: int | None = None
    category_number: int | None = None
    fixed_note_code: int | None = None
    user_code: int | None = None
