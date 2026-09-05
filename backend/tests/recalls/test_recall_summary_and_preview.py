"""Synthetic recall call-list counts and generation-versus-contact regressions."""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy import event, func, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.patient import Patient, RecallStatus
from app.models.patient_recall import PatientRecall, PatientRecallKind, PatientRecallStatus
from app.models.patient_recall_communication import (
    PatientRecallCommunication,
    PatientRecallCommunicationChannel,
    PatientRecallCommunicationDirection,
    PatientRecallCommunicationStatus,
)
from app.models.user import Role, User
from app.routers.recalls import _build_recall_summary, _load_recall_dashboard_row
from app.services.capabilities import replace_user_capabilities
from app.services.dashboard import london_day_start
from app.services.users import create_user

NOW = datetime(2040, 6, 10, 9, tzinfo=timezone.utc)


@pytest.fixture
def recall_db(api_client):
    # All aggregate fixtures are uncommitted and invisible to parallel UI tests.
    del api_client
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == Role.superadmin))
        assert actor is not None
        yield db, actor.id
        db.rollback()


def patient(db, actor_id, *, archived=False):
    row = Patient(first_name="Synthetic", last_name=f"Recall-{uuid4().hex[:10]}",
                  phone="01632 960001", created_by_user_id=actor_id,
                  deleted_at=NOW if archived else None)
    db.add(row)
    db.flush()
    return row


def recall(db, actor_id, owner, *, due=NOW.date(),
           status=PatientRecallStatus.upcoming, linked=None):
    row = PatientRecall(patient_id=owner.id, kind=PatientRecallKind.exam,
                        due_date=due, status=status,
                        linked_appointment_id=linked.id if linked else None,
                        created_by_user_id=actor_id)
    db.add(row)
    db.flush()
    return row


def appointment(db, actor_id, owner, start, *, status=AppointmentStatus.booked, deleted=False):
    row = Appointment(patient_id=owner.id, starts_at=start,
                      ends_at=start + timedelta(minutes=30), status=status,
                      deleted_at=NOW if deleted else None, created_by_user_id=actor_id)
    db.add(row)
    db.flush()
    return row


def test_counts_use_dates_open_native_recalls_and_not_list_limits(recall_db):
    db, actor_id = recall_db
    owner = patient(db, actor_id)
    archived = patient(db, actor_id, archived=True)
    before = _build_recall_summary(db, can_view_appointments=True, now=NOW)
    # The stored status can be stale; the dates, not its wording, determine cards.
    stale = recall(db, actor_id, owner, due=before.periods.week_start)
    for _ in range(205):
        recall(db, actor_id, owner, due=before.periods.week_end, status=PatientRecallStatus.overdue)
    recall(db, actor_id, owner, due=before.periods.week_start - timedelta(days=1))
    recall(db, actor_id, owner, due=before.periods.week_end + timedelta(days=1))
    recall(db, actor_id, owner, status=PatientRecallStatus.completed)
    recall(db, actor_id, owner, status=PatientRecallStatus.cancelled)
    recall(db, actor_id, archived)
    # Legacy Patient fields are a different workflow and must not contribute.
    owner.recall_due_date = NOW.date()
    owner.recall_status = RecallStatus.due
    db.flush()
    result = _build_recall_summary(db, can_view_appointments=True, now=NOW)
    assert result.due_this_week - before.due_this_week == 206
    expected_overdue = 1 + (1 if before.periods.week_start < result.as_of_date else 0)
    assert result.overdue - before.overdue == expected_overdue
    assert stale.status == PatientRecallStatus.upcoming
    assert result.conversion_rate is None
    assert result.conversion_availability == "unavailable"
    assert "cohort" in result.conversion_reason


