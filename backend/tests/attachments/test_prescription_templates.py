from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.prescription_template import PrescriptionTemplate
from app.models.user import Role, User
from app.services.capabilities import replace_user_capabilities
from app.services.prescription_defaults import ensure_prescription_defaults
from app.services.users import create_user


@pytest.mark.parametrize("strength", ["250", "500"])
@pytest.mark.parametrize("state", ["untouched", "explicit_blank", "custom_supply", "renamed_inactive"])
def test_liquid_default_upgrade_preserves_practice_edits(auth_headers, strength, state):
    with SessionLocal() as db:
        actor = db.scalar(select(User).order_by(User.id))
        preset = db.scalar(select(PrescriptionTemplate).where(
            PrescriptionTemplate.stock_key == f"amoxicillin-liquid-{strength}"
        ))
        fields = ("name", "quantity", "is_active", "updated_by_user_id")
        original = {field: getattr(preset, field) for field in fields}
        try:
            preset.quantity = ""
            preset.updated_by_user_id = None
            if state == "explicit_blank":
                preset.updated_by_user_id = actor.id
            elif state == "custom_supply":
                preset.quantity = "75 mL"
            elif state == "renamed_inactive":
                preset.name = "Synthetic custom liquid"
                preset.is_active = False
            db.commit()
            expected = {field: getattr(preset, field) for field in fields}
            if state == "untouched":
                expected["quantity"] = "100 mL"
            for _ in range(2):
                ensure_prescription_defaults(db, actor=actor)
                db.refresh(preset)
                assert {field: getattr(preset, field) for field in fields} == expected
        finally:
            for field, value in original.items():
                setattr(preset, field, value)
            db.commit()


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
