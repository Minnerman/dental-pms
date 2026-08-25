from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capabilities
from app.models.attachment import Attachment
from app.models.audit_log import AuditLog
from app.models.document_template import DocumentTemplate
from app.models.patient import Patient
from app.models.patient_document import PatientDocument
from app.models.user import User
from app.schemas.attachment import AttachmentOut
from app.schemas.patient_document import (
    PatientDocumentCreate,
    PatientDocumentOut,
    PatientDocumentPreview,
)
from app.services import storage
from app.services.audit import log_event
from app.services.document_render import render_template_with_warnings
from app.services.pdf_documents import generate_patient_document_pdf
from app.services.practice_profile import load_profile

router = APIRouter(prefix="/patients/{patient_id}/documents", tags=["patient-documents"])
documents_router = APIRouter(prefix="/patient-documents", tags=["patient-documents"])


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "document"


def normalize_request_id(value: str | None) -> str | None:
    request_id = value.strip() if value else None
    if request_id and len(request_id) > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request identifier is invalid")
    return request_id


def validate_rendered_title(value: str) -> str:
    title = value.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document title is required")
    if len(title) > 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document title is too long")
    return title


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def get_template_or_404(db: Session, template_id: int) -> DocumentTemplate:
    template = db.get(DocumentTemplate, template_id)
    if not template or template.deleted_at is not None or not template.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


def get_document_or_404(db: Session, document_id: int) -> PatientDocument:
    document = db.get(PatientDocument, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    get_patient_or_404(db, document.patient_id)
    return document


def replayed_document_create(
    db: Session,
    *,
    user: User,
    patient_id: int,
    request_id: str | None,
) -> PatientDocument | None:
    if request_id is None:
        return None
    entry = db.scalar(
        select(AuditLog)
        .where(
            AuditLog.actor_user_id == user.id,
            AuditLog.action == "patient_document.created",
            AuditLog.request_id == request_id,
        )
        .order_by(AuditLog.id.desc())
    )
    if entry is None:
        return None
    document = db.get(PatientDocument, int(entry.entity_id)) if entry.entity_id.isdigit() else None
    if document and document.patient_id == patient_id:
        return document
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Request identifier has already been used",
    )


@router.get("", response_model=list[PatientDocumentOut])
def list_patient_documents(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capabilities("documents.download")),
):
    get_patient_or_404(db, patient_id)
    stmt = (
        select(PatientDocument)
        .where(PatientDocument.patient_id == patient_id)
        .order_by(PatientDocument.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.post("/preview", response_model=PatientDocumentPreview)
def preview_patient_document(
    patient_id: int,
    payload: PatientDocumentCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capabilities("documents.download", "documents.upload")),
):
    patient = get_patient_or_404(db, patient_id)
    template = get_template_or_404(db, payload.template_id)
    title_input = payload.title or template.name
    rendered_title, title_unknown = render_template_with_warnings(title_input, patient)
    rendered_title = validate_rendered_title(rendered_title)
    rendered, content_unknown = render_template_with_warnings(template.content, patient)
    unknown_fields = sorted({*title_unknown, *content_unknown})
    return PatientDocumentPreview(
        title=rendered_title,
        rendered_content=rendered,
        unknown_fields=unknown_fields,
    )


@router.post("", response_model=PatientDocumentOut, status_code=status.HTTP_201_CREATED)
def create_patient_document(
    patient_id: int,
    payload: PatientDocumentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capabilities("documents.download", "documents.upload")),
    request_id: str | None = Header(default=None),
):
    patient = get_patient_or_404(db, patient_id)
    request_id = normalize_request_id(request_id)
    replay = replayed_document_create(
        db,
        user=user,
        patient_id=patient_id,
        request_id=request_id,
    )
    if replay is not None:
        return replay
    template = get_template_or_404(db, payload.template_id)
    title_input = payload.title or template.name
    rendered_title, title_unknown = render_template_with_warnings(title_input, patient)
    rendered_title = validate_rendered_title(rendered_title)
    rendered, content_unknown = render_template_with_warnings(template.content, patient)
    unknown_fields = sorted({*title_unknown, *content_unknown})
    document = PatientDocument(
        patient_id=patient_id,
        template_id=template.id,
        title=rendered_title,
        rendered_content=rendered,
        created_by_user_id=user.id,
    )
    try:
        db.add(document)
        db.flush()
        log_event(
            db,
            actor=user,
            action="patient_document.created",
            entity_type="patient_document",
            entity_id=str(document.id),
            after_data={
                "patient_id": document.patient_id,
                "template_id": document.template_id,
                "title": document.title,
            },
            request_id=request_id,
            ip_address=request.client.host if request else None,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save patient document",
        )
    db.refresh(document)
    output = PatientDocumentOut.model_validate(document)
    return output.model_copy(update={"unknown_fields": unknown_fields})


