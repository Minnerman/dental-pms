from datetime import datetime, timezone


def test_create_allows_same_clinician_overlap(api_client, auth_headers):
    users_res = api_client.get("/users", headers=auth_headers)
    assert users_res.status_code == 200, users_res.text
    clinicians = [user for user in users_res.json() if user.get("is_active")]
    assert clinicians, "Expected at least one active clinician user"
    clinician_id = clinicians[0]["id"]

    patient_a_res = api_client.post(
        "/patients",
        json={"first_name": "Conflict", "last_name": "One"},
        headers=auth_headers,
    )
    assert patient_a_res.status_code == 201, patient_a_res.text
    patient_a_id = patient_a_res.json()["id"]

    patient_b_res = api_client.post(
        "/patients",
        json={"first_name": "Conflict", "last_name": "Two"},
        headers=auth_headers,
    )
    assert patient_b_res.status_code == 201, patient_b_res.text
    patient_b_id = patient_b_res.json()["id"]

    first_res = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_a_id,
            "clinician_user_id": clinician_id,
            "starts_at": datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc).isoformat(),
            "ends_at": datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc).isoformat(),
            "status": "booked",
            "location_type": "clinic",
            "location": "Room 1",
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert first_res.status_code == 201, first_res.text

    overlapping_res = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_b_id,
            "clinician_user_id": clinician_id,
            "starts_at": datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc).isoformat(),
            "ends_at": datetime(2026, 1, 15, 9, 45, tzinfo=timezone.utc).isoformat(),
            "status": "booked",
            "location_type": "clinic",
            "location": "Room 1",
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert overlapping_res.status_code == 201, overlapping_res.text
    created = overlapping_res.json()
    assert created["clinician_user_id"] == clinician_id
    assert created["patient"]["id"] == patient_b_id
