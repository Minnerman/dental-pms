from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.invoice import PaymentMethod


class CashupPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    patient_first_name: str
    patient_last_name: str
    method: Optional[PaymentMethod] = None
    amount_pence: int
    reference: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class CashupReportOut(BaseModel):
    date: date
    totals_by_method: dict[str, int]
    total_pence: int
    payments: list[CashupPaymentOut]
