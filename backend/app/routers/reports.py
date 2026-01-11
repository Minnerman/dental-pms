from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.patient import Patient
from app.models.user import User
from app.schemas.reports import CashupPaymentOut, CashupReportOut
from app.schemas.reports_finance import (
    CashupDailyOut,
    FinanceCashupOut,
    FinanceOutstandingDebtorOut,
    FinanceOutstandingOut,
    FinanceTrendPointOut,
    FinanceTrendsOut,
)

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


@router.get("/finance/cashup", response_model=FinanceCashupOut)
def cashup_report_range(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
):
    today = date.today()
    range_end = end or today
    range_start = start or (range_end - timedelta(days=30))
    start_dt = datetime.combine(range_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(range_end, time.max, tzinfo=timezone.utc)

    stmt = (
        select(
            func.date(PatientLedgerEntry.created_at).label("day"),
            PatientLedgerEntry.method,
            func.coalesce(func.sum(func.abs(PatientLedgerEntry.amount_pence)), 0).label(
                "total_pence"
            ),
        )
        .where(PatientLedgerEntry.entry_type == LedgerEntryType.payment)
        .where(PatientLedgerEntry.created_at >= start_dt, PatientLedgerEntry.created_at <= end_dt)
        .group_by(func.date(PatientLedgerEntry.created_at), PatientLedgerEntry.method)
        .order_by(func.date(PatientLedgerEntry.created_at).asc())
    )

    totals_by_method: dict[str, int] = {}
    totals_by_day: dict[date, dict[str, int]] = {}
    total_pence = 0

    for day, method, total in db.execute(stmt).all():
        method_key = method.value if method else "other"
        totals_by_method[method_key] = totals_by_method.get(method_key, 0) + int(total)
        total_pence += int(total)
        totals_by_day.setdefault(day, {})
        totals_by_day[day][method_key] = int(total)

    daily: list[CashupDailyOut] = []
    for day in sorted(totals_by_day.keys()):
        day_totals = totals_by_day[day]
        daily.append(
            CashupDailyOut(
                date=day,
                total_pence=sum(day_totals.values()),
                totals_by_method=day_totals,
            )
        )

    return FinanceCashupOut(
        range={"from": range_start, "to": range_end},
        totals_by_method=totals_by_method,
        total_pence=total_pence,
        daily=daily,
    )


@router.get("/finance/outstanding", response_model=FinanceOutstandingOut)
def outstanding_report(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    as_of: date | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    target = as_of or date.today()
    cutoff = datetime.combine(target, time.max, tzinfo=timezone.utc)

    balances = (
        select(
            PatientLedgerEntry.patient_id.label("patient_id"),
            func.coalesce(func.sum(PatientLedgerEntry.amount_pence), 0).label("balance_pence"),
        )
        .where(PatientLedgerEntry.created_at <= cutoff)
        .group_by(PatientLedgerEntry.patient_id)
        .subquery()
    )

    outstanding_stmt = (
        select(
            Patient.id,
            Patient.first_name,
            Patient.last_name,
            balances.c.balance_pence,
        )
        .join(balances, balances.c.patient_id == Patient.id)
        .where(Patient.deleted_at.is_(None))
        .where(balances.c.balance_pence > 0)
        .order_by(balances.c.balance_pence.desc())
    )

    rows = db.execute(outstanding_stmt).all()
    total_outstanding = sum(row.balance_pence for row in rows)
    count_patients = len(rows)

    top_debtors = [
        FinanceOutstandingDebtorOut(
            patient_id=row.id,
            patient_name=f"{row.last_name.upper()}, {row.first_name}",
            balance_pence=row.balance_pence,
        )
        for row in rows[:limit]
    ]

    return FinanceOutstandingOut(
        as_of=target,
        total_outstanding_pence=total_outstanding,
        count_patients_with_balance=count_patients,
        top_debtors=top_debtors,
    )


@router.get("/finance/trends", response_model=FinanceTrendsOut)
def finance_trends(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    days: int = Query(default=30, ge=7, le=365),
):
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

    stmt = (
        select(
            func.date(PatientLedgerEntry.created_at).label("day"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            PatientLedgerEntry.entry_type == LedgerEntryType.payment,
                            func.abs(PatientLedgerEntry.amount_pence),
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("payments_pence"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            PatientLedgerEntry.entry_type.in_(
                                [LedgerEntryType.charge, LedgerEntryType.adjustment]
                            ),
                            PatientLedgerEntry.amount_pence,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("charges_pence"),
            func.coalesce(func.sum(PatientLedgerEntry.amount_pence), 0).label("net_pence"),
        )
        .where(PatientLedgerEntry.created_at >= start_dt, PatientLedgerEntry.created_at <= end_dt)
        .group_by(func.date(PatientLedgerEntry.created_at))
        .order_by(func.date(PatientLedgerEntry.created_at).asc())
    )

    totals_by_day: dict[date, tuple[int, int, int]] = {}
    for day, payments, charges, net in db.execute(stmt).all():
        totals_by_day[day] = (int(payments), int(charges), int(net))

    series: list[FinanceTrendPointOut] = []
    current = start_date
    while current <= end_date:
        payments, charges, net = totals_by_day.get(current, (0, 0, 0))
        series.append(
            FinanceTrendPointOut(
                date=current,
                payments_pence=payments,
                charges_pence=charges,
                net_pence=net,
            )
        )
        current += timedelta(days=1)

    return FinanceTrendsOut(days=days, series=series)
