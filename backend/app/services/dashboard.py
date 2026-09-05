"""Read-only, capability-scoped Home metrics from native PMS tables.

No R4 lookup, implicit confirmation inference, or recall-conversion estimate.
Calendar boundaries are computed in the practice timezone before UTC queries.
"""

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.invoice import Invoice, InvoiceStatus, Payment
from app.models.patient import Patient
from app.models.patient_recall import PatientRecall, PatientRecallStatus
from app.models.user import User
from app.schemas.dashboard import (
    AppointmentPeriod, DashboardAppointment, DashboardAppointments, DashboardPatients,
    DashboardPayments, DashboardPeriods, DashboardRecalls, HomeDashboard, OverdueInvoice,
    RecentPatient, UnavailableMetric,
)

PRACTICE_TIMEZONE = ZoneInfo("Europe/London")
ISSUED_STATUSES = (InvoiceStatus.issued, InvoiceStatus.part_paid, InvoiceStatus.paid)
OPEN_RECALL_STATUSES = (
    PatientRecallStatus.upcoming, PatientRecallStatus.due, PatientRecallStatus.overdue,
)
DEFINITIONS = {
    "appointments": "Native PMS appointments by start time; cancelled, deleted and archived-patient appointments excluded. No-shows remain in appointment totals.",
    "in_clinic": "Today's clinic appointments marked arrived or in progress; excludes home visits and domiciliary appointments.",
    "periods": "Last seven London calendar dates including today versus the preceding seven dates. Date ranges are inclusive; time queries use exclusive next-day boundaries.",
    "completion_rate": "Completed appointments divided by all non-cancelled appointments in the same date range; unavailable when the denominator is zero.",
    "overdue": "Issued or part-paid invoices with a due date before today and a positive invoice total less recorded invoice payments. Undated ledger balances are not classified as overdue invoices.",
    "invoiced": "Issued, part-paid and paid invoice totals by issue date, in GBP pence; not collected cash. Drafts, voids and archived patients excluded.",
    "recent_patients": "Most recently created active patient records, not a history of viewed records or recent attendance.",
    "recalls": "Open recall records for active patients. Due this week uses the Monday-Sunday calendar week and can overlap overdue; overdue means due date before today, without changing stored status.",
    "scheduled_recalls": "Distinct native appointments in this calendar month linked to a non-cancelled recall; cancelled/deleted appointments and archived patients excluded. Completed appointments remain counted.",
    "unavailable": "Appointment confirmation and a reliable contacted-to-booked recall conversion cohort are not recorded; these metrics are unavailable, never assumed zero.",
    "lists": "Lists are bounded previews; aggregate counts and balances are calculated independently without list truncation.",
}


def london_day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=PRACTICE_TIMEZONE).astimezone(timezone.utc)


def _appointment_filters(start: date, end_exclusive: date):
    return (
        Appointment.deleted_at.is_(None),
        Appointment.status != AppointmentStatus.cancelled,
        or_(Appointment.patient_id.is_(None), Patient.deleted_at.is_(None)),
        Appointment.starts_at >= london_day_start(start),
        Appointment.starts_at < london_day_start(end_exclusive),
    )


def _appointment_period(db: Session, start: date, end_exclusive: date) -> AppointmentPeriod:
    count, completed = db.execute(
        select(
            func.count(Appointment.id),
            func.count(Appointment.id).filter(Appointment.status == AppointmentStatus.completed),
        ).outerjoin(Patient, Patient.id == Appointment.patient_id)
        .where(*_appointment_filters(start, end_exclusive))
    ).one()
    return AppointmentPeriod(
        appointments=count, completed=completed,
        completion_rate=round(100 * completed / count, 1) if count else None,
    )


