from __future__ import annotations

import enum
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.patient import PatientCategory


class EstimateStatus(str, enum.Enum):
    draft = "DRAFT"
    issued = "ISSUED"
    accepted = "ACCEPTED"
    declined = "DECLINED"
    superseded = "SUPERSEDED"


class EstimateFeeType(str, enum.Enum):
    fixed = "FIXED"
    range = "RANGE"


class Estimate(Base, AuditMixin):
    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True, index=True
    )
    category_snapshot: Mapped[PatientCategory] = mapped_column(
        Enum(PatientCategory, name="patient_category"), nullable=False
    )
    status: Mapped[EstimateStatus] = mapped_column(
        Enum(EstimateStatus, name="estimate_status"),
        nullable=False,
        default=EstimateStatus.draft,
    )
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient = relationship("Patient", back_populates="estimates", lazy="joined")
    appointment = relationship("Appointment", back_populates="estimates", lazy="joined")
    items = relationship(
        "EstimateItem",
        back_populates="estimate",
        cascade="all, delete-orphan",
        order_by="EstimateItem.sort_order",
        lazy="selectin",
    )


class EstimateItem(Base):
    __tablename__ = "estimate_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"), nullable=False, index=True)
    treatment_id: Mapped[int | None] = mapped_column(ForeignKey("treatments.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_unit_amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_unit_amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fee_type: Mapped[EstimateFeeType] = mapped_column(
        Enum(EstimateFeeType, name="estimate_fee_type"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    estimate = relationship("Estimate", back_populates="items")
    treatment = relationship("Treatment", lazy="joined")
