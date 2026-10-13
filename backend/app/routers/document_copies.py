from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.session import get_db
from app.deps import require_capabilities
from app.models.document_copy import DocumentCopy
from app.models.note import Note, NoteType
from app.models.patient_document import PatientDocument
from app.models.user import User
from app.routers.patient_documents import get_document_or_404, get_patient_or_404
from app.services.audit import log_event
from app.services import recall_email

router = APIRouter(tags=["document-copies"])
read_copy = require_capabilities("documents.download", "notes.view")
write_copy = require_capabilities("documents.download", "notes.view", "notes.write")


class CopyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["print", "email"] = "print"


class CopyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    title: str
    document_kind: str
    method: str
    status: str
    recipient: str | None
    sender: str | None
    created_at: datetime
    completed_at: datetime | None


def copy_or_404(db, copy_id, *, lock=False):
    stmt = select(DocumentCopy).where(DocumentCopy.id == copy_id)
    if lock:
        stmt = stmt.with_for_update()
    copy = db.scalar(stmt)
    if not copy:
        raise HTTPException(404, "Document copy not found")
    get_patient_or_404(db, copy.patient_id)
    return copy


def audit(db, copy, user, request, action):
    log_event(db, actor=user, action=action, entity_type="document_copy", entity_id=str(copy.id),
              after_data={"patient_id": copy.patient_id, "method": copy.method, "status": copy.status},
              request_id=copy.request_id, ip_address=request.client.host if request.client else None)


def complete(db, copy, user, request):
    copy.completed_at = datetime.now(timezone.utc)
    copy.completed_by_user_id = user.id
    action = "Printed" if copy.method == "print" else "Emailed (accepted by mail server)"
    extra = " Copy is before handwritten signature." if copy.document_kind == "prescription" else ""
    note = Note(patient_id=copy.patient_id, note_type=NoteType.clinical,
                body=f"{action}: {copy.title}. Open the saved document.{extra}",
                document_copy_id=copy.id, created_by_user_id=user.id)
    db.add(note)
    db.flush()
    log_event(db, actor=user, action="note.created", entity_type="note", entity_id=str(note.id),
              after_data={"patient_id": copy.patient_id, "document_copy_id": copy.id},
              request_id=copy.request_id, ip_address=request.client.host if request.client else None)
    audit(db, copy, user, request, "document_copy." + copy.status)
    db.commit()
    db.refresh(copy)
    return copy


@router.get("/document-delivery-settings")
def delivery_settings(_user: User = Depends(read_copy)):
    return {"recall_email_ready": recall_email.email_ready(), "sender": str(settings.smtp_from_email)}


@router.post("/patient-documents/{document_id}/copies", response_model=CopyOut, status_code=201)
def prepare_copy(document_id: int, payload: CopyCreate, request: Request,
                 request_id: UUID = Header(), db: Session = Depends(get_db), user: User = Depends(write_copy)):
    # Serialize request-key checks for this actor, including requests for different source documents.
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    existing = db.scalar(select(DocumentCopy).where(DocumentCopy.created_by_user_id == user.id,
                                                  DocumentCopy.request_id == str(request_id)))
    if existing:
        get_patient_or_404(db, existing.patient_id)
        if existing.source_document_id != document_id or existing.method != payload.method:
            raise HTTPException(409, "Request identifier has already been used")
        return existing
    document = get_document_or_404(db, document_id)
    # Hold the source until the snapshot is committed, preventing concurrent deletion.
    db.scalar(select(PatientDocument.id).where(PatientDocument.id == document_id).with_for_update())
    patient = get_patient_or_404(db, document.patient_id)
    if not document.frozen_pdf or document.issue_blockers is None:
        raise HTTPException(409, "Create a new document from a template before printing or emailing")
    if document.issue_blockers:
        raise HTTPException(409, "; ".join(document.issue_blockers))
    recipient = None
    if payload.method == "email":
        if document.document_kind != "recall":
            raise HTTPException(400, "Only recall letters can be emailed; prescriptions are print-only")
        if not recall_email.email_ready():
            raise HTTPException(409, "Recall email is switched off; print the letter for now")
        try:
            recipient = str(TypeAdapter(EmailStr).validate_python(patient.email))
        except ValidationError:
            raise HTTPException(409, "Add a valid patient email address before preparing an email")
    copy = DocumentCopy(patient_id=patient.id, document_id=document.id, source_document_id=document.id,
                        title=document.title, document_kind=document.document_kind,
                        method=payload.method, status="prepared", recipient=recipient,
                        sender=str(settings.smtp_from_email) if recipient else None,
                        pdf_bytes=document.frozen_pdf, request_id=str(request_id), created_by_user_id=user.id)
    db.add(copy)
    db.flush()
    audit(db, copy, user, request, "document_copy.prepared")
    db.commit()
    db.refresh(copy)
    return copy


@router.get("/document-copies/{copy_id}", response_model=CopyOut)
def get_copy(copy_id: int, db: Session = Depends(get_db), _user: User = Depends(read_copy)):
    return copy_or_404(db, copy_id)


@router.get("/document-copies/{copy_id}/pdf")
def get_pdf(copy_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(read_copy)):
    copy = copy_or_404(db, copy_id)
    audit(db, copy, user, request, "document_copy.viewed")
    db.commit()
    return Response(copy.pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="document-copy-{copy.id}.pdf"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.post("/document-copies/{copy_id}/confirm-print", response_model=CopyOut)
def confirm_print(copy_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(write_copy)):
    copy = copy_or_404(db, copy_id, lock=True)
    if copy.method != "print":
        raise HTTPException(409, "This copy was prepared for email")
    if copy.status == "printed":
        return copy
    if copy.status != "prepared":
        raise HTTPException(409, "This copy cannot be marked as printed")
    copy.status = "printed"
    return complete(db, copy, user, request)


@router.post("/document-copies/{copy_id}/send-email", response_model=CopyOut)
def send_email(copy_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(write_copy)):
    copy = copy_or_404(db, copy_id, lock=True)
    if copy.method != "email" or copy.document_kind != "recall":
        raise HTTPException(400, "Only prepared recall emails can be sent")
    if copy.status == "sent":
        return copy
    if copy.status != "prepared":
        raise HTTPException(409, "Email outcome is unconfirmed; check the mail service before sending another copy")
    if not recall_email.email_ready():
        raise HTTPException(409, "Recall email is switched off; print the letter for now")
    patient = get_patient_or_404(db, copy.patient_id)
    if patient.email != copy.recipient or str(settings.smtp_from_email) != copy.sender:
        raise HTTPException(409, "Email address changed; prepare and review a new email")
    # Commit before SMTP: a retry must never resend an ambiguously accepted message.
    copy.status = "sending"
    audit(db, copy, user, request, "document_copy.sending")
    db.commit()
    try:
        recall_email.send_recall(copy)
    except Exception:
        copy.status = "uncertain"
        audit(db, copy, user, request, "document_copy.email_unconfirmed")
        db.commit()
        raise HTTPException(502, "Email outcome is unconfirmed; check the mail service before sending another copy")
    copy.status = "sent"
    return complete(db, copy, user, request)
