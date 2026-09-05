"""Synthetic native root observations; no R4 or production access."""

from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.schemas.clinical import RootConditionUpdate, schematic_root_count
from tests.patients.test_tooth_conditions import (
    _action_payload, _counts, _patient, _path, _reset_related_snapshot,
    _seed_reset_related_records, _user_with_capabilities,
)


def root_path(patient_id):
    return f"/patients/{patient_id}/clinical/root-conditions"


def payload(tooth="UR6", root=1, revision=0, dentition="permanent", **observation):
    return {"tooth": tooth, "root": root, "dentition": dentition,
            "expected_revision": revision, **observation}


def audits(patient_id):
    with SessionLocal() as db:
        return [(row.id, row.action, row.before_json, row.after_json) for row in db.scalars(
            select(AuditLog).where(AuditLog.entity_type == "patient",
                AuditLog.entity_id == str(patient_id),
                AuditLog.action.in_(("clinical.tooth_conditions.recorded", "clinical.root_conditions.recorded")))
            .order_by(AuditLog.id))]


@pytest.mark.parametrize("tooth,dentition,count", [
    ("UR6", "permanent", 3), ("UL8", "permanent", 3), ("LR6", "permanent", 2),
    ("LL8", "permanent", 2), ("UR4", "permanent", 2), ("UL4", "permanent", 2),
    ("UR5", "permanent", 1), ("LR4", "permanent", 1), ("UL1", "permanent", 1),
    ("UR4", "deciduous", 3), ("UL5", "deciduous", 3), ("LR4", "deciduous", 2),
    ("LL5", "deciduous", 2), ("UL3", "deciduous", 1),
])
def test_root_schematic_counts_match_supported_dentition(tooth, dentition, count):
    assert schematic_root_count(tooth, dentition) == count
    valid = RootConditionUpdate(**payload(tooth, count, dentition=dentition, apicectomy=True))
    assert valid.root == count
    with pytest.raises(ValueError):
        RootConditionUpdate(**payload(tooth, count + 1, dentition=dentition, apicectomy=True))


def test_root_edits_are_isolated_partial_persistent_and_never_treatment_or_finance(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    whole = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], condition="unrecorded", movement="forward", rotation="clockwise"))
    assert whole.status_code == 200
    _seed_reset_related_records(patient_id, whole.json()["teeth"]["UR6"]["updated_by"]["id"], ["UR6", "LL4"])
    before_related = _reset_related_snapshot(patient_id)
    before_counts = _counts(patient_id)
    first = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revision=1, condition="filled_sound"))
    assert first.status_code == 200
    row = first.json()["teeth"]["UR6"]
    assert row["root_observations"] == {"1": {"condition": "filled_sound", "apicectomy": False}}
    assert (row["condition"], row["movement"], row["rotation"]) == ("unrecorded", "forward", "clockwise")
    second = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(root=2, revision=2, condition="post_core_defective", apicectomy=True))
    assert second.status_code == 200
    apex = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(root=1, revision=3, apicectomy=True))
    assert apex.status_code == 200
    assert apex.json()["teeth"]["UR6"]["root_observations"]["1"] == {"condition": "filled_sound", "apicectomy": True}
    reset = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(root=1, revision=4, condition=None, apicectomy=False))
    assert reset.status_code == 200
    roots = reset.json()["teeth"]["UR6"]["root_observations"]
    assert roots == {"1": {"condition": None, "apicectomy": False},
                     "2": {"condition": "post_core_defective", "apicectomy": True}}
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == reset.json()
    assert _counts(patient_id) == before_counts
    assert _reset_related_snapshot(patient_id) == before_related
    event = audits(patient_id)[-1]
    assert event[1] == "clinical.root_conditions.recorded"
    assert event[2]["teeth"]["UR6"]["root_observations"]["1"]["apicectomy"] is True
    assert event[3]["teeth"]["UR6"]["root_observations"] == roots
    assert event[3]["changed_roots"] == ["1"]


