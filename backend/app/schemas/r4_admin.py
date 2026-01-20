from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class R4TreatmentPlanSummary(BaseModel):
    id: int
    legacy_patient_code: int
    legacy_tp_number: int
    plan_index: int | None = None
    is_master: bool
    is_current: bool
    is_accepted: bool
    creation_date: datetime | None = None
    acceptance_date: datetime | None = None
    completion_date: datetime | None = None
    status_code: int | None = None
    reason_id: int | None = None
    tp_group: int | None = None
    item_count: int


class R4TreatmentPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    legacy_source: str
    legacy_patient_code: int
    legacy_tp_number: int
    plan_index: int | None = None
    is_master: bool
    is_current: bool
    is_accepted: bool
    creation_date: datetime | None = None
    acceptance_date: datetime | None = None
    completion_date: datetime | None = None
    status_code: int | None = None
    reason_id: int | None = None
    tp_group: int | None = None


class R4TreatmentPlanItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    treatment_plan_id: int
    legacy_source: str
    legacy_tp_item: int
    legacy_tp_item_key: int | None = None
    code_id: int | None = None
    tooth: int | None = None
    surface: int | None = None
    appointment_need_id: int | None = None
    completed: bool
    completed_date: datetime | None = None
    patient_cost: Decimal | None = None
    dpb_cost: Decimal | None = None
    discretionary_cost: Decimal | None = None
    material: str | None = None
    arch_code: int | None = None


class R4TreatmentPlanReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    treatment_plan_id: int
    temporary_note: str | None = None
    reviewed: bool
    last_edit_user: str | None = None
    last_edit_date: datetime | None = None


class R4TreatmentPlanDetail(BaseModel):
    plan: R4TreatmentPlanOut
    items: list[R4TreatmentPlanItemOut]
    reviews: list[R4TreatmentPlanReviewOut]


class R4UnmappedPlanPatientCode(BaseModel):
    legacy_patient_code: int
    plan_count: int


class R4PatientMappingCreate(BaseModel):
    legacy_patient_code: int
    patient_id: int
    notes: str | None = None


class R4PatientMappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    legacy_source: str
    legacy_patient_code: int
    patient_id: int
