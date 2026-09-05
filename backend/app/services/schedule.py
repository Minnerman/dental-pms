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
    hours = list(db.scalars(select(PracticeHour).order_by(PracticeHour.day_of_week, PracticeHour.start_time, PracticeHour.id)))
    closures = list(db.scalars(select(PracticeClosure).order_by(PracticeClosure.start_date, PracticeClosure.end_date, PracticeClosure.id)))
    overrides = list(db.scalars(select(PracticeOverride).order_by(PracticeOverride.date, PracticeOverride.start_time, PracticeOverride.id)))
    return hours, closures, overrides


def _is_date_closed(target: date, closures: list[PracticeClosure]) -> PracticeClosure | None:
    for closure in closures:
        if closure.start_date <= target <= closure.end_date:
            return closure
    return None


def get_practice_sessions(
    target: date,
    hours: list[PracticeHour],
    closures: list[PracticeClosure],
    overrides: list[PracticeOverride],
) -> tuple[list[tuple[time, time]], str | None]:
    day_overrides = [item for item in overrides if item.date == target]
    if day_overrides:
        # Be conservative about old malformed/mixed data: a closed override
        # must not be hidden by row order or accidentally fall back to weekly hours.
        closed = next((item for item in day_overrides if item.is_closed), None)
        if closed:
            return [], closed.reason or "Practice closed (override)."
        return _open_sessions(day_overrides)

    closure = _is_date_closed(target, closures)
    if closure:
        reason = closure.reason or "Practice closed (holiday)."
        return [], reason

    day_hours = [row for row in hours if row.day_of_week == target.weekday()]
    if not day_hours or any(row.is_closed for row in day_hours):
        return [], "Practice closed."
    return _open_sessions(day_hours)


def _open_sessions(rows) -> tuple[list[tuple[time, time]], str | None]:
    if any(not row.start_time or not row.end_time or
           row.start_time.tzinfo is not None or row.end_time.tzinfo is not None or
           row.end_time <= row.start_time for row in rows):
        return [], "Practice hours not configured."
    sessions = sorted((row.start_time, row.end_time) for row in rows)
    if any(current[0] < previous[1] for previous, current in zip(sessions, sessions[1:])):
        return [], "Practice hours not configured."
    # Adjacent sessions have no closed gap and can cover a single appointment.
    merged: list[tuple[time, time]] = []
    for start, end in sessions:
        if merged and start == merged[-1][1]:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged, None


def get_practice_window(
    target: date,
    hours: list[PracticeHour],
    closures: list[PracticeClosure],
    overrides: list[PracticeOverride],
) -> tuple[time | None, time | None, str | None]:
    """Compatibility envelope for display only; session validation preserves gaps."""
    sessions, reason = get_practice_sessions(target, hours, closures, overrides)
    if not sessions:
        return None, None, reason
    return sessions[0][0], sessions[-1][1], None


def validate_appointment_window(
    starts_at: datetime,
    ends_at: datetime,
    hours: list[PracticeHour],
    closures: list[PracticeClosure],
    overrides: list[PracticeOverride],
) -> tuple[bool, str | None]:
    """Advisory hours classification, not an appointment authorisation gate."""
    if starts_at.tzinfo is None or starts_at.utcoffset() is None or ends_at.tzinfo is None or ends_at.utcoffset() is None:
        return False, "Appointment times must include a timezone."
    if ends_at <= starts_at:
        return False, "Appointment end time must be after start time."

    start_local = starts_at.astimezone(LOCAL_TZ)
    end_local = ends_at.astimezone(LOCAL_TZ)
    if start_local.date() != end_local.date():
        return False, "Appointments must start and end on the same day."

    sessions, reason = get_practice_sessions(start_local.date(), hours, closures, overrides)
    if not sessions:
        return False, reason or "Practice closed."

    if not any(start_local.time() >= day_start and end_local.time() <= day_end for day_start, day_end in sessions):
        return False, "Appointment falls outside practice hours."

    return True, None
