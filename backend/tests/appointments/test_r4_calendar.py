import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_appointment import R4Appointment
from app.models.r4_user import R4User


DEFAULT_STATUSSET = {"pending", "checked-in", "checked in", "arrived", "did not attend", "dna"}


def _create_patient(session, legacy_id: str) -> Patient:
    patient = Patient(
        first_name="R4",
        last_name="Patient",
        legacy_source="r4",
        legacy_id=legacy_id,
    )
    session.add(patient)
    session.flush()
    return patient


def _create_user(session, legacy_code: int, full_name: str) -> R4User:
    user = R4User(
        legacy_source="r4",
        legacy_user_code=legacy_code,
        full_name=full_name,
        display_name=full_name,
        is_current=True,
    )
    session.add(user)
    session.flush()
    return user


def _create_appointment(
    session,
    legacy_id: int,
    patient_code: int | None,
    clinician_code: int | None,
    status: str,
    starts_at: datetime,
) -> R4Appointment:
    appt = R4Appointment(
        legacy_source="r4",
        legacy_appointment_id=legacy_id,
        patient_code=patient_code,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        duration_minutes=30,
        clinician_code=clinician_code,
        status=status,
        appointment_type="Test",
    )
    session.add(appt)
    session.flush()
    return appt


def _unique_legacy_id() -> str:
    return str(uuid.uuid4().int % 10000000)


