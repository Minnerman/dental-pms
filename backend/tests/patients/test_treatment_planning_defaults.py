"""Explicit catalogue defaults, native stable suggestions and group scope."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.treatment import Treatment
from app.schemas.treatment import suggested_planning_defaults
from tests.patients.test_tooth_conditions import _user_with_capabilities
from tests.patients.test_treatment_planning import setup_case, start, add
from tests.patients.test_planning_appliances import prepared, create_group, DENTURE


def test_explicit_defaults_revision_clear_and_old_metadata_preservation(api_client, auth_headers):
    response = api_client.post("/treatments", headers=auth_headers, json={"name": f"Defaults {uuid4().hex}",
        "level": "crown", "description": "Keep this description", "planning_defaults": {"drawing_kind": "bridge", "material": "gold"}})
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["planning_defaults_revision"] == 1 and row["suggested_planning_defaults"] is None
    path = f"/treatments/{row['id']}"
    assert api_client.patch(path, headers=auth_headers, json={"planning_defaults": None}).status_code == 422
    assert api_client.patch(path, headers=auth_headers, json={"planning_defaults": None, "expected_planning_defaults_revision": 0}).status_code == 409
    assert api_client.patch(path, headers=auth_headers, json={"level": "root"}).status_code == 422
    renamed = api_client.patch(path, headers=auth_headers, json={"name": f"Renamed {uuid4().hex}"})
    assert renamed.status_code == 200 and renamed.json()["planning_defaults"] == row["planning_defaults"]
    cleared = api_client.patch(path, headers=auth_headers, json={"planning_defaults": None, "expected_planning_defaults_revision": 1})
    assert cleared.status_code == 200 and cleared.json()["planning_defaults_revision"] == 2
    assert cleared.json()["description"] == row["description"]
    with SessionLocal() as db:
        events = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "treatment", AuditLog.entity_id == str(row["id"])).order_by(AuditLog.id)))
        assert events[-1].before_json["planning_defaults"] == row["planning_defaults"]
        assert events[-1].after_json["planning_defaults"] is None
        assert events[-1].after_json["planning_defaults_revision"] == 2


@pytest.mark.parametrize("level,defaults", [(None, {"drawing_kind": "crown", "material": None}),
    ("root", {"drawing_kind": "crown", "material": None}),
    ("crown", {"drawing_kind": "crown", "material": "resin"}),
    ("surface", {"drawing_kind": "filling", "material": "gold", "unknown": True})])
def test_invalid_defaults_never_saved(api_client, auth_headers, level, defaults):
    response = api_client.post("/treatments", headers=auth_headers,
        json={"name": f"Invalid defaults {uuid4().hex}", "level": level, "planning_defaults": defaults})
    assert response.status_code == 422


def test_suggestions_use_only_owned_keys_and_do_not_backfill(api_client, auth_headers):
    assert suggested_planning_defaults("routine-v1:crown:3", "crown") == {"drawing_kind": "denture", "material": "denture_acrylic"}
    assert suggested_planning_defaults("routine-v1:crown:1", "crown") == {"drawing_kind": "crown", "material": None}
    assert suggested_planning_defaults("routine-v1:root:1", "root") == {"drawing_kind": "other", "material": None}
    assert suggested_planning_defaults("routine-v1:crown:3", "root") is None
    created = api_client.post("/treatments", headers=auth_headers, json={"name": "Bridge unit", "level": "crown"}).json()
    assert created["planning_defaults"] is None and created["suggested_planning_defaults"] is None
    assert api_client.get(f"/treatments/{created['id']}", headers=auth_headers).json()["planning_defaults_revision"] == 0


def test_appliance_picker_filters_profiles_before_count_paging_and_unpriced_visible(api_client, auth_headers):
    pid, quote, _ = prepared(api_client, auth_headers)
    prefix = f"group-filter-{uuid4().hex}"
    with SessionLocal() as db:
        source = db.get(Treatment, quote["id"])
        source.name = f"{prefix} Z matching"
        for index in range(60):
            db.add(Treatment(name=f"{prefix} A irrelevant {index}", level="crown", created_by_user_id=source.created_by_user_id,
                updated_by_user_id=source.updated_by_user_id, planning_defaults={"drawing_kind": "crown", "material": "gold"}, planning_defaults_revision=1))
        unpriced = Treatment(name=f"{prefix} Y unpriced", level="crown", created_by_user_id=source.created_by_user_id,
            updated_by_user_id=source.updated_by_user_id, planning_defaults={"drawing_kind": "bridge", "material": None}, planning_defaults_revision=1)
        db.add(unpriced)
        db.commit()
    path = f"/patients/{pid}/planning/catalogue"
    first = api_client.get(path, headers=auth_headers, params={"q": prefix, "appliance_kind": "bridge", "limit": 1}).json()
    second = api_client.get(path, headers=auth_headers, params={"q": prefix, "appliance_kind": "bridge", "limit": 1, "offset": 1}).json()
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["fee"]["type"] == "UNAVAILABLE"
    assert second["items"][0]["id"] == quote["id"]
    assert api_client.get(path, headers=auth_headers, params={"q": prefix}).json()["total"] == 62
    viewer = _user_with_capabilities(["clinical.view"])
    assert api_client.get(path, headers=viewer, params={"appliance_kind": "bridge"}).status_code == 200
    assert api_client.patch(f"/treatments/{quote['id']}", headers=viewer,
        json={"planning_defaults": None, "expected_planning_defaults_revision": 1}).status_code == 403


def test_new_defaults_do_not_change_saved_item_or_fee(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    item = add(api_client, auth_headers, pid, quote)
    result = api_client.patch(f"/treatments/{quote['id']}", headers=auth_headers,
        json={"level": "surface", "planning_defaults": {"drawing_kind": "filling", "material": "gold"}, "expected_planning_defaults_revision": 0})
    assert result.status_code == 200
    saved = api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["items"][0]
    assert saved == item and saved["material"] is None


def test_populated_defaults_downgrade_refuses_before_ddl(api_client, auth_headers, monkeypatch):
    created = api_client.post("/treatments", headers=auth_headers, json={"name": f"Migration {uuid4().hex}", "level": "root",
        "planning_defaults": {"drawing_kind": "root_canal", "material": None}})
    assert created.status_code == 201
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0062_treatment_planning_defaults.py"
    spec = spec_from_file_location("planning_defaults_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    def no_ddl(*args, **kwargs):
        pytest.fail("Downgrade must refuse before DDL")
    with SessionLocal() as db:
        monkeypatch.setattr(migration.op, "get_bind", lambda: db.connection())
        monkeypatch.setattr(migration.op, "drop_column", no_ddl)
        monkeypatch.setattr(migration.op, "drop_constraint", no_ddl)
        with pytest.raises(RuntimeError, match="planning defaults or their revision history exist"):
            migration.downgrade()
