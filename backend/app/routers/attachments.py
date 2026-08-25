from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capabilities
from app.models.attachment import Attachment
from app.models.audit_log import AuditLog
from app.models.patient import Patient
from app.models.patient_document import PatientDocument
from app.models.user import User
from app.schemas.attachment import AttachmentOut
from app.services import storage
from app.services.audit import log_event

router = APIRouter(prefix="/patients/{patient_id}/attachments", tags=["attachments"])
attachments_router = APIRouter(prefix="/attachments", tags=["attachments"])

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENT_FILENAME_LENGTH = 255
MAX_CONTENT_TYPE_LENGTH = 120
CONTENT_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
SAFE_PREVIEW_CONTENT_TYPES = {
    "application/pdf",
    "image/bmp",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
}


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "attachment"


def normalize_upload_filename(value: str | None) -> str:
    filename = re.split(r"[/\\]", value or "")[-1].strip()
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")
    if len(filename) > MAX_ATTACHMENT_FILENAME_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is too long")
    if any(ord(character) < 32 or ord(character) == 127 for character in filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is invalid")
    return filename


def normalize_content_type(value: str | None) -> str:
    content_type = (value or "application/octet-stream").split(";", 1)[0].strip().lower()
    if (
        not content_type
        or len(content_type) > MAX_CONTENT_TYPE_LENGTH
        or not CONTENT_TYPE_PATTERN.fullmatch(content_type)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content type is invalid")
    return content_type


def normalize_request_id(value: str | None) -> str | None:
    request_id = value.strip() if value else None
    if request_id and len(request_id) > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request identifier is invalid")
    return request_id


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def get_attachment_or_404(db: Session, attachment_id: int) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return attachment


def require_active_attachment_patient(db: Session, attachment: Attachment) -> Patient:
    return get_patient_or_404(db, attachment.patient_id)


def replayed_upload(
    db: Session,
    *,
    user: User,
    patient_id: int,
    request_id: str | None,
) -> Attachment | None:
    if request_id is None:
        return None
    entry = db.scalar(
        select(AuditLog)
        .where(
            AuditLog.actor_user_id == user.id,
            AuditLog.action == "attachment.uploaded",
            AuditLog.request_id == request_id,
        )
        .order_by(AuditLog.id.desc())
    )
    if entry is None:
        return None
    attachment = db.get(Attachment, int(entry.entity_id)) if entry.entity_id.isdigit() else None
    source = (entry.after_json or {}).get("source")
    if attachment and attachment.patient_id == patient_id and source == "patient_upload":
        return attachment
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Request identifier has already been used",
    )


@router.get("", response_model=list[AttachmentOut])
def list_attachments(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capabilities("documents.download")),
):
    get_patient_or_404(db, patient_id)
    stmt = (
        select(Attachment)
        .where(Attachment.patient_id == patient_id)
        .order_by(Attachment.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.post("", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    patient_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_capabilities("documents.download", "documents.upload")),
    request_id: str | None = Header(default=None),
):
    get_patient_or_404(db, patient_id)
    request_id = normalize_request_id(request_id)
    replay = replayed_upload(db, user=user, patient_id=patient_id, request_id=request_id)
    if replay is not None:
        return replay
    filename = normalize_upload_filename(file.filename)
    content_type = normalize_content_type(file.content_type)

    try:
        storage_key, byte_size = storage.save_upload(file, MAX_ATTACHMENT_BYTES)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store attachment",
        )
    if byte_size == 0:
        storage.delete_file(storage_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment is empty")

    attachment = Attachment(
        patient_id=patient_id,
        original_filename=filename,
        content_type=content_type,
        byte_size=byte_size,
        storage_key=storage_key,
        created_by_user_id=user.id,
    )
    try:
        db.add(attachment)
        db.flush()
        log_event(
            db,
            actor=user,
            action="attachment.uploaded",
            entity_type="attachment",
            entity_id=str(attachment.id),
            after_data={
                "patient_id": attachment.patient_id,
                "filename": sanitize_filename(attachment.original_filename),
                "content_type": attachment.content_type,
                "byte_size": attachment.byte_size,
                "source": "patient_upload",
            },
            request_id=request_id,
            ip_address=request.client.host if request else None,
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete_file(storage_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save attachment",
        )
    db.refresh(attachment)
    return attachment


@attachments_router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capabilities("documents.download")),
    request_id: str | None = Header(default=None),
):
    request_id = normalize_request_id(request_id)
    attachment = get_attachment_or_404(db, attachment_id)
    require_active_attachment_patient(db, attachment)
    filename = sanitize_filename(attachment.original_filename)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    try:
        handle = storage.open_file(attachment.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file missing",
        )
    log_event(
        db,
        actor=user,
        action="attachment.downloaded",
        entity_type="attachment",
        entity_id=str(attachment.id),
        after_data={
            "patient_id": attachment.patient_id,
            "filename": filename,
        },
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    return StreamingResponse(
        handle,
        media_type=attachment.content_type,
        headers=headers,
    )


@attachments_router.get("/{attachment_id}/preview")
def preview_attachment(
    attachment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capabilities("documents.download")),
    request_id: str | None = Header(default=None),
):
    request_id = normalize_request_id(request_id)
    attachment = get_attachment_or_404(db, attachment_id)
    require_active_attachment_patient(db, attachment)
    if attachment.content_type not in SAFE_PREVIEW_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attachment preview is unavailable",
        )
    filename = sanitize_filename(attachment.original_filename)
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}
    try:
        handle = storage.open_file(attachment.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file missing",
        )
    log_event(
        db,
        actor=user,
        action="attachment.previewed",
        entity_type="attachment",
        entity_id=str(attachment.id),
        after_data={
            "patient_id": attachment.patient_id,
            "filename": filename,
        },
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    return StreamingResponse(
        handle,
        media_type=attachment.content_type,
        headers=headers,
    )


@attachments_router.delete("/{attachment_id}", response_model=AttachmentOut)
def delete_attachment(
    attachment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capabilities("documents.download", "documents.delete")),
    request_id: str | None = Header(default=None),
):
    request_id = normalize_request_id(request_id)
    attachment = get_attachment_or_404(db, attachment_id)
    require_active_attachment_patient(db, attachment)
    before_data = {
        "patient_id": attachment.patient_id,
        "filename": sanitize_filename(attachment.original_filename),
        "content_type": attachment.content_type,
        "byte_size": attachment.byte_size,
    }
    storage_key = attachment.storage_key
    try:
        staged_key = storage.stage_delete(storage_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment",
        )
    try:
        linked_documents = list(
            db.scalars(
                select(PatientDocument).where(PatientDocument.attachment_id == attachment.id)
            )
        )
        for document in linked_documents:
            document.attachment_id = None
            db.add(document)
        db.delete(attachment)
        log_event(
            db,
            actor=user,
            action="attachment.deleted",
            entity_type="attachment",
            entity_id=str(attachment.id),
            before_data=before_data,
            request_id=request_id,
            ip_address=request.client.host if request else None,
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.restore_staged_delete(staged_key, storage_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment",
        )
    try:
        storage.finalize_staged_delete(staged_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Attachment cleanup did not complete",
        )
    return attachment
