from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.estimate import EstimateFeeType, EstimateStatus
from app.models.patient import PatientCategory


class EstimateItemBase(BaseModel):
    treatment_id: Optional[int] = None
    description: Optional[str] = None
    qty: int = Field(default=1, ge=1)
    fee_type: EstimateFeeType
    unit_amount_pence: Optional[int] = Field(default=None, ge=0)
    min_unit_amount_pence: Optional[int] = Field(default=None, ge=0)
    max_unit_amount_pence: Optional[int] = Field(default=None, ge=0)
    sort_order: Optional[int] = Field(default=None, ge=1)


class EstimateItemCreate(EstimateItemBase):
    pass


class EstimateItemUpdate(BaseModel):
    treatment_id: Optional[int] = None
    description: Optional[str] = None
    qty: Optional[int] = Field(default=None, ge=1)
    fee_type: Optional[EstimateFeeType] = None
    unit_amount_pence: Optional[int] = Field(default=None, ge=0)
    min_unit_amount_pence: Optional[int] = Field(default=None, ge=0)
    max_unit_amount_pence: Optional[int] = Field(default=None, ge=0)
    sort_order: Optional[int] = Field(default=None, ge=1)


class EstimateItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    treatment_id: Optional[int] = None
    description: str
    qty: int
    fee_type: EstimateFeeType
    unit_amount_pence: Optional[int] = None
    min_unit_amount_pence: Optional[int] = None
    max_unit_amount_pence: Optional[int] = None
    sort_order: int


class EstimateCreate(BaseModel):
    appointment_id: Optional[int] = None
    category_snapshot: Optional[PatientCategory] = None
    valid_until: Optional[date] = None
    notes: Optional[str] = None


class EstimateUpdate(BaseModel):
    status: Optional[EstimateStatus] = None
    valid_until: Optional[date] = None
    notes: Optional[str] = None


class EstimateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    category_snapshot: PatientCategory
    status: EstimateStatus
    valid_until: Optional[date] = None
    notes: Optional[str] = None
    created_by_user_id: int
    updated_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    items: list[EstimateItemOut]
