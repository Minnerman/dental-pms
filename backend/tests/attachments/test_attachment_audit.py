def test_attachment_audit_entries(api_client, auth_headers):
    patient_payload = {"first_name": "Attach", "last_name": "Audit"}
    patient_res = api_client.post("/patients", json=patient_payload, headers=auth_headers)
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    upload_res = api_client.post(
        f"/patients/{patient_id}/attachments",
        files={"file": ("sample.pdf", b"sample", "application/pdf")},
        headers=auth_headers,
    )
    assert upload_res.status_code == 201, upload_res.text
    attachment_id = upload_res.json()["id"]

    delete_res = api_client.delete(
        f"/attachments/{attachment_id}",
        headers=auth_headers,
    )
    assert delete_res.status_code == 200, delete_res.text

    audit_res = api_client.get(
        "/audit",
        params={"entity_type": "attachment", "entity_id": str(attachment_id)},
        headers=auth_headers,
    )
    assert audit_res.status_code == 200, audit_res.text
    actions = {entry["action"] for entry in audit_res.json()}
    assert "attachment.uploaded" in actions
    assert "attachment.deleted" in actions


def test_patient_document_audit_entries(api_client, auth_headers):
    patient_payload = {"first_name": "Document", "last_name": "Audit"}
    patient_res = api_client.post("/patients", json=patient_payload, headers=auth_headers)
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    template_payload = {
        "name": "Patient Document Audit Template",
        "kind": "letter",
        "content": "Audit body for {{patient.full_name}}",
        "is_active": True,
    }
    template_res = api_client.post(
        "/document-templates",
        json=template_payload,
        headers=auth_headers,
    )
    assert template_res.status_code == 201, template_res.text
    template_id = template_res.json()["id"]

    create_res = api_client.post(
        f"/patients/{patient_id}/documents",
        json={"template_id": template_id, "title": "Patient Document Audit Proof"},
        headers=auth_headers,
    )
    assert create_res.status_code == 201, create_res.text
    document_id = create_res.json()["id"]

    download_res = api_client.get(
        f"/patient-documents/{document_id}/download",
        params={"format": "text"},
        headers=auth_headers,
    )
    assert download_res.status_code == 200, download_res.text

    delete_res = api_client.delete(
        f"/patient-documents/{document_id}",
        headers=auth_headers,
    )
    assert delete_res.status_code == 200, delete_res.text

    audit_res = api_client.get(
        "/audit",
        params={"entity_type": "patient_document", "entity_id": str(document_id)},
        headers=auth_headers,
    )
    assert audit_res.status_code == 200, audit_res.text
    actions = {entry["action"] for entry in audit_res.json()}
    assert "patient_document.created" in actions
    assert "patient_document.downloaded" in actions
    assert "patient_document.deleted" in actions


def test_document_template_audit_entries(api_client, auth_headers):
    create_res = api_client.post(
        "/document-templates",
        json={
            "name": "Template Audit Proof",
            "kind": "letter",
            "content": "Template audit proof body",
            "is_active": True,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201, create_res.text
    template_id = create_res.json()["id"]

    update_res = api_client.patch(
        f"/document-templates/{template_id}",
        json={
            "name": "Template Audit Proof Updated",
            "kind": "letter",
            "content": "Template audit proof updated body",
            "is_active": True,
        },
        headers=auth_headers,
    )
    assert update_res.status_code == 200, update_res.text

    download_res = api_client.get(
        f"/document-templates/{template_id}/download",
        headers=auth_headers,
    )
    assert download_res.status_code == 200, download_res.text

    delete_res = api_client.delete(
        f"/document-templates/{template_id}",
        headers=auth_headers,
    )
    assert delete_res.status_code == 200, delete_res.text

    audit_res = api_client.get(
        "/audit",
        params={"entity_type": "document_template", "entity_id": str(template_id)},
        headers=auth_headers,
    )
    assert audit_res.status_code == 200, audit_res.text
    actions = {entry["action"] for entry in audit_res.json()}
    assert "document_template.created" in actions
    assert "document_template.updated" in actions
    assert "document_template.downloaded" in actions
    assert "document_template.deleted" in actions


def test_billing_paid_receipt_audit_entries(api_client, auth_headers):
    patient_res = api_client.post(
        "/patients",
        json={"first_name": "Billing", "last_name": "Audit"},
        headers=auth_headers,
    )
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    invoice_res = api_client.post(
        "/invoices",
        json={"patient_id": patient_id},
        headers=auth_headers,
    )
    assert invoice_res.status_code == 201, invoice_res.text
    invoice_id = invoice_res.json()["id"]

    line_res = api_client.post(
        f"/invoices/{invoice_id}/lines",
        json={
            "description": "Audit proof exam",
            "quantity": 1,
            "unit_price_pence": 2500,
        },
        headers=auth_headers,
    )
    assert line_res.status_code == 201, line_res.text

    issue_res = api_client.post(
        f"/invoices/{invoice_id}/issue",
        headers=auth_headers,
    )
    assert issue_res.status_code == 200, issue_res.text

    payment_res = api_client.post(
        f"/invoices/{invoice_id}/payments",
        json={"amount_pence": 2500, "method": "card"},
        headers=auth_headers,
    )
    assert payment_res.status_code == 201, payment_res.text
    payment_id = payment_res.json()["id"]

    receipt_res = api_client.get(
        f"/payments/{payment_id}/receipt.pdf",
        headers=auth_headers,
    )
    assert receipt_res.status_code == 200, receipt_res.text

    audit_res = api_client.get(
        "/audit",
        params={"entity_type": "invoice", "entity_id": str(invoice_id)},
        headers=auth_headers,
    )
    assert audit_res.status_code == 200, audit_res.text
    actions = {entry["action"] for entry in audit_res.json()}
    assert "payment.recorded" in actions
    assert "invoice.paid" in actions
    assert "payment.receipt_generated" in actions
