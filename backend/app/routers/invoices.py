from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.appointment import Appointment
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, Payment
from app.models.patient import Patient
from app.models.user import User
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceLineOut,
    InvoiceLineUpdate,
    InvoiceOut,
    InvoiceSummaryOut,
    InvoiceUpdate,
    PaymentCreate,
    PaymentOut,
)
from app.services.audit import log_event, snapshot_model

router = APIRouter(prefix="/invoices", tags=["invoices"])


def format_invoice_number(invoice_id: int) -> str:
    return f"INV-{invoice_id:06d}"


def recalculate_totals(db: Session, invoice: Invoice) -> None:
    subtotal = (
        db.scalar(
            select(func.coalesce(func.sum(InvoiceLine.line_total_pence), 0)).where(
                InvoiceLine.invoice_id == invoice.id
            )
        )
        or 0
    )
    discount = invoice.discount_pence or 0
    invoice.subtotal_pence = subtotal
    invoice.total_pence = max(subtotal - discount, 0)


def update_status_from_payments(invoice: Invoice) -> None:
    if invoice.status == InvoiceStatus.void:
        return
    paid = invoice.paid_pence
    if paid <= 0:
        if invoice.status != InvoiceStatus.draft:
            invoice.status = InvoiceStatus.issued
    elif paid < invoice.total_pence:
        invoice.status = InvoiceStatus.part_paid
    else:
        invoice.status = InvoiceStatus.paid


