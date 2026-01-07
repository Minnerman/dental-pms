from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.patient import Patient
from app.models.user import User
from app.schemas.reports import CashupPaymentOut, CashupReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/cashup", response_model=CashupReportOut)
def cashup_report(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    report_date: date | None = Query(default=None, alias="date"),
):
    target = report_date or date.today()
    start = datetime.combine(target, time.min, tzinfo=timezone.utc)
    end = datetime.combine(target, time.max, tzinfo=timezone.utc)
    stmt = (
        select(PatientLedgerEntry, Patient)
        .join(Patient, Patient.id == PatientLedgerEntry.patient_id)
        .where(PatientLedgerEntry.entry_type == LedgerEntryType.payment)
        .where(PatientLedgerEntry.created_at >= start, PatientLedgerEntry.created_at <= end)
        .order_by(PatientLedgerEntry.created_at.asc())
    )
    totals: dict[str, int] = {}
    total_pence = 0
    payments: list[CashupPaymentOut] = []
    for entry, patient in db.execute(stmt).all():
        method_key = entry.method.value if entry.method else "other"
        totals[method_key] = totals.get(method_key, 0) + abs(entry.amount_pence)
        total_pence += abs(entry.amount_pence)
        payments.append(
            CashupPaymentOut(
                id=entry.id,
                patient_id=patient.id,
                patient_first_name=patient.first_name,
                patient_last_name=patient.last_name,
                method=entry.method,
                amount_pence=abs(entry.amount_pence),
                reference=entry.reference,
                note=entry.note,
                created_at=entry.created_at,
            )
        )
    return CashupReportOut(
        date=target,
        totals_by_method=totals,
        total_pence=total_pence,
        payments=payments,
    )
