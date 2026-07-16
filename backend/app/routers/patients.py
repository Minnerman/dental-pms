from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
import base64
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, func, literal, nullslast, or_, select
from sqlalchemy.orm import Session, aliased

from app.db.session import get_db
from app.deps import get_current_user, require_capability
from app.models.audit_log import AuditLog
from app.models.appointment import Appointment
from app.models.invoice import Invoice, Payment
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.patient import Patient, PatientCategory, RecallStatus
from app.models.patient_recall import PatientRecall, PatientRecallStatus
from app.models.r4_treatment_plan import R4Treatment
from app.models.r4_treatment_transaction import R4TreatmentTransaction
from app.models.patient_recall_communication import (
    PatientRecallCommunication,
    PatientRecallCommunicationChannel,
    PatientRecallCommunicationDirection,
    PatientRecallCommunicationStatus,
)
from app.models.r4_user import R4User
from app.services.audit import log_event, snapshot_model
from app.services.recall_letter_pdf import build_recall_letter_pdf
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
from app.schemas.recall_communication import (
    RecallCommunicationCreate,
    RecallCommunicationOut,
)
from app.schemas.ledger import LedgerChargeCreate, LedgerEntryOut, LedgerPaymentCreate
from app.schemas.r4_treatment_transaction import R4TreatmentTransactionListOut
from app.models.user import User
from app.services.recall_communications import log_recall_communication
from app.services.recalls_audit import (
    build_patient_recall_settings_snapshot,
    build_recall_snapshot,
    log_patient_recall_settings_changes,
    log_recall_activity,
    log_recall_changes,
    log_recall_created,
)
from app.routers.recalls import bump_export_count_cache_epoch

