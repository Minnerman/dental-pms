def test_patient_ledger_payment_audit_entry(api_client, auth_headers):
    patient_res = api_client.post(
        "/patients",
        json={"first_name": "Ledger", "last_name": "Audit"},
        headers=auth_headers,
    )
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    payment_payload = {
        "amount_pence": 2500,
        "method": "card",
        "reference": "LEDGER-AUDIT-001",
        "note": "Quick payment audit proof",
    }
    payment_res = api_client.post(
        f"/patients/{patient_id}/payments",
        json=payment_payload,
        headers=auth_headers,
    )
    assert payment_res.status_code == 200, payment_res.text

    audit_res = api_client.get(
        "/audit",
        params={"entity_type": "patient", "entity_id": str(patient_id)},
        headers=auth_headers,
    )
    assert audit_res.status_code == 200, audit_res.text

    payment_entry = next(
        entry
        for entry in audit_res.json()
        if entry["action"] == "ledger.payment_recorded"
        and entry.get("after_json", {}).get("entry_type") == "payment"
        and entry.get("after_json", {}).get("amount_pence") == -2500
        and entry.get("after_json", {}).get("method") == "card"
        and entry.get("after_json", {}).get("reference") == "LEDGER-AUDIT-001"
    )
    assert payment_entry["after_json"]["note"] == "Quick payment audit proof"
