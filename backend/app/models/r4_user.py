from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class R4User(Base, AuditMixin):
    __tablename__ = "r4_users"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_user_code",
            name="uq_r4_users_legacy_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_user_code: Mapped[int] = mapped_column(Integer, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    forename: Mapped[str | None] = mapped_column(String(120), nullable=True)
    surname: Mapped[str | None] = mapped_column(String(120), nullable=True)
    initials: Mapped[str | None] = mapped_column(String(40), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
