from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.invoice import Invoice, Payment
from app.models.patient import Patient, RecallStatus
from app.models.user import User
from app.schemas.patient import PatientRecallOut, RecallUpdate
from app.schemas.patient_document import PatientDocumentCreate, PatientDocumentOut
from app.models.document_template import DocumentTemplate
from app.models.patient_document import PatientDocument
from app.services.audit import log_event, snapshot_model
from app.services.document_render import render_template_with_warnings

router = APIRouter(prefix="/recalls", tags=["recalls"])


def _stringify(value: object | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, str) and not value.strip():
        return "none"
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _log_recall_timeline(
    db: Session,
    *,
    actor: User,
    patient: Patient,
    before_data: dict,
    request_id: str | None,
    ip_address: str | None,
) -> None:
    old_status = _stringify(before_data.get("recall_status"))
    new_status = _stringify(patient.recall_status)
    if old_status != new_status:
        log_event(
            db,
            actor=actor,
            action=f"recall.status: {old_status} -> {new_status}",
            entity_type="patient",
            entity_id=str(patient.id),
            after_data={"recall_status": new_status},
            request_id=request_id,
            ip_address=ip_address,
        )

    old_type = _stringify(before_data.get("recall_type"))
    new_type = _stringify(patient.recall_type)
    if old_type != new_type:
        log_event(
            db,
            actor=actor,
            action=f"recall.type: {old_type} -> {new_type}",
            entity_type="patient",
            entity_id=str(patient.id),
            after_data={"recall_type": new_type},
            request_id=request_id,
            ip_address=ip_address,
        )

    old_notes = (before_data.get("recall_notes") or "").strip()
    new_notes = (patient.recall_notes or "").strip()
    if old_notes != new_notes:
        log_event(
            db,
            actor=actor,
            action="recall.notes_updated",
            entity_type="patient",
            entity_id=str(patient.id),
            after_data={"recall_notes": bool(new_notes)},
            request_id=request_id,
            ip_address=ip_address,
        )

    old_contacted = before_data.get("recall_last_contacted_at")
    new_contacted = (
        patient.recall_last_contacted_at.isoformat()
        if patient.recall_last_contacted_at
        else None
    )
    if not old_contacted and new_contacted:
        log_event(
            db,
            actor=actor,
            action="recall.contacted",
            entity_type="patient",
            entity_id=str(patient.id),
            after_data={"recall_last_contacted_at": new_contacted},
            request_id=request_id,
            ip_address=ip_address,
        )

@router.get("", response_model=list[PatientRecallOut])
def list_recalls(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    status: RecallStatus | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    payment_sum = (
        select(
            Payment.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(Payment.amount_pence), 0).label("paid_pence"),
        )
        .group_by(Payment.invoice_id)
        .subquery()
    )
    invoice_balance = (
        select(
            Invoice.patient_id.label("patient_id"),
            (Invoice.total_pence - func.coalesce(payment_sum.c.paid_pence, 0)).label(
                "balance_pence"
            ),
        )
        .outerjoin(payment_sum, payment_sum.c.invoice_id == Invoice.id)
        .subquery()
    )
    patient_balance = (
        select(
            invoice_balance.c.patient_id.label("patient_id"),
            func.coalesce(func.sum(invoice_balance.c.balance_pence), 0).label("balance_pence"),
        )
        .group_by(invoice_balance.c.patient_id)
        .subquery()
    )

    stmt = (
        select(Patient, patient_balance.c.balance_pence)
        .outerjoin(patient_balance, patient_balance.c.patient_id == Patient.id)
        .where(Patient.deleted_at.is_(None))
        .where(Patient.recall_due_date.is_not(None))
        .order_by(Patient.recall_due_date.asc(), Patient.last_name.asc())
        .limit(limit)
        .offset(offset)
    )
    if start:
        stmt = stmt.where(Patient.recall_due_date >= start)
    if end:
        stmt = stmt.where(Patient.recall_due_date <= end)
    if status:
        stmt = stmt.where(Patient.recall_status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.phone.ilike(like),
                Patient.postcode.ilike(like),
            )
        )

    results = db.execute(stmt).all()
    output: list[PatientRecallOut] = []
    for patient, balance_pence in results:
        output.append(
            PatientRecallOut(
                id=patient.id,
                first_name=patient.first_name,
                last_name=patient.last_name,
                phone=patient.phone,
                postcode=patient.postcode,
                recall_interval_months=patient.recall_interval_months,
                recall_due_date=patient.recall_due_date,
                recall_status=patient.recall_status,
                recall_type=patient.recall_type,
                recall_last_contacted_at=patient.recall_last_contacted_at,
                recall_notes=patient.recall_notes,
                recall_last_set_at=patient.recall_last_set_at,
                balance_pence=balance_pence,
            )
        )
    return output


@router.patch("/{patient_id}", response_model=PatientRecallOut)
def update_recall(
    patient_id: int,
    payload: RecallUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    before_data = snapshot_model(patient)
    if payload.interval_months is not None:
        patient.recall_interval_months = payload.interval_months
    if payload.due_date is not None:
        patient.recall_due_date = payload.due_date
    if payload.status is not None:
        patient.recall_status = payload.status
    if payload.recall_type is not None:
        patient.recall_type = payload.recall_type
    if payload.notes is not None:
        patient.recall_notes = payload.notes
    if payload.last_contacted_at is not None:
        patient.recall_last_contacted_at = payload.last_contacted_at
    elif payload.status == RecallStatus.contacted and not patient.recall_last_contacted_at:
        patient.recall_last_contacted_at = datetime.now(timezone.utc)

    if patient.recall_due_date and not patient.recall_status:
        patient.recall_status = RecallStatus.due
    if not patient.recall_due_date:
        patient.recall_status = None

    patient.recall_last_set_at = datetime.now(timezone.utc)
    patient.recall_last_set_by_user_id = user.id
    patient.updated_by_user_id = user.id
    patient.updated_at = datetime.now(timezone.utc)
    db.add(patient)
    _log_recall_timeline(
        db,
        actor=user,
        patient=patient,
        before_data=before_data or {},
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return PatientRecallOut(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        phone=patient.phone,
        postcode=patient.postcode,
        recall_interval_months=patient.recall_interval_months,
        recall_due_date=patient.recall_due_date,
        recall_status=patient.recall_status,
        recall_type=patient.recall_type,
        recall_last_contacted_at=patient.recall_last_contacted_at,
        recall_notes=patient.recall_notes,
        recall_last_set_at=patient.recall_last_set_at,
        balance_pence=None,
    )


@router.post("/{patient_id}/generate-document", response_model=PatientDocumentOut)
def generate_recall_document(
    patient_id: int,
    payload: PatientDocumentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    template = db.get(DocumentTemplate, payload.template_id)
    if not template or template.deleted_at is not None or not template.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

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
            "source": "recalls",
        },
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    log_event(
        db,
        actor=user,
        action="recall.letter_generated",
        entity_type="patient",
        entity_id=str(patient.id),
        after_data={
            "patient_document_id": document.id,
            "template_id": template.id,
            "pdf_available": True,
        },
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(document)
    output = PatientDocumentOut.model_validate(document)
    return output.model_copy(update={"unknown_fields": unknown_fields})
