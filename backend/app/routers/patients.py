from calendar import monthrange
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, nullslast, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.audit_log import AuditLog
from app.models.invoice import Invoice, Payment
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.patient import Patient, PatientCategory, RecallStatus
from app.models.patient_recall import PatientRecall, PatientRecallStatus
from app.services.audit import log_event, snapshot_model
from app.services.recalls import resolve_recall_status
from app.schemas.audit_log import AuditLogOut
from app.schemas.patient import (
    PatientCreate,
    PatientFinanceItemOut,
    PatientFinanceSummaryOut,
    PatientOut,
    PatientSearchOut,
    PatientRecallCreate,
    PatientRecallOut,
    PatientRecallUpdate,
    PatientUpdate,
    RecallUpdate,
)
from app.schemas.ledger import LedgerChargeCreate, LedgerEntryOut, LedgerPaymentCreate
from app.models.user import User

router = APIRouter(prefix="/patients", tags=["patients"])


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


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


@router.get("", response_model=list[PatientOut])
def list_patients(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    query: str | None = Query(default=None, alias="query"),
    q: str | None = Query(default=None, alias="q"),
    email: str | None = Query(default=None),
    dob: date | None = Query(default=None),
    category: PatientCategory | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Patient).order_by(Patient.last_name, Patient.first_name)
    if not include_deleted:
        stmt = stmt.where(Patient.deleted_at.is_(None))
    search = q or query
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.email.ilike(like),
                Patient.phone.ilike(like),
            )
        )
    if email:
        stmt = stmt.where(Patient.email.ilike(f"%{email.strip()}%"))
    if dob:
        stmt = stmt.where(Patient.date_of_birth == dob)
    if category:
        stmt = stmt.where(Patient.patient_category == category)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/search", response_model=list[PatientSearchOut])
