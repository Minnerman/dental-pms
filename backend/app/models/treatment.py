from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.patient import PatientCategory


class FeeType(str, enum.Enum):
    fixed = "FIXED"
    range = "RANGE"
    not_applicable = "N_A"


class Treatment(Base, AuditMixin):
    __tablename__ = "treatments"
    __table_args__ = (
        CheckConstraint("level IS NULL OR level IN ('tooth','root','crown','surface','general')", name="ck_treatment_level"),
        CheckConstraint("display_order >= 0", name="ck_treatment_display_order"),
        UniqueConstraint("routine_key", name="uq_treatments_routine_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_denplan_included_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    level: Mapped[str | None] = mapped_column(String(12), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    routine_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

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


class TreatmentFeeVersion(Base):
    """Immutable effective-date fee entries; original undated fees stay intact."""
    __tablename__ = "treatment_fee_versions"
    __table_args__ = (
        UniqueConstraint("treatment_id", "patient_category", "revision", name="uq_treatment_fee_revision"),
        UniqueConstraint("recorded_by_user_id", "request_id", name="uq_treatment_fee_request"),
        CheckConstraint("revision > 0", name="ck_treatment_fee_revision"),
        Index("ix_treatment_fee_effective", "treatment_id", "patient_category", "effective_from", "revision"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    treatment_id: Mapped[int] = mapped_column(ForeignKey("treatments.id"), nullable=False)
    patient_category: Mapped[PatientCategory] = mapped_column(Enum(PatientCategory, name="patient_category"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    fee_type: Mapped[FeeType | None] = mapped_column(Enum(FeeType, name="fee_type"), nullable=True)
    amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_by = relationship("User", lazy="joined")
