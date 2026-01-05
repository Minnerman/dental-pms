from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.invoice import InvoiceStatus, PaymentMethod


class InvoiceLineBase(BaseModel):
    description: str
    quantity: int = Field(ge=1)
    unit_price_pence: int = Field(ge=0)


class InvoiceLineCreate(InvoiceLineBase):
    pass


class InvoiceLineUpdate(BaseModel):
    description: Optional[str] = None
    quantity: Optional[int] = Field(default=None, ge=1)
    unit_price_pence: Optional[int] = Field(default=None, ge=0)


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    quantity: int
    unit_price_pence: int
    line_total_pence: int


class PaymentCreate(BaseModel):
    amount_pence: int = Field(ge=1)
    method: PaymentMethod
    paid_at: Optional[datetime] = None
    reference: Optional[str] = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_pence: int
    method: PaymentMethod
    paid_at: datetime
    reference: Optional[str] = None
    received_by_user_id: int


class InvoiceCreate(BaseModel):
    patient_id: int
    appointment_id: Optional[int] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    discount_pence: int = Field(default=0, ge=0)


class InvoiceUpdate(BaseModel):
    appointment_id: Optional[int] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    discount_pence: Optional[int] = Field(default=None, ge=0)


class InvoiceSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    invoice_number: str
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    status: InvoiceStatus
    subtotal_pence: int
    discount_pence: int
    total_pence: int
    paid_pence: int
    balance_pence: int
    created_at: datetime
    updated_at: datetime


class InvoiceOut(InvoiceSummaryOut):
    model_config = ConfigDict(from_attributes=True)

    notes: Optional[str] = None
    created_by_user_id: int
    updated_by_user_id: Optional[int] = None
    lines: list[InvoiceLineOut]
    payments: list[PaymentOut]
