from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capability
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.note import Note, NoteType
from app.models.patient import Patient
from app.models.user import User
from app.schemas.audit_log import AuditLogOut
from app.schemas.note import AppointmentNoteCreate, NoteCreate, NoteOut, NoteUpdate, NoteAmendment
from app.schemas.clinical_note import NativeNoteHistoryOut
from app.services import native_notes
from app.services.audit import log_event

patient_router = APIRouter(prefix="/patients/{patient_id}/notes", tags=["notes"])
appointment_router = APIRouter(prefix="/appointments/{appointment_id}/notes", tags=["notes"])
router = APIRouter(prefix="/notes", tags=["notes"])

NOTES_VIEW = require_capability("notes.view")
NOTES_WRITE = require_capability("notes.write")


def require_notes_mutation(
    user: User = Depends(NOTES_WRITE),
    _viewer: User = Depends(NOTES_VIEW),
) -> User:
    return user


NOTES_MUTATE = require_notes_mutation


def _require_patient(
    db: Session,
    patient_id: int,
    *,
    for_update: bool = False,
) -> Patient:
    stmt = select(Patient).where(
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    )
    if for_update:
        stmt = stmt.with_for_update(of=Patient)
    patient = db.scalar(stmt)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def _require_appointment(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    if appointment.patient_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is not linked to a patient",
        )
    _require_patient(db, appointment.patient_id)
    return appointment


def _validate_note_appointment(
    db: Session,
    *,
    appointment_id: int | None,
    patient_id: int,
) -> Appointment | None:
    if appointment_id is None:
        return None
    appointment = _require_appointment(db, appointment_id)
    if appointment.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="appointment_id does not belong to patient_id",
        )
    return appointment


def _require_note(
    db: Session,
    note_id: int,
    *,
    patient_id: int | None = None,
    appointment_id: int | None = None,
    include_deleted: bool = False,
    for_update: bool = False,
) -> Note:
    if for_update:
        owner_id = db.scalar(select(Note.patient_id).where(Note.id == note_id))
        if owner_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        # Match patient-first ordering used by creation/archive operations;
        # an amendment cannot race a parent archive after its eligibility check.
        _require_patient(db, owner_id, for_update=True)
    stmt = select(Note).where(Note.id == note_id)
    if for_update:
        stmt = stmt.with_for_update(of=Note)
    note = db.scalar(stmt)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if patient_id is not None and note.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if appointment_id is not None and note.appointment_id != appointment_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if not include_deleted and note.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    _require_patient(db, note.patient_id)
    if note.appointment_id is not None:
        appointment = _require_appointment(db, note.appointment_id)
        if appointment.patient_id != note.patient_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def _safe_note_values(note: Note, *, changed_fields: set[str] | None = None) -> dict:
    fields = changed_fields or set()
    values: dict[str, object] = {
        "note_id": note.id,
        "patient_id": note.patient_id,
        "appointment_id": note.appointment_id,
        "note_type": note.note_type.value,
        "archived": note.deleted_at is not None,
        "revision": note.revision,
    }
    if changed_fields is not None:
        values["changed_fields"] = sorted(fields)
        if "body" in fields:
            values["body_changed"] = True
    return values