def test_root_validation_rejects_malformed_or_unavailable_roots_without_writes(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    invalid = [payload(), payload(root=True, condition="filled_sound"),
        payload(root="1", condition="filled_sound"), payload(root=0, condition="filled_sound"),
        payload(tooth="UR9", condition="filled_sound"), payload(tooth=12, condition="filled_sound"),
        payload(tooth="UL1", root=2, condition="filled_sound"),
        payload(tooth="LR7", root=3, condition="filled_sound"),
        payload(tooth="UR6", dentition="deciduous", condition="filled_sound"),
        payload(tooth="UR4", dentition="deciduous", condition="filled_sound"),
        payload(condition="healthy"), payload(apicectomy=None), payload(apicectomy="false"),
        payload(apicectomy=1), payload(revision=True, condition="filled_sound"),
        payload(revision=-1, condition="filled_sound"),
        {**payload(condition="filled_sound"), "fee_pence": 2500}]
    before = _counts(patient_id)
    for item in invalid:
        assert api_client.post(root_path(patient_id), headers=auth_headers, json=item).status_code == 422
    assert _counts(patient_id) == before
    assert audits(patient_id) == []
    for condition in ("missing", "implant", "unerupted"):
        patient = _patient(api_client, auth_headers)
        assert api_client.post(_path(patient), headers=auth_headers,
            json=_action_payload(["UR6"], condition=condition)).status_code == 200
        assert api_client.post(root_path(patient), headers=auth_headers,
            json=payload(revision=1, condition="filled_sound")).status_code == 422
        assert api_client.get(_path(patient), headers=auth_headers).json()["teeth"]["UR6"]["root_observations"] == {}


def test_root_dentition_must_match_current_tooth_and_dentition_change_clears_roots(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], condition="deciduous")).status_code == 200
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload("UR4", revision=1, condition="filled_sound")).status_code == 422
    primary = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload("UR4", 3, 1, "deciduous", condition="post_core_sound"))
    assert primary.status_code == 200
    permanent = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 2}, condition="present"))
    assert permanent.status_code == 200
    assert permanent.json()["teeth"]["UR4"]["root_observations"] == {}
    assert audits(patient_id)[-1][2]["teeth"]["UR4"]["root_observations"]["3"]["condition"] == "post_core_sound"
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload("UR4", 3, 3, "deciduous", condition="filled_sound")).status_code == 422
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload("UR4", 2, 3, condition="filled_defective")).status_code == 200
    back_to_primary = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 4}, condition="deciduous"))
    assert back_to_primary.status_code == 200
    assert back_to_primary.json()["teeth"]["UR4"]["root_observations"] == {}


@pytest.mark.parametrize("condition", ["unrecorded", "missing", "implant", "unerupted"])
def test_whole_tooth_reset_or_unavailable_state_clears_roots_with_one_revision(api_client, auth_headers, condition):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], condition="unrecorded")).status_code == 200
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revision=1, condition="filled_defective", apicectomy=True)).status_code == 200
    position = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], {"UR6": 2}, movement="backward"))
    assert position.status_code == 200
    assert position.json()["teeth"]["UR6"]["root_observations"]
    reset = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], {"UR6": 3}, condition=condition))
    assert reset.status_code == 200
    row = reset.json()["teeth"]["UR6"]
    assert row["revision"] == 4
    assert row["root_observations"] == {}
    event = audits(patient_id)[-1]
    assert event[2]["teeth"]["UR6"]["root_observations"]["1"]["condition"] == "filled_defective"
    assert event[3]["teeth"]["UR6"]["root_observations"] == {}
    # A dialog opened before the reset cannot resurrect its root observations.
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revision=3, condition="filled_sound")).status_code == 409


