from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.clinical_note import NativeNoteMetadata


class ProcedureStatus(str, enum.Enum):
    completed = "completed"


class TreatmentPlanStatus(str, enum.Enum):
    proposed = "proposed"
    accepted = "accepted"
    declined = "declined"
    completed = "completed"
    cancelled = "cancelled"


class ToothConditionValue(str, enum.Enum):
    # Explicit neutral override: history remains, but is not inferred as current.
    unrecorded = "unrecorded"
    present = "present"
    missing = "missing"
    deciduous = "deciduous"
    implant = "implant"
    unerupted = "unerupted"
    impacted = "impacted"


class ToothBridgeGroup(Base, AuditMixin):
    """Explicit native bridge identity; members live on revisioned tooth rows."""

    __tablename__ = "tooth_bridge_groups"
    __table_args__ = (UniqueConstraint("id", "patient_id", name="uq_tooth_bridge_group_patient"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)


class ToothCondition(Base, AuditMixin):
    """Native current observations, deliberately separate from treatment/billing.

    Condition, movement and rotation are independent observations. Clearing one
    never discards another. The revision remains after reset so an older editor
    cannot accidentally overwrite a later observation.
    """

    __tablename__ = "tooth_conditions"
    __table_args__ = (
        UniqueConstraint("patient_id", "tooth", name="uq_tooth_conditions_patient_tooth"),
        CheckConstraint("revision > 0", name="ck_tooth_conditions_revision"),
        CheckConstraint(
            "condition IS NULL OR condition IN "
            "('present', 'missing', 'deciduous', 'implant', 'unerupted', 'impacted', 'unrecorded')",
            name="ck_tooth_conditions_value",
        ),
        CheckConstraint(
            "dentition IS NULL OR dentition IN ('permanent', 'deciduous')",
            name="ck_tooth_conditions_dentition",
        ),
        CheckConstraint(
            "dentition IS DISTINCT FROM 'deciduous' OR right(tooth, 1) IN ('1', '2', '3', '4', '5')",
            name="ck_tooth_conditions_deciduous_position",
        ),
        CheckConstraint(
            "movement IS NULL OR movement IN ('forward', 'backward')",
            name="ck_tooth_conditions_movement",
        ),
        CheckConstraint(
            "rotation IS NULL OR rotation IN ('clockwise', 'anticlockwise')",
            name="ck_tooth_conditions_rotation",
        ),
        CheckConstraint(
            "jsonb_typeof(root_observations) = 'object' AND "
            "root_observations - '1' - '2' - '3' = '{}'::jsonb",
            name="ck_tooth_conditions_root_keys",
        ),
        CheckConstraint(
            "crown_observation IS NULL OR jsonb_typeof(crown_observation) = 'object'",
            name="ck_tooth_conditions_crown_object",
        ),
        CheckConstraint(
            "jsonb_typeof(surface_observations) = 'object' AND "
            "surface_observations - 'M' - 'O' - 'I' - 'D' - 'B' - 'P' - 'L' = '{}'::jsonb",
            name="ck_tooth_conditions_surface_keys",
        ),
        ForeignKeyConstraint(
            ["bridge_group_id", "patient_id"], ["tooth_bridge_groups.id", "tooth_bridge_groups.patient_id"],
            name="fk_tooth_condition_bridge_patient",
        ),
        CheckConstraint(
            "(bridge_group_id IS NULL AND bridge_role IS NULL) OR "
            "(bridge_group_id IS NOT NULL AND bridge_role IS NOT NULL "
            "AND bridge_role IN ('abutment', 'pontic', 'wing'))",
            name="ck_tooth_conditions_bridge_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    tooth: Mapped[str] = mapped_column(String(3), nullable=False)
    condition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Identity is independent of presence/eruption. NULL is unspecified.
    dentition: Mapped[str | None] = mapped_column(String(9), nullable=True)
    movement: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rotation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    root_observations: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    # SQL NULL is no current override; a non-null neutral object is a reset.
    crown_observation: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    # Missing keys are unspecified; neutral entries explicitly reset a surface.
    surface_observations: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    bridge_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    bridge_role: Mapped[str | None] = mapped_column(String(12), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ToothNote(Base, NativeNoteMetadata):
    __tablename__ = "tooth_notes"
    __table_args__ = (Index("ix_tooth_notes_journal_patient", "patient_id", "created_at", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    tooth: Mapped[str] = mapped_column(String(12), nullable=False)
    surface: Mapped[str | None] = mapped_column(String(12), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    patient = relationship("Patient", back_populates="tooth_notes")
    created_by = relationship("User", foreign_keys=[created_by_user_id], lazy="joined")


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    tooth: Mapped[str | None] = mapped_column(String(12), nullable=True)
    surface: Mapped[str | None] = mapped_column(String(12), nullable=True)
    procedure_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    fee_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ProcedureStatus] = mapped_column(
        Enum(ProcedureStatus, name="procedure_status"),
        default=ProcedureStatus.completed,
        nullable=False,
    )
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    patient = relationship("Patient", back_populates="procedures")
    appointment = relationship("Appointment")
    created_by = relationship("User", foreign_keys=[created_by_user_id], lazy="joined")


class TreatmentPlanItem(Base, AuditMixin):
    __tablename__ = "treatment_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    tooth: Mapped[str | None] = mapped_column(String(12), nullable=True)
    surface: Mapped[str | None] = mapped_column(String(12), nullable=True)
    procedure_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    fee_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[TreatmentPlanStatus] = mapped_column(
        Enum(TreatmentPlanStatus, name="treatment_plan_status"),
        default=TreatmentPlanStatus.proposed,
        nullable=False,
    )

    patient = relationship("Patient", back_populates="treatment_plan_items")
    appointment = relationship("Appointment")