def test_scheduled_counts_distinct_same_patient_links_and_london_month_boundaries(recall_db):
    db, actor_id = recall_db
    owner = patient(db, actor_id)
    other = patient(db, actor_id)
    archived = patient(db, actor_id, archived=True)
    before = _build_recall_summary(db, can_view_appointments=True, now=NOW)
    start = london_day_start(before.periods.month_start)
    end = london_day_start(before.periods.month_end + timedelta(days=1))
    first = appointment(db, actor_id, owner, start)
    last = appointment(db, actor_id, owner, end - timedelta(seconds=1), status=AppointmentStatus.completed)
    for linked in (first, first, last):
        recall(db, actor_id, owner, linked=linked, status=PatientRecallStatus.completed)
    for linked in (
        appointment(db, actor_id, owner, start - timedelta(seconds=1)),
        appointment(db, actor_id, owner, end),
        appointment(db, actor_id, owner, start, status=AppointmentStatus.cancelled),
        appointment(db, actor_id, owner, start, status=AppointmentStatus.no_show),
        appointment(db, actor_id, owner, start, deleted=True),
        appointment(db, actor_id, other, start),
    ):
        recall(db, actor_id, owner, linked=linked)
    recall(db, actor_id, owner, linked=appointment(db, actor_id, owner, start),
           status=PatientRecallStatus.cancelled)
    recall(db, actor_id, archived, linked=appointment(db, actor_id, archived, start))
    result = _build_recall_summary(db, can_view_appointments=True, now=NOW)
    assert result.scheduled_this_month - before.scheduled_this_month == 2
    assert result.scheduled_availability == "available"


@pytest.mark.parametrize("instant,local_day", [
    (datetime(2040, 6, 9, 23, 30, tzinfo=timezone.utc), date(2040, 6, 10)),
    (datetime(2040, 1, 9, 23, 30, tzinfo=timezone.utc), date(2040, 1, 9)),
    (datetime(2026, 3, 29, 23, 30, tzinfo=timezone.utc), date(2026, 3, 30)),
    (datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc), date(2026, 10, 25)),
])
def test_summary_uses_london_date_week_and_dst(recall_db, instant, local_day):
    db, _ = recall_db
    result = _build_recall_summary(db, can_view_appointments=False, now=instant)
    assert result.as_of_date == local_day
    assert result.periods.week_start.weekday() == 0
    assert result.periods.week_end == result.periods.week_start + timedelta(days=6)
    assert result.periods.week_start <= local_day <= result.periods.week_end
    assert result.periods.month_start.day == 1
    assert result.periods.month_end.month == local_day.month


def test_summary_is_read_only_and_does_not_query_appointments_without_permission(recall_db):
    db, _ = recall_db
    connection = db.connection()
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower().strip())

    event.listen(connection, "before_cursor_execute", capture)
    try:
        result = _build_recall_summary(db, can_view_appointments=False, now=NOW)
        assert result.scheduled_this_month is None
        assert result.scheduled_availability == "forbidden"
        assert len(statements) == 1
        assert "appointments" not in statements[0]
        statements.clear()
        _build_recall_summary(db, can_view_appointments=True, now=NOW)
        assert len(statements) == 2
        assert all(statement.startswith("select") for statement in statements)
        assert all("r4_" not in statement for statement in statements)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    with pytest.raises(ValueError, match="timezone-aware"):
        _build_recall_summary(db, can_view_appointments=False, now=datetime(2040, 6, 10))


def test_phone_is_actual_patient_phone_and_no_preference_or_dnc_is_inferred(recall_db):
    db, actor_id = recall_db
    owner = patient(db, actor_id)
    row = recall(db, actor_id, owner)
    owner.recall_status = RecallStatus.not_required
    owner.primary_contact_phone = "01632 960002"
    db.flush()
    payload = _load_recall_dashboard_row(db, row.id).model_dump()
    assert payload["phone"] == "01632 960001"
    assert "contact_preference" not in payload
    assert "do_not_contact" not in payload
    owner.phone = None
    db.flush()
    assert _load_recall_dashboard_row(db, row.id).phone is None


