from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class R4Appointment(Base, AuditMixin):
    __tablename__ = "r4_appointments"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_appointment_id",
            name="uq_r4_appointments_legacy_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_appointment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clinician_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cancelled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    clinic_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    treatment_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    appointment_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    appt_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)
