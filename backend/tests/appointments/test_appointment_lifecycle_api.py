from datetime import datetime, timezone


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_appointment_create_edit_archive_restore_lifecycle(api_client, auth_headers):
    patient_response = api_client.post(
        "/patients",
        json={"first_name": "Appointment", "last_name": "Lifecycle"},
        headers=auth_headers,
    )
    assert patient_response.status_code == 201, patient_response.text
    patient_id = patient_response.json()["id"]

    starts_at = datetime(2026, 2, 2, 9, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 2, 2, 9, 30, tzinfo=timezone.utc)
    create_response = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "status": "booked",
            "appointment_type": "Initial exam",
            "clinician": "Test clinician",
            "location": "Test surgery",
            "location_type": "clinic",
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    appointment_id = created["id"]
    assert created["patient"]["id"] == patient_id
    assert _parse_datetime(created["starts_at"]) == starts_at
    assert _parse_datetime(created["ends_at"]) == ends_at
    assert created["status"] == "booked"
    assert created["appointment_type"] == "Initial exam"
    assert created["clinician"] == "Test clinician"
    assert created["location"] == "Test surgery"

    update_response = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"appointment_type": "Review exam"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["appointment_type"] == "Review exam"
    assert _parse_datetime(updated["starts_at"]) == starts_at
    assert _parse_datetime(updated["ends_at"]) == ends_at
    assert updated["status"] == "booked"
    assert updated["clinician"] == "Test clinician"
    assert updated["location"] == "Test surgery"

    archive_response = api_client.post(
        f"/appointments/{appointment_id}/archive",
        headers=auth_headers,
    )
    assert archive_response.status_code == 200, archive_response.text
    assert archive_response.json()["deleted_at"] is not None

    get_archived = api_client.get(
        f"/appointments/{appointment_id}",
        headers=auth_headers,
    )
    assert get_archived.status_code == 404

    edit_archived = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"appointment_type": "Should not apply"},
        headers=auth_headers,
    )
    assert edit_archived.status_code == 404

    active_list = api_client.get(
        "/appointments",
        params={"patient_id": patient_id},
        headers=auth_headers,
    )
    assert active_list.status_code == 200, active_list.text
    assert appointment_id not in {item["id"] for item in active_list.json()}

    archived_list = api_client.get(
        "/appointments",
        params={"patient_id": patient_id, "include_deleted": True},
        headers=auth_headers,
    )
    assert archived_list.status_code == 200, archived_list.text
    archived = next(item for item in archived_list.json() if item["id"] == appointment_id)
    assert archived["deleted_at"] is not None
    assert archived["appointment_type"] == "Review exam"

    restore_response = api_client.post(
        f"/appointments/{appointment_id}/restore",
        headers=auth_headers,
    )
    assert restore_response.status_code == 200, restore_response.text
    restored = restore_response.json()
    assert restored["deleted_at"] is None
    assert restored["appointment_type"] == "Review exam"
    assert _parse_datetime(restored["starts_at"]) == starts_at
    assert _parse_datetime(restored["ends_at"]) == ends_at
    assert restored["status"] == "booked"
    assert restored["clinician"] == "Test clinician"
    assert restored["location"] == "Test surgery"

    get_restored = api_client.get(
        f"/appointments/{appointment_id}",
        headers=auth_headers,
    )
    assert get_restored.status_code == 200, get_restored.text
    assert get_restored.json()["appointment_type"] == "Review exam"
