from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.ledger import LedgerEntryType
from app.models.invoice import PaymentMethod
from app.schemas.actor import ActorOut


class LedgerEntryCreate(BaseModel):
    entry_type: LedgerEntryType
    amount_pence: int
    method: Optional[PaymentMethod] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    related_invoice_id: Optional[int] = None


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    entry_type: LedgerEntryType
    amount_pence: int
    method: Optional[PaymentMethod] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    related_invoice_id: Optional[int] = None
    created_at: datetime
    created_by: ActorOut


class LedgerPaymentCreate(BaseModel):
    amount_pence: int
    method: PaymentMethod
    reference: Optional[str] = None
    note: Optional[str] = None
    related_invoice_id: Optional[int] = None


class LedgerChargeCreate(BaseModel):
    amount_pence: int
    entry_type: LedgerEntryType = LedgerEntryType.charge
    note: Optional[str] = None
    reference: Optional[str] = None
    related_invoice_id: Optional[int] = None
