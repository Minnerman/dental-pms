from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.invoice import Invoice, Payment
from app.models.patient import Patient, RecallStatus
from app.models.user import User
from app.schemas.patient import PatientRecallOut

router = APIRouter(prefix="/recalls", tags=["recalls"])


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
                recall_last_set_at=patient.recall_last_set_at,
                balance_pence=balance_pence,
            )
        )
    return output
