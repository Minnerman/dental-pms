from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.user import User


class Base(DeclarativeBase):
    pass


class AuditMixin:
    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        )

    @declared_attr
    def created_by_user_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("users.id"), nullable=False)

    @declared_attr
    def updated_by_user_id(cls) -> Mapped[int | None]:
        return mapped_column(ForeignKey("users.id"), nullable=True)

    @declared_attr
    def created_by(cls) -> Mapped["User"]:
        return relationship("User", foreign_keys=[cls.created_by_user_id], lazy="joined")

    @declared_attr
    def updated_by(cls) -> Mapped["User"]:
        return relationship("User", foreign_keys=[cls.updated_by_user_id], lazy="joined")


class SoftDeleteMixin:
    @declared_attr
    def deleted_at(cls) -> Mapped[datetime | None]:
        return mapped_column(DateTime(timezone=True), nullable=True, index=True)

    @declared_attr
    def deleted_by_user_id(cls) -> Mapped[int | None]:
        return mapped_column(ForeignKey("users.id"), nullable=True)

    @declared_attr
    def deleted_by(cls) -> Mapped["User"]:
        return relationship("User", foreign_keys=[cls.deleted_by_user_id], lazy="joined")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
