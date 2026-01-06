from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.patient import PatientCategory


class FeeType(str, enum.Enum):
    fixed = "FIXED"
    range = "RANGE"
    not_applicable = "N_A"


class Treatment(Base, AuditMixin):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_denplan_included_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    fees = relationship(
        "TreatmentFee",
        back_populates="treatment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TreatmentFee(Base):
    __tablename__ = "treatment_fees"
    __table_args__ = (UniqueConstraint("treatment_id", "patient_category"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    treatment_id: Mapped[int] = mapped_column(ForeignKey("treatments.id"), nullable=False)
    patient_category: Mapped[PatientCategory] = mapped_column(
        Enum(PatientCategory, name="patient_category"), nullable=False
    )
    fee_type: Mapped[FeeType] = mapped_column(Enum(FeeType, name="fee_type"), nullable=False)
    amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    treatment = relationship("Treatment", back_populates="fees")
