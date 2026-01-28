from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class R4ManualMapping(Base):
    __tablename__ = "r4_manual_mappings"
    __table_args__ = (
        CheckConstraint(
            "legacy_patient_code IS NOT NULL OR legacy_person_key IS NOT NULL",
            name="r4_manual_mappings_has_legacy_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_person_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_patient_id: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
