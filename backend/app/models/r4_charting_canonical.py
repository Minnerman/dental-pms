from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class R4ChartingCanonicalRecord(Base):
    __tablename__ = "r4_charting_canonical_records"
    __table_args__ = (
        Index("ix_r4_charting_canonical_patient", "patient_id"),
        Index("ix_r4_charting_canonical_domain", "domain"),
        Index("ix_r4_charting_canonical_source", "r4_source"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    unique_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False)
    r4_source: Mapped[str] = mapped_column(String(120), nullable=False)
    r4_source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    surface: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    code_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
