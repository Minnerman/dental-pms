"""Old optional-field requests retain their original replay identities."""
from copy import deepcopy
from uuid import uuid4

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.treatment_planning import PlanningMutationReceipt
from app.services.native_notes import request_fingerprint
from tests.patients.test_treatment_planning import counts, headers, payload, setup_case, start


def audit_request(pid, key, action):
    with SessionLocal() as db:
        rows = list(db.scalars(select(AuditLog).where(
            AuditLog.entity_type == "patient", AuditLog.entity_id == str(pid),
            AuditLog.request_id == key, AuditLog.action == action,
        )))
        assert len(rows) == 1
        return deepcopy(rows[0].after_json["request"])


def test_omitted_material_keeps_old_create_fingerprint_and_replays_latest_item(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    key = f"old-planning-create-{uuid4().hex}"
    body = payload(quote)
    url = f"/patients/{pid}/planning/items"
    first = api_client.post(url, headers=headers(auth_headers, key), json=body)
    assert first.status_code == 201, first.text
    item = first.json()
    assert item["material"] is None
    # This literal is the pre-material normalized request, including its old
    # nullable fee defaults and canonical surface order; not a new-model dump.
    old_request = {
        "patient_id": pid, "treatment_id": quote["id"], "quote_token": quote["quote_token"],
        "target": {"level": "surface", "tooth": "UR4", "surfaces": ["M", "O", "P"]},
        "drawing_kind": "filling", "fee_mode": "catalogue", "fee_pence": None, "fee_reason": None,
    }
    with SessionLocal() as db:
        receipt = db.scalar(select(PlanningMutationReceipt).where(PlanningMutationReceipt.request_id == key))
        assert receipt.action == "clinical.planning.item.created"
        assert receipt.fingerprint == request_fingerprint(old_request)
        assert receipt.target_id == item["id"]
    updated = api_client.patch(f"{url}/{item['id']}", headers=headers(auth_headers), json={
        "expected_revision": 1, "fee_mode": "override", "fee_pence": 9900,
        "fee_reason": "Synthetic newer fee retained on old replay",
    })
    assert updated.status_code == 200, updated.text
    repeated = api_client.post(url, headers=headers(auth_headers, key), json=body)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json() == updated.json()
    workspace = api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()
    assert [row["id"] for row in workspace["plan"]["items"]] == [item["id"]]
    assert counts(pid) == (0, 0, 0, 0)
    with SessionLocal() as db:
        assert db.scalar(select(func.count(PlanningMutationReceipt.id)).where(PlanningMutationReceipt.request_id == key)) == 1


def test_old_crown_request_omits_projection_token_and_replay_preserves_newer_finding(api_client, auth_headers):
    pid, _ = setup_case(api_client, auth_headers)
    url = f"/patients/{pid}/clinical/crown-conditions"
    key = f"old-crown-{uuid4().hex}"
    body = {"teeth": ["UR4"], "kind": "gold", "issues": [], "expected_revisions": {"UR4": 0}}
    first = api_client.post(url, headers=headers(auth_headers, key), json=body)
    assert first.status_code == 200, first.text
    assert audit_request(pid, key, "clinical.crown_conditions.recorded") == body
    changed = api_client.post(url, headers=headers(auth_headers), json={
        **body, "kind": "porcelain", "expected_revisions": {"UR4": 1},
    })
    assert changed.status_code == 200, changed.text
    repeated = api_client.post(url, headers=headers(auth_headers, key), json=body)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["teeth"] == changed.json()["teeth"]
    assert repeated.json()["teeth"]["UR4"]["crown_observation"]["kind"] == "porcelain"
    assert audit_request(pid, key, "clinical.crown_conditions.recorded") == body
    assert counts(pid) == (0, 0, 0, 0)


def test_old_surface_request_omits_projection_token_and_replay_preserves_newer_surface(api_client, auth_headers):
    pid, _ = setup_case(api_client, auth_headers)
    url = f"/patients/{pid}/clinical/surface-conditions"
    key = f"old-surface-{uuid4().hex}"
    body = {"targets": [{"tooth": "UR4", "surfaces": ["M", "O"]}],
        "observation": {"kind": "restored", "material": "gold", "condition": "sound", "defects": []},
        "expected_revisions": {"UR4": 0}}
    first = api_client.post(url, headers=headers(auth_headers, key), json=body)
    assert first.status_code == 200, first.text
    assert audit_request(pid, key, "clinical.surface_conditions.recorded") == body
    changed = api_client.post(url, headers=headers(auth_headers), json={
        "targets": [{"tooth": "UR4", "surfaces": ["M"]}],
        "observation": {"kind": "restored", "material": "resin", "condition": "sound", "defects": []},
        "expected_revisions": {"UR4": 1},
    })
    assert changed.status_code == 200, changed.text
    repeated = api_client.post(url, headers=headers(auth_headers, key), json=body)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["teeth"] == changed.json()["teeth"]
    surfaces = repeated.json()["teeth"]["UR4"]["surface_observations"]
    assert surfaces["M"]["material"] == "resin" and surfaces["O"]["material"] == "gold"
    assert audit_request(pid, key, "clinical.surface_conditions.recorded") == body
    assert counts(pid) == (0, 0, 0, 0)


def test_old_bridge_reset_replays_after_group_removal_without_resetting_later_crown(api_client, auth_headers):
    pid, _ = setup_case(api_client, auth_headers)
    created = api_client.post(f"/patients/{pid}/clinical/bridges", headers=headers(auth_headers), json={
        "members": [{"tooth": "UR4", "role": "abutment"}, {"tooth": "UR3", "role": "pontic"}],
        "expected_revisions": {"UR4": 0, "UR3": 0},
    })
    assert created.status_code == 200, created.text
    bridge_id = created.json()["bridges"][0]["id"]
    body = {"expected_revisions": {tooth: created.json()["teeth"][tooth]["revision"] for tooth in ["UR4", "UR3"]}}
    url = f"/patients/{pid}/clinical/bridges/{bridge_id}/reset"
    key = f"old-bridge-reset-{uuid4().hex}"
    reset = api_client.post(url, headers=headers(auth_headers, key), json=body)
    assert reset.status_code == 200, reset.text
    assert reset.json()["bridges"] == []
    old_request = {"bridge_id": bridge_id, **body}
    assert audit_request(pid, key, "clinical.bridge.reset") == old_request
    changed = api_client.post(f"/patients/{pid}/clinical/crown-conditions", headers=headers(auth_headers), json={
        "teeth": ["UR4"], "kind": "gold", "issues": [],
        "expected_revisions": {"UR4": reset.json()["teeth"]["UR4"]["revision"]},
    })
    assert changed.status_code == 200, changed.text
    repeated = api_client.post(url, headers=headers(auth_headers, key), json=body)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["bridges"] == []
    assert repeated.json()["teeth"] == changed.json()["teeth"]
    assert repeated.json()["teeth"]["UR4"]["crown_observation"]["kind"] == "gold"
    assert audit_request(pid, key, "clinical.bridge.reset") == old_request
    assert counts(pid) == (0, 0, 0, 0)
