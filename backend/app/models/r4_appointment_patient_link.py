from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class R4AppointmentPatientLink(Base):
    __tablename__ = "r4_appointment_patient_links"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_appointment_id",
            name="uq_r4_appointment_patient_links_legacy_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_appointment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    linked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
