from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.patient import Patient
from app.models.patient_recall import PatientRecall, PatientRecallKind, PatientRecallStatus
from app.models.user import Role, User
from app.services.capabilities import replace_user_capabilities
from app.services.dashboard import build_home_dashboard, london_day_start
from app.services.users import create_user

NOW = datetime(2040, 6, 10, 9, tzinfo=timezone.utc)
TODAY = NOW.date()
ALL_CAPS = {"patients.view", "appointments.view", "billing.view", "recalls.view"}


@pytest.fixture
def dashboard_db(api_client):
    # Keep synthetic fixtures in an uncommitted transaction, invisible to any
    # parallel browser tests and rolled back after each test.
    del api_client
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == Role.superadmin))
        assert actor is not None
        yield db, actor.id
        db.rollback()


def patient(db, actor_id, *, archived=False, label="Dashboard"):
    row = Patient(first_name="Synthetic", last_name=f"{label}-{uuid4().hex[:8]}",
        created_by_user_id=actor_id, created_at=NOW, updated_at=NOW,
        deleted_at=NOW if archived else None)
    db.add(row)
    db.flush()
    return row


def appointment(db, actor_id, owner, *, day=TODAY, hour=10,
                status=AppointmentStatus.booked, visit=False, domiciliary=False, deleted=False):
    start = london_day_start(day) + timedelta(hours=hour)
    row = Appointment(patient_id=owner.id, starts_at=start, ends_at=start + timedelta(minutes=30),
        status=status, location_type=AppointmentLocationType.visit if visit else AppointmentLocationType.clinic,
        is_domiciliary=domiciliary, created_by_user_id=actor_id,
        deleted_at=NOW if deleted else None)
    db.add(row)
    db.flush()
    return row


def invoice(db, actor_id, owner, *, amount=10000, paid=0, status=InvoiceStatus.issued,
            issued=TODAY, due=TODAY - timedelta(days=1)):
    row = Invoice(patient_id=owner.id, invoice_number=f"DASH-{uuid4().hex[:20]}",
        issue_date=issued, due_date=due, status=status, subtotal_pence=amount,
        total_pence=amount, created_by_user_id=actor_id)
    db.add(row)
    db.flush()
    if paid:
        db.add(Payment(invoice_id=row.id, amount_pence=paid, method=PaymentMethod.card,
            paid_at=NOW, received_by_user_id=actor_id))
        db.flush()
    return row


def recall(db, actor_id, owner, *, due=TODAY, status=PatientRecallStatus.upcoming, linked=None):
    row = PatientRecall(patient_id=owner.id, kind=PatientRecallKind.exam, due_date=due,
        status=status, linked_appointment_id=linked.id if linked else None,
        created_by_user_id=actor_id)
    db.add(row)
    db.flush()
    return row


def test_london_calendar_boundaries_handle_dst_and_local_midnight_without_queries():
    assert london_day_start(date(2026, 3, 30)) - london_day_start(date(2026, 3, 29)) == timedelta(hours=23)
    assert london_day_start(date(2026, 10, 26)) - london_day_start(date(2026, 10, 25)) == timedelta(hours=25)
    # No capability means build must not attempt domain queries at all.
    result = build_home_dashboard(None, set(), now=datetime(2040, 6, 9, 23, 30, tzinfo=timezone.utc))
    assert result.date == TODAY
    assert result.timezone == "Europe/London"
    assert result.periods.current_start == TODAY - timedelta(days=6)
    assert result.periods.previous_end == TODAY - timedelta(days=7)
    assert result.periods.previous_start == TODAY - timedelta(days=13)


