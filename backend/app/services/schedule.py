from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.practice_schedule import PracticeClosure, PracticeHour, PracticeOverride

LOCAL_TZ = ZoneInfo("Europe/London")


def ensure_default_hours(db: Session) -> None:
    existing = db.scalar(select(PracticeHour.id))
    if existing:
        return
    defaults = [
        (0, time(9, 0), time(17, 30), False),
        (1, time(9, 0), time(17, 30), False),
        (2, time(9, 0), time(17, 30), False),
        (3, time(9, 0), time(17, 30), False),
        (4, time(9, 0), time(17, 30), False),
        (5, None, None, True),
        (6, None, None, True),
    ]
    for day, start, end, closed in defaults:
        db.add(
            PracticeHour(
                day_of_week=day,
                start_time=start,
                end_time=end,
                is_closed=closed,
            )
        )
    db.commit()


def load_schedule(db: Session) -> tuple[list[PracticeHour], list[PracticeClosure], list[PracticeOverride]]:
    ensure_default_hours(db)
    hours = list(db.scalars(select(PracticeHour).order_by(PracticeHour.day_of_week)))
    closures = list(db.scalars(select(PracticeClosure).order_by(PracticeClosure.start_date)))
    overrides = list(db.scalars(select(PracticeOverride).order_by(PracticeOverride.date)))
    return hours, closures, overrides


def _is_date_closed(target: date, closures: list[PracticeClosure]) -> PracticeClosure | None:
    for closure in closures:
        if closure.start_date <= target <= closure.end_date:
            return closure
    return None


def get_practice_window(
    target: date,
    hours: list[PracticeHour],
    closures: list[PracticeClosure],
    overrides: list[PracticeOverride],
) -> tuple[time | None, time | None, str | None]:
    override = next((item for item in overrides if item.date == target), None)
    if override:
        if override.is_closed:
            reason = override.reason or "Practice closed (override)."
            return None, None, reason
        if override.start_time and override.end_time:
            return override.start_time, override.end_time, None

    closure = _is_date_closed(target, closures)
    if closure:
        reason = closure.reason or "Practice closed (holiday)."
        return None, None, reason

    day_hours = {row.day_of_week: row for row in hours}.get(target.weekday())
    if not day_hours or day_hours.is_closed:
        return None, None, "Practice closed."
    if not day_hours.start_time or not day_hours.end_time:
        return None, None, "Practice hours not configured."
    return day_hours.start_time, day_hours.end_time, None


def validate_appointment_window(
    starts_at: datetime,
    ends_at: datetime,
    hours: list[PracticeHour],
    closures: list[PracticeClosure],
    overrides: list[PracticeOverride],
) -> tuple[bool, str | None]:
    if ends_at <= starts_at:
        return False, "Appointment end time must be after start time."

    start_local = starts_at.astimezone(LOCAL_TZ)
    end_local = ends_at.astimezone(LOCAL_TZ)
    if start_local.date() != end_local.date():
        return False, "Appointments must start and end on the same day."

    day_start, day_end, reason = get_practice_window(start_local.date(), hours, closures, overrides)
    if not day_start or not day_end:
        return False, reason or "Practice closed."

    if start_local.time() < day_start or end_local.time() > day_end:
        return False, "Appointment falls outside practice hours."

    return True, None

