from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin
from app.models.clinical_note import NativeNoteMetadata


class NoteType(str, enum.Enum):
    clinical = "clinical"
    admin = "admin"


class Note(Base, AuditMixin, SoftDeleteMixin, NativeNoteMetadata):
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_journal_patient", "patient_id", "created_at", "id"),)

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