def test_summary_endpoint_capability_and_cache_contract(api_client, auth_headers):
    assert api_client.get("/recalls/summary").status_code == 401
    with SessionLocal() as db:
        user = create_user(db, email=f"recall-summary-{uuid4().hex}@example.com",
                           password="SyntheticRecall123!", role=Role.reception)
        replace_user_capabilities(db, user.id, [])
        token = create_access_token(subject=str(user.id), secret=settings.secret_key,
                                    alg=settings.jwt_alg, expires_minutes=5)
        user_id = user.id
    headers = {"Authorization": f"Bearer {token}"}
    assert api_client.get("/recalls/summary", headers=headers).status_code == 403
    with SessionLocal() as db:
        replace_user_capabilities(db, user_id, ["recalls.view"])
    response = api_client.get("/recalls/summary", headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["scheduled_this_month"] is None
    assert payload["scheduled_availability"] == "forbidden"
    assert payload["conversion_rate"] is None
    assert isinstance(payload["due_this_week"], int)
    with SessionLocal() as db:
        replace_user_capabilities(db, user_id, ["recalls.view", "appointments.view"])
    response = api_client.get("/recalls/summary", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json()["scheduled_this_month"], int)


@pytest.mark.parametrize("historical_generated_contact", [False, True])
def test_pdf_and_zip_generation_never_mark_sent_or_replace_last_contact(
    api_client, auth_headers, historical_generated_contact
):
    response = api_client.post("/patients", headers=auth_headers, json={
        "first_name": "Synthetic", "last_name": f"Letter-{uuid4().hex[:10]}",
        "phone": "01632 960003",
    })
    assert response.status_code == 201
    patient_id = response.json()["id"]
    due_date = "2087-04-15"
    response = api_client.post(f"/patients/{patient_id}/recalls", headers=auth_headers,
        json={"kind": "custom", "due_date": due_date, "status": "due"})
    assert response.status_code == 201
    recall_id = response.json()["id"]
    if historical_generated_contact:
        # Preserve previous-version records; do not silently rewrite history.
        with SessionLocal() as db:
            actor_id = db.scalar(select(User.id).where(User.role == Role.superadmin))
            db.add(PatientRecallCommunication(patient_id=patient_id, recall_id=recall_id,
                channel=PatientRecallCommunicationChannel.letter,
                direction=PatientRecallCommunicationDirection.outbound,
                status=PatientRecallCommunicationStatus.sent,
                notes="Recall letters ZIP generated",
                contacted_at=datetime.now(timezone.utc) - timedelta(days=2),
                created_by_user_id=actor_id))
            db.commit()

    def snapshot():
        with SessionLocal() as db:
            row = _load_recall_dashboard_row(db, recall_id)
            count = db.scalar(select(func.count(PatientRecallCommunication.id))
                              .where(PatientRecallCommunication.recall_id == recall_id))
            return row.model_dump(mode="json"), count

    before, contact_count = snapshot()
    for _ in range(2):
        pdf = api_client.get(f"/patients/{patient_id}/recalls/{recall_id}/letter.pdf",
                             headers=auth_headers)
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")
        assert pdf.headers["cache-control"] == "no-store"
    params = {"start": due_date, "end": due_date, "type": "custom", "status": "due"}
    zip_request_id = f"recall-preview-{uuid4()}"
    zipped = api_client.get("/recalls/letters.zip",
        headers={**auth_headers, "x-request-id": zip_request_id}, params=params)
    assert zipped.status_code == 200
    with ZipFile(BytesIO(zipped.content)) as archive:
        assert any(f"_{patient_id}_" in name for name in archive.namelist())
    assert snapshot() == (before, contact_count)
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AuditLog.id)).where(
            AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient_id),
            AuditLog.action == "recall.letter_generated")) == 2
        assert db.scalar(select(func.count(AuditLog.id)).where(
            AuditLog.action == "recalls.export_letters_zip",
            AuditLog.request_id == zip_request_id)) == 1
    list_response = api_client.get("/recalls", headers=auth_headers, params=params)
    assert list_response.status_code == 200
    listed = next(item for item in list_response.json() if item["id"] == recall_id)
    assert listed["phone"] == "01632 960003"
    assert listed["last_contacted_at"] == before["last_contacted_at"]

    # Only an explicit confirmed sending/contact action updates the call list.
    sent = api_client.post(f"/recalls/{recall_id}/contact", headers=auth_headers,
        json={"method": "letter", "note": "Synthetic letter posted by operator"})
    assert sent.status_code == 200
    after, after_count = snapshot()
    assert after_count == contact_count + 1
    assert after["last_contacted_at"] != before["last_contacted_at"]
    assert after["last_contact_note"] == "Synthetic letter posted by operator"
    assert sent.json()["phone"] == "01632 960003"
