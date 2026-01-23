from datetime import date, datetime, time, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import aliased, Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.patient import Patient
from app.models.r4_appointment import R4Appointment
from app.models.r4_user import R4User
from app.services.r4_import.status import normalize_status

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

DEFAULT_VISIBLE_STATUSES = {
    "pending",
    "checked-in",
    "checked in",
    "arrived",
    "did not attend",
    "dna",
}


class CalendarItem(BaseModel):
    legacy_appointment_id: int
    starts_at: datetime
    ends_at: datetime | None = None
    duration_minutes: int | None = None
    status: str | None = None
    status_raw: str | None = None
    clinician_code: int | None = None
    clinician_name: str | None = None
    clinician_role: str | None = None
    clinician_is_current: bool | None = None
    patient_id: int | None = None
    patient_display_name: str | None = None
    is_unlinked: bool
    title: str | None = None
    notes: str | None = None


class CalendarList(BaseModel):
    items: List[CalendarItem]
    total_count: int | None = None


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} must be YYYY-MM-DD")


def _build_status_expression():
    return func.lower(
        func.trim(
            func.regexp_replace(
                func.coalesce(R4Appointment.status, ""),
                r"\\s+",
                " ",
                "g",
            )
        )
    )


def _clinician_name(user: R4User | None) -> str | None:
    if not user:
        return None
    if user.display_name:
        return user.display_name
    if user.full_name:
        return user.full_name
    names = " ".join(filter(None, [user.forename, user.surname])).strip()
    return names or None


def _apply_filters(
    stmt,
    patient_alias,
    status_expr,
    from_dt,
    to_dt,
    clinician_code,
    show_hidden,
    show_unlinked,
):
    stmt = stmt.where(R4Appointment.starts_at >= from_dt, R4Appointment.starts_at < to_dt)
    if clinician_code:
        stmt = stmt.where(R4Appointment.clinician_code == clinician_code)
    if not show_hidden:
        stmt = stmt.where(status_expr.in_(DEFAULT_VISIBLE_STATUSES))
    if not show_unlinked:
        stmt = stmt.where(patient_alias.id.is_not(None))
    return stmt


@router.get("", response_model=CalendarList)
def list_r4_calendar(
    *,
    db: Session = Depends(get_db),
    _user: object = Depends(get_current_user),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    clinician_code: int | None = Query(default=None),
    show_hidden: bool = Query(default=False),
    show_unlinked: bool = Query(default=False),
    include_total: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
):
    parsed_from = _parse_date(from_date, "from")
    parsed_to = _parse_date(to_date, "to")
    if parsed_to < parsed_from:
        raise HTTPException(status_code=400, detail="`to` must be on or after `from`")
    from_dt = datetime.combine(parsed_from, time.min, tzinfo=timezone.utc)
    to_dt = datetime.combine(parsed_to + timedelta(days=1), time.min, tzinfo=timezone.utc)

    patient_alias = aliased(Patient)
    status_expr = _build_status_expression()

    join_condition = patient_alias.legacy_id == cast(R4Appointment.patient_code, String)

    base_stmt = (
        select(R4Appointment)
        .outerjoin(patient_alias, join_condition)
    )
    base_stmt = _apply_filters(
        base_stmt,
        patient_alias,
        status_expr,
        from_dt,
        to_dt,
        clinician_code,
        show_hidden,
        show_unlinked,
    )

    total_count: int | None = None
    if include_total:
        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = int(db.scalar(total_stmt) or 0)

    data_stmt = (
        select(R4Appointment, patient_alias, R4User)
        .outerjoin(patient_alias, join_condition)
        .outerjoin(R4User, R4User.legacy_user_code == R4Appointment.clinician_code)
    )
    data_stmt = _apply_filters(
        data_stmt,
        patient_alias,
        status_expr,
        from_dt,
        to_dt,
        clinician_code,
        show_hidden,
        show_unlinked,
    )
    data_stmt = (
        data_stmt.order_by(R4Appointment.starts_at.asc(), R4Appointment.legacy_appointment_id.asc())
        .limit(limit)
    )

    rows = db.execute(data_stmt).all()

    items: List[CalendarItem] = []
    for appointment, patient, clinician in rows:
        patient_id = patient.id if patient else None
        patient_name = None
        if patient:
            patient_name = " ".join(
                filter(None, [patient.first_name, patient.last_name])
            ).strip()
        is_unlinked = patient_id is None
        item = CalendarItem(
            legacy_appointment_id=appointment.legacy_appointment_id,
            starts_at=appointment.starts_at,
            ends_at=appointment.ends_at,
            duration_minutes=appointment.duration_minutes,
            status=normalize_status(appointment.status),
            status_raw=appointment.status,
            clinician_code=appointment.clinician_code,
            clinician_name=_clinician_name(clinician),
            clinician_role=clinician.role if clinician else None,
            clinician_is_current=clinician.is_current if clinician else None,
            patient_id=patient_id,
            patient_display_name=patient_name or None,
            is_unlinked=is_unlinked,
            title=appointment.appointment_type,
            notes=appointment.notes,
        )
        items.append(item)

    response = {"items": items}
    if include_total:
        response["total_count"] = total_count
    return response