@documents_router.get("/{document_id}", response_model=PatientDocumentOut)
def get_patient_document(
    document_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capabilities("documents.download")),
):
    return get_document_or_404(db, document_id)


@documents_router.get("/{document_id}/download")
def download_patient_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capabilities("documents.download")),
    request_id: str | None = Header(default=None),
    format: str = Query(default="text"),
):
    request_id = normalize_request_id(request_id)
    document = get_document_or_404(db, document_id)
    patient = get_patient_or_404(db, document.patient_id)
    safe_title = sanitize_filename(document.title)
    safe_patient_name = sanitize_filename(patient.last_name)
    date_suffix = date.today().isoformat()
    if format == "pdf":
        filename = f"{safe_title}_{safe_patient_name}_{date_suffix}.pdf"
        profile = load_profile(db)
        pdf_bytes = generate_patient_document_pdf(
            patient, document.title, document.rendered_content, profile
        )
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        log_event(
            db,
            actor=user,
            action="patient_document.downloaded_pdf",
            entity_type="patient_document",
            entity_id=str(document.id),
            after_data={
                "patient_id": document.patient_id,
                "filename": filename,
            },
            request_id=request_id,
            ip_address=request.client.host if request else None,
        )
        db.commit()
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
    if format != "text":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="format must be text or pdf",
        )
    filename = f"{safe_title}_{safe_patient_name}_{date_suffix}.txt"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    log_event(
        db,
        actor=user,
        action="patient_document.downloaded",
        entity_type="patient_document",
        entity_id=str(document.id),
        after_data={
            "patient_id": document.patient_id,
            "filename": filename,
        },
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    return Response(content=document.rendered_content, media_type="text/plain", headers=headers)


@documents_router.delete("/{document_id}", response_model=PatientDocumentOut)
def delete_patient_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capabilities("documents.download", "documents.delete")),
    request_id: str | None = Header(default=None),
):
    request_id = normalize_request_id(request_id)
    document = get_document_or_404(db, document_id)
    before_data = {
        "patient_id": document.patient_id,
        "template_id": document.template_id,
        "title": document.title,
    }
    try:
        db.delete(document)
        log_event(
            db,
            actor=user,
            action="patient_document.deleted",
            entity_type="patient_document",
            entity_id=str(document.id),
            before_data=before_data,
            request_id=request_id,
            ip_address=request.client.host if request else None,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete patient document",
        )
    return document


@documents_router.post("/{document_id}/attach-pdf", response_model=AttachmentOut)
def attach_patient_document_pdf(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capabilities("documents.download", "documents.upload")),
    request_id: str | None = Header(default=None),
):
    request_id = normalize_request_id(request_id)
    document = get_document_or_404(db, document_id)
    patient = get_patient_or_404(db, document.patient_id)
    if document.attachment_id is not None:
        existing = db.get(Attachment, document.attachment_id)
        if (
            existing is None
            or existing.patient_id != document.patient_id
            or existing.content_type != "application/pdf"
            or not storage.file_exists(existing.storage_key)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Attached PDF is unavailable",
            )
        return existing
    profile = load_profile(db)
    pdf_bytes = generate_patient_document_pdf(
        patient, document.title, document.rendered_content, profile
    )
    try:
        storage_key, byte_size = storage.save_bytes(pdf_bytes)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store generated PDF",
        )
    safe_title = sanitize_filename(document.title)
    filename = f"{safe_title}.pdf"
    attachment = Attachment(
        patient_id=document.patient_id,
        original_filename=filename,
        content_type="application/pdf",
        byte_size=byte_size,
        storage_key=storage_key,
        created_by_user_id=user.id,
    )
    try:
        db.add(attachment)
        db.flush()
        document.attachment_id = attachment.id
        db.add(document)
        log_event(
            db,
            actor=user,
            action="attachment.uploaded",
            entity_type="attachment",
            entity_id=str(attachment.id),
            after_data={
                "patient_id": attachment.patient_id,
                "patient_document_id": document.id,
                "filename": sanitize_filename(attachment.original_filename),
                "content_type": attachment.content_type,
                "byte_size": attachment.byte_size,
                "source": "generated_patient_document",
            },
            request_id=request_id,
            ip_address=request.client.host if request else None,
        )
        log_event(
            db,
            actor=user,
            action="patient_document.pdf_attached",
            entity_type="patient_document",
            entity_id=str(document.id),
            after_data={
                "patient_id": document.patient_id,
                "attachment_id": attachment.id,
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
            detail="Failed to attach generated PDF",
        )
    db.refresh(attachment)
    return attachment
