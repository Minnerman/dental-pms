from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin


class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    cancelled = "cancelled"
    completed = "completed"


class Appointment(Base, AuditMixin, SoftDeleteMixin):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    clinician_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status"),
        default=AppointmentStatus.booked,
        nullable=False,
    )
    appointment_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    clinician: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_domiciliary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visit_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient = relationship("Patient", back_populates="appointments", lazy="joined")
    invoices = relationship("Invoice", back_populates="appointment")
    estimates = relationship("Estimate", back_populates="appointment")

    @property
    def patient_has_alerts(self) -> bool:
        patient = self.patient
        if not patient:
            return False
        return any(
            value.strip()
            for value in (
                patient.allergies,
                patient.medical_alerts,
                patient.safeguarding_notes,
            )
            if value
        )
