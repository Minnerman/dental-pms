def test_patient_create_edit_archive_restore_lifecycle(api_client, auth_headers):
    create_response = api_client.post(
        "/patients",
        headers=auth_headers,
        json={
            "first_name": "Lifecycle",
            "last_name": "Regression",
            "date_of_birth": "1990-04-15",
            "email": "lifecycle.regression@example.com",
            "phone": "02079460000",
            "patient_category": "CLINIC_PRIVATE",
            "care_setting": "CLINIC",
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    patient_id = created["id"]
    assert created["first_name"] == "Lifecycle"
    assert created["last_name"] == "Regression"
    assert created["deleted_at"] is None

    update_response = api_client.patch(
        f"/patients/{patient_id}",
        headers=auth_headers,
        json={
            "last_name": "Regression-Updated",
            "phone": "02079460001",
            "care_setting": "HOME",
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["first_name"] == "Lifecycle"
    assert updated["last_name"] == "Regression-Updated"
    assert updated["phone"] == "02079460001"
    assert updated["care_setting"] == "HOME"

    active_list_response = api_client.get("/patients", headers=auth_headers)
    assert active_list_response.status_code == 200, active_list_response.text
    assert patient_id in {patient["id"] for patient in active_list_response.json()}

    archive_response = api_client.post(
        f"/patients/{patient_id}/archive",
        headers=auth_headers,
    )
    assert archive_response.status_code == 200, archive_response.text
    assert archive_response.json()["deleted_at"] is not None

    hidden_response = api_client.get(
        f"/patients/{patient_id}",
        headers=auth_headers,
    )
    assert hidden_response.status_code == 404

    hidden_list_response = api_client.get("/patients", headers=auth_headers)
    assert hidden_list_response.status_code == 200, hidden_list_response.text
    assert patient_id not in {
        patient["id"] for patient in hidden_list_response.json()
    }

    archived_list_response = api_client.get(
        "/patients",
        params={"include_deleted": True},
        headers=auth_headers,
    )
    assert archived_list_response.status_code == 200, archived_list_response.text
    archived = next(
        patient
        for patient in archived_list_response.json()
        if patient["id"] == patient_id
    )
    assert archived["deleted_at"] is not None

    archived_update_response = api_client.patch(
        f"/patients/{patient_id}",
        headers=auth_headers,
        json={"last_name": "Must-Not-Apply"},
    )
    assert archived_update_response.status_code == 404

    restore_response = api_client.post(
        f"/patients/{patient_id}/restore",
        headers=auth_headers,
    )
    assert restore_response.status_code == 200, restore_response.text
    restored = restore_response.json()
    assert restored["deleted_at"] is None
    assert restored["last_name"] == "Regression-Updated"

    restored_get_response = api_client.get(
        f"/patients/{patient_id}",
        headers=auth_headers,
    )
    assert restored_get_response.status_code == 200, restored_get_response.text
    assert restored_get_response.json()["last_name"] == "Regression-Updated"
