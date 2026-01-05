from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin


class NoteType(str, enum.Enum):
    clinical = "clinical"
    admin = "admin"


class Note(Base, AuditMixin, SoftDeleteMixin):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[NoteType] = mapped_column(
        Enum(NoteType, name="note_type"), default=NoteType.clinical, nullable=False
    )

    patient = relationship("Patient", back_populates="notes_list")
    appointment = relationship("Appointment")
