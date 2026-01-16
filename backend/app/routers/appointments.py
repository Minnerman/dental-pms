from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import get_current_user
from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.estimate import Estimate
from app.models.patient import CareSetting, Patient
from app.models.user import Role, User
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.schemas.audit_log import AuditLogOut
from app.schemas.estimate import EstimateOut
from app.services.audit import log_event, snapshot_model
from app.services.run_sheet_pdf import build_run_sheet_pdf
from app.services.schedule import load_schedule, validate_appointment_window

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("/range", response_model=list[AppointmentOut])
def list_appointments_range(
    start: date,
    end: date,
    location: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, time.min, tzinfo=timezone.utc)
    stmt = (
        select(Appointment)
        .where(Appointment.deleted_at.is_(None))
        .where(Appointment.starts_at >= start_dt, Appointment.starts_at < end_dt)
        .options(selectinload(Appointment.patient))
        .order_by(Appointment.starts_at.asc())
    )
    if location == "clinic":
        stmt = stmt.where(Appointment.location_type == AppointmentLocationType.clinic)
    elif location == "visit":
        stmt = stmt.where(Appointment.location_type == AppointmentLocationType.visit)
    return list(db.scalars(stmt))


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, payload.patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

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
    _user: User = Depends(get_current_user),
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

    if payload.starts_at is not None or payload.ends_at is not None:
        starts_at = payload.starts_at or appt.starts_at
        ends_at = payload.ends_at or appt.ends_at
        allow_outside = bool(payload.allow_outside_hours) and user.role == Role.superadmin
        if not allow_outside:
            hours, closures, overrides = load_schedule(db)
            ok, reason = validate_appointment_window(starts_at, ends_at, hours, closures, overrides)
            if not ok:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    before_data = snapshot_model(appt)
    if payload.starts_at is not None:
        appt.starts_at = payload.starts_at
    if payload.ends_at is not None:
        appt.ends_at = payload.ends_at
    if payload.status is not None:
        appt.status = payload.status
        if appt.status in (AppointmentStatus.cancelled, AppointmentStatus.no_show):
            if payload.cancel_reason is not None:
                appt.cancel_reason = payload.cancel_reason
            if not appt.cancelled_at:
                appt.cancelled_at = datetime.now(timezone.utc)
            appt.cancelled_by_user_id = user.id
        else:
            if payload.cancel_reason is not None:
                appt.cancel_reason = None
            appt.cancelled_at = None
            appt.cancelled_by_user_id = None
    if payload.clinician is not None:
        appt.clinician = payload.clinician
    if payload.clinician_user_id is not None:
        appt.clinician_user_id = payload.clinician_user_id
    if payload.appointment_type is not None:
        appt.appointment_type = payload.appointment_type
    if payload.location is not None:
        appt.location = payload.location
    if payload.location_type is not None:
        appt.location_type = payload.location_type
    if payload.location_text is not None:
        appt.location_text = payload.location_text
    if payload.is_domiciliary is not None:
        appt.is_domiciliary = payload.is_domiciliary
    if payload.visit_address is not None:
        appt.visit_address = payload.visit_address
    if payload.cancel_reason is not None and payload.status is None:
        appt.cancel_reason = payload.cancel_reason
    if payload.location_type is None and payload.is_domiciliary is not None:
        appt.location_type = (
            AppointmentLocationType.visit
            if appt.is_domiciliary
            else AppointmentLocationType.clinic
        )
    if payload.location_text is None and payload.visit_address is not None:
        appt.location_text = appt.visit_address
    if appt.location_type == AppointmentLocationType.visit:
        if not (appt.location_text or "").strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Visit address required")
        appt.is_domiciliary = True
        appt.visit_address = appt.location_text
    else:
        appt.is_domiciliary = False
        appt.visit_address = None
        appt.location_text = None
    appt.updated_by_user_id = user.id
    db.add(appt)
    log_event(
        db,
        actor=user,
        action="appointment.updated",
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
):
    end_date = end or date
    start_dt = datetime.combine(date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
    stmt = (
        select(Appointment)
        .where(Appointment.deleted_at.is_(None))
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
