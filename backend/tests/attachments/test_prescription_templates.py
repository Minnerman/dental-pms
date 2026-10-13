from uuid import uuid4

from sqlalchemy import select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.user import Role
from app.services.capabilities import replace_user_capabilities
from app.services.users import create_user


def template_payload(**changes):
    return {
        "name": f"Synthetic usual prescription {uuid4().hex[:8]}",
        "medicine": "Synthetic medicine - no clinical use",
        "directions": "Synthetic directions\nSecond line",
        "quantity": "Synthetic quantity",
        "is_active": True,
        **changes,
    }


def test_prescription_template_persistence_activation_and_audit(api_client, auth_headers):
    payload = template_payload()
    response = api_client.post("/prescription-templates", headers=auth_headers, json=payload)
    assert response.status_code == 201, response.text
    template_id = response.json()["id"]
    rows = api_client.get("/prescription-templates", headers=auth_headers).json()
    assert next(row for row in rows if row["id"] == template_id)["directions"] == payload["directions"]
    updated = {**payload, "directions": "Updated synthetic directions", "is_active": False}
    response = api_client.put(f"/prescription-templates/{template_id}", headers=auth_headers, json=updated)
    assert response.status_code == 200, response.text
    assert response.json()["directions"] == updated["directions"]
    active = api_client.get("/prescription-templates", headers=auth_headers).json()
    assert all(row["id"] != template_id for row in active)
    all_rows = api_client.get("/prescription-templates?include_inactive=true", headers=auth_headers).json()
    assert next(row for row in all_rows if row["id"] == template_id)["is_active"] is False
    with SessionLocal() as db:
        events = list(db.scalars(select(AuditLog).where(
            AuditLog.entity_type == "prescription_template", AuditLog.entity_id == str(template_id)
        ).order_by(AuditLog.id)))
        assert [row.action for row in events] == ["prescription_template.created", "prescription_template.updated"]
        assert events[0].after_json == {"name": payload["name"], "is_active": True}
        assert events[1].before_json["is_active"] is True
        assert events[1].after_json["is_active"] is False
    response = api_client.put(f"/prescription-templates/{template_id}", headers=auth_headers, json=payload)
    assert response.status_code == 200
    assert any(row["id"] == template_id for row in api_client.get("/prescription-templates", headers=auth_headers).json())


def test_prescription_template_validation_and_missing_record(api_client, auth_headers):
    invalid = [
        {"name": "   "}, {"medicine": ""}, {"directions": "x" * 2001},
        {"quantity": "\x00"}, {"quantity": None}, {"prescriber_gdc": "not a template field"},
    ]
    for fields in invalid:
        response = api_client.post("/prescription-templates", headers=auth_headers, json=template_payload(**fields))
        assert response.status_code == 422, response.text
    payload = template_payload(name="  Synthetic trimmed template  ")
    response = api_client.post("/prescription-templates", headers=auth_headers, json=payload)
    assert response.status_code == 201
    assert response.json()["name"] == payload["name"].strip()
    assert api_client.put("/prescription-templates/2147483647", headers=auth_headers, json=payload).status_code == 404


def test_prescription_templates_enforce_read_and_management_permissions(api_client, auth_headers):
    with SessionLocal() as db:
        user = create_user(db, email=f"synthetic-prescription-{uuid4().hex}@example.com",
                           password="SyntheticPrescription123!", full_name="Synthetic Template User", role=Role.dentist)
        user_id = user.id
        replace_user_capabilities(db, user_id, ["documents.download"])
    token = create_access_token(subject=str(user_id), secret=settings.secret_key, alg=settings.jwt_alg,
                                expires_minutes=settings.access_token_expire_minutes)
    headers = {"Authorization": f"Bearer {token}"}
    payload = template_payload()
    created = api_client.post("/prescription-templates", headers=auth_headers, json=payload)
    assert created.status_code == 201
    assert api_client.get("/prescription-templates").status_code == 401
    assert api_client.get("/prescription-templates", headers=headers).status_code == 200
    assert api_client.post("/prescription-templates", headers=headers, json=payload).status_code == 403
    assert api_client.put(f"/prescription-templates/{created.json()['id']}", headers=headers, json=payload).status_code == 403
    with SessionLocal() as db:
        replace_user_capabilities(db, user_id, [])
    assert api_client.get("/prescription-templates", headers=headers).status_code == 403
