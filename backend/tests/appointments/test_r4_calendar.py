import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_appointment import R4Appointment
from app.models.r4_appointment_patient_link import R4AppointmentPatientLink
from app.models.r4_user import R4User
from app.models.user import User
from app.services.users import ensure_admin_user


DEFAULT_STATUSSET = {"pending", "checked-in", "checked in", "arrived", "did not attend", "dna"}


def _actor_id(session) -> int:
    actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
    if not actor:
        actor = ensure_admin_user(
            session, email="admin@example.com", password="ChangeMe123!"
        )
    return actor.id


def _create_patient(session, legacy_id: str) -> Patient:
    actor_id = _actor_id(session)
    patient = Patient(
        first_name="R4",
        last_name="Patient",
        legacy_source="r4",
        legacy_id=legacy_id,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(patient)
    session.flush()
    return patient


def _create_user(session, legacy_code: int, full_name: str) -> R4User:
    actor_id = _actor_id(session)
    user = R4User(
        legacy_source="r4",
        legacy_user_code=legacy_code,
        full_name=full_name,
        display_name=full_name,
        is_current=True,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
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
    actor_id = _actor_id(session)
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
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(appt)
    session.flush()
    return appt


def _unique_legacy_id() -> str:
    return str(uuid.uuid4().int % 10000000)


def _cleanup(session, patient_ids: list[int] | None = None):
    session.execute(delete(R4Appointment).where(R4Appointment.legacy_source == "r4"))
    session.execute(
        delete(R4AppointmentPatientLink).where(
            R4AppointmentPatientLink.legacy_source == "r4"
        )
    )
    session.execute(delete(R4User).where(R4User.legacy_source == "r4"))
    if patient_ids:
        session.execute(delete(Patient).where(Patient.id.in_(patient_ids)))
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

    _cleanup(db_session, [patient.id])


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

    _cleanup(db_session, [patient.id])


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

    _cleanup(db_session, [patient.id])


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

    _cleanup(db_session, [patient.id])


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

    _cleanup(db_session, [patient.id])


def test_r4_calendar_link_endpoint_precedence(api_client, auth_headers, db_session):
    patient_code = _create_patient(db_session, _unique_legacy_id())
    linked_patient = _create_patient(db_session, _unique_legacy_id())
    clinician = _create_user(db_session, legacy_code=101000, full_name="Dr Link")
    appt = _create_appointment(
        db_session,
        legacy_id=10001,
        patient_code=int(patient_code.legacy_id),
        clinician_code=clinician.legacy_user_code,
        status="Pending",
        starts_at=datetime(2025, 6, 1, 9, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    res_link = api_client.post(
        f"/api/appointments/{appt.legacy_appointment_id}/link",
        json={"patient_id": linked_patient.id},
        headers=auth_headers,
    )
    assert res_link.status_code == 200, res_link.text

    res = api_client.get(
        "/api/appointments",
        params={"from": "2025-06-01", "to": "2025-06-02"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    linked_item = next(
        item for item in items if item["legacy_appointment_id"] == appt.legacy_appointment_id
    )
    assert linked_item["patient_id"] == linked_patient.id
    assert linked_item["is_unlinked"] is False

    _cleanup(db_session, [patient_code.id, linked_patient.id])


def test_r4_calendar_link_endpoint_idempotent_and_update(api_client, auth_headers, db_session):
    patient_a = _create_patient(db_session, _unique_legacy_id())
    patient_b = _create_patient(db_session, _unique_legacy_id())
    appt = _create_appointment(
        db_session,
        legacy_id=10002,
        patient_code=None,
        clinician_code=None,
        status="Pending",
        starts_at=datetime(2025, 6, 2, 9, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    res_first = api_client.post(
        f"/api/appointments/{appt.legacy_appointment_id}/link",
        json={"patient_id": patient_a.id},
        headers=auth_headers,
    )
    assert res_first.status_code == 200, res_first.text
    link_id = res_first.json()["id"]

    res_same = api_client.post(
        f"/api/appointments/{appt.legacy_appointment_id}/link",
        json={"patient_id": patient_a.id},
        headers=auth_headers,
    )
    assert res_same.status_code == 200, res_same.text
    assert res_same.json()["id"] == link_id

    res_update = api_client.post(
        f"/api/appointments/{appt.legacy_appointment_id}/link",
        json={"patient_id": patient_b.id},
        headers=auth_headers,
    )
    assert res_update.status_code == 200, res_update.text
    assert res_update.json()["id"] == link_id
    assert res_update.json()["patient_id"] == patient_b.id

    _cleanup(db_session, [patient_a.id, patient_b.id])


def test_r4_calendar_link_endpoint_invalid_patient(api_client, auth_headers, db_session):
    appt = _create_appointment(
        db_session,
        legacy_id=10003,
        patient_code=None,
        clinician_code=None,
        status="Pending",
        starts_at=datetime(2025, 6, 3, 9, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    res = api_client.post(
        f"/api/appointments/{appt.legacy_appointment_id}/link",
        json={"patient_id": 999999999},
        headers=auth_headers,
    )
    assert res.status_code == 404, res.text

    _cleanup(db_session)
