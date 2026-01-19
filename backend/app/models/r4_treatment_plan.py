from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class R4Treatment(Base, AuditMixin):
    __tablename__ = "r4_treatments"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_treatment_code",
            name="uq_r4_treatments_legacy_source_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_treatment_code: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exam: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    patient_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class R4TreatmentPlan(Base, AuditMixin):
    __tablename__ = "r4_treatment_plans"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_patient_code",
            "legacy_tp_number",
            name="uq_r4_treatment_plans_legacy_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_patient_code: Mapped[int] = mapped_column(Integer, nullable=False)
    legacy_tp_number: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_index: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    is_master: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creation_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acceptance_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tp_group: Mapped[int | None] = mapped_column(Integer, nullable=True)

    items = relationship(
        "R4TreatmentPlanItem",
        back_populates="treatment_plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    reviews = relationship(
        "R4TreatmentPlanReview",
        back_populates="treatment_plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class R4TreatmentPlanItem(Base, AuditMixin):
    __tablename__ = "r4_treatment_plan_items"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_tp_item_key",
            name="uq_r4_treatment_plan_items_legacy_key",
        ),
        UniqueConstraint(
            "treatment_plan_id",
            "legacy_tp_item",
            name="uq_r4_treatment_plan_items_plan_item",
        ),
        Index(
            "ix_r4_treatment_plan_items_plan_id",
            "treatment_plan_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    treatment_plan_id: Mapped[int] = mapped_column(
        ForeignKey("r4_treatment_plans.id"), nullable=False
    )
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_tp_item: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    legacy_tp_item_key: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    surface: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    appointment_need_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    patient_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    dpb_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    discretionary_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    material: Mapped[str | None] = mapped_column(String(1), nullable=True)
    arch_code: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    treatment_plan = relationship("R4TreatmentPlan", back_populates="items")


class R4TreatmentPlanReview(Base, AuditMixin):
    __tablename__ = "r4_treatment_plan_reviews"
    __table_args__ = (
        UniqueConstraint(
            "treatment_plan_id",
            name="uq_r4_treatment_plan_reviews_plan",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    treatment_plan_id: Mapped[int] = mapped_column(
        ForeignKey("r4_treatment_plans.id"), nullable=False
    )
    temporary_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_edit_user: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_edit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    treatment_plan = relationship("R4TreatmentPlan", back_populates="reviews")
