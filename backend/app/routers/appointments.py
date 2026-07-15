from datetime import date, datetime, time, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import get_current_user, require_capability
from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.estimate import Estimate
from app.models.patient import CareSetting, Patient
from app.models.user import Role, User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    DiarySnapshotOut,
)
from app.schemas.audit_log import AuditLogOut
from app.schemas.estimate import EstimateOut
from app.services.appointments_snapshot import build_appointments_snapshot
from app.services.audit import log_event, snapshot_model
from app.services.capabilities import get_user_capabilities
from app.services.run_sheet_pdf import build_run_sheet_pdf
from app.services.schedule import LOCAL_TZ, load_schedule, validate_appointment_window

router = APIRouter(prefix="/appointments", tags=["appointments"])


def find_conflicting_appointments(
    db: Session,
    clinician_user_id: int | None,
    starts_at: datetime,
    ends_at: datetime,
    location_type: AppointmentLocationType | None = None,
    location: str | None = None,
    exclude_id: int | None = None,
) -> list[Appointment]:
    resource_filters = []
    if clinician_user_id:
        resource_filters.append(Appointment.clinician_user_id == clinician_user_id)
    normalized_location = (location or "").strip().lower()
    if location_type == AppointmentLocationType.clinic and normalized_location:
        resource_filters.append(
            func.lower(func.trim(Appointment.location)) == normalized_location
        )
    if not resource_filters:
        return []
    stmt = (
        select(Appointment)
        .where(Appointment.deleted_at.is_(None))
        .where(or_(*resource_filters))
        .where(Appointment.starts_at < ends_at, Appointment.ends_at > starts_at)
        .where(Appointment.status.notin_([AppointmentStatus.cancelled, AppointmentStatus.no_show]))
        .options(selectinload(Appointment.patient))
    )
    if exclude_id is not None:
        stmt = stmt.where(Appointment.id != exclude_id)
    return list(db.scalars(stmt))


def _require_user_capabilities(db: Session, user: User, *codes: str) -> None:
    available = {capability.code for capability in get_user_capabilities(db, user.id)}
    if any(code not in available for code in codes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _validate_basic_appointment_window(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment start time must include a timezone.",
        )
    if ends_at.tzinfo is None or ends_at.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment end time must include a timezone.",
        )
    if ends_at <= starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment end time must be after start time.",
        )
    if starts_at.astimezone(LOCAL_TZ).date() != ends_at.astimezone(LOCAL_TZ).date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointments must start and end on the same day.",
        )


def _target_value(payload: AppointmentUpdate, field: str, current):
    if field not in payload.model_fields_set:
        return current
    value = getattr(payload, field)
    if value is None and field in {"starts_at", "ends_at", "status", "location_type"}:
        return current
    return value


def _update_capability_codes(
    appointment: Appointment,
    payload: AppointmentUpdate,
) -> set[str]:
    fields = payload.model_fields_set
    target_status = _target_value(payload, "status", appointment.status)
    required: set[str] = set()

    reschedule_fields = {
        "starts_at",
        "ends_at",
        "clinician_user_id",
        "location",
        "location_type",
        "location_text",
        "is_domiciliary",
        "visit_address",
    }
    if any(
        field in fields
        and _target_value(payload, field, getattr(appointment, field))
        != getattr(appointment, field)
        for field in reschedule_fields
    ):
        required.add("appointments.reschedule")

    status_changed = target_status != appointment.status
    cancel_reason_changed = (
        "cancel_reason" in fields and payload.cancel_reason != appointment.cancel_reason
    )
    if target_status in {AppointmentStatus.cancelled, AppointmentStatus.no_show} and (
        status_changed or cancel_reason_changed
    ):
        required.add("appointments.cancel")
    elif status_changed or cancel_reason_changed:
        required.add("appointments.write")

    general_fields = {"appointment_type", "clinician"}
    if any(
        field in fields and getattr(payload, field) != getattr(appointment, field)
        for field in general_fields
    ):
        required.add("appointments.write")

    if not required:
        required.add("appointments.write")
    return required


def conflict_response(conflicts: list[Appointment]) -> JSONResponse:
    items = []
    for appt in conflicts:
        patient_name = ""
        if appt.patient:
            patient_name = f"{appt.patient.first_name} {appt.patient.last_name}".strip()
        items.append(
            {
                "id": appt.id,
                "starts_at": appt.starts_at.isoformat(),
                "ends_at": appt.ends_at.isoformat(),
                "patient_name": patient_name or "Another patient",
                "location": appt.location_text or appt.location or None,
                "location_type": appt.location_type.value if appt.location_type else None,
            }
        )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "Appointment overlaps with an existing booking.",
            "conflicts": items,
        },
    )


