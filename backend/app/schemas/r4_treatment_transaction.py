from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class R4TreatmentTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_transaction_id: int
    performed_at: datetime
    treatment_code: int | None = None
    trans_code: int | None = None
    patient_cost: Decimal | None = None
    dpb_cost: Decimal | None = None
    treatment_name: str | None = None
    recorded_by: int | None = None
    user_code: int | None = None
    recorded_by_name: str | None = None
    user_name: str | None = None


class R4TreatmentTransactionListOut(BaseModel):
    items: list[R4TreatmentTransactionOut]
    next_cursor: str | None = None
