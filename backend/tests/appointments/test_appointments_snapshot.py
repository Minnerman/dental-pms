from datetime import datetime, timezone


def _create_patient(api_client, auth_headers, *, first_name: str, last_name: str) -> int:
    response = api_client.post(
        "/patients",
        json={"first_name": first_name, "last_name": last_name},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _create_appointment(
    api_client,
    auth_headers,
    *,
    patient_id: int,
    starts_at: datetime,
    ends_at: datetime,
    location: str = "Room 1",
) -> int:
    payload = {
        "patient_id": patient_id,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "status": "booked",
        "location_type": "clinic",
        "location": location,
        "allow_outside_hours": True,
    }
    response = api_client.post("/appointments", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_snapshot_day_returns_flags_and_masked_patient_name(api_client, auth_headers):
    patient_id = _create_patient(
        api_client,
        auth_headers,
        first_name="Snapshot",
        last_name="Case",
    )
    starts_at = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
    appointment_id = _create_appointment(
        api_client,
        auth_headers,
        patient_id=patient_id,
        starts_at=starts_at,
        ends_at=ends_at,
        location="Snapshot Room",
    )

    note_response = api_client.post(
        "/notes",
        json={
            "patient_id": patient_id,
            "appointment_id": appointment_id,
            "body": "Snapshot note flag",
            "note_type": "clinical",
        },
        headers=auth_headers,
    )
    assert note_response.status_code == 201, note_response.text

    response = api_client.get(
        "/appointments/snapshot",
        params={"date": "2026-01-15", "view": "day"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["date"] == "2026-01-15"
    assert payload["view"] == "day"
    assert payload["range_start"] == "2026-01-15"
    assert payload["range_end"] == "2026-01-15"

    appointment_rows = [item for item in payload["appointments"] if item["id"] == appointment_id]
    assert appointment_rows
    row = appointment_rows[0]
    assert row["duration_minutes"] == 30
    assert row["status"] == "booked"
    assert row["flags"]["has_notes"] is True
    assert row["column_key"].startswith("chair:")
    assert "***" in row["patient_display_name"]

    assert payload["summary"]["total_appointments"] >= 1
    assert payload["summary"]["status_booked"] >= 1
    assert payload["summary"]["total_columns"] >= 1


def test_snapshot_week_includes_anchor_week_and_unmasked_names(api_client, auth_headers):
    patient_id = _create_patient(
        api_client,
        auth_headers,
        first_name="Week",
        last_name="Anchor",
    )
    starts_at = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 15, 14, 45, tzinfo=timezone.utc)
    appointment_id = _create_appointment(
        api_client,
        auth_headers,
        patient_id=patient_id,
        starts_at=starts_at,
        ends_at=ends_at,
        location="Week Room",
    )

    response = api_client.get(
        "/appointments/snapshot",
        params={"date": "2026-01-15", "view": "week", "mask_names": "false"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["date"] == "2026-01-15"
    assert payload["view"] == "week"
    assert payload["range_start"] == "2026-01-12"
    assert payload["range_end"] == "2026-01-18"

    appointment_rows = [item for item in payload["appointments"] if item["id"] == appointment_id]
    assert appointment_rows
    row = appointment_rows[0]
    assert row["patient_display_name"] == "Week Anchor"
    assert row["duration_minutes"] == 45


def test_snapshot_rejects_unsupported_view(api_client, auth_headers):
    response = api_client.get(
        "/appointments/snapshot",
        params={"date": "2026-01-15", "view": "month"},
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
