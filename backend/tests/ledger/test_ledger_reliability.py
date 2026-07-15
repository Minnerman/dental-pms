from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.ledger import PatientLedgerEntry
from app.models.user import Role
from app.services.capabilities import get_user_capabilities, replace_user_capabilities
from app.services.users import create_user


def _create_patient(api_client, auth_headers, suffix: str) -> int:
    response = api_client.post(
        "/patients",
        json={"first_name": "Ledger", "last_name": suffix},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _headers_without_payment_capability(api_client) -> dict[str, str]:
    email = f"ledger-denied-{uuid4().hex[:10]}@example.com"
    password = "LedgerDenied123!"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password=password,
            full_name="Ledger Denied",
            role=Role.reception,
        )
        user_id = int(user.id)
        retained_codes = [
            capability.code
            for capability in get_user_capabilities(session, user_id)
            if capability.code != "billing.payments.write"
        ]
        replace_user_capabilities(session, user_id, retained_codes)
    finally:
        session.close()

    # Startup must not silently restore an explicitly revoked capability.
    from app.main import startup

    startup()
    session = SessionLocal()
    try:
        restarted_user_codes = {
            capability.code
            for capability in get_user_capabilities(session, user_id)
        }
    finally:
        session.close()
    assert "billing.payments.write" not in restarted_user_codes

    login = api_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_ledger_writes_require_payment_capability_without_side_effects(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, "Permission")
    invoice = api_client.post(
        "/invoices",
        json={"patient_id": patient_id},
        headers=auth_headers,
    )
    assert invoice.status_code == 201, invoice.text

    denied_headers = _headers_without_payment_capability(api_client)
    capabilities = api_client.get("/me/capabilities", headers=denied_headers)
    assert capabilities.status_code == 200, capabilities.text
    assert "billing.payments.write" not in capabilities.json()

    manual_payment = api_client.post(
        f"/patients/{patient_id}/payments",
        json={"amount_pence": 1500, "method": "card"},
        headers=denied_headers,
    )
    adjustment = api_client.post(
        f"/patients/{patient_id}/charges",
        json={"amount_pence": 300, "entry_type": "adjustment"},
        headers=denied_headers,
    )
    invoice_payment = api_client.post(
        f"/invoices/{invoice.json()['id']}/payments",
        json={"amount_pence": 1500, "method": "card"},
        headers=denied_headers,
    )
    assert manual_payment.status_code == 403, manual_payment.text
    assert adjustment.status_code == 403, adjustment.text
    assert invoice_payment.status_code == 403, invoice_payment.text

    session = SessionLocal()
    try:
        ledger_count = session.scalar(
            select(func.count(PatientLedgerEntry.id)).where(
                PatientLedgerEntry.patient_id == patient_id
            )
        )
        ledger_audit_count = session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_type == "patient",
                AuditLog.entity_id == str(patient_id),
                AuditLog.action.in_(
                    [
                        "ledger.payment_recorded",
                        "ledger.charge_recorded",
                        "ledger.adjustment_recorded",
                    ]
                ),
            )
        )
    finally:
        session.close()
    assert ledger_count == 0
    assert ledger_audit_count == 0


