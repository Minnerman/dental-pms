from __future__ import annotations

import enum
from datetime import date

from sqlalchemy import Date, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin


class PatientCategory(str, enum.Enum):
    clinic_private = "CLINIC_PRIVATE"
    domiciliary_private = "DOMICILIARY_PRIVATE"
    denplan = "DENPLAN"


class Patient(Base, AuditMixin, SoftDeleteMixin):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nhs_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postcode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    patient_category: Mapped[PatientCategory] = mapped_column(
        Enum(PatientCategory, name="patient_category"),
        default=PatientCategory.clinic_private,
        nullable=False,
    )
    denplan_member_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    denplan_plan_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    medical_alerts: Mapped[str | None] = mapped_column(Text, nullable=True)
    safeguarding_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    appointments = relationship("Appointment", back_populates="patient")
    notes_list = relationship("Note", back_populates="patient")
    invoices = relationship("Invoice", back_populates="patient")
    estimates = relationship("Estimate", back_populates="patient")