@router.post("", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, payload.patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if payload.appointment_id is not None:
        appointment = db.get(Appointment, payload.appointment_id)
        if not appointment or appointment.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    invoice = Invoice(
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        invoice_number="",
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        status=InvoiceStatus.draft,
        notes=payload.notes,
        subtotal_pence=0,
        discount_pence=payload.discount_pence,
        total_pence=0,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(invoice)
    db.flush()
    invoice.invoice_number = format_invoice_number(invoice.id)
    recalculate_totals(db, invoice)
    log_event(
        db,
        actor=user,
        action="invoice.created",
        entity_type="invoice",
        entity_id=str(invoice.id),
        before_obj=None,
        after_obj=invoice,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("", response_model=list[InvoiceSummaryOut])
def list_invoices(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    patient_id: int | None = Query(default=None),
    status: InvoiceStatus | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Invoice)
    if patient_id is not None:
        stmt = stmt.where(Invoice.patient_id == patient_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    if q:
        stmt = stmt.where(Invoice.invoice_number.ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    before_data = snapshot_model(invoice)
    if invoice.status != InvoiceStatus.draft:
        allowed = {"notes"}
        payload_fields = set(payload.model_dump(exclude_unset=True).keys())
        if payload_fields - allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only notes can be updated once an invoice is issued.",
            )

    data = payload.model_dump(exclude_unset=True)
    if invoice.status == InvoiceStatus.draft:
        if "appointment_id" in data:
            if data["appointment_id"] is None:
                invoice.appointment_id = None
            else:
                appointment = db.get(Appointment, data["appointment_id"])
                if not appointment or appointment.deleted_at is not None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
                    )
                invoice.appointment_id = data["appointment_id"]
        if "issue_date" in data:
            invoice.issue_date = data["issue_date"]
        if "due_date" in data:
            invoice.due_date = data["due_date"]
        if "discount_pence" in data and data["discount_pence"] is not None:
            invoice.discount_pence = data["discount_pence"]
    if "notes" in data:
        invoice.notes = data["notes"]

    invoice.updated_by_user_id = user.id
    recalculate_totals(db, invoice)
    log_event(
        db,
        actor=user,
        action="invoice.updated",
        entity_type="invoice",
        entity_id=str(invoice.id),
        before_data=before_data,
        after_obj=invoice,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/lines", response_model=InvoiceLineOut, status_code=status.HTTP_201_CREATED)
def add_invoice_line(
    invoice_id: int,
    payload: InvoiceLineCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is not editable")

    line = InvoiceLine(
        invoice_id=invoice.id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price_pence=payload.unit_price_pence,
        line_total_pence=payload.quantity * payload.unit_price_pence,
    )
    db.add(line)
    db.flush()
    recalculate_totals(db, invoice)
    invoice.updated_by_user_id = user.id
    log_event(
        db,
        actor=user,
        action="invoice.updated",
        entity_type="invoice",
        entity_id=str(invoice.id),
        before_obj=None,
        after_obj=invoice,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(line)
    return line


@router.patch("/{invoice_id}/lines/{line_id}", response_model=InvoiceLineOut)
def update_invoice_line(
    invoice_id: int,
    line_id: int,
    payload: InvoiceLineUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is not editable")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")

    data = payload.model_dump(exclude_unset=True)
    if "description" in data:
        line.description = data["description"]
    if "quantity" in data and data["quantity"] is not None:
        line.quantity = data["quantity"]
    if "unit_price_pence" in data and data["unit_price_pence"] is not None:
        line.unit_price_pence = data["unit_price_pence"]
    line.line_total_pence = line.quantity * line.unit_price_pence
    recalculate_totals(db, invoice)
    invoice.updated_by_user_id = user.id
    log_event(
        db,
        actor=user,
        action="invoice.updated",
        entity_type="invoice",
        entity_id=str(invoice.id),
        before_obj=None,
        after_obj=invoice,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(line)
    return line


@router.delete("/{invoice_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice_line(
    invoice_id: int,
    line_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is not editable")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")
    db.delete(line)
    recalculate_totals(db, invoice)
    invoice.updated_by_user_id = user.id
    log_event(
        db,
        actor=user,
        action="invoice.updated",
        entity_type="invoice",
        entity_id=str(invoice.id),
        before_obj=None,
        after_obj=invoice,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    return None


@router.post("/{invoice_id}/issue", response_model=InvoiceOut)
def issue_invoice(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status != InvoiceStatus.draft:
        return invoice

    recalculate_totals(db, invoice)
    if invoice.issue_date is None:
        invoice.issue_date = date.today()
    invoice.status = InvoiceStatus.issued
    invoice.updated_by_user_id = user.id
    log_event(
        db,
        actor=user,
        action="invoice.issued",
        entity_type="invoice",
        entity_id=str(invoice.id),
        before_obj=None,
        after_obj=invoice,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/void", response_model=InvoiceOut)
def void_invoice(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status == InvoiceStatus.void:
        return invoice

    invoice.status = InvoiceStatus.void
    invoice.updated_by_user_id = user.id
    log_event(
        db,
        actor=user,
        action="invoice.voided",
        entity_type="invoice",
        entity_id=str(invoice.id),
        before_obj=None,
        after_obj=invoice,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def add_payment(
    invoice_id: int,
    payload: PaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status == InvoiceStatus.void:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is void")
    if invoice.status == InvoiceStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue the invoice before recording payments",
        )

    payment = Payment(
        invoice_id=invoice.id,
        amount_pence=payload.amount_pence,
        method=payload.method,
        paid_at=payload.paid_at or datetime.now(timezone.utc),
        reference=payload.reference,
        received_by_user_id=user.id,
    )
    db.add(payment)
    db.flush()

    before_status = invoice.status
    update_status_from_payments(invoice)
    invoice.updated_by_user_id = user.id
    log_event(
        db,
        actor=user,
        action="payment.recorded",
        entity_type="invoice",
        entity_id=str(invoice.id),
        before_obj=None,
        after_obj=invoice,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    if before_status != InvoiceStatus.paid and invoice.status == InvoiceStatus.paid:
        log_event(
            db,
            actor=user,
            action="invoice.paid",
            entity_type="invoice",
            entity_id=str(invoice.id),
            before_obj=None,
            after_obj=invoice,
            request_id=request_id,
            ip_address=request.client.host if request else None,
        )
    db.commit()
    db.refresh(payment)
    return payment