def test_manual_entries_persist_in_order_with_specific_audit_actions(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, "Ordering")

    payment = api_client.post(
        f"/patients/{patient_id}/payments",
        json={
            "amount_pence": 2500,
            "method": "cash",
            "reference": "ORDER-PAYMENT",
            "note": "First ledger entry",
        },
        headers=auth_headers,
    )
    adjustment = api_client.post(
        f"/patients/{patient_id}/charges",
        json={
            "amount_pence": 725,
            "entry_type": "adjustment",
            "reference": "ORDER-ADJUSTMENT",
            "note": "Second ledger entry",
        },
        headers=auth_headers,
    )
    assert payment.status_code == 200, payment.text
    assert adjustment.status_code == 200, adjustment.text

    ledger = api_client.get(
        f"/patients/{patient_id}/ledger",
        headers=auth_headers,
    )
    assert ledger.status_code == 200, ledger.text
    entries = ledger.json()
    assert [entry["id"] for entry in entries] == [
        payment.json()["id"],
        adjustment.json()["id"],
    ]
    assert entries[0]["amount_pence"] == -2500
    assert entries[0]["method"] == "cash"
    assert entries[1]["amount_pence"] == 725
    assert entries[1]["entry_type"] == "adjustment"
    assert entries[0]["created_by"]["id"] == entries[1]["created_by"]["id"]

    audit = api_client.get(
        "/audit",
        params={"entity_type": "patient", "entity_id": str(patient_id)},
        headers=auth_headers,
    )
    assert audit.status_code == 200, audit.text
    actions = [entry["action"] for entry in audit.json()]
    assert "ledger.payment_recorded" in actions
    assert "ledger.adjustment_recorded" in actions
    assert "ledger.charge_recorded" not in actions


def test_manual_entry_validation_rejects_invalid_requests_without_mutation(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, "Validation")

    requests = [
        ("payments", {"amount_pence": 0, "method": "card"}, 400),
        ("payments", {"amount_pence": -1, "method": "cash"}, 400),
        ("payments", {"amount_pence": 100}, 422),
        ("payments", {"amount_pence": 100, "method": "unsupported"}, 422),
        ("charges", {"amount_pence": 0, "entry_type": "adjustment"}, 400),
        ("charges", {"amount_pence": -1, "entry_type": "charge"}, 400),
        ("charges", {"amount_pence": 100, "entry_type": "payment"}, 400),
        ("charges", {"amount_pence": 100, "entry_type": "unsupported"}, 422),
    ]
    for endpoint, payload, expected_status in requests:
        response = api_client.post(
            f"/patients/{patient_id}/{endpoint}",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == expected_status, response.text

    missing_patient = api_client.post(
        "/patients/999999999/payments",
        json={"amount_pence": 100, "method": "card"},
        headers=auth_headers,
    )
    assert missing_patient.status_code == 404, missing_patient.text

    archive = api_client.post(
        f"/patients/{patient_id}/archive",
        headers=auth_headers,
    )
    assert archive.status_code == 200, archive.text
    archived_patient = api_client.post(
        f"/patients/{patient_id}/charges",
        json={"amount_pence": 100, "entry_type": "adjustment"},
        headers=auth_headers,
    )
    assert archived_patient.status_code == 404, archived_patient.text

    session = SessionLocal()
    try:
        ledger_count = session.scalar(
            select(func.count(PatientLedgerEntry.id)).where(
                PatientLedgerEntry.patient_id == patient_id
            )
        )
    finally:
        session.close()
    assert ledger_count == 0


def test_related_invoice_must_belong_to_ledger_patient(api_client, auth_headers):
    ledger_patient_id = _create_patient(api_client, auth_headers, "InvoiceOwner")
    other_patient_id = _create_patient(api_client, auth_headers, "OtherInvoiceOwner")
    invoice = api_client.post(
        "/invoices",
        json={"patient_id": other_patient_id},
        headers=auth_headers,
    )
    assert invoice.status_code == 201, invoice.text

    for endpoint, payload in [
        (
            "payments",
            {
                "amount_pence": 1000,
                "method": "card",
                "related_invoice_id": invoice.json()["id"],
            },
        ),
        (
            "charges",
            {
                "amount_pence": 1000,
                "entry_type": "adjustment",
                "related_invoice_id": invoice.json()["id"],
            },
        ),
    ]:
        response = api_client.post(
            f"/patients/{ledger_patient_id}/{endpoint}",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "Related invoice does not belong to this patient"

    ledger = api_client.get(
        f"/patients/{ledger_patient_id}/ledger",
        headers=auth_headers,
    )
    assert ledger.status_code == 200, ledger.text
    assert ledger.json() == []
