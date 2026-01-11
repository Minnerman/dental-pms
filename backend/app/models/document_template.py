from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, SoftDeleteMixin


class DocumentTemplateKind(str, enum.Enum):
    letter = "letter"
    prescription = "prescription"


class DocumentTemplate(Base, AuditMixin, SoftDeleteMixin):
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[DocumentTemplateKind] = mapped_column(
        Enum(DocumentTemplateKind, name="document_template_kind"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
