"""Native note metadata and immutable snapshots; never writes imported notes."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class NativeNoteMetadata:
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    clinical_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("clinical_note_templates.id"), nullable=True)
    template_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))


class ClinicalNoteTemplate(Base, AuditMixin):
    __tablename__ = "clinical_note_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ClinicalNoteTemplateRevision(Base):
    __tablename__ = "clinical_note_template_revisions"
    __table_args__ = (UniqueConstraint("template_id", "revision", name="uq_clinical_template_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("clinical_note_templates.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class NativeNoteRevision(Base):
    __tablename__ = "native_note_revisions"
    __table_args__ = (
        CheckConstraint("(note_id IS NULL) <> (tooth_note_id IS NULL)", name="ck_native_revision_one_source"),
        UniqueConstraint("note_id", "revision", name="uq_native_note_revision"),
        UniqueConstraint("tooth_note_id", "revision", name="uq_native_tooth_note_revision"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    tooth_note_id: Mapped[int | None] = mapped_column(ForeignKey("tooth_notes.id"), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # NULL means the pre-feature baseline author of the latest content is unknown.
    recorded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recorded_by = relationship("User", lazy="joined")


class NoteMutationReceipt(Base):
    """Bounded request fingerprint only; clinical content stays in revision storage."""
    __tablename__ = "note_mutation_receipts"
    __table_args__ = (UniqueConstraint("actor_user_id", "request_id", name="uq_note_mutation_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
