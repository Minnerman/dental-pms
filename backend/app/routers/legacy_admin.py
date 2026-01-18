from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_admin
from app.models.appointment import Appointment
from app.models.legacy_resolution_event import LegacyResolutionEvent
from app.models.patient import Patient
from app.models.user import User
from app.schemas.legacy_admin import (
    LegacyResolveRequest,
    LegacyResolveResponse,
    UnmappedLegacyAppointmentList,
)

router = APIRouter(prefix="/admin/legacy", tags=["legacy-admin"])


@router.get("/unmapped-appointments", response_model=UnmappedLegacyAppointmentList)
def list_unmapped_appointments(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    legacy_source: str | None = Query(default="r4"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="starts_at"),
    direction: str = Query(default="asc", alias="dir"),
):
    filters = [
        Appointment.patient_id.is_(None),
        Appointment.legacy_source.is_not(None),
    ]
    if legacy_source:
        filters.append(Appointment.legacy_source == legacy_source)
    if from_date:
        start_dt = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        filters.append(Appointment.starts_at >= start_dt)
    if to_date:
        end_dt = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        filters.append(Appointment.starts_at <= end_dt)

    sort_fields = {
        "starts_at": Appointment.starts_at,
        "created_at": Appointment.created_at,
    }
    sort_col = sort_fields.get(sort, Appointment.starts_at)
    order_by = sort_col.asc() if direction.lower() == "asc" else desc(sort_col)

    total = db.scalar(select(func.count()).select_from(Appointment).where(*filters)) or 0
    stmt = (
        select(Appointment)
        .where(*filters)
        .order_by(order_by)
        .limit(limit)
        .offset(offset)
    )
    items = list(db.scalars(stmt))
    return UnmappedLegacyAppointmentList(
        items=items,
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/unmapped-appointments/{appointment_id}/resolve",
    response_model=LegacyResolveResponse,
)
def resolve_unmapped_appointment(
    appointment_id: int,
    payload: LegacyResolveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.patient_id is not None:
        raise HTTPException(
            status_code=409, detail="Appointment already linked to a patient"
        )
    patient = db.get(Patient, payload.patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Patient not found")

    from_patient_id = appt.patient_id
    appt.patient_id = patient.id
    appt.updated_by_user_id = admin.id
    db.add(appt)

    event = LegacyResolutionEvent(
        actor_user_id=admin.id,
        entity_type="appointment",
        entity_id=str(appt.id),
        legacy_source=appt.legacy_source,
        legacy_id=appt.legacy_id,
        action="link_patient",
        from_patient_id=from_patient_id,
        to_patient_id=patient.id,
        notes=payload.notes,
    )
    db.add(event)
    db.commit()
    db.refresh(appt)
    return LegacyResolveResponse(
        id=appt.id,
        patient_id=appt.patient_id,
        legacy_source=appt.legacy_source,
        legacy_id=appt.legacy_id,
    )
