from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.practice_schedule import PracticeClosure, PracticeHour, PracticeOverride
from app.models.practice_profile import PracticeProfile
from app.models.user import Role, User
from app.schemas.practice_profile import PracticeProfileOut, PracticeProfileUpdate
from app.schemas.practice_schedule import (
    PracticeClosureIn,
    PracticeHourIn,
    PracticeOverrideIn,
    PracticeScheduleOut,
    PracticeScheduleUpdate,
)
from app.services.schedule import load_schedule
from app.services.practice_profile import default_profile

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/schedule", response_model=PracticeScheduleOut)
def get_schedule(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    hours, closures, overrides = load_schedule(db)
    return {"hours": hours, "closures": closures, "overrides": overrides}


@router.get("/profile", response_model=PracticeProfileOut)
def get_practice_profile(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    profile = db.query(PracticeProfile).first()
    if profile:
        return profile
    defaults = default_profile()
    return PracticeProfileOut(id=None, **defaults)


def _validate_sessions(entries, key_name: str) -> None:
    grouped = {}
    for entry in entries:
        grouped.setdefault(getattr(entry, key_name), []).append(entry)
        if entry.is_closed:
            if entry.start_time is not None or entry.end_time is not None:
                raise HTTPException(status_code=400, detail="Closed days must not include session times")
            continue
        if not entry.start_time or not entry.end_time:
            raise HTTPException(status_code=400, detail="Open sessions require start_time and end_time")
        if entry.end_time <= entry.start_time:
            raise HTTPException(status_code=400, detail="end_time must be after start_time")
    for rows in grouped.values():
        if any(row.is_closed for row in rows) and len(rows) != 1:
            raise HTTPException(status_code=400, detail="A closed day cannot contain other sessions")
        sessions = sorted((row.start_time, row.end_time) for row in rows if not row.is_closed)
        if any(current[0] < previous[1] for previous, current in zip(sessions, sessions[1:])):
            raise HTTPException(status_code=400, detail="Sessions must not overlap or duplicate one another")


def _validate_hours(entries: list[PracticeHourIn]) -> None:
    _validate_sessions(entries, "day_of_week")


def _validate_closures(entries: list[PracticeClosureIn]) -> None:
    for entry in entries:
        if entry.end_date < entry.start_date:
            raise HTTPException(status_code=400, detail="Closure end_date must be after start_date")
    ranges = sorted((entry.start_date, entry.end_date) for entry in entries)
    if any(current[0] <= previous[1] for previous, current in zip(ranges, ranges[1:])):
        raise HTTPException(status_code=400, detail="Closure date ranges must not overlap or duplicate one another")


def _validate_overrides(entries: list[PracticeOverrideIn]) -> None:
    _validate_sessions(entries, "date")


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


@router.put("/profile", response_model=PracticeProfileOut)
def update_practice_profile(
    payload: PracticeProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != Role.superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    profile = db.query(PracticeProfile).first()
    if not profile:
        profile = PracticeProfile()
        db.add(profile)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