def test_appointments_have_full_counts_clinic_only_presence_and_nonoverlapping_periods(dashboard_db):
    db, actor_id = dashboard_db
    owner = patient(db, actor_id)
    archived = patient(db, actor_id, archived=True)
    before = build_home_dashboard(db, ALL_CAPS, now=NOW, limit=2)
    for status in (AppointmentStatus.booked, AppointmentStatus.arrived, AppointmentStatus.in_progress,
                   AppointmentStatus.completed, AppointmentStatus.no_show):
        appointment(db, actor_id, owner, status=status)
    appointment(db, actor_id, owner, status=AppointmentStatus.arrived, visit=True)
    appointment(db, actor_id, owner, status=AppointmentStatus.in_progress, domiciliary=True)
    appointment(db, actor_id, owner, status=AppointmentStatus.cancelled)
    appointment(db, actor_id, owner, deleted=True)
    appointment(db, actor_id, archived, status=AppointmentStatus.arrived)
    appointment(db, actor_id, owner, day=TODAY - timedelta(days=6), hour=0, status=AppointmentStatus.completed)
    appointment(db, actor_id, owner, day=TODAY - timedelta(days=7), status=AppointmentStatus.completed)
    appointment(db, actor_id, owner, day=TODAY - timedelta(days=13), hour=0)
    appointment(db, actor_id, owner, day=TODAY - timedelta(days=14), status=AppointmentStatus.completed)
    appointment(db, actor_id, owner, day=TODAY + timedelta(days=1), hour=0)
    result = build_home_dashboard(db, ALL_CAPS, now=NOW, limit=2)
    assert result.appointments.today_count - before.appointments.today_count == 7
    assert result.appointments.in_clinic_count - before.appointments.in_clinic_count == 2
    assert len(result.appointments.schedule) == 2
    assert result.appointments.schedule_has_more is True
    current = result.appointments.last_7_days
    previous = result.appointments.previous_7_days
    assert current.appointments - before.appointments.last_7_days.appointments == 8
    assert current.completed - before.appointments.last_7_days.completed == 2
    assert previous.appointments - before.appointments.previous_7_days.appointments == 2
    assert previous.completed - before.appointments.previous_7_days.completed == 1
    assert current.completion_rate == round(current.completed / current.appointments * 100, 1)
    assert result.appointments.unconfirmed_tomorrow.availability == "unavailable"
    assert result.appointments.unconfirmed_tomorrow.value is None


def test_overdue_invoices_subtract_payments_and_never_mistake_ledger_debt_for_due_invoices(dashboard_db):
    db, actor_id = dashboard_db
    owner = patient(db, actor_id)
    archived = patient(db, actor_id, archived=True)
    before = build_home_dashboard(db, ALL_CAPS, now=NOW, limit=1)
    invoice(db, actor_id, owner, amount=10000, paid=2500, status=InvoiceStatus.part_paid)
    invoice(db, actor_id, owner, amount=2000)
    invoice(db, actor_id, owner, amount=3000, paid=3000, status=InvoiceStatus.paid)
    invoice(db, actor_id, owner, amount=5000, paid=6000)
    invoice(db, actor_id, owner, amount=7000, status=InvoiceStatus.draft)
    invoice(db, actor_id, owner, amount=8000, status=InvoiceStatus.void)
    invoice(db, actor_id, owner, amount=9000, due=TODAY)
    invoice(db, actor_id, owner, amount=11000, due=None)
    invoice(db, actor_id, archived, amount=99999)
    invoice(db, actor_id, owner, amount=4000, issued=TODAY - timedelta(days=7), due=TODAY + timedelta(days=1))
    db.add(PatientLedgerEntry(patient_id=owner.id, entry_type=LedgerEntryType.charge,
        amount_pence=123456, created_by_user_id=actor_id))
    db.flush()
    result = build_home_dashboard(db, ALL_CAPS, now=NOW, limit=1)
    assert result.payments.overdue_invoice_count - before.payments.overdue_invoice_count == 2
    assert result.payments.overdue_balance_pence - before.payments.overdue_balance_pence == 9500
    assert len(result.payments.items) == 1
    assert result.payments.items_has_more is True
    assert result.payments.last_7_days_invoiced_pence - before.payments.last_7_days_invoiced_pence == 40000
    assert result.payments.previous_7_days_invoiced_pence - before.payments.previous_7_days_invoiced_pence == 4000
    assert result.currency == "GBP"


def test_schedule_resolves_assigned_clinician_name_without_exposing_user_private_fields(dashboard_db):
    db, actor_id = dashboard_db
    owner = patient(db, actor_id)
    named = User(email=f"private-clinician-{uuid4().hex}@example.com", full_name="Synthetic Assigned Clinician",
        hashed_password="synthetic-not-a-login-hash", role=Role.dentist)
    unnamed = User(email=f"private-unnamed-{uuid4().hex}@example.com", full_name="  ",
        hashed_password="synthetic-not-a-login-hash", role=Role.dentist)
    db.add_all([named, unnamed])
    db.flush()
    assigned = appointment(db, actor_id, owner, hour=0)
    assigned.clinician_user_id = named.id
    assigned.clinician = None
    fallback = appointment(db, actor_id, owner, hour=1)
    fallback.clinician_user_id = unnamed.id
    fallback.clinician = "  Synthetic Stored Clinician  "
    db.flush()
    result = build_home_dashboard(db, ALL_CAPS, now=NOW, limit=20)
    schedule = {item.id: item for item in result.appointments.schedule}
    assert schedule[assigned.id].clinician == "Synthetic Assigned Clinician"
    assert schedule[fallback.id].clinician == "Synthetic Stored Clinician"
    payload = result.model_dump_json()
    assert named.email not in payload
    assert unnamed.email not in payload
    assert named.hashed_password not in payload


