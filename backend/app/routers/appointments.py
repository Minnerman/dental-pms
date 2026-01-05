from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.patient import Patient
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentOut
from app.schemas.audit_log import AuditLogOut
from app.services.audit import log_event, snapshot_model

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    patient_id: int | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    include_deleted: bool = Query(default=False),
):
    stmt = select(Appointment).order_by(Appointment.starts_at.desc())
    if not include_deleted:
        stmt = stmt.where(Appointment.deleted_at.is_(None))
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    if from_dt:
        stmt = stmt.where(Appointment.starts_at >= from_dt)
    if to_dt:
        stmt = stmt.where(Appointment.starts_at <= to_dt)
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

    appt = Appointment(
        patient_id=payload.patient_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        status=payload.status,
        clinician=payload.clinician,
        location=payload.location,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(appt)
    db.flush()
    log_event(
        db,
        actor=user,
        action="create",
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
        action="delete",
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
        action="restore",
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