def search_patients(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
):
    term = q.strip()
    like = f"%{term}%"
    stmt = select(Patient).where(Patient.deleted_at.is_(None))
    criteria = [
        Patient.first_name.ilike(like),
        Patient.last_name.ilike(like),
        Patient.phone.ilike(like),
    ]
    try:
        parsed = date.fromisoformat(term)
        criteria.append(Patient.date_of_birth == parsed)
    except ValueError:
        pass
    stmt = stmt.where(or_(*criteria)).order_by(Patient.last_name, Patient.first_name).limit(limit)
    return list(db.scalars(stmt))


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = Patient(
        nhs_number=payload.nhs_number,
        title=payload.title,
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=payload.date_of_birth,
        phone=payload.phone,
        email=payload.email,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        postcode=payload.postcode,
        patient_category=payload.patient_category,
        denplan_member_no=payload.denplan_member_no,
        denplan_plan_name=payload.denplan_plan_name,
        care_setting=payload.care_setting,
        visit_address_text=payload.visit_address_text,
        access_notes=payload.access_notes,
        primary_contact_name=payload.primary_contact_name,
        primary_contact_phone=payload.primary_contact_phone,
        primary_contact_relationship=payload.primary_contact_relationship,
        referral_source=payload.referral_source,
        referral_contact_name=payload.referral_contact_name,
        referral_contact_phone=payload.referral_contact_phone,
        referral_notes=payload.referral_notes,
        notes=payload.notes,
        allergies=payload.allergies,
        medical_alerts=payload.medical_alerts,
        safeguarding_notes=payload.safeguarding_notes,
        alerts_financial=payload.alerts_financial,
        alerts_access=payload.alerts_access,
        recall_interval_months=payload.recall_interval_months or 6,
        recall_due_date=payload.recall_due_date,
        recall_status=payload.recall_status,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    if patient.recall_due_date and not patient.recall_status:
        patient.recall_status = RecallStatus.due
    db.add(patient)
    db.flush()
    log_event(
        db,
        actor=user,
        action="create",
        entity_type="patient",
        entity_id=str(patient.id),
        before_obj=None,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    include_deleted: bool = Query(default=False),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is not None and not include_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    before_data = snapshot_model(patient)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    if any(
        field in payload.model_fields_set
        for field in ("recall_due_date", "recall_interval_months", "recall_status")
    ):
        patient.recall_last_set_at = datetime.now(timezone.utc)
        patient.recall_last_set_by_user_id = user.id
        if patient.recall_due_date and not patient.recall_status:
            patient.recall_status = RecallStatus.due
        if not patient.recall_due_date:
            patient.recall_status = None
    patient.updated_by_user_id = user.id
    patient.updated_at = datetime.now(timezone.utc)
    db.add(patient)
    log_event(
        db,
        actor=user,
        action="update",
        entity_type="patient",
        entity_id=str(patient.id),
        before_data=before_data,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/archive", response_model=PatientOut)
def archive_patient(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is not None:
        return patient

    before_data = snapshot_model(patient)
    patient.deleted_at = datetime.now(timezone.utc)
    patient.deleted_by_user_id = user.id
    patient.updated_by_user_id = user.id
    db.add(patient)
    log_event(
        db,
        actor=user,
        action="delete",
        entity_type="patient",
        entity_id=str(patient.id),
        before_data=before_data,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/restore", response_model=PatientOut)
def restore_patient(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is None:
        return patient

    before_data = snapshot_model(patient)
    patient.deleted_at = None
    patient.deleted_by_user_id = None
    patient.updated_by_user_id = user.id
    db.add(patient)
    log_event(
        db,
        actor=user,
        action="restore",
        entity_type="patient",
        entity_id=str(patient.id),
        before_data=before_data,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/recall", response_model=PatientOut)
def set_patient_recall(
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
    elif payload.interval_months is not None:
        patient.recall_due_date = add_months(
            date.today(), max(patient.recall_interval_months, 1)
        )
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
    elif patient.recall_due_date and not patient.recall_status:
        patient.recall_status = RecallStatus.due

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
    return patient


@router.get("/{patient_id}/audit", response_model=list[AuditLogOut])
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


@router.get("/{patient_id}/ledger", response_model=list[LedgerEntryOut])
def list_patient_ledger(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    stmt = (
        select(PatientLedgerEntry)
        .where(PatientLedgerEntry.patient_id == patient_id)
        .order_by(PatientLedgerEntry.created_at.asc(), PatientLedgerEntry.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


@router.get("/{patient_id}/balance")
def get_patient_balance(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    balance = (
        db.scalar(
            select(func.coalesce(func.sum(PatientLedgerEntry.amount_pence), 0)).where(
                PatientLedgerEntry.patient_id == patient_id
            )
        )
        or 0
    )
    return {"balance_pence": balance}


@router.get("/{patient_id}/finance-summary", response_model=PatientFinanceSummaryOut)
def get_patient_finance_summary(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=20),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    balance = (
        db.scalar(
            select(func.coalesce(func.sum(PatientLedgerEntry.amount_pence), 0)).where(
                PatientLedgerEntry.patient_id == patient_id
            )
        )
        or 0
    )

    invoices = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.patient_id == patient_id)
            .order_by(nullslast(Invoice.issue_date.desc()), Invoice.created_at.desc())
            .limit(limit)
        )
    )
    payments = list(
        db.scalars(
            select(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(Invoice.patient_id == patient_id)
            .order_by(Payment.paid_at.desc())
            .limit(limit)
        )
    )

    items: list[tuple[datetime, PatientFinanceItemOut]] = []
    for invoice in invoices:
        invoice_date = invoice.issue_date or invoice.created_at.date()
        sort_key = (
            datetime.combine(invoice_date, datetime.min.time())
            if invoice.issue_date
            else invoice.created_at
        )
        items.append(
            (
                sort_key,
                PatientFinanceItemOut(
                    id=invoice.id,
                    kind="invoice",
                    date=invoice_date,
                    amount_pence=invoice.total_pence,
                    status=invoice.status.value,
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                ),
            )
        )

    for payment in payments:
        invoice = payment.invoice
        items.append(
            (
                payment.paid_at,
                PatientFinanceItemOut(
                    id=payment.id,
                    kind="payment",
                    date=payment.paid_at.date(),
                    amount_pence=payment.amount_pence,
                    status="received",
                    invoice_id=payment.invoice_id,
                    payment_id=payment.id,
                    invoice_number=invoice.invoice_number if invoice else None,
                ),
            )
        )

    items.sort(key=lambda entry: entry[0], reverse=True)
    summary_items = [entry for _, entry in items[:limit]]

    return PatientFinanceSummaryOut(
        patient_id=patient_id,
        outstanding_balance_pence=int(balance),
        items=summary_items,
    )


@router.get("/{patient_id}/recalls", response_model=list[PatientRecallOut])
def list_patient_recalls(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    recalls = list(
        db.scalars(
            select(PatientRecall)
            .where(PatientRecall.patient_id == patient_id)
            .order_by(PatientRecall.due_date.asc(), PatientRecall.id.asc())
        )
    )
    output: list[PatientRecallOut] = []
    for recall in recalls:
        resolved_status = resolve_recall_status(recall)
        recall_out = PatientRecallOut.model_validate(recall).model_copy(
            update={"status": resolved_status}
        )
        output.append(recall_out)
    return output


@router.post(
    "/{patient_id}/recalls",
    response_model=PatientRecallOut,
    status_code=status.HTTP_201_CREATED,
)
def create_patient_recall(
    patient_id: int,
    payload: PatientRecallCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    recall = PatientRecall(
        patient_id=patient_id,
        kind=payload.kind,
        due_date=payload.due_date,
        status=payload.status,
        notes=payload.notes,
        completed_at=payload.completed_at,
        outcome=payload.outcome,
        linked_appointment_id=payload.linked_appointment_id,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    if recall.status == PatientRecallStatus.completed and recall.completed_at is None:
        recall.completed_at = datetime.now(timezone.utc)
    db.add(recall)
    db.commit()
    db.refresh(recall)
    resolved_status = resolve_recall_status(recall)
    return PatientRecallOut.model_validate(recall).model_copy(
        update={"status": resolved_status}
    )


@router.patch(
    "/{patient_id}/recalls/{recall_id}",
    response_model=PatientRecallOut,
)
def update_patient_recall(
    patient_id: int,
    recall_id: int,
    payload: PatientRecallUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    recall = db.get(PatientRecall, recall_id)
    if not recall or recall.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recall not found")

    if payload.kind is not None:
        recall.kind = payload.kind
    if payload.due_date is not None:
        recall.due_date = payload.due_date
    if payload.status is not None:
        recall.status = payload.status
    if payload.notes is not None:
        recall.notes = payload.notes
    if payload.completed_at is not None:
        recall.completed_at = payload.completed_at
    if payload.outcome is not None:
        recall.outcome = payload.outcome
    if payload.linked_appointment_id is not None:
        recall.linked_appointment_id = payload.linked_appointment_id
    if payload.status == PatientRecallStatus.completed and payload.completed_at is None:
        recall.completed_at = datetime.now(timezone.utc)

    recall.updated_by_user_id = user.id
    db.commit()
    db.refresh(recall)
    resolved_status = resolve_recall_status(recall)
    return PatientRecallOut.model_validate(recall).model_copy(
        update={"status": resolved_status}
    )


@router.post("/{patient_id}/payments", response_model=LedgerEntryOut)
def add_patient_payment(
    patient_id: int,
    payload: LedgerPaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if payload.amount_pence <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

    entry = PatientLedgerEntry(
        patient_id=patient_id,
        entry_type=LedgerEntryType.payment,
        amount_pence=-abs(payload.amount_pence),
        method=payload.method,
        reference=payload.reference,
        note=payload.note,
        related_invoice_id=payload.related_invoice_id,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(entry)
    db.flush()
    log_event(
        db,
        actor=user,
        action="ledger.payment_recorded",
        entity_type="patient",
        entity_id=str(patient_id),
        before_obj=None,
        after_obj=entry,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{patient_id}/charges", response_model=LedgerEntryOut)
def add_patient_charge(
    patient_id: int,
    payload: LedgerChargeCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if payload.amount_pence <= 0:
        raise HTTPException(status_code=400, detail="Charge amount must be positive")
    if payload.entry_type not in (LedgerEntryType.charge, LedgerEntryType.adjustment):
        raise HTTPException(status_code=400, detail="Invalid ledger entry type")

    entry = PatientLedgerEntry(
        patient_id=patient_id,
        entry_type=payload.entry_type,
        amount_pence=abs(payload.amount_pence),
        reference=payload.reference,
        note=payload.note,
        related_invoice_id=payload.related_invoice_id,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(entry)
    db.flush()
    log_event(
        db,
        actor=user,
        action="ledger.charge_recorded",
        entity_type="patient",
        entity_id=str(patient_id),
        before_obj=None,
        after_obj=entry,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(entry)
    return entry
