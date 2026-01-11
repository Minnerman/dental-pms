from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.patient import CareSetting, PatientCategory, RecallStatus
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
    care_setting: CareSetting = CareSetting.clinic
    visit_address_text: Optional[str] = None
    access_notes: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None
    primary_contact_relationship: Optional[str] = None
    referral_source: Optional[str] = None
    referral_contact_name: Optional[str] = None
    referral_contact_phone: Optional[str] = None
    referral_notes: Optional[str] = None
    notes: Optional[str] = None
    allergies: Optional[str] = None
    medical_alerts: Optional[str] = None
    safeguarding_notes: Optional[str] = None
    alerts_financial: Optional[str] = None
    alerts_access: Optional[str] = None
    recall_interval_months: Optional[int] = 6
    recall_due_date: Optional[date] = None
    recall_status: Optional[RecallStatus] = None


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
    care_setting: Optional[CareSetting] = None
    visit_address_text: Optional[str] = None
    access_notes: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None
    primary_contact_relationship: Optional[str] = None
    referral_source: Optional[str] = None
    referral_contact_name: Optional[str] = None
    referral_contact_phone: Optional[str] = None
    referral_notes: Optional[str] = None
    notes: Optional[str] = None
    allergies: Optional[str] = None
    medical_alerts: Optional[str] = None
    safeguarding_notes: Optional[str] = None
    alerts_financial: Optional[str] = None
    alerts_access: Optional[str] = None
    recall_interval_months: Optional[int] = None
    recall_due_date: Optional[date] = None
    recall_status: Optional[RecallStatus] = None


class PatientOut(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[ActorOut] = None
    recall_last_set_at: Optional[datetime] = None
    recall_last_set_by_user_id: Optional[int] = None


class PatientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    patient_category: PatientCategory
    care_setting: CareSetting
    allergies: Optional[str] = None
    medical_alerts: Optional[str] = None
    alerts_financial: Optional[str] = None
    alerts_access: Optional[str] = None
    recall_due_date: Optional[date] = None
    recall_status: Optional[RecallStatus] = None


class PatientSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None


class RecallUpdate(BaseModel):
    interval_months: Optional[int] = None
    due_date: Optional[date] = None
    status: Optional[RecallStatus] = None


class PatientRecallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    phone: Optional[str] = None
    postcode: Optional[str] = None
    recall_interval_months: Optional[int] = None
    recall_due_date: Optional[date] = None
    recall_status: Optional[RecallStatus] = None
    recall_last_set_at: Optional[datetime] = None
    balance_pence: Optional[int] = None