def _appointments(db: Session, caps: set[str], today: date, periods: DashboardPeriods, limit: int):
    allowed = "appointments.view" in caps
    identities = allowed and "patients.view" in caps
    result = DashboardAppointments(
        availability="available" if allowed else "forbidden", today_count=None,
        in_clinic_count=None, schedule_availability="available" if identities else "forbidden",
        schedule=[], schedule_has_more=False,
        unconfirmed_tomorrow=UnavailableMetric(
            availability="unavailable" if allowed else "forbidden",
            reason="confirmation_not_recorded" if allowed else "permission_required",
        ), last_7_days=None, previous_7_days=None,
    )
    if not allowed:
        return result
    tomorrow = today + timedelta(days=1)
    filters = _appointment_filters(today, tomorrow)
    result.today_count, result.in_clinic_count = db.execute(
        select(
            func.count(Appointment.id),
            func.count(Appointment.id).filter(and_(
                Appointment.status.in_((AppointmentStatus.arrived, AppointmentStatus.in_progress)),
                Appointment.location_type == AppointmentLocationType.clinic,
                Appointment.is_domiciliary.is_(False),
            )),
        ).outerjoin(Patient, Patient.id == Appointment.patient_id).where(*filters)
    ).one()
    if identities:
        assigned_clinician = aliased(User)
        clinician_name = func.coalesce(
            func.nullif(func.trim(assigned_clinician.full_name), ""),
            func.nullif(func.trim(Appointment.clinician), ""),
        ).label("clinician_name")
        rows = db.execute(select(
            Appointment.id, Appointment.patient_id, Patient.first_name, Patient.last_name,
            Appointment.starts_at, Appointment.ends_at, Appointment.status,
            Appointment.appointment_type, clinician_name, Appointment.location_type,
        ).outerjoin(Patient, Patient.id == Appointment.patient_id)
            .outerjoin(assigned_clinician, assigned_clinician.id == Appointment.clinician_user_id)
            .where(*filters)
            .order_by(Appointment.starts_at, Appointment.id).limit(limit + 1)).all()
        result.schedule_has_more = len(rows) > limit
        result.schedule = [DashboardAppointment(
            id=row.id, patient_id=row.patient_id,
            patient_name=f"{row.first_name} {row.last_name}" if row.patient_id else None,
            starts_at=row.starts_at, ends_at=row.ends_at, status=row.status.value,
            appointment_type=row.appointment_type, clinician=row.clinician_name,
            location_type=row.location_type.value,
        ) for row in rows[:limit]]
    result.last_7_days = _appointment_period(db, periods.current_start, tomorrow)
    result.previous_7_days = _appointment_period(db, periods.previous_start, periods.current_start)
    return result


def _invoiced(db: Session, start: date, end: date) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(Invoice.total_pence), 0))
        .join(Patient, Patient.id == Invoice.patient_id).where(
            Patient.deleted_at.is_(None), Invoice.status.in_(ISSUED_STATUSES),
            Invoice.issue_date >= start, Invoice.issue_date <= end,
        )) or 0)


def _payments(db: Session, caps: set[str], today: date, periods: DashboardPeriods, limit: int):
    allowed = "billing.view" in caps
    identities = allowed and "patients.view" in caps
    result = DashboardPayments(
        availability="available" if allowed else "forbidden", overdue_invoice_count=None,
        overdue_balance_pence=None, items_availability="available" if identities else "forbidden",
        items=[], items_has_more=False, last_7_days_invoiced_pence=None,
        previous_7_days_invoiced_pence=None,
    )
    if not allowed:
        return result
    paid = select(Payment.invoice_id, func.sum(Payment.amount_pence).label("paid_pence")) \
        .group_by(Payment.invoice_id).subquery()
    balance = Invoice.total_pence - func.coalesce(paid.c.paid_pence, 0)
    overdue = select(Invoice.id.label("invoice_id"), Invoice.invoice_number, Invoice.patient_id,
        Invoice.due_date, balance.label("balance_pence")) \
        .join(Patient, Patient.id == Invoice.patient_id) \
        .outerjoin(paid, paid.c.invoice_id == Invoice.id).where(
            Patient.deleted_at.is_(None), Invoice.status.in_((InvoiceStatus.issued, InvoiceStatus.part_paid)),
            Invoice.due_date < today, balance > 0,
        ).subquery()
    count, total = db.execute(select(func.count(), func.coalesce(func.sum(overdue.c.balance_pence), 0)).select_from(overdue)).one()
    result.overdue_invoice_count, result.overdue_balance_pence = int(count), int(total)
    if identities:
        rows = db.execute(select(overdue, Patient.first_name, Patient.last_name)
            .join(Patient, Patient.id == overdue.c.patient_id)
            .order_by(overdue.c.due_date, overdue.c.invoice_id).limit(limit + 1)).all()
        result.items_has_more = len(rows) > limit
        result.items = [OverdueInvoice(
            invoice_id=row.invoice_id, invoice_number=row.invoice_number,
            patient_id=row.patient_id, patient_name=f"{row.first_name} {row.last_name}",
            due_date=row.due_date, balance_pence=row.balance_pence,
        ) for row in rows[:limit]]
    result.last_7_days_invoiced_pence = _invoiced(db, periods.current_start, periods.current_end)
    result.previous_7_days_invoiced_pence = _invoiced(db, periods.previous_start, periods.previous_end)
    return result


