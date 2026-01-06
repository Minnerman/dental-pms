from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.patient import PatientCategory
from app.models.treatment import FeeType


class TreatmentBase(BaseModel):
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    is_active: bool = True
    default_duration_minutes: Optional[int] = Field(default=None, ge=1)
    is_denplan_included_default: bool = False


class TreatmentCreate(TreatmentBase):
    pass


class TreatmentUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    default_duration_minutes: Optional[int] = Field(default=None, ge=1)
    is_denplan_included_default: Optional[bool] = None


class TreatmentOut(TreatmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    created_by_user_id: int
    updated_by_user_id: Optional[int] = None


class TreatmentFeeBase(BaseModel):
    patient_category: PatientCategory
    fee_type: FeeType
    amount_pence: Optional[int] = Field(default=None, ge=0)
    min_amount_pence: Optional[int] = Field(default=None, ge=0)
    max_amount_pence: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class TreatmentFeeUpsert(TreatmentFeeBase):
    pass


class TreatmentFeeOut(TreatmentFeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    treatment_id: int
