from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class PrescriptionTemplate(Base, AuditMixin):
    __tablename__ = "prescription_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    medicine: Mapped[str] = mapped_column(String(500), nullable=False)
    directions: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
