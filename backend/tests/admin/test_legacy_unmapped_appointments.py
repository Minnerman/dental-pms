from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.patient import Patient
from app.models.user import Role, User
from app.services.users import create_user


def seed_unmapped_appointments(session, actor_id: int) -> tuple[int, datetime]:
    base_start = datetime(2030, 1, 15, 9, 0, tzinfo=timezone.utc)
    suffix = uuid4().hex[:8]
    patient = Patient(
        first_name="Mapped",
        last_name="Patient",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(patient)
    session.flush()

    mapped = Appointment(
        patient_id=patient.id,
        starts_at=base_start - timedelta(days=1),
        ends_at=base_start - timedelta(days=1) + timedelta(minutes=30),
        status=AppointmentStatus.booked,
        location_type=AppointmentLocationType.clinic,
        is_domiciliary=False,
        legacy_source="r4",
        legacy_id=f"MAPPED-{suffix}",
        legacy_patient_code="1001",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(mapped)

    unmapped = Appointment(
        patient_id=None,
        starts_at=base_start,
        ends_at=base_start + timedelta(minutes=30),
        status=AppointmentStatus.booked,
        location_type=AppointmentLocationType.clinic,
        is_domiciliary=False,
        legacy_source="r4",
        legacy_id=f"UNMAPPED-{suffix}",
        legacy_patient_code="9999",
        appointment_type="Checkup",
        clinician="Dr Example",
        location="Room 1",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(unmapped)
    session.commit()
    session.refresh(unmapped)
    return unmapped.id, base_start


def test_unmapped_queue_requires_admin(api_client):
    session = SessionLocal()
    try:
        email = f"external-{uuid4().hex[:8]}@example.com"
        password = "ChangeMe123!000"
        create_user(session, email=email, password=password, role=Role.external)
    finally:
        session.close()

    res = api_client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = api_client.get("/admin/legacy/unmapped-appointments", headers=headers)
    assert res.status_code == 403, res.text


def test_unmapped_queue_lists_only_null_patient(api_client, auth_headers):
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        unmapped_id, base_start = seed_unmapped_appointments(session, actor.id)
    finally:
        session.close()

    res = api_client.get(
        "/admin/legacy/unmapped-appointments",
        headers=auth_headers,
        params={
            "limit": 50,
            "offset": 0,
            "legacy_source": "r4",
            "from": base_start.date().isoformat(),
            "to": base_start.date().isoformat(),
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    assert payload["total"] >= 1
    ids = [item["id"] for item in payload["items"]]
    assert unmapped_id in ids
    assert all(item["legacy_source"] == "r4" for item in payload["items"])
    assert all(item["legacy_patient_code"] is not None for item in payload["items"])
