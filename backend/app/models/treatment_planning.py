"""Frozen planning workspaces and immutable native item revisions."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
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


class TreatmentPlanCompletion(Base):
    """One immutable completion cycle, including its exact accounting source."""
    __tablename__ = "treatment_plan_completions"
    __table_args__ = (
        UniqueConstraint("item_id", "cycle", name="uq_plan_completion_cycle"),
        CheckConstraint("cycle > 0", name="ck_plan_completion_cycle"),
        CheckConstraint("previous_status IN ('proposed', 'accepted')", name="ck_plan_completion_previous_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("treatment_plan_items.id"), nullable=False)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_status: Mapped[str] = mapped_column(String(12), nullable=False)
    procedure_id: Mapped[int] = mapped_column(ForeignKey("procedures.id"), nullable=False, unique=True)
    charge_id: Mapped[int | None] = mapped_column(ForeignKey("patient_ledger_entries.id"), nullable=True, unique=True)
    # The original procedure retains its true performance date and author.
    # This timestamp states when the linkage was recorded, including verified
    # pre-0060 linkage; it is not an invented historic completion timestamp.
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TreatmentPlanCompletionReversal(Base):
    """Append-only correction; charges/payments and procedure content survive."""
    __tablename__ = "treatment_plan_completion_reversals"
    id: Mapped[int] = mapped_column(primary_key=True)
    completion_id: Mapped[int] = mapped_column(ForeignKey("treatment_plan_completions.id"), nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    adjustment_id: Mapped[int | None] = mapped_column(ForeignKey("patient_ledger_entries.id"), nullable=True, unique=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    recorded_by = relationship("User", lazy="joined")