def test_recalls_exclude_closed_and_archived_records_and_count_linked_appointments_once(dashboard_db):
    db, actor_id = dashboard_db
    owner = patient(db, actor_id)
    archived = patient(db, actor_id, archived=True)
    before = build_home_dashboard(db, ALL_CAPS, now=NOW)
    recall(db, actor_id, owner)
    recall(db, actor_id, owner, due=TODAY - timedelta(days=30))
    recall(db, actor_id, owner, status=PatientRecallStatus.cancelled)
    recall(db, actor_id, owner, status=PatientRecallStatus.completed)
    recall(db, actor_id, archived)
    booked = appointment(db, actor_id, owner, day=TODAY + timedelta(days=2))
    cancelled = appointment(db, actor_id, owner, status=AppointmentStatus.cancelled)
    deleted = appointment(db, actor_id, owner, deleted=True)
    another_patient = patient(db, actor_id)
    cross_patient = appointment(db, actor_id, another_patient)
    for linked in (booked, booked, cancelled, deleted, cross_patient):
        recall(db, actor_id, owner, due=TODAY + timedelta(days=60), status=PatientRecallStatus.completed, linked=linked)
    result = build_home_dashboard(db, ALL_CAPS, now=NOW)
    assert result.recalls.due_this_week - before.recalls.due_this_week == 1
    assert result.recalls.overdue - before.recalls.overdue == 1
    assert result.recalls.scheduled_this_month - before.recalls.scheduled_this_month == 1
    assert result.recalls.conversion_rate.availability == "unavailable"
    assert result.recalls.conversion_rate.value is None


def test_capability_sections_do_not_leak_patient_identities_or_financial_metrics(dashboard_db):
    db, actor_id = dashboard_db
    owner = patient(db, actor_id, label="PrivateName")
    owner.phone = "01632960001"
    db.flush()
    appointment(db, actor_id, owner)
    invoice(db, actor_id, owner, amount=654321)
    recall(db, actor_id, owner)
    for capability in ALL_CAPS:
        result = build_home_dashboard(db, {capability}, now=NOW, limit=1)
        assert result.appointments.availability == ("available" if capability == "appointments.view" else "forbidden")
        assert result.payments.availability == ("available" if capability == "billing.view" else "forbidden")
        assert result.recalls.availability == ("available" if capability == "recalls.view" else "forbidden")
        assert result.patients.availability == ("available" if capability == "patients.view" else "forbidden")
        assert result.appointments.schedule == []
        assert result.payments.items == []
        if capability != "patients.view":
            assert owner.last_name not in result.model_dump_json()
            assert owner.phone not in result.model_dump_json()
            assert result.patients.recent == []
        if capability != "billing.view":
            assert result.payments.overdue_balance_pence is None
            assert result.payments.last_7_days_invoiced_pence is None
    result = build_home_dashboard(db, ALL_CAPS, now=NOW, limit=1)
    assert result.patients.basis == "created_at"
    assert len(result.patients.recent) == 1
    assert result.patients.recent[0].id == owner.id
    assert result.patients.recent[0].phone == owner.phone


def test_dashboard_build_only_executes_reads_against_native_tables(dashboard_db):
    db, _ = dashboard_db
    statements = []
    connection = db.connection()
    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower().strip())
    event.listen(connection, "before_cursor_execute", capture)
    try:
        build_home_dashboard(db, ALL_CAPS, now=NOW)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert statements
    assert all(statement.startswith("select") for statement in statements)
    assert all("r4_" not in statement for statement in statements)


def test_dashboard_endpoint_authentication_limits_no_cache_and_denied_sections(api_client, auth_headers):
    assert api_client.get("/dashboard/home").status_code == 401
    response = api_client.get("/dashboard/home?limit=1", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert len(response.json()["patients"]["recent"]) <= 1
    for limit in (0, 21, -1):
        assert api_client.get(f"/dashboard/home?limit={limit}", headers=auth_headers).status_code == 422
    with SessionLocal() as db:
        user = create_user(db, email=f"dashboard-denied-{uuid4().hex}@example.com",
            password="SyntheticDashboard123!", role=Role.reception, full_name="Synthetic Viewer")
        replace_user_capabilities(db, user.id, [])
        token = create_access_token(subject=str(user.id), secret=settings.secret_key,
            alg=settings.jwt_alg, expires_minutes=5)
    denied = api_client.get("/dashboard/home", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 200
    data = denied.json()
    assert all(data[section]["availability"] == "forbidden" for section in ("appointments", "payments", "patients", "recalls"))
    assert data["appointments"]["today_count"] is None
    assert data["payments"]["overdue_balance_pence"] is None
    assert data["recalls"]["due_this_week"] is None
    assert data["patients"]["recent"] == []
