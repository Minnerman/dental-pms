from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.attachment import Attachment
from app.models.patient import Patient
from app.models.user import User
from app.schemas.attachment import AttachmentOut
from app.services import storage

router = APIRouter(prefix="/patients/{patient_id}/attachments", tags=["attachments"])
attachments_router = APIRouter(prefix="/attachments", tags=["attachments"])

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "attachment"


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


@router.get("", response_model=list[AttachmentOut])
def list_attachments(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
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
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_patient_or_404(db, patient_id)
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")

    try:
        storage_key, byte_size = storage.save_upload(file, MAX_ATTACHMENT_BYTES)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store attachment",
        )

    attachment = Attachment(
        patient_id=patient_id,
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        byte_size=byte_size,
        storage_key=storage_key,
        created_by_user_id=user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@attachments_router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    attachment = get_attachment_or_404(db, attachment_id)
    filename = sanitize_filename(attachment.original_filename)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    try:
        handle = storage.open_file(attachment.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file missing",
        )
    return StreamingResponse(
        handle,
        media_type=attachment.content_type,
        headers=headers,
    )


@attachments_router.delete("/{attachment_id}", response_model=AttachmentOut)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    attachment = get_attachment_or_404(db, attachment_id)
    storage.delete_file(attachment.storage_key)
    db.delete(attachment)
    db.commit()
    return attachment
