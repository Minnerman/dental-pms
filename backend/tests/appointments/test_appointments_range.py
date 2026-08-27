from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


def test_range_excludes_end_boundary(api_client, auth_headers):
    patient_payload = {"first_name": "Range", "last_name": "Boundary"}
    patient_res = api_client.post("/patients", json=patient_payload, headers=auth_headers)
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    def create_appt(start_dt: datetime, end_dt: datetime):
        payload = {
            "patient_id": patient_id,
            "starts_at": start_dt.isoformat(),
            "ends_at": end_dt.isoformat(),
            "status": "booked",
            "location_type": "clinic",
            "allow_outside_hours": True,
        }
        res = api_client.post("/appointments", json=payload, headers=auth_headers)
        assert res.status_code == 201, res.text
        return res.json()["id"]

    start_included = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    end_exclusive = datetime(2026, 1, 11, 9, 0, tzinfo=timezone.utc)

    included_id = create_appt(start_included, start_included.replace(hour=9, minute=30))
    excluded_id = create_appt(end_exclusive, end_exclusive.replace(hour=9, minute=30))

    res = api_client.get(
        "/appointments/range",
        params={"start": "2026-01-10", "end": "2026-01-11"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    ids = {item["id"] for item in res.json()}

    assert included_id in ids
    assert excluded_id not in ids


def test_range_excludes_end_day_includes_late_start(api_client, auth_headers):
    patient_payload = {"first_name": "Late", "last_name": "Start"}
    patient_res = api_client.post("/patients", json=patient_payload, headers=auth_headers)
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    def create_appt(start_dt: datetime, end_dt: datetime):
        payload = {
            "patient_id": patient_id,
            "starts_at": start_dt.isoformat(),
            "ends_at": end_dt.isoformat(),
            "status": "booked",
            "location_type": "clinic",
            "allow_outside_hours": True,
        }
        res = api_client.post("/appointments", json=payload, headers=auth_headers)
        assert res.status_code == 201, res.text
        return res.json()["id"]

    late_start = datetime(2026, 1, 19, 23, 59, 0, tzinfo=timezone.utc)
    late_end = datetime(2026, 1, 19, 23, 59, 59, tzinfo=timezone.utc)
    end_day_start = datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc)
    end_day_end = datetime(2026, 1, 20, 10, 30, tzinfo=timezone.utc)

    included_id = create_appt(late_start, late_end)
    excluded_id = create_appt(end_day_start, end_day_end)

    res = api_client.get(
        "/appointments/range",
        params={"start": "2026-01-15", "end": "2026-01-20"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    ids = {item["id"] for item in res.json()}

    assert included_id in ids
    assert excluded_id not in ids


def test_range_includes_latest_active_note_preview(api_client, auth_headers):
    patient_res = api_client.post(
        "/patients",
        json={"first_name": "Note", "last_name": "Preview"},
        headers=auth_headers,
    )
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    appointment_res = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "starts_at": "2026-01-21T09:00:00+00:00",
            "ends_at": "2026-01-21T09:30:00+00:00",
            "status": "booked",
            "location_type": "clinic",
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert appointment_res.status_code == 201, appointment_res.text
    appointment_id = appointment_res.json()["id"]

    note_res = api_client.post(
        f"/appointments/{appointment_id}/notes",
        json={"body": "Bring the referral letter", "note_type": "clinical"},
        headers=auth_headers,
    )
    assert note_res.status_code == 201, note_res.text

    range_res = api_client.get(
        "/appointments/range",
        params={"start": "2026-01-21", "end": "2026-01-22"},
        headers=auth_headers,
    )
    assert range_res.status_code == 200, range_res.text
    row = next(item for item in range_res.json() if item["id"] == appointment_id)
    assert row["note_preview"] == "Bring the referral letter"


def test_note_preview_is_not_queried_without_notes_permission(monkeypatch):
    from app.routers import appointments as appointments_router

    monkeypatch.setattr(appointments_router, "get_user_capabilities", lambda _db, _id: [])
    db = SimpleNamespace(execute=lambda _stmt: pytest.fail("notes query must not run"))
    user = SimpleNamespace(id=123)
    appointment = SimpleNamespace(id=456)

    result = appointments_router._attach_note_previews(db, user, [appointment])

    assert result == [appointment]
    assert not hasattr(appointment, "note_preview")
