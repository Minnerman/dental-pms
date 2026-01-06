from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.patient import PatientCategory
from app.schemas.actor import ActorOut


class PatientBase(BaseModel):
    nhs_number: Optional[str] = None
    title: Optional[str] = None
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    patient_category: PatientCategory = PatientCategory.clinic_private
    denplan_member_no: Optional[str] = None
    denplan_plan_name: Optional[str] = None
    notes: Optional[str] = None
    allergies: Optional[str] = None
    medical_alerts: Optional[str] = None
    safeguarding_notes: Optional[str] = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    nhs_number: Optional[str] = None
    title: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    patient_category: Optional[PatientCategory] = None
    denplan_member_no: Optional[str] = None
    denplan_plan_name: Optional[str] = None
    notes: Optional[str] = None
    allergies: Optional[str] = None
    medical_alerts: Optional[str] = None
    safeguarding_notes: Optional[str] = None


class PatientOut(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[ActorOut] = None


class PatientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str


class PatientSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
