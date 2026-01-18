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
