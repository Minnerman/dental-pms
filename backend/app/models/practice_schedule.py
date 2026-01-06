from __future__ import annotations

from datetime import date, time

from sqlalchemy import Boolean, Date, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PracticeHour(Base):
    __tablename__ = "practice_hours"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PracticeClosure(Base):
    __tablename__ = "practice_closures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PracticeOverride(Base):
    __tablename__ = "practice_overrides"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
