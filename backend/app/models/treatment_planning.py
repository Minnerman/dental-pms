"""Frozen planning workspaces and immutable native item revisions."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class PatientTreatmentPlan(Base, AuditMixin):
    __tablename__ = "patient_treatment_plans"
    __table_args__ = (
        UniqueConstraint("patient_id", name="uq_patient_treatment_plan_patient"),
        UniqueConstraint("id", "patient_id", name="uq_patient_treatment_plan_identity"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)


class TreatmentPlanItemRevision(Base):
    __tablename__ = "treatment_plan_item_revisions"
    __table_args__ = (UniqueConstraint("item_id", "revision", name="uq_planning_item_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("treatment_plan_items.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    recorded_by = relationship("User", lazy="joined")


class PlanningMutationReceipt(Base):
    __tablename__ = "planning_mutation_receipts"
    __table_args__ = (UniqueConstraint("actor_user_id", "request_id", name="uq_planning_mutation_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