router = APIRouter(prefix="/patients", tags=["patients"])


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _encode_tx_cursor(performed_at: datetime, legacy_transaction_id: int) -> str:
    payload = {
        "performed_at": performed_at.isoformat(),
        "legacy_transaction_id": legacy_transaction_id,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return encoded


def _naive_utc_sort_key(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _decode_tx_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        payload = json.loads(raw)
        performed_at = datetime.fromisoformat(payload["performed_at"])
        legacy_transaction_id = int(payload["legacy_transaction_id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor.") from exc
    return performed_at, legacy_transaction_id


@router.get("", response_model=list[PatientOut])
def list_patients(
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("patients.view")),
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
                (Patient.first_name + literal(" ") + Patient.last_name).ilike(like),
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
    _user: User = Depends(require_capability("patients.view")),
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
    user: User = Depends(require_capability("patients.write")),
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
    _user: User = Depends(require_capability("patients.view")),
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
    user: User = Depends(require_capability("patients.write")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    updates = payload.model_dump(exclude_unset=True)
    changed_updates = {
        field: value
        for field, value in updates.items()
        if getattr(patient, field) != value
    }
    if not changed_updates:
        return patient

    before_data = snapshot_model(patient)
    for field, value in changed_updates.items():
        setattr(patient, field, value)
    if any(
        field in changed_updates
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
    user: User = Depends(require_capability("patients.write")),
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
        action="archive",
        entity_type="patient",
        entity_id=str(patient.id),
        before_data=before_data,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    bump_export_count_cache_epoch("patients.archive_patient")
    return patient


@router.post("/{patient_id}/restore", response_model=PatientOut)
def restore_patient(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("patients.write")),
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
    bump_export_count_cache_epoch("patients.restore_patient")
    return patient


@router.post("/{patient_id}/recall", response_model=PatientOut)
def set_patient_recall(
    patient_id: int,
    payload: RecallUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("recalls.write")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    before_data = build_patient_recall_settings_snapshot(patient)
    before_notes = patient.recall_notes
    fields = payload.model_fields_set
    if "interval_months" in fields and payload.interval_months is not None:
        patient.recall_interval_months = payload.interval_months
    if "due_date" in fields:
        patient.recall_due_date = payload.due_date
    elif "interval_months" in fields and payload.interval_months is not None:
        patient.recall_due_date = add_months(
            date.today(), max(patient.recall_interval_months, 1)
        )
    if "status" in fields:
        patient.recall_status = payload.status
    if "recall_type" in fields:
        patient.recall_type = payload.recall_type
    if "notes" in fields:
        patient.recall_notes = payload.notes
    if "last_contacted_at" in fields:
        patient.recall_last_contacted_at = payload.last_contacted_at
    elif payload.status == RecallStatus.contacted and not patient.recall_last_contacted_at:
        patient.recall_last_contacted_at = datetime.now(timezone.utc)
    if patient.recall_due_date and not patient.recall_status:
        patient.recall_status = RecallStatus.due
    if not patient.recall_due_date:
        patient.recall_status = None

    after_data = build_patient_recall_settings_snapshot(patient)
    notes_changed = before_notes != patient.recall_notes
    if before_data == after_data and not notes_changed:
        return patient

    patient.recall_last_set_at = datetime.now(timezone.utc)
    patient.recall_last_set_by_user_id = user.id
    patient.updated_by_user_id = user.id
    patient.updated_at = datetime.now(timezone.utc)
    db.add(patient)
    log_patient_recall_settings_changes(
        db,
        user=user,
        patient_id=patient.id,
        before=before_data,
        after=after_data,
        notes_changed=notes_changed,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    bump_export_count_cache_epoch("patients.set_patient_recall")
    return patient


@router.get("/{patient_id}/audit", response_model=list[AuditLogOut])
def patient_audit(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("patients.view")),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
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


@router.get(
    "/{patient_id}/treatment-transactions",
    response_model=R4TreatmentTransactionListOut,
)
def list_patient_treatment_transactions(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    cost_only: bool = Query(default=False),
    include_total: bool = Query(default=False),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if not patient.legacy_id:
        return {
            "items": [],
            "next_cursor": None,
            "total_count": 0 if include_total else None,
        }
    try:
        patient_code = int(patient.legacy_id)
    except ValueError:
        return {
            "items": [],
            "next_cursor": None,
            "total_count": 0 if include_total else None,
        }

    recorded_user = aliased(R4User)
    entry_user = aliased(R4User)
    treatment = aliased(R4Treatment)
    filters = [R4TreatmentTransaction.patient_code == patient_code]
    if cost_only:
        filters.append(
            or_(
                R4TreatmentTransaction.patient_cost > 0,
                R4TreatmentTransaction.dpb_cost > 0,
            )
        )
    if date_from is not None:
        start = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        filters.append(R4TreatmentTransaction.performed_at >= start)
    if date_to is not None:
        end = datetime.combine(date_to, datetime.min.time()).replace(
            tzinfo=timezone.utc
        ) + timedelta(days=1)
        filters.append(R4TreatmentTransaction.performed_at < end)
    stmt = (
        select(
            R4TreatmentTransaction,
            recorded_user.display_name.label("recorded_by_name"),
            entry_user.display_name.label("user_name"),
            treatment.description.label("treatment_name"),
            recorded_user.is_current.label("recorded_by_is_current"),
            entry_user.is_current.label("user_is_current"),
            recorded_user.role.label("recorded_by_role"),
            entry_user.role.label("user_role"),
        )
        .where(*filters)
        .outerjoin(
            recorded_user,
            and_(
                recorded_user.legacy_source == R4TreatmentTransaction.legacy_source,
                recorded_user.legacy_user_code == R4TreatmentTransaction.recorded_by,
            ),
        )
        .outerjoin(
            entry_user,
            and_(
                entry_user.legacy_source == R4TreatmentTransaction.legacy_source,
                entry_user.legacy_user_code == R4TreatmentTransaction.user_code,
            ),
        )
        .outerjoin(
            treatment,
            and_(
                treatment.legacy_source == R4TreatmentTransaction.legacy_source,
                treatment.legacy_treatment_code == R4TreatmentTransaction.treatment_code,
            ),
        )
    )
    if cursor:
        cursor_dt, cursor_id = _decode_tx_cursor(cursor)
        stmt = stmt.where(
            or_(
                R4TreatmentTransaction.performed_at < cursor_dt,
                and_(
                    R4TreatmentTransaction.performed_at == cursor_dt,
                    R4TreatmentTransaction.legacy_transaction_id < cursor_id,
                ),
            )
        )

    stmt = stmt.order_by(
        R4TreatmentTransaction.performed_at.desc(),
        R4TreatmentTransaction.legacy_transaction_id.desc(),
    ).limit(limit + 1)
    rows = list(db.execute(stmt).all())
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last_tx = items[-1][0]
        next_cursor = _encode_tx_cursor(last_tx.performed_at, last_tx.legacy_transaction_id)
    total_count = None
    if include_total:
        total_count = (
            db.scalar(
                select(func.count())
                .select_from(R4TreatmentTransaction)
                .where(*filters)
            )
            or 0
        )
    payload_items: list[dict[str, object]] = []
    for (
        tx,
        recorded_name,
        user_name,
        treatment_name,
        recorded_is_current,
        user_is_current,
        recorded_role,
        user_role,
    ) in items:
        payload_items.append(
            {
                "legacy_transaction_id": tx.legacy_transaction_id,
                "performed_at": tx.performed_at,
                "treatment_code": tx.treatment_code,
                "trans_code": tx.trans_code,
                "patient_cost": tx.patient_cost,
                "dpb_cost": tx.dpb_cost,
                "treatment_name": treatment_name,
                "recorded_by": tx.recorded_by,
                "user_code": tx.user_code,
                "recorded_by_name": recorded_name,
                "user_name": user_name,
                "recorded_by_is_current": recorded_is_current,
                "user_is_current": user_is_current,
                "recorded_by_role": recorded_role,
                "user_role": user_role,
            }
        )
    return {
        "items": payload_items,
        "next_cursor": next_cursor,
        "total_count": total_count,
    }


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
        sort_key = _naive_utc_sort_key(
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
                _naive_utc_sort_key(payment.paid_at),
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
    _user: User = Depends(require_capability("recalls.view")),
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
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("recalls.write")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if payload.linked_appointment_id is not None:
        appointment = db.get(Appointment, payload.linked_appointment_id)
        if (
            not appointment
            or appointment.deleted_at is not None
            or appointment.patient_id != patient_id
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Linked appointment must belong to this patient.",
            )

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
    db.flush()
    log_recall_created(
        db,
        user=user,
        recall=recall,
        request_id=request_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(recall)
    bump_export_count_cache_epoch("patients.create_recall")
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
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("recalls.write")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    recall = db.get(PatientRecall, recall_id)
    if not recall or recall.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recall not found")

    fields = payload.model_fields_set
    if "kind" in fields and payload.kind is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recall type cannot be empty.",
        )
    if "due_date" in fields and payload.due_date is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recall due date cannot be empty.",
        )
    if "status" in fields and payload.status is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recall status cannot be empty.",
        )

    target_status = payload.status if "status" in fields else recall.status
    if (
        recall.status in {PatientRecallStatus.completed, PatientRecallStatus.cancelled}
        and target_status in {PatientRecallStatus.completed, PatientRecallStatus.cancelled}
        and target_status != recall.status
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unsupported recall transition.",
        )
    if (
        target_status != PatientRecallStatus.completed
        and "completed_at" in fields
        and payload.completed_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Completion time is only valid for completed recalls.",
        )
    if "linked_appointment_id" in fields and payload.linked_appointment_id is not None:
        appointment = db.get(Appointment, payload.linked_appointment_id)
        if (
            not appointment
            or appointment.deleted_at is not None
            or appointment.patient_id != patient_id
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Linked appointment must belong to this patient.",
            )

    before_data = build_recall_snapshot(recall)
    before_notes = recall.notes
    if "kind" in fields:
        recall.kind = payload.kind
    if "due_date" in fields:
        recall.due_date = payload.due_date
    if "status" in fields:
        recall.status = payload.status
    if "notes" in fields:
        recall.notes = payload.notes
    if "outcome" in fields:
        recall.outcome = payload.outcome
    if "linked_appointment_id" in fields:
        recall.linked_appointment_id = payload.linked_appointment_id

    if target_status == PatientRecallStatus.completed:
        if recall.status != PatientRecallStatus.completed:
            recall.status = PatientRecallStatus.completed
        if before_data["status"] != PatientRecallStatus.completed.value:
            recall.completed_at = payload.completed_at or datetime.now(timezone.utc)
        elif recall.completed_at is None:
            recall.completed_at = payload.completed_at or datetime.now(timezone.utc)
    else:
        recall.completed_at = None
        if before_data["status"] in {
            PatientRecallStatus.completed.value,
            PatientRecallStatus.cancelled.value,
        } and "outcome" not in fields:
            recall.outcome = None

    after_data = build_recall_snapshot(recall)
    notes_changed = before_notes != recall.notes
    if before_data == after_data and not notes_changed:
        return PatientRecallOut.model_validate(recall).model_copy(
            update={"status": resolve_recall_status(recall)}
        )

    recall.updated_by_user_id = user.id
    log_recall_changes(
        db,
        user=user,
        patient_id=patient_id,
        before=before_data,
        after=after_data,
        notes_changed=notes_changed,
        request_id=request_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(recall)
    bump_export_count_cache_epoch("patients.update_recall")
    resolved_status = resolve_recall_status(recall)
    return PatientRecallOut.model_validate(recall).model_copy(
        update={"status": resolved_status}
    )


@router.get(
    "/{patient_id}/recalls/{recall_id}/communications",
    response_model=list[RecallCommunicationOut],
)
def list_recall_communications(
    patient_id: int,
    recall_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_capability("recalls.view")),
    limit: int = Query(default=3, ge=1, le=50),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    recall = db.get(PatientRecall, recall_id)
    if not recall or recall.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recall not found")
    rows = list(
        db.scalars(
            select(PatientRecallCommunication)
            .where(PatientRecallCommunication.patient_id == patient_id)
            .where(PatientRecallCommunication.recall_id == recall_id)
            .order_by(
                func.coalesce(
                    PatientRecallCommunication.contacted_at,
                    PatientRecallCommunication.created_at,
                ).desc(),
                PatientRecallCommunication.id.desc(),
            )
            .limit(limit)
        )
    )
    return [RecallCommunicationOut.model_validate(row) for row in rows]


@router.post(
    "/{patient_id}/recalls/{recall_id}/communications",
    response_model=RecallCommunicationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_recall_communication(
    patient_id: int,
    recall_id: int,
    payload: RecallCommunicationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("recalls.write")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    recall = db.get(PatientRecall, recall_id)
    if not recall or recall.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recall not found")
    entry = log_recall_communication(
        db,
        patient_id=patient_id,
        recall_id=recall_id,
        channel=payload.channel,
        direction=PatientRecallCommunicationDirection.outbound,
        status=PatientRecallCommunicationStatus.sent,
        notes=payload.notes,
        other_detail=payload.other_detail,
        outcome=payload.outcome,
        contacted_at=payload.contacted_at,
        created_by_user_id=user.id,
        guard_seconds=60,
    )
    if entry is None:
        existing_query = (
            select(PatientRecallCommunication)
            .where(PatientRecallCommunication.patient_id == patient_id)
            .where(PatientRecallCommunication.recall_id == recall_id)
            .where(PatientRecallCommunication.channel == payload.channel)
            .where(
                PatientRecallCommunication.direction
                == PatientRecallCommunicationDirection.outbound
            )
            .where(
                PatientRecallCommunication.status
                == PatientRecallCommunicationStatus.sent
            )
            .where(PatientRecallCommunication.notes == payload.notes)
            .where(PatientRecallCommunication.other_detail == payload.other_detail)
            .where(PatientRecallCommunication.outcome == payload.outcome)
            .where(PatientRecallCommunication.created_by_user_id == user.id)
            .where(
                PatientRecallCommunication.created_at
                >= datetime.now(timezone.utc) - timedelta(seconds=60)
            )
        )
        if payload.contacted_at is not None:
            existing_query = existing_query.where(
                PatientRecallCommunication.contacted_at == payload.contacted_at
            )
        existing = db.scalar(
            existing_query
            .order_by(PatientRecallCommunication.created_at.desc())
            .limit(1)
        )
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Recall communication could not be recorded.",
            )
        return RecallCommunicationOut.model_validate(existing)
    db.flush()
    log_recall_activity(
        db,
        user=user,
        patient_id=patient_id,
        recall_id=recall_id,
        action="recall.communication_logged",
        metadata={
            "channel": payload.channel,
            "contacted_at": entry.contacted_at,
            "note_present": bool(payload.notes),
            "outcome_present": bool(payload.outcome),
            "other_detail_present": bool(payload.other_detail),
        },
        request_id=request_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(entry)
    bump_export_count_cache_epoch("patients.create_recall_communication")
    return RecallCommunicationOut.model_validate(entry)


@router.get("/{patient_id}/recalls/{recall_id}/letter.pdf")
def get_recall_letter_pdf(
    patient_id: int,
    recall_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("recalls.export")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    recall = db.get(PatientRecall, recall_id)
    if not recall or recall.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recall not found")
    pdf_bytes = build_recall_letter_pdf(patient, recall)
    notes = (
        f"Recall letter generated (PDF) - Type: {recall.kind.value}, "
        f"Due: {recall.due_date.isoformat()}"
    )
    communication = log_recall_communication(
        db,
        patient_id=patient_id,
        recall_id=recall_id,
        channel=PatientRecallCommunicationChannel.letter,
        direction=PatientRecallCommunicationDirection.outbound,
        status=PatientRecallCommunicationStatus.sent,
        notes=notes,
        created_by_user_id=user.id if user else None,
        guard_seconds=60,
    )
    if communication is not None:
        log_recall_activity(
            db,
            user=user,
            patient_id=patient_id,
            recall_id=recall_id,
            action="recall.letter_generated",
            metadata={"format": "pdf"},
            request_id=request_id,
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        bump_export_count_cache_epoch("patients.recall_letter_pdf")
    filename = f"recall-{patient_id}-{recall_id}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.post("/{patient_id}/payments", response_model=LedgerEntryOut)
def add_patient_payment(
    patient_id: int,
    payload: LedgerPaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("billing.payments.write")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if payload.amount_pence <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")
    if payload.related_invoice_id is not None:
        related_invoice = db.get(Invoice, payload.related_invoice_id)
        if not related_invoice or related_invoice.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Related invoice does not belong to this patient",
            )

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
    user: User = Depends(require_capability("billing.payments.write")),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if payload.amount_pence <= 0:
        raise HTTPException(status_code=400, detail="Charge amount must be positive")
    if payload.entry_type not in (LedgerEntryType.charge, LedgerEntryType.adjustment):
        raise HTTPException(status_code=400, detail="Invalid ledger entry type")
    if payload.related_invoice_id is not None:
        related_invoice = db.get(Invoice, payload.related_invoice_id)
        if not related_invoice or related_invoice.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Related invoice does not belong to this patient",
            )

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
        action=(
            "ledger.adjustment_recorded"
            if payload.entry_type == LedgerEntryType.adjustment
            else "ledger.charge_recorded"
        ),
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
