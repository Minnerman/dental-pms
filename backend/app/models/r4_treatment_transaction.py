from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class R4TreatmentTransaction(Base, AuditMixin):
    __tablename__ = "r4_treatment_transactions"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_transaction_id",
            name="uq_r4_treatment_transactions_legacy_key",
        ),
        Index(
            "ix_r4_treatment_transactions_patient_code_performed_at",
            "patient_code",
            "performed_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_transaction_id: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_code: Mapped[int] = mapped_column(Integer, nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    treatment_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trans_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    dpb_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tp_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tp_item: Mapped[int | None] = mapped_column(Integer, nullable=True)
