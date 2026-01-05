from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.audit_log import AuditLog
from app.models.appointment import Appointment
from app.models.note import Note
from app.models.patient import Patient
from app.models.user import User
from app.schemas.timeline import TimelineItem

router = APIRouter(prefix="/patients/{patient_id}/timeline", tags=["timeline"])


@router.get("", response_model=list[TimelineItem])
def patient_timeline(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=500),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    appointment_ids = [str(row[0]) for row in db.execute(select(Appointment.id).where(Appointment.patient_id == patient_id)).all()]
    note_ids = [str(row[0]) for row in db.execute(select(Note.id).where(Note.patient_id == patient_id)).all()]

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    logs: list[AuditLog] = []

    logs.extend(
        db.scalars(
            stmt.where(AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient_id))
        ).all()
    )
    if appointment_ids:
        logs.extend(
            db.scalars(
                stmt.where(
                    AuditLog.entity_type == "appointment",
                    AuditLog.entity_id.in_(appointment_ids),
                )
            ).all()
        )
    if note_ids:
        logs.extend(
            db.scalars(
                stmt.where(AuditLog.entity_type == "note", AuditLog.entity_id.in_(note_ids))
            ).all()
        )

    logs = sorted(logs, key=lambda l: l.created_at, reverse=True)[:limit]

    items: list[TimelineItem] = []
    for log in logs:
        link = None
        if log.entity_type == "patient":
            link = f"/patients/{patient_id}/audit"
        elif log.entity_type == "appointment":
            link = f"/appointments/{log.entity_id}/audit"
        elif log.entity_type == "note":
            link = f"/notes/{log.entity_id}/audit"
        actor_email = log.actor.email if log.actor else log.actor_email
        actor_role = log.actor.role.value if log.actor else None
        summary = f"{log.action} {log.entity_type}"
        items.append(
            TimelineItem(
                type=log.entity_type,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                action=log.action,
                occurred_at=log.created_at,
                actor_email=actor_email,
                actor_role=actor_role,
                summary=summary,
                link=link,
            )
        )

    return items
