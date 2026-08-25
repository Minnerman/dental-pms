from __future__ import annotations

from uuid import uuid4


def _restricted_headers(api_client, auth_headers, capability_codes: list[str]) -> dict[str, str]:
    suffix = uuid4().hex[:10]
    email = f"completion-permissions-{suffix}@example.com"
    password = "CompletionPermissions123!"
    created = api_client.post(
        "/users",
        headers=auth_headers,
        json={
            "email": email,
            "full_name": "Completion Permissions User",
            "role": "reception",
            "temp_password": password,
        },
    )
    assert created.status_code == 201, created.text
    updated = api_client.put(
        f"/users/{created.json()['id']}/capabilities",
        headers=auth_headers,
        json={"capability_codes": capability_codes},
    )
    assert updated.status_code == 200, updated.text
    login = api_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _patient(api_client, auth_headers) -> int:
    response = api_client.post(
        "/patients",
        headers=auth_headers,
        json={"first_name": "Completion", "last_name": uuid4().hex[:10]},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_finance_reads_require_billing_capabilities(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    payment = api_client.post(
        f"/patients/{patient_id}/payments",
        headers=auth_headers,
        json={"amount_pence": 1000, "method": "cash"},
    )
    assert payment.status_code == 200, payment.text
    invoice = api_client.post(
        "/invoices",
        headers=auth_headers,
        json={"patient_id": patient_id},
    )
    assert invoice.status_code == 201, invoice.text
    invoice_id = int(invoice.json()["id"])

    patient_only = _restricted_headers(api_client, auth_headers, ["patients.view"])
    for path in (
        f"/patients/{patient_id}/ledger",
        f"/patients/{patient_id}/balance",
        f"/patients/{patient_id}/finance-summary",
        "/invoices",
        f"/invoices/{invoice_id}",
        f"/invoices/{invoice_id}/pdf",
        "/reports/cashup",
        "/reports/finance/cashup",
        "/reports/finance/outstanding",
        "/reports/finance/trends",
        "/reports/finance/month-pack?year=2032&month=1&format=pdf",
    ):
        response = api_client.get(path, headers=patient_only)
        assert response.status_code == 403, path

    billing_viewer = _restricted_headers(
        api_client,
        auth_headers,
        ["patients.view", "billing.view"],
    )
    for path in (
        f"/patients/{patient_id}/ledger",
        f"/patients/{patient_id}/balance",
        f"/patients/{patient_id}/finance-summary",
        "/invoices",
        f"/invoices/{invoice_id}",
        "/reports/finance/outstanding",
        "/reports/finance/trends",
    ):
        response = api_client.get(path, headers=billing_viewer)
        assert response.status_code == 200, path
    assert api_client.get("/reports/cashup", headers=billing_viewer).status_code == 403
    assert api_client.get("/reports/finance/cashup", headers=billing_viewer).status_code == 403

    cashup_user = _restricted_headers(
        api_client,
        auth_headers,
        ["billing.view", "billing.cashup"],
    )
    assert api_client.get("/reports/cashup", headers=cashup_user).status_code == 200
    assert api_client.get("/reports/finance/cashup", headers=cashup_user).status_code == 200
    assert (
        api_client.get(
            "/reports/finance/month-pack?year=2032&month=1&format=pdf",
            headers=cashup_user,
        ).status_code
        == 200
    )


def test_audit_and_timeline_reads_follow_domain_capabilities(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    note = api_client.post(
        f"/patients/{patient_id}/notes",
        headers=auth_headers,
        json={"body": "Synthetic completion audit note", "note_type": "clinical"},
    )
    assert note.status_code == 201, note.text
    note_id = int(note.json()["id"])

    no_capabilities = _restricted_headers(api_client, auth_headers, [])
    for path in (
        "/audit",
        f"/audit/patients/{patient_id}",
        f"/audit/notes/{note_id}",
        f"/patients/{patient_id}/timeline",
    ):
        response = api_client.get(path, headers=no_capabilities)
        assert response.status_code == 403, path

    patient_viewer = _restricted_headers(
        api_client,
        auth_headers,
        ["patients.view"],
    )
    assert api_client.get(f"/audit/patients/{patient_id}", headers=patient_viewer).status_code == 200
    assert api_client.get(f"/patients/{patient_id}/timeline", headers=patient_viewer).status_code == 200
    assert api_client.get(f"/audit/notes/{note_id}", headers=patient_viewer).status_code == 403
    assert api_client.get("/audit", headers=patient_viewer).status_code == 403

    note_viewer = _restricted_headers(
        api_client,
        auth_headers,
        ["notes.view"],
    )
    assert api_client.get(f"/audit/notes/{note_id}", headers=note_viewer).status_code == 200
    assert api_client.get("/audit", headers=auth_headers).status_code == 200
