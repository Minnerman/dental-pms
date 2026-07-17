from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.patient import CareSetting, PatientCategory, RecallStatus
from app.models.patient_recall import (
    PatientRecallKind,
    PatientRecallOutcome,
    PatientRecallStatus,
)
from app.schemas.actor import ActorOut


class PatientBase(BaseModel):
    nhs_number: Optional[str] = None
    title: Optional[str] = None
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    date_of_birth: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = Field(default=None, max_length=320)
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
    recall_type: Optional[str] = None
    recall_last_contacted_at: Optional[datetime] = None
    recall_notes: Optional[str] = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def normalize_required_names(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("date_of_birth")
    @classmethod
    def reject_future_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return value


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    nhs_number: Optional[str] = None
    title: Optional[str] = None
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    date_of_birth: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = Field(default=None, max_length=320)
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
    recall_type: Optional[str] = None
    recall_last_contacted_at: Optional[datetime] = None
    recall_notes: Optional[str] = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def normalize_required_names(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("date_of_birth")
    @classmethod
    def reject_future_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return value

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        required_fields = {
            "first_name",
            "last_name",
            "patient_category",
            "care_setting",
        }
        for field_name in required_fields.intersection(self.model_fields_set):
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


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
    interval_months: Optional[int] = Field(default=None, ge=1, le=120)
    due_date: Optional[date] = None
    status: Optional[RecallStatus] = None
    recall_type: Optional[str] = Field(default=None, max_length=40)
    last_contacted_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("recall_type", "notes", mode="before")
    @classmethod
    def normalize_optional_recall_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def reject_null_interval(self):
        if "interval_months" in self.model_fields_set and self.interval_months is None:
            raise ValueError("Recall interval cannot be null.")
        return self


class PatientRecallSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    phone: Optional[str] = None
    postcode: Optional[str] = None
    recall_interval_months: Optional[int] = None
    recall_due_date: Optional[date] = None
    recall_status: Optional[RecallStatus] = None
    recall_type: Optional[str] = None
    recall_last_contacted_at: Optional[datetime] = None
    recall_notes: Optional[str] = None
    recall_last_set_at: Optional[datetime] = None
    balance_pence: Optional[int] = None


class PatientFinanceItemOut(BaseModel):
    id: int
    kind: Literal["invoice", "payment"]
    date: date
    amount_pence: int
    status: str
    invoice_id: Optional[int] = None
    payment_id: Optional[int] = None
    invoice_number: Optional[str] = None


class PatientFinanceSummaryOut(BaseModel):
    patient_id: int
    outstanding_balance_pence: int
    items: list[PatientFinanceItemOut]


class PatientRecallBase(BaseModel):
    kind: PatientRecallKind
    due_date: date
    status: PatientRecallStatus = PatientRecallStatus.upcoming
    notes: Optional[str] = Field(default=None, max_length=2000)
    completed_at: Optional[datetime] = None
    outcome: Optional[PatientRecallOutcome] = None
    linked_appointment_id: Optional[int] = None

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_recall_notes(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_completion_state(self):
        if self.status != PatientRecallStatus.completed and self.completed_at is not None:
            raise ValueError("Completion time is only valid for completed recalls.")
        return self


class PatientRecallCreate(PatientRecallBase):
    pass


class PatientRecallUpdate(BaseModel):
    kind: Optional[PatientRecallKind] = None
    due_date: Optional[date] = None
    status: Optional[PatientRecallStatus] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    completed_at: Optional[datetime] = None
    outcome: Optional[PatientRecallOutcome] = None
    linked_appointment_id: Optional[int] = None

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_recall_notes(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class PatientRecallOut(PatientRecallBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime
