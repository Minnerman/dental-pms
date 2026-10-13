from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class DocumentCopy(Base):
    """An immutable PDF snapshot, with an append-only completion record in Notes."""
    __tablename__ = "document_copies"
    __table_args__ = (UniqueConstraint("created_by_user_id", "request_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("patient_documents.id", ondelete="SET NULL"))
    source_document_id: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    document_kind: Mapped[str] = mapped_column(String(30))
    method: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="prepared")
    recipient: Mapped[str | None] = mapped_column(String(320))
    sender: Mapped[str | None] = mapped_column(String(320))
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    request_id: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    completed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
