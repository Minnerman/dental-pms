from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class ProcedureStatus(str, enum.Enum):
    completed = "completed"


class TreatmentPlanStatus(str, enum.Enum):
    proposed = "proposed"
    accepted = "accepted"
    declined = "declined"
    completed = "completed"
    cancelled = "cancelled"


class ToothNote(Base):
    __tablename__ = "tooth_notes"

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
