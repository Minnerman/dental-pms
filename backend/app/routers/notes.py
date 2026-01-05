from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.audit_log import AuditLog
from app.models.note import Note
from app.models.patient import Patient
from app.models.user import User
from app.schemas.note import NoteCreate, NoteOut
from app.schemas.audit_log import AuditLogOut
from app.services.audit import log_event, snapshot_model

patient_router = APIRouter(prefix="/patients/{patient_id}/notes", tags=["notes"])
router = APIRouter(prefix="/notes", tags=["notes"])


@patient_router.get("", response_model=list[NoteOut])
def list_notes(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    include_deleted: bool = Query(default=False),
):
    stmt = (
        select(Note)
        .where(Note.patient_id == patient_id)
        .order_by(Note.created_at.desc())
    )
    if not include_deleted:
        stmt = stmt.where(Note.deleted_at.is_(None))
    return list(db.scalars(stmt))


@patient_router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    patient_id: int,
    payload: NoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    note = Note(
        patient_id=patient_id,
        appointment_id=payload.appointment_id,
        body=payload.body,
        note_type=payload.note_type,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(note)
    db.flush()
    log_event(
        db,
        actor=user,
        action="create",
        entity_type="note",
        entity_id=str(note.id),
        before_obj=None,
        after_obj=note,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(note)
    return note


@patient_router.post("/{note_id}/archive", response_model=NoteOut)
def archive_note(
    patient_id: int,
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    note = db.get(Note, note_id)
    if not note or note.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if note.deleted_at is not None:
        return note

    before_data = snapshot_model(note)
    note.deleted_at = datetime.now(timezone.utc)
    note.deleted_by_user_id = user.id
    note.updated_by_user_id = user.id
    db.add(note)
    log_event(
        db,
        actor=user,
        action="delete",
        entity_type="note",
        entity_id=str(note.id),
        before_data=before_data,
        after_obj=note,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(note)
    return note


@patient_router.post("/{note_id}/restore", response_model=NoteOut)
def restore_note(
    patient_id: int,
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    note = db.get(Note, note_id)
    if not note or note.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if note.deleted_at is None:
        return note

    before_data = snapshot_model(note)
    note.deleted_at = None
    note.deleted_by_user_id = None
    note.updated_by_user_id = user.id
    db.add(note)
    log_event(
        db,
        actor=user,
        action="restore",
        entity_type="note",
        entity_id=str(note.id),
        before_data=before_data,
        after_obj=note,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(note)
    return note


@router.get("", response_model=list[NoteOut])
def list_all_notes(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    include_deleted: bool = Query(default=False),
    patient_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Note).order_by(Note.created_at.desc())
    if patient_id is not None:
        stmt = stmt.where(Note.patient_id == patient_id)
    if not include_deleted:
        stmt = stmt.where(Note.deleted_at.is_(None))
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.post("/{note_id}/archive", response_model=NoteOut)
def archive_note_global(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    note = db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if note.deleted_at is not None:
        return note

    before_data = snapshot_model(note)
    note.deleted_at = datetime.now(timezone.utc)
    note.deleted_by_user_id = user.id
    note.updated_by_user_id = user.id
    db.add(note)
    log_event(
        db,
        actor=user,
        action="delete",
        entity_type="note",
        entity_id=str(note.id),
        before_data=before_data,
        after_obj=note,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(note)
    return note


@router.post("/{note_id}/restore", response_model=NoteOut)
def restore_note_global(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    note = db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if note.deleted_at is None:
        return note

    before_data = snapshot_model(note)
    note.deleted_at = None
    note.deleted_by_user_id = None
    note.updated_by_user_id = user.id
    db.add(note)
    log_event(
        db,
        actor=user,
        action="restore",
        entity_type="note",
        entity_id=str(note.id),
        before_data=before_data,
        after_obj=note,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(note)
    return note


@router.get("/{note_id}/audit", response_model=list[AuditLogOut])
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
