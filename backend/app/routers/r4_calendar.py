from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import aliased, Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.patient import Patient
from app.models.r4_appointment import R4Appointment
from app.models.r4_appointment_patient_link import R4AppointmentPatientLink
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
LOCAL_TZ = ZoneInfo("Europe/London")


class CalendarItem(BaseModel):
    legacy_appointment_id: int
    starts_at: datetime
    ends_at: datetime | None = None
    duration_minutes: int | None = None
    status_normalised: str | None = None
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


class AppointmentLinkRequest(BaseModel):
    patient_id: int


class AppointmentLinkResponse(BaseModel):
    id: int
    legacy_source: str
    legacy_appointment_id: int
    patient_id: int
    linked_by_user_id: int
    linked_at: datetime


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


def _parse_status_values(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    parsed: list[str] = []
    for value in values:
        if not value:
            continue
        parts = [chunk.strip() for chunk in value.split(",")]
        for chunk in parts:
            if chunk:
                parsed.append(chunk)
    normalized = [normalize_status(value) for value in parsed]
    return [value for value in normalized if value]


def _patient_name(patient: Patient | None) -> str | None:
    if not patient:
        return None
    name = " ".join(filter(None, [patient.first_name, patient.last_name])).strip()
    return name or None


def _resolve_patient_display(
    linked_patient: Patient | None, code_patient: Patient | None
) -> dict[str, object]:
    patient = linked_patient or code_patient
    name = _patient_name(patient)
    if patient and name:
        return {
            "patient_id": patient.id,
            "patient_display_name": name,
            "is_unlinked": False,
        }
    return {"patient_id": None, "patient_display_name": "Unlinked", "is_unlinked": True}


def _apply_filters(
    stmt,
    resolved_patient_id,
    status_expr,
    from_dt,
    to_dt,
    clinician_code,
    show_hidden,
    show_unlinked,
    unlinked_only,
    linked_only,
    include_statuses,
    exclude_statuses,
):
    stmt = stmt.where(R4Appointment.starts_at >= from_dt, R4Appointment.starts_at < to_dt)
    if clinician_code:
        stmt = stmt.where(R4Appointment.clinician_code == clinician_code)
    if include_statuses:
        stmt = stmt.where(status_expr.in_(include_statuses))
    if exclude_statuses:
        stmt = stmt.where(~status_expr.in_(exclude_statuses))
    if unlinked_only and linked_only:
        raise HTTPException(
            status_code=400, detail="`unlinked_only` and `linked_only` cannot both be true"
        )
    if unlinked_only:
        stmt = stmt.where(resolved_patient_id.is_(None))
    elif linked_only:
        stmt = stmt.where(resolved_patient_id.is_not(None))
    elif not show_unlinked:
        stmt = stmt.where(resolved_patient_id.is_not(None))
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
    unlinked_only: bool = Query(default=False),
    linked_only: bool = Query(default=False),
    statuses: list[str] | None = Query(default=None),
    exclude_statuses: list[str] | None = Query(default=None),
    include_total: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
):
    parsed_from = _parse_date(from_date, "from")
    parsed_to = _parse_date(to_date, "to")
    if parsed_to < parsed_from:
        raise HTTPException(status_code=400, detail="`to` must be on or after `from`")
    from_local = datetime.combine(parsed_from, time.min, tzinfo=LOCAL_TZ)
    to_local = datetime.combine(parsed_to + timedelta(days=1), time.min, tzinfo=LOCAL_TZ)
    from_dt = from_local.astimezone(timezone.utc)
    to_dt = to_local.astimezone(timezone.utc)

    link_alias = aliased(R4AppointmentPatientLink)
    linked_patient = aliased(Patient)
    code_patient = aliased(Patient)
    status_expr = _build_status_expression()
    include_statuses = _parse_status_values(statuses)
    exclude_statuses = _parse_status_values(exclude_statuses)
    if not include_statuses and not show_hidden:
        include_statuses = list(DEFAULT_VISIBLE_STATUSES)

    join_condition = code_patient.legacy_id == cast(R4Appointment.patient_code, String)
    resolved_patient_id = func.coalesce(linked_patient.id, code_patient.id)

    base_stmt = (
        select(R4Appointment)
        .outerjoin(
            link_alias,
            (link_alias.legacy_source == R4Appointment.legacy_source)
            & (link_alias.legacy_appointment_id == R4Appointment.legacy_appointment_id),
        )
        .outerjoin(linked_patient, linked_patient.id == link_alias.patient_id)
        .outerjoin(code_patient, join_condition)
    )
    base_stmt = _apply_filters(
        base_stmt,
        resolved_patient_id,
        status_expr,
        from_dt,
        to_dt,
        clinician_code,
        show_hidden,
        show_unlinked,
        unlinked_only,
        linked_only,
        include_statuses,
        exclude_statuses,
    )

    total_count: int | None = None
    if include_total:
        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = int(db.scalar(total_stmt) or 0)

    data_stmt = (
        select(R4Appointment, linked_patient, code_patient, R4User)
        .outerjoin(
            link_alias,
            (link_alias.legacy_source == R4Appointment.legacy_source)
            & (link_alias.legacy_appointment_id == R4Appointment.legacy_appointment_id),
        )
        .outerjoin(linked_patient, linked_patient.id == link_alias.patient_id)
        .outerjoin(code_patient, join_condition)
        .outerjoin(R4User, R4User.legacy_user_code == R4Appointment.clinician_code)
    )
    data_stmt = _apply_filters(
        data_stmt,
        resolved_patient_id,
        status_expr,
        from_dt,
        to_dt,
        clinician_code,
        show_hidden,
        show_unlinked,
        unlinked_only,
        linked_only,
        include_statuses,
        exclude_statuses,
    )
    data_stmt = (
        data_stmt.order_by(R4Appointment.starts_at.asc(), R4Appointment.legacy_appointment_id.asc())
        .limit(limit)
    )

    rows = db.execute(data_stmt).all()

    items: List[CalendarItem] = []
    for appointment, linked_patient_row, code_patient_row, clinician in rows:
        patient_payload = _resolve_patient_display(linked_patient_row, code_patient_row)
        item = CalendarItem(
            legacy_appointment_id=appointment.legacy_appointment_id,
            starts_at=appointment.starts_at,
            ends_at=appointment.ends_at,
            duration_minutes=appointment.duration_minutes,
            status_normalised=normalize_status(appointment.status),
            status_raw=appointment.status,
            clinician_code=appointment.clinician_code,
            clinician_name=_clinician_name(clinician),
            clinician_role=clinician.role if clinician else None,
            clinician_is_current=clinician.is_current if clinician else None,
            patient_id=patient_payload["patient_id"],
            patient_display_name=patient_payload["patient_display_name"],
            is_unlinked=patient_payload["is_unlinked"],
            title=appointment.appointment_type,
            notes=appointment.notes,
        )
        items.append(item)

    response = {"items": items}
    if include_total:
        response["total_count"] = total_count
    return response


@router.post("/{legacy_appointment_id}/link", response_model=AppointmentLinkResponse)
def link_r4_appointment(
    *,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    legacy_appointment_id: int,
    payload: AppointmentLinkRequest,
):
    appointment = db.scalar(
        select(R4Appointment).where(
            R4Appointment.legacy_source == "r4",
            R4Appointment.legacy_appointment_id == legacy_appointment_id,
        )
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    patient = db.get(Patient, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    link = db.scalar(
        select(R4AppointmentPatientLink).where(
            R4AppointmentPatientLink.legacy_source == appointment.legacy_source,
            R4AppointmentPatientLink.legacy_appointment_id
            == appointment.legacy_appointment_id,
        )
    )
    now = datetime.now(timezone.utc)
    if link:
        if link.patient_id == payload.patient_id:
            return link
        link.patient_id = payload.patient_id
        link.linked_by_user_id = user.id
        link.linked_at = now
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    link = R4AppointmentPatientLink(
        legacy_source=appointment.legacy_source,
        legacy_appointment_id=appointment.legacy_appointment_id,
        patient_id=payload.patient_id,
        linked_by_user_id=user.id,
        linked_at=now,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
