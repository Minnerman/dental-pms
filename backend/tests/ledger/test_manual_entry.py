def test_manual_adjustment_persists_in_patient_ledger(api_client, auth_headers):
    patient_response = api_client.post(
        "/patients",
        json={"first_name": "Ledger", "last_name": "Adjustment"},
        headers=auth_headers,
    )
    assert patient_response.status_code == 201, patient_response.text
    patient_id = patient_response.json()["id"]

    actor_response = api_client.get("/me", headers=auth_headers)
    assert actor_response.status_code == 200, actor_response.text
    actor_id = actor_response.json()["id"]

    adjustment_response = api_client.post(
        f"/patients/{patient_id}/charges",
        json={
            "entry_type": "adjustment",
            "amount_pence": 725,
            "reference": "MANUAL-ADJUSTMENT-001",
            "note": "Manual balance correction",
        },
        headers=auth_headers,
    )
    assert adjustment_response.status_code == 200, adjustment_response.text
    created = adjustment_response.json()
    assert created["patient_id"] == patient_id
    assert created["entry_type"] == "adjustment"
    assert created["amount_pence"] == 725
    assert created["method"] is None
    assert created["reference"] == "MANUAL-ADJUSTMENT-001"
    assert created["note"] == "Manual balance correction"
    assert created["created_by"]["id"] == actor_id

    ledger_response = api_client.get(
        f"/patients/{patient_id}/ledger",
        headers=auth_headers,
    )
    assert ledger_response.status_code == 200, ledger_response.text
    persisted = next(
        entry for entry in ledger_response.json() if entry["id"] == created["id"]
    )
    assert persisted == created
