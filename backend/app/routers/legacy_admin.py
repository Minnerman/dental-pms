from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_admin
from app.models.appointment import Appointment
from app.models.user import User
from app.schemas.legacy_admin import UnmappedLegacyAppointmentList

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
