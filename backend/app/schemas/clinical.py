from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.clinical import ProcedureStatus, TreatmentPlanStatus
from app.schemas.actor import ActorOut


class ToothNoteCreate(BaseModel):
    tooth: str
    surface: Optional[str] = None
    note: str


class ToothNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    tooth: str
    surface: Optional[str] = None
    note: str
    created_at: datetime
    created_by: ActorOut


class ProcedureCreate(BaseModel):
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: str
    description: str
    fee_pence: Optional[int] = None
    performed_at: Optional[datetime] = None


class ProcedureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: str
    description: str
    fee_pence: Optional[int] = None
    status: ProcedureStatus
    performed_at: datetime
    created_by: ActorOut


class TreatmentPlanItemCreate(BaseModel):
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: str
    description: str
    fee_pence: Optional[int] = None


class TreatmentPlanItemUpdate(BaseModel):
    appointment_id: Optional[int] = None
    procedure_code: Optional[str] = None
    description: Optional[str] = None
    fee_pence: Optional[int] = None
    status: Optional[TreatmentPlanStatus] = None


class TreatmentPlanItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: str
    description: str
    fee_pence: Optional[int] = None
    status: TreatmentPlanStatus
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None


class ToothHistoryOut(BaseModel):
    notes: list[ToothNoteOut]
    procedures: list[ProcedureOut]


class ClinicalSummaryOut(BaseModel):
    recent_tooth_notes: list[ToothNoteOut]
    recent_procedures: list[ProcedureOut]
    treatment_plan_items: list[TreatmentPlanItemOut]