def _cleanup(session):
    session.execute(delete(R4Appointment).where(R4Appointment.legacy_source == "r4"))
    session.execute(delete(R4User).where(R4User.legacy_source == "r4"))
    session.execute(delete(Patient).where(Patient.legacy_source == "r4"))
    session.commit()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_r4_calendar_status_filters(api_client, auth_headers, db_session):
    patient = _create_patient(db_session, _unique_legacy_id())
    clinician = _create_user(db_session, legacy_code=100500, full_name="Dr Filter")
    # default statuses (pending)
    default_appt = _create_appointment(
        db_session,
        legacy_id=5001,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician.legacy_user_code,
        status="Pending",
        starts_at=datetime(2025, 1, 5, 9, 0, tzinfo=timezone.utc),
    )
    # hidden status (complete)
    hidden_appt = _create_appointment(
        db_session,
        legacy_id=5002,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician.legacy_user_code,
        status="Complete",
        starts_at=datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc),
    )
    hidden_cancelled = _create_appointment(
        db_session,
        legacy_id=5003,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician.legacy_user_code,
        status="Cancelled",
        starts_at=datetime(2025, 1, 6, 11, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    params = {"from": "2025-01-04", "to": "2025-01-07"}
    res = api_client.get("/api/appointments", params=params, headers=auth_headers)
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert any(item["legacy_appointment_id"] == default_appt.legacy_appointment_id for item in items)
    assert all(item["status_normalised"] in DEFAULT_STATUSSET for item in items)

    res_hidden = api_client.get(
        "/api/appointments",
        params={"from": "2025-01-04", "to": "2025-01-07", "show_hidden": "true"},
        headers=auth_headers,
    )
    assert res_hidden.status_code == 200, res_hidden.text
    items_hidden = res_hidden.json()["items"]
    assert any(item["legacy_appointment_id"] == hidden_appt.legacy_appointment_id for item in items_hidden)
    assert any(
        item["legacy_appointment_id"] == hidden_cancelled.legacy_appointment_id
        for item in items_hidden
    )

    _cleanup(db_session)


def test_r4_calendar_unlinked_and_total(api_client, auth_headers, db_session):
    patient = _create_patient(db_session, _unique_legacy_id())
    clinician = _create_user(db_session, legacy_code=100600, full_name="Dr Unlinked")
    linked = _create_appointment(
        db_session,
        legacy_id=6001,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician.legacy_user_code,
        status="Pending",
        starts_at=datetime(2025, 2, 10, 9, 0, tzinfo=timezone.utc),
    )
    unlinked = _create_appointment(
        db_session,
        legacy_id=6002,
        patient_code=None,
        clinician_code=clinician.legacy_user_code,
        status="Pending",
        starts_at=datetime(2025, 2, 11, 9, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    params = {"from": "2025-02-09", "to": "2025-02-12"}
    res = api_client.get("/api/appointments", params=params, headers=auth_headers)
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert all(item["is_unlinked"] is False for item in items)

    res_unlinked = api_client.get(
        "/api/appointments",
        params={
            "from": "2025-02-09",
            "to": "2025-02-12",
            "show_unlinked": "true",
            "include_total": "true",
        },
        headers=auth_headers,
    )
    assert res_unlinked.status_code == 200, res_unlinked.text
    body = res_unlinked.json()
    assert body["total_count"] >= 2
    assert any(item["legacy_appointment_id"] == unlinked.legacy_appointment_id for item in body["items"])
    assert any(item["is_unlinked"] for item in body["items"])

    _cleanup(db_session)


def test_r4_calendar_clinician_filter(api_client, auth_headers, db_session):
    patient = _create_patient(db_session, _unique_legacy_id())
    clinician_a = _create_user(db_session, legacy_code=100700, full_name="Dr Alpha")
    clinician_b = _create_user(db_session, legacy_code=100701, full_name="Dr Beta")
    appt_a = _create_appointment(
        db_session,
        legacy_id=7001,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician_a.legacy_user_code,
        status="Pending",
        starts_at=datetime(2025, 3, 3, 9, 0, tzinfo=timezone.utc),
    )
    _create_appointment(
        db_session,
        legacy_id=7002,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician_b.legacy_user_code,
        status="Pending",
        starts_at=datetime(2025, 3, 3, 10, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    res = api_client.get(
        "/api/appointments",
        params={
            "from": "2025-03-02",
            "to": "2025-03-04",
            "clinician_code": str(clinician_a.legacy_user_code),
        },
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert items
    assert all(item["clinician_code"] == clinician_a.legacy_user_code for item in items)
    assert any(item["legacy_appointment_id"] == appt_a.legacy_appointment_id for item in items)

    _cleanup(db_session)


def test_r4_calendar_linked_unlinked_toggles(api_client, auth_headers, db_session):
    patient = _create_patient(db_session, _unique_legacy_id())
    clinician = _create_user(db_session, legacy_code=100800, full_name="Dr Toggle")
    linked = _create_appointment(
        db_session,
        legacy_id=8001,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician.legacy_user_code,
        status="Pending",
        starts_at=datetime(2025, 4, 1, 9, 0, tzinfo=timezone.utc),
    )
    unlinked = _create_appointment(
        db_session,
        legacy_id=8002,
        patient_code=None,
        clinician_code=clinician.legacy_user_code,
        status="Pending",
        starts_at=datetime(2025, 4, 1, 10, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    res_linked = api_client.get(
        "/api/appointments",
        params={"from": "2025-03-31", "to": "2025-04-02", "linked_only": "true"},
        headers=auth_headers,
    )
    assert res_linked.status_code == 200, res_linked.text
    items_linked = res_linked.json()["items"]
    assert items_linked
    assert all(item["is_unlinked"] is False for item in items_linked)
    assert any(item["legacy_appointment_id"] == linked.legacy_appointment_id for item in items_linked)

    res_unlinked = api_client.get(
        "/api/appointments",
        params={"from": "2025-03-31", "to": "2025-04-02", "unlinked_only": "true"},
        headers=auth_headers,
    )
    assert res_unlinked.status_code == 200, res_unlinked.text
    items_unlinked = res_unlinked.json()["items"]
    assert items_unlinked
    assert all(item["is_unlinked"] is True for item in items_unlinked)
    assert any(item["legacy_appointment_id"] == unlinked.legacy_appointment_id for item in items_unlinked)

    _cleanup(db_session)


def test_r4_calendar_ordering_stability(api_client, auth_headers, db_session):
    patient = _create_patient(db_session, _unique_legacy_id())
    clinician = _create_user(db_session, legacy_code=100900, full_name="Dr Order")
    starts_at = datetime(2025, 5, 2, 9, 0, tzinfo=timezone.utc)
    appt_low = _create_appointment(
        db_session,
        legacy_id=9001,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician.legacy_user_code,
        status="Pending",
        starts_at=starts_at,
    )
    appt_high = _create_appointment(
        db_session,
        legacy_id=9002,
        patient_code=int(patient.legacy_id),
        clinician_code=clinician.legacy_user_code,
        status="Pending",
        starts_at=starts_at,
    )
    db_session.commit()

    res = api_client.get(
        "/api/appointments",
        params={"from": "2025-05-01", "to": "2025-05-03", "show_unlinked": "true"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    ids = [item["legacy_appointment_id"] for item in items]
    assert ids.index(appt_low.legacy_appointment_id) < ids.index(appt_high.legacy_appointment_id)

    _cleanup(db_session)
