from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/patients/{patient_id}", response_model=list[AuditLogOut])
def patient_audit(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient_id))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


@router.get("/appointments/{appointment_id}", response_model=list[AuditLogOut])
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


@router.get("/notes/{note_id}", response_model=list[AuditLogOut])
def note_audit(
    note_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == "note", AuditLog.entity_id == str(note_id))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))