def _patients(db: Session, caps: set[str], limit: int):
    allowed = "patients.view" in caps
    result = DashboardPatients(availability="available" if allowed else "forbidden", recent=[], recent_has_more=False)
    if allowed:
        rows = db.execute(select(Patient.id, Patient.first_name, Patient.last_name, Patient.phone, Patient.created_at)
            .where(Patient.deleted_at.is_(None)).order_by(Patient.created_at.desc(), Patient.id.desc())
            .limit(limit + 1)).all()
        result.recent_has_more = len(rows) > limit
        result.recent = [RecentPatient(id=row.id, name=f"{row.first_name} {row.last_name}", phone=row.phone, created_at=row.created_at) for row in rows[:limit]]
    return result


def _recalls(db: Session, caps: set[str], today: date, periods: DashboardPeriods):
    allowed = "recalls.view" in caps
    result = DashboardRecalls(
        availability="available" if allowed else "forbidden", due_this_week=None,
        overdue=None, scheduled_this_month=None,
        conversion_rate=UnavailableMetric(availability="unavailable" if allowed else "forbidden",
            reason="conversion_not_recorded" if allowed else "permission_required"),
    )
    if not allowed:
        return result
    result.due_this_week, result.overdue = db.execute(select(
        func.count(PatientRecall.id).filter(and_(PatientRecall.due_date >= periods.week_start, PatientRecall.due_date <= periods.week_end)),
        func.count(PatientRecall.id).filter(PatientRecall.due_date < today),
    ).join(Patient, Patient.id == PatientRecall.patient_id).where(
        Patient.deleted_at.is_(None), PatientRecall.status.in_(OPEN_RECALL_STATUSES),
    )).one()
    result.scheduled_this_month = int(db.scalar(select(func.count(func.distinct(Appointment.id)))
        .select_from(PatientRecall).join(Patient, Patient.id == PatientRecall.patient_id)
        .join(Appointment, and_(Appointment.id == PatientRecall.linked_appointment_id, Appointment.patient_id == PatientRecall.patient_id))
        .where(Patient.deleted_at.is_(None), PatientRecall.status != PatientRecallStatus.cancelled,
            Appointment.deleted_at.is_(None), Appointment.status != AppointmentStatus.cancelled,
            Appointment.starts_at >= london_day_start(periods.month_start),
            Appointment.starts_at < london_day_start(periods.month_end + timedelta(days=1)),
        )) or 0)
    return result


def build_home_dashboard(db: Session, capabilities: set[str], *, now: datetime | None = None, limit: int = 8) -> HomeDashboard:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Dashboard clock must be timezone-aware")
    today = instant.astimezone(PRACTICE_TIMEZONE).date()
    week_start = today - timedelta(days=today.weekday())
    periods = DashboardPeriods(
        current_start=today - timedelta(days=6), current_end=today,
        previous_start=today - timedelta(days=13), previous_end=today - timedelta(days=7),
        week_start=week_start, week_end=week_start + timedelta(days=6),
        month_start=today.replace(day=1), month_end=today.replace(day=monthrange(today.year, today.month)[1]),
    )
    return HomeDashboard(
        generated_at=instant, date=today, periods=periods,
        appointments=_appointments(db, capabilities, today, periods, limit),
        payments=_payments(db, capabilities, today, periods, limit),
        patients=_patients(db, capabilities, limit),
        recalls=_recalls(db, capabilities, today, periods), definitions=DEFINITIONS,
    )