@router.get("/range", response_model=list[AppointmentOut])
def list_appointments_range(
    start: date,
    end: date,
    location: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("appointments.view")),
):
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, time.min, tzinfo=timezone.utc)
    stmt = (
        select(Appointment)
        .where(Appointment.deleted_at.is_(None))
        .where(Appointment.patient_id.is_not(None))
        .where(Appointment.starts_at >= start_dt, Appointment.starts_at < end_dt)
        .options(selectinload(Appointment.patient))
        .order_by(Appointment.starts_at.asc())
    )
    if location == "clinic":
        stmt = stmt.where(Appointment.location_type == AppointmentLocationType.clinic)
    elif location == "visit":
        stmt = stmt.where(Appointment.location_type == AppointmentLocationType.visit)
    return list(db.scalars(stmt))


@router.get("/snapshot", response_model=DiarySnapshotOut)
def appointments_snapshot(
    snapshot_date: date = Query(..., alias="date"),
    view: Literal["day", "week"] = Query(default="day"),
    mask_names: bool = Query(default=True),
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("appointments.view")),
):
    return build_appointments_snapshot(
        db,
        anchor_date=snapshot_date,
        view=view,
        mask_names=mask_names,
    )


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("appointments.view")),
    patient_id: int | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    date_filter: date | None = Query(default=None, alias="date"),
    _view: str | None = Query(default=None, alias="view"),
    q: str | None = Query(default=None),
    domiciliary: bool | None = Query(default=None),
    location_type: AppointmentLocationType | None = Query(default=None),
    include_deleted: bool = Query(default=False),
):
    stmt = select(Appointment)
    if q:
        q_like = f"%{q.strip().lower()}%"
        stmt = stmt.join(Patient).where(
            or_(
                Patient.first_name.ilike(q_like),
                Patient.last_name.ilike(q_like),
                (Patient.first_name + " " + Patient.last_name).ilike(q_like),
            )
        )
    stmt = stmt.order_by(Appointment.starts_at.desc())
    if not include_deleted:
        stmt = stmt.where(Appointment.deleted_at.is_(None))
    stmt = stmt.where(Appointment.patient_id.is_not(None))
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    if date_filter and not (from_dt or to_dt):
        day_start = datetime.combine(date_filter, time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(date_filter, time.max, tzinfo=timezone.utc)
        from_dt = day_start
        to_dt = day_end
    if from_dt:
        stmt = stmt.where(Appointment.starts_at >= from_dt)
    if to_dt:
        stmt = stmt.where(Appointment.starts_at <= to_dt)
    if domiciliary is not None:
        stmt = stmt.where(Appointment.is_domiciliary == domiciliary)
    if location_type is not None:
        stmt = stmt.where(Appointment.location_type == location_type)
    return list(db.scalars(stmt))


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("appointments.write")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, payload.patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if payload.clinician_user_id is not None:
        clinician = db.get(User, payload.clinician_user_id)
        if not clinician or not clinician.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clinician not found",
            )

    _validate_basic_appointment_window(payload.starts_at, payload.ends_at)

    location_type = payload.location_type
    if location_type is None:
        if payload.is_domiciliary is not None:
            location_type = (
                AppointmentLocationType.visit
                if payload.is_domiciliary
                else AppointmentLocationType.clinic
            )
        elif patient.care_setting != CareSetting.clinic:
            location_type = AppointmentLocationType.visit
        else:
            location_type = AppointmentLocationType.clinic

    location_text = payload.location_text
    if not location_text:
        location_text = payload.visit_address or payload.location
    if location_type == AppointmentLocationType.visit and not (location_text or "").strip():
        location_text = patient.visit_address_text

    allow_outside = bool(payload.allow_outside_hours) and user.role == Role.superadmin
    if not allow_outside:
        hours, closures, overrides = load_schedule(db)
        ok, reason = validate_appointment_window(payload.starts_at, payload.ends_at, hours, closures, overrides)
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    appt = Appointment(
        patient_id=payload.patient_id,
        clinician_user_id=payload.clinician_user_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        status=payload.status or AppointmentStatus.booked,
        appointment_type=payload.appointment_type,
        clinician=payload.clinician,
        location=payload.location,
        location_type=location_type,
        location_text=location_text,
        is_domiciliary=location_type == AppointmentLocationType.visit,
        visit_address=location_text if location_type == AppointmentLocationType.visit else None,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    if appt.location_type == AppointmentLocationType.visit and not (appt.location_text or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Visit address required")
    if appt.location_type == AppointmentLocationType.clinic:
        appt.location_text = None
        appt.visit_address = None
        appt.is_domiciliary = False
    db.add(appt)
    db.flush()
    log_event(
        db,
        actor=user,
        action="appointment.created",
        entity_type="appointment",
        entity_id=str(appt.id),
        before_obj=None,
        after_obj=appt,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(appt)
    return appt


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("appointments.view")),
):
    appt = db.get(Appointment, appointment_id)
    if not appt or appt.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appt


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    appt = db.get(Appointment, appointment_id)
    if not appt or appt.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    required_capabilities = _update_capability_codes(appt, payload)
    _require_user_capabilities(db, user, *sorted(required_capabilities))

    fields = payload.model_fields_set
    starts_at = _target_value(payload, "starts_at", appt.starts_at)
    ends_at = _target_value(payload, "ends_at", appt.ends_at)
    target_status = _target_value(payload, "status", appt.status)
    target_clinician_user_id = _target_value(
        payload,
        "clinician_user_id",
        appt.clinician_user_id,
    )
    target_location_type = _target_value(
        payload,
        "location_type",
        appt.location_type,
    )
    target_location = _target_value(payload, "location", appt.location)
    target_location_text = _target_value(
        payload,
        "location_text",
        appt.location_text,
    )
    if "location_type" not in fields and "is_domiciliary" in fields:
        target_location_type = (
            AppointmentLocationType.visit
            if payload.is_domiciliary
            else AppointmentLocationType.clinic
        )
    if "location_text" not in fields and "visit_address" in fields:
        target_location_text = payload.visit_address

    if "clinician_user_id" in fields and target_clinician_user_id is not None:
        clinician = db.get(User, target_clinician_user_id)
        if not clinician or not clinician.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clinician not found",
            )

    if "starts_at" in fields or "ends_at" in fields:
        _validate_basic_appointment_window(starts_at, ends_at)
        allow_outside = bool(payload.allow_outside_hours) and user.role == Role.superadmin
        if not allow_outside:
            hours, closures, overrides = load_schedule(db)
            ok, reason = validate_appointment_window(starts_at, ends_at, hours, closures, overrides)
            if not ok:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    target_cancel_reason = (
        payload.cancel_reason if "cancel_reason" in fields else appt.cancel_reason
    )
    if target_status == AppointmentStatus.cancelled and not (
        target_cancel_reason or ""
    ).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cancellation reason is required.",
        )

    reschedule_fields = {
        "starts_at",
        "ends_at",
        "clinician_user_id",
        "location",
        "location_type",
        "location_text",
        "is_domiciliary",
        "visit_address",
    }
    reschedule_changed = any(
        field in fields
        and _target_value(payload, field, getattr(appt, field)) != getattr(appt, field)
        for field in reschedule_fields
    )
    if reschedule_changed and target_status not in {
        AppointmentStatus.cancelled,
        AppointmentStatus.no_show,
    }:
        conflicts = find_conflicting_appointments(
            db,
            target_clinician_user_id,
            starts_at,
            ends_at,
            location_type=target_location_type,
            location=target_location,
            exclude_id=appt.id,
        )
        if conflicts:
            return conflict_response(conflicts)

    before_data = snapshot_model(appt)
    previous_status = appt.status
    if "starts_at" in fields:
        appt.starts_at = starts_at
    if "ends_at" in fields:
        appt.ends_at = ends_at
    if "clinician" in fields:
        appt.clinician = payload.clinician
    if "clinician_user_id" in fields:
        appt.clinician_user_id = target_clinician_user_id
    if "appointment_type" in fields:
        appt.appointment_type = payload.appointment_type

    location_fields = {
        "location",
        "location_type",
        "location_text",
        "is_domiciliary",
        "visit_address",
    }
    location_changed = bool(fields & location_fields)
    if location_changed:
        appt.location = target_location
        appt.location_type = target_location_type
        appt.location_text = target_location_text
        if appt.location_type == AppointmentLocationType.visit:
            if not (appt.location_text or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Visit address required",
                )
            appt.is_domiciliary = True
            appt.visit_address = appt.location_text
        else:
            appt.is_domiciliary = False
            appt.visit_address = None
            appt.location_text = None

    if "status" in fields:
        appt.status = target_status
    if "status" in fields or "cancel_reason" in fields:
        if target_status in {AppointmentStatus.cancelled, AppointmentStatus.no_show}:
            appt.cancel_reason = target_cancel_reason
            if previous_status != target_status or not appt.cancelled_at:
                appt.cancelled_at = datetime.now(timezone.utc)
                appt.cancelled_by_user_id = user.id
        else:
            appt.cancel_reason = None
            appt.cancelled_at = None
            appt.cancelled_by_user_id = None

    if appt.location_type == AppointmentLocationType.visit and not (
        appt.location_text or ""
    ).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visit address required",
        )

    if target_status == AppointmentStatus.cancelled and previous_status != target_status:
        audit_action = "appointment.cancelled"
    elif target_status == AppointmentStatus.no_show and previous_status != target_status:
        audit_action = "appointment.no_show_recorded"
    elif reschedule_changed:
        audit_action = "appointment.rescheduled"
    else:
        audit_action = "appointment.updated"
    appt.updated_by_user_id = user.id
    db.add(appt)
    log_event(
        db,
        actor=user,
        action=audit_action,
        entity_type="appointment",
        entity_id=str(appt.id),
        before_data=before_data,
        after_obj=appt,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/archive", response_model=AppointmentOut)
def archive_appointment(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("appointments.write")),
    request_id: str | None = Header(default=None),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    if appt.deleted_at is not None:
        return appt

    before_data = snapshot_model(appt)
    appt.deleted_at = datetime.now(timezone.utc)
    appt.deleted_by_user_id = user.id
    appt.updated_by_user_id = user.id
    db.add(appt)
    log_event(
        db,
        actor=user,
        action="appointment.archived",
        entity_type="appointment",
        entity_id=str(appt.id),
        before_data=before_data,
        after_obj=appt,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/restore", response_model=AppointmentOut)
def restore_appointment(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("appointments.write")),
    request_id: str | None = Header(default=None),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    if appt.deleted_at is None:
        return appt

    before_data = snapshot_model(appt)
    appt.deleted_at = None
    appt.deleted_by_user_id = None
    appt.updated_by_user_id = user.id
    db.add(appt)
    log_event(
        db,
        actor=user,
        action="appointment.restored",
        entity_type="appointment",
        entity_id=str(appt.id),
        before_data=before_data,
        after_obj=appt,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(appt)
    return appt


@router.get("/{appointment_id}/audit", response_model=list[AuditLogOut])
def appointment_audit(
    appointment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("appointments.view")),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(AuditLog)
        .where(
            AuditLog.entity_type == "appointment",
            AuditLog.entity_id == str(appointment_id),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


@router.get("/{appointment_id}/estimates", response_model=list[EstimateOut])
def appointment_estimates(
    appointment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("appointments.view")),
):
    appt = db.get(Appointment, appointment_id)
    if not appt or appt.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    stmt = select(Estimate).where(Estimate.appointment_id == appointment_id)
    return list(db.scalars(stmt))


@router.post("/{appointment_id}/attach-estimate/{estimate_id}", response_model=EstimateOut)
def attach_estimate_to_appointment(
    appointment_id: int,
    estimate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("appointments.write")),
    request_id: str | None = Header(default=None),
):
    appt = db.get(Appointment, appointment_id)
    if not appt or appt.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    estimate = db.get(Estimate, estimate_id)
    if not estimate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found")
    if estimate.patient_id != appt.patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estimate does not belong to appointment patient",
        )
    estimate.appointment_id = appointment_id
    estimate.updated_by_user_id = user.id
    db.add(estimate)
    log_event(
        db,
        actor=user,
        action="estimate.attached_to_appointment",
        entity_type="estimate",
        entity_id=str(estimate.id),
        before_obj=None,
        after_obj=estimate,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(estimate)
    return estimate


@router.get("/run-sheet.pdf")
def get_run_sheet_pdf(
    date: date,
    end: date | None = Query(default=None),
    location: str | None = Query(default="visit"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("appointments.view")),
):
    end_date = end or date
    start_dt = datetime.combine(date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
    stmt = (
        select(Appointment)
        .where(Appointment.deleted_at.is_(None))
        .where(Appointment.patient_id.is_not(None))
        .where(Appointment.starts_at >= start_dt, Appointment.starts_at <= end_dt)
        .options(selectinload(Appointment.patient), selectinload(Appointment.estimates))
        .order_by(Appointment.starts_at.asc())
    )
    if location == "clinic":
        stmt = stmt.where(Appointment.location_type == AppointmentLocationType.clinic)
    elif location == "visit":
        stmt = stmt.where(Appointment.location_type == AppointmentLocationType.visit)

    appointments = list(db.scalars(stmt))
    pdf_bytes = build_run_sheet_pdf(appointments, date, end_date)
    headers = {"Content-Disposition": 'attachment; filename="run-sheet.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
