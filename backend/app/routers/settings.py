from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.practice_schedule import PracticeClosure, PracticeHour, PracticeOverride
from app.models.user import Role, User
from app.schemas.practice_schedule import (
    PracticeClosureIn,
    PracticeHourIn,
    PracticeOverrideIn,
    PracticeScheduleOut,
    PracticeScheduleUpdate,
)
from app.services.schedule import load_schedule

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/schedule", response_model=PracticeScheduleOut)
def get_schedule(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    hours, closures, overrides = load_schedule(db)
    return {"hours": hours, "closures": closures, "overrides": overrides}


def _validate_hours(entries: list[PracticeHourIn]) -> None:
    for entry in entries:
        if entry.day_of_week < 0 or entry.day_of_week > 6:
            raise HTTPException(status_code=400, detail="day_of_week must be 0-6")
        if entry.is_closed:
            continue
        if not entry.start_time or not entry.end_time:
            raise HTTPException(status_code=400, detail="Open days require start_time and end_time")
        if entry.end_time <= entry.start_time:
            raise HTTPException(status_code=400, detail="end_time must be after start_time")


def _validate_closures(entries: list[PracticeClosureIn]) -> None:
    for entry in entries:
        if entry.end_date < entry.start_date:
            raise HTTPException(status_code=400, detail="Closure end_date must be after start_date")


def _validate_overrides(entries: list[PracticeOverrideIn]) -> None:
    for entry in entries:
        if entry.is_closed:
            continue
        if entry.start_time and entry.end_time and entry.end_time <= entry.start_time:
            raise HTTPException(status_code=400, detail="Override end_time must be after start_time")


@router.put("/schedule", response_model=PracticeScheduleOut)
def update_schedule(
    payload: PracticeScheduleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != Role.superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    _validate_hours(payload.hours)
    _validate_closures(payload.closures)
    _validate_overrides(payload.overrides)

    db.execute(delete(PracticeHour))
    db.execute(delete(PracticeClosure))
    db.execute(delete(PracticeOverride))

    for entry in payload.hours:
        db.add(
            PracticeHour(
                day_of_week=entry.day_of_week,
                start_time=None if entry.is_closed else entry.start_time,
                end_time=None if entry.is_closed else entry.end_time,
                is_closed=entry.is_closed,
            )
        )
    for entry in payload.closures:
        db.add(
            PracticeClosure(
                start_date=entry.start_date,
                end_date=entry.end_date,
                reason=entry.reason,
            )
        )
    for entry in payload.overrides:
        db.add(
            PracticeOverride(
                date=entry.date,
                start_time=None if entry.is_closed else entry.start_time,
                end_time=None if entry.is_closed else entry.end_time,
                is_closed=entry.is_closed,
                reason=entry.reason,
            )
        )
    db.commit()

    hours, closures, overrides = load_schedule(db)
    return {"hours": hours, "closures": closures, "overrides": overrides}