def _create_note_record(
    *,
    patient_id: int,
    appointment_id: int | None,
    body: str,
    note_type: NoteType,
    request: Request,
    db: Session,
    user: User,
    request_id: str | None,
    metadata_payload,
) -> Note:
    _require_patient(db, patient_id, for_update=True)
    fingerprint_payload = {**metadata_payload.model_dump(mode="json"), "patient_id": patient_id, "appointment_id": appointment_id}
    duplicate_id = native_notes.replay_target(db, user.id, request_id, "note.created", fingerprint_payload)
    if duplicate_id is not None:
        return _require_note(db, duplicate_id, patient_id=patient_id)
    metadata = native_notes.creation_metadata(db, metadata_payload, user)
    note = Note(
        patient_id=patient_id,
        appointment_id=appointment_id,
        body=body,
        note_type=note_type,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
        **metadata,
    )
    db.add(note)
    db.flush()
    native_notes.save_snapshot(db, note, user.id)
    native_notes.record_receipt(db, user.id, request_id, "note.created", fingerprint_payload, note.id)
    log_event(
        db,
        actor=user,
        action="note.created",
        entity_type="note",
        entity_id=str(note.id),
        after_data=_safe_note_values(note),
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(note)
    return note


def _update_note_record(
    *,
    note: Note,
    payload: NoteUpdate,
    request: Request,
    db: Session,
    user: User,
    request_id: str | None,
) -> Note:
    fingerprint_payload = {"note_id": note.id, **payload.model_dump(mode="json", exclude_unset=True)}
    if native_notes.replay_target(db, user.id, request_id, "note.updated", fingerprint_payload) is not None:
        return note
    native_notes.check_revision(note, payload.expected_revision)
    updates = payload.model_dump(exclude_unset=True, exclude={"expected_revision", "reason"})
    changed_fields = {
        field for field, value in updates.items() if getattr(note, field) != value
    }
    if not changed_fields:
        native_notes.record_receipt(db, user.id, request_id, "note.updated", fingerprint_payload, note.id)
        db.commit()
        return note
    native_notes.ensure_baseline(db, note)
    before_data = _safe_note_values(note, changed_fields=changed_fields)
    for field in changed_fields:
        setattr(note, field, updates[field])
    note.updated_by_user_id = user.id
    note.revision += 1
    native_notes.save_snapshot(db, note, user.id, reason=payload.reason)
    native_notes.record_receipt(db, user.id, request_id, "note.updated", fingerprint_payload, note.id)
    db.add(note)
    log_event(
        db,
        actor=user,
        action="note.updated",
        entity_type="note",
        entity_id=str(note.id),
        before_data=before_data,
        after_data=_safe_note_values(note, changed_fields=changed_fields),
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(note)
    return note


def _set_note_archived(
    *,
    note: Note,
    archived: bool,
    request: Request,
    db: Session,
    user: User,
    request_id: str | None,
) -> Note:
    action = "note.archived" if archived else "note.restored"
    fingerprint_payload = {"note_id": note.id, "archived": archived}
    if native_notes.replay_target(db, user.id, request_id, action, fingerprint_payload) is not None:
        return note
    if (note.deleted_at is not None) == archived:
        native_notes.record_receipt(db, user.id, request_id, action, fingerprint_payload, note.id)
        db.commit()
        return note
    native_notes.ensure_baseline(db, note)
    before_data = _safe_note_values(note, changed_fields={"archived"})
    if archived:
        note.deleted_at = datetime.now(timezone.utc)
        note.deleted_by_user_id = user.id
        action = "note.archived"
    else:
        note.deleted_at = None
        note.deleted_by_user_id = None
        action = "note.restored"
    note.updated_by_user_id = user.id
    note.revision += 1
    native_notes.save_snapshot(db, note, user.id, reason="Archived" if archived else "Restored")
    native_notes.record_receipt(db, user.id, request_id, action, fingerprint_payload, note.id)
    db.add(note)
    log_event(
        db,
        actor=user,
        action=action,
        entity_type="note",
        entity_id=str(note.id),
        before_data=before_data,
        after_data=_safe_note_values(note, changed_fields={"archived"}),
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(note)
    return note


def _safe_note_scope(stmt):
    return (
        stmt.join(Patient, Patient.id == Note.patient_id)
        .outerjoin(Appointment, Appointment.id == Note.appointment_id)
        .where(
            Patient.deleted_at.is_(None),
            or_(
                Note.appointment_id.is_(None),
                and_(
                    Appointment.id.is_not(None),
                    Appointment.deleted_at.is_(None),
                    Appointment.patient_id == Note.patient_id,
                ),
            ),
        )
    )


@patient_router.get("", response_model=list[NoteOut])
def list_notes(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(NOTES_VIEW),
    include_deleted: bool = Query(default=False),
):
    _require_patient(db, patient_id)
    stmt = _safe_note_scope(select(Note)).where(Note.patient_id == patient_id)
    if not include_deleted:
        stmt = stmt.where(Note.deleted_at.is_(None))
    return list(db.scalars(stmt.order_by(Note.created_at.desc(), Note.id.desc())))


@patient_router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_patient_note(
    patient_id: int,
    payload: NoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    _require_patient(db, patient_id)
    _validate_note_appointment(db, appointment_id=payload.appointment_id, patient_id=patient_id)
    return _create_note_record(
        patient_id=patient_id,
        appointment_id=payload.appointment_id,
        body=payload.body,
        note_type=payload.note_type,
        metadata_payload=payload,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@appointment_router.get("", response_model=list[NoteOut])
def list_appointment_notes(
    appointment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(NOTES_VIEW),
    include_deleted: bool = Query(default=False),
):
    appointment = _require_appointment(db, appointment_id)
    stmt = select(Note).where(
        Note.appointment_id == appointment_id,
        Note.patient_id == appointment.patient_id,
    )
    if not include_deleted:
        stmt = stmt.where(Note.deleted_at.is_(None))
    return list(db.scalars(stmt.order_by(Note.created_at.desc(), Note.id.desc())))


@appointment_router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_appointment_note(
    appointment_id: int,
    payload: AppointmentNoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    appointment = _require_appointment(db, appointment_id)
    return _create_note_record(
        patient_id=appointment.patient_id,
        appointment_id=appointment_id,
        body=payload.body,
        note_type=payload.note_type,
        metadata_payload=payload,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@appointment_router.patch("/{note_id}", response_model=NoteOut)
def update_appointment_note(
    appointment_id: int,
    note_id: int,
    payload: NoteUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    _require_appointment(db, appointment_id)
    note = _require_note(db, note_id, appointment_id=appointment_id, for_update=True)
    return _update_note_record(
        note=note,
        payload=payload,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@appointment_router.post("/{note_id}/archive", response_model=NoteOut)
def archive_appointment_note(
    appointment_id: int,
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    _require_appointment(db, appointment_id)
    note = _require_note(
        db,
        note_id,
        appointment_id=appointment_id,
        include_deleted=True,
        for_update=True,
    )
    return _set_note_archived(
        note=note,
        archived=True,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@appointment_router.post("/{note_id}/restore", response_model=NoteOut)
def restore_appointment_note(
    appointment_id: int,
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    _require_appointment(db, appointment_id)
    note = _require_note(
        db,
        note_id,
        appointment_id=appointment_id,
        include_deleted=True,
        for_update=True,
    )
    return _set_note_archived(
        note=note,
        archived=False,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@patient_router.post("/{note_id}/archive", response_model=NoteOut)
def archive_note(
    patient_id: int,
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    _require_patient(db, patient_id)
    note = _require_note(
        db,
        note_id,
        patient_id=patient_id,
        include_deleted=True,
        for_update=True,
    )
    return _set_note_archived(
        note=note,
        archived=True,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@patient_router.post("/{note_id}/restore", response_model=NoteOut)
def restore_note(
    patient_id: int,
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    _require_patient(db, patient_id)
    note = _require_note(
        db,
        note_id,
        patient_id=patient_id,
        include_deleted=True,
        for_update=True,
    )
    return _set_note_archived(
        note=note,
        archived=False,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@router.get("", response_model=list[NoteOut])
def list_all_notes(
    db: Session = Depends(get_db),
    _user: User = Depends(NOTES_VIEW),
    include_deleted: bool = Query(default=False),
    patient_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = _safe_note_scope(select(Note))
    if patient_id is not None:
        stmt = stmt.where(Note.patient_id == patient_id)
    if not include_deleted:
        stmt = stmt.where(Note.deleted_at.is_(None))
    stmt = stmt.order_by(Note.created_at.desc(), Note.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note_global(
    payload: NoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    if payload.patient_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id required")
    _require_patient(db, payload.patient_id)
    _validate_note_appointment(
        db,
        appointment_id=payload.appointment_id,
        patient_id=payload.patient_id,
    )
    return _create_note_record(
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        body=payload.body,
        note_type=payload.note_type,
        metadata_payload=payload,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@router.patch("/{note_id}", response_model=NoteOut)
def update_note(
    note_id: int,
    payload: NoteUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    note = _require_note(db, note_id, for_update=True)
    return _update_note_record(
        note=note,
        payload=payload,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@router.post("/{note_id}/amendments", response_model=NoteOut)
def amend_note(
    note_id: int, payload: NoteAmendment, request: Request,
    db: Session = Depends(get_db), user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    note = _require_note(db, note_id, for_update=True)
    return _update_note_record(note=note, payload=payload, request=request, db=db, user=user, request_id=request_id)


@router.get("/{note_id}/revisions", response_model=NativeNoteHistoryOut)
def note_revisions(
    note_id: int, db: Session = Depends(get_db), _user: User = Depends(NOTES_VIEW),
    limit: int = Query(default=100, ge=1, le=200),
    before_revision: int | None = Query(default=None, ge=1),
):
    return native_notes.history(db, _require_note(db, note_id, include_deleted=True), limit=limit, before_revision=before_revision)


@router.post("/{note_id}/archive", response_model=NoteOut)
def archive_note_global(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    note = _require_note(db, note_id, include_deleted=True, for_update=True)
    return _set_note_archived(
        note=note,
        archived=True,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@router.post("/{note_id}/restore", response_model=NoteOut)
def restore_note_global(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(NOTES_MUTATE),
    request_id: str | None = Header(default=None, max_length=120),
):
    note = _require_note(db, note_id, include_deleted=True, for_update=True)
    return _set_note_archived(
        note=note,
        archived=False,
        request=request,
        db=db,
        user=user,
        request_id=request_id,
    )


@router.get("/{note_id}/audit", response_model=list[AuditLogOut])
def note_audit(
    note_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(NOTES_VIEW),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _require_note(db, note_id, include_deleted=True)
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == "note", AuditLog.entity_id == str(note_id))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))