def test_root_requests_are_idempotent_noop_and_cross_endpoint_collision_safe(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    data = payload(condition="filled_sound")
    first = api_client.post(root_path(patient_id), headers=headers, json=data)
    assert first.status_code == 200
    assert api_client.post(root_path(patient_id), headers=headers, json=data).json() == first.json()
    assert len(audits(patient_id)) == 1
    assert api_client.post(root_path(patient_id), headers=headers,
        json=payload(revision=1, condition="filled_defective")).status_code == 409
    assert api_client.post(_path(patient_id), headers=headers,
        json=_action_payload(["UR6"], {"UR6": 1}, condition="unrecorded")).status_code == 409
    noop = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revision=1, condition="filled_sound"))
    assert noop.status_code == 200
    assert noop.json()["teeth"]["UR6"]["revision"] == 1
    assert audits(patient_id)[-1][3]["changed_roots"] == []
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revision=1, apicectomy=True)).status_code == 200
    replay = api_client.post(root_path(patient_id), headers=headers, json=data)
    assert replay.json()["teeth"]["UR6"]["revision"] == 2
    assert replay.json()["teeth"]["UR6"]["root_observations"]["1"]["apicectomy"] is True


def test_root_and_whole_tooth_reset_race_has_one_atomic_winner(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(condition="filled_sound")).status_code == 200

    def root_edit():
        return api_client.post(root_path(patient_id), headers=auth_headers,
            json=payload(revision=1, apicectomy=True))

    def whole_reset():
        return api_client.post(_path(patient_id), headers=auth_headers,
            json=_action_payload(["UR6"], {"UR6": 1}, condition="unrecorded", movement=None, rotation=None))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(root_edit), pool.submit(whole_reset)]
        responses = [future.result() for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == winner.json()
    assert winner.json()["teeth"]["UR6"]["revision"] == 2
    assert len(audits(patient_id)) == 2


def test_root_endpoint_permissions_archived_patients_and_denials_are_side_effect_free(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    data = payload(condition="filled_sound")
    assert api_client.post(root_path(patient_id), json=data).status_code == 401
    for codes in ([], ["clinical.view"], ["clinical.write"]):
        headers = _user_with_capabilities(codes)
        assert api_client.post(root_path(patient_id), headers=headers, json=data).status_code == 403
        assert api_client.post(root_path(2000000000), headers=headers, json=data).status_code == 403
    assert _counts(patient_id)["tooth_conditions"] == 0
    assert audits(patient_id) == []
    assert api_client.post(root_path(patient_id), headers=_user_with_capabilities(["clinical.view", "clinical.write"]), json=data).status_code == 200
    before = audits(patient_id)
    assert api_client.post(f"/patients/{patient_id}/archive", headers=auth_headers).status_code == 200
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revision=1, apicectomy=True)).status_code == 404
    assert audits(patient_id) == before


@pytest.mark.parametrize("observation", [{"condition": "filled_sound"}, {"condition": None, "apicectomy": False}])
def test_root_migration_refuses_loss_of_findings_or_explicit_reset(api_client, auth_headers, monkeypatch, observation):
    patient_id = _patient(api_client, auth_headers)
    response = api_client.post(root_path(patient_id), headers=auth_headers, json=payload(**observation))
    assert response.status_code == 200
    migration_path = Path(__file__).resolve().parents[2] / "alembic/versions/0052_root_observations.py"
    spec = spec_from_file_location("native_root_migration", migration_path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    def forbid_ddl(*_args, **_kwargs):
        pytest.fail("Root downgrade must refuse before attempting DDL")

    with SessionLocal() as db:
        monkeypatch.setattr(migration.op, "get_bind", lambda: db.connection())
        monkeypatch.setattr(migration.op, "drop_constraint", forbid_ddl)
        monkeypatch.setattr(migration.op, "drop_column", forbid_ddl)
        with pytest.raises(RuntimeError, match="native root observations exist"):
            migration.downgrade()
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == response.json()
