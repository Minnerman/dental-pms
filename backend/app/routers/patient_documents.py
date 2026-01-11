from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.document_template import DocumentTemplate
from app.models.patient import Patient
from app.models.patient_document import PatientDocument
from app.models.user import User
from app.schemas.patient_document import (
    PatientDocumentCreate,
    PatientDocumentOut,
    PatientDocumentPreview,
)
from app.services.document_render import render_template, render_template_with_warnings

router = APIRouter(prefix="/patients/{patient_id}/documents", tags=["patient-documents"])
documents_router = APIRouter(prefix="/patient-documents", tags=["patient-documents"])


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "document"


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
    return document


@router.get("", response_model=list[PatientDocumentOut])
def list_patient_documents(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
):
    patient = get_patient_or_404(db, patient_id)
    template = get_template_or_404(db, payload.template_id)
    title_input = payload.title or template.name
    rendered_title, title_unknown = render_template_with_warnings(title_input, patient)
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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = get_patient_or_404(db, patient_id)
    template = get_template_or_404(db, payload.template_id)
    title_input = payload.title or template.name
    rendered_title, title_unknown = render_template_with_warnings(title_input, patient)
    rendered, content_unknown = render_template_with_warnings(template.content, patient)
    unknown_fields = sorted({*title_unknown, *content_unknown})
    document = PatientDocument(
        patient_id=patient_id,
        template_id=template.id,
        title=rendered_title,
        rendered_content=rendered,
        created_by_user_id=user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    output = PatientDocumentOut.model_validate(document)
    return output.model_copy(update={"unknown_fields": unknown_fields})


@documents_router.get("/{document_id}", response_model=PatientDocumentOut)
def get_patient_document(
    document_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return get_document_or_404(db, document_id)


@documents_router.get("/{document_id}/download")
def download_patient_document(
    document_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id)
    filename = sanitize_filename(document.title)
    headers = {"Content-Disposition": f'attachment; filename="{filename}.txt"'}
    return Response(
        content=document.rendered_content,
        media_type="text/plain",
        headers=headers,
    )


@documents_router.delete("/{document_id}", response_model=PatientDocumentOut)
def delete_patient_document(
    document_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id)
    db.delete(document)
    db.commit()
    return document
