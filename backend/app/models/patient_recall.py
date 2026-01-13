from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class PatientRecallKind(str, enum.Enum):
    exam = "exam"
    hygiene = "hygiene"
    perio = "perio"
    implant = "implant"
    custom = "custom"


class PatientRecallStatus(str, enum.Enum):
    upcoming = "upcoming"
    due = "due"
    overdue = "overdue"
    completed = "completed"
    cancelled = "cancelled"


class PatientRecallOutcome(str, enum.Enum):
    attended = "attended"
    dna = "dna"
    cancelled = "cancelled"
    rebooked = "rebooked"


class PatientRecall(Base, AuditMixin):
    __tablename__ = "patient_recalls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    kind: Mapped[PatientRecallKind] = mapped_column(
        Enum(PatientRecallKind, name="patient_recall_kind"), nullable=False
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PatientRecallStatus] = mapped_column(
        Enum(PatientRecallStatus, name="patient_recall_status"),
        nullable=False,
        default=PatientRecallStatus.upcoming,
    )
    outcome: Mapped[PatientRecallOutcome | None] = mapped_column(
        Enum(PatientRecallOutcome, name="patient_recall_outcome"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    linked_appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )

    patient = relationship("Patient", back_populates="recalls", lazy="joined")
    communications = relationship(
        "PatientRecallCommunication", back_populates="recall"
    )
