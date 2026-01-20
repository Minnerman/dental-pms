from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class R4PatientMapping(Base, AuditMixin):
    __tablename__ = "r4_patient_mappings"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_patient_code",
            name="uq_r4_patient_mappings_legacy_key",
        ),
        UniqueConstraint(
            "legacy_source",
            "patient_id",
            name="uq_r4_patient_mappings_patient",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_patient_code: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)

    patient = relationship("Patient", lazy="joined")
