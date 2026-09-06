"""Synthetic whole-root-area observations; no R4 or production access."""

from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.clinical import ToothCondition
from app.schemas.clinical import RootConditionUpdate, schematic_root_count
from tests.patients.test_tooth_conditions import (
    _action_payload, _counts, _patient, _path, _reset_related_snapshot,
    _seed_reset_related_records, _user_with_capabilities,
)


def root_path(patient_id):
    return f"/patients/{patient_id}/clinical/root-conditions"


def payload(teeth=None, revisions=None, **observation):
    teeth = ["UR6"] if teeth is None else teeth
    return {"teeth": teeth,
            "expected_revisions": {tooth: 0 for tooth in teeth} if revisions is None else revisions,
            **observation}


def roots(count, condition, apicectomy=False):
    return {str(root): {"condition": condition, "apicectomy": apicectomy}
            for root in range(1, count + 1)}


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


def test_root_batch_schema_canonicalizes_the_same_selection_as_whole_tooth():
    valid = RootConditionUpdate(**payload([" ur6 ", "ll1"], {"UR6": 2, " LL1 ": 0}, apicectomy=True))
    assert valid.teeth == ["LL1", "UR6"]
    assert valid.expected_revisions == {"UR6": 2, "LL1": 0}


def test_root_area_edits_are_partial_persistent_and_never_treatment_or_finance(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    whole = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], condition="unrecorded", movement="forward", rotation="clockwise"))
    assert whole.status_code == 200
    _seed_reset_related_records(patient_id, whole.json()["teeth"]["UR6"]["updated_by"]["id"], ["UR6", "LL4"])
    before_related = _reset_related_snapshot(patient_id)
    before_counts = _counts(patient_id)
    before_audits = audits(patient_id)
    first = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revisions={"UR6": 1}, condition="filled_sound"))
    assert first.status_code == 200
    row = first.json()["teeth"]["UR6"]
    assert row["root_observations"] == roots(3, "filled_sound")
    assert row["revision"] == 2  # one revision for the entire root area
    assert (row["condition"], row["movement"], row["rotation"]) == ("unrecorded", "forward", "clockwise")
    apex = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revisions={"UR6": 2}, apicectomy=True))
    assert apex.status_code == 200
    assert apex.json()["teeth"]["UR6"]["root_observations"] == roots(3, "filled_sound", True)
    reset = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revisions={"UR6": 3}, condition=None, apicectomy=False))
    assert reset.status_code == 200
    assert reset.json()["teeth"]["UR6"]["root_observations"] == roots(3, None)
    assert reset.json()["teeth"]["UR6"]["revision"] == 4
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == reset.json()
    assert _counts(patient_id) == before_counts
    assert _reset_related_snapshot(patient_id) == before_related
    events = audits(patient_id)
    assert events[:len(before_audits)] == before_audits
    event = events[-1]
    assert event[1] == "clinical.root_conditions.recorded"
    assert event[2]["teeth"]["UR6"]["root_observations"] == roots(3, "filled_sound", True)
    assert event[3]["teeth"]["UR6"]["root_observations"] == roots(3, None)
    assert event[3]["changed_teeth"] == ["UR6"]
    assert event[3]["changed_roots"] == {"UR6": ["1", "2", "3"]}


@pytest.mark.parametrize("patch,expected", [
    ({"condition": "post_core_sound"}, {
        "1": {"condition": "post_core_sound", "apicectomy": False},
        "2": {"condition": "post_core_sound", "apicectomy": True},
        "3": {"condition": "post_core_sound", "apicectomy": False}}),
    ({"apicectomy": True}, {
        "1": {"condition": "filled_sound", "apicectomy": True},
        "2": {"condition": "post_core_defective", "apicectomy": True},
        "3": {"condition": None, "apicectomy": True}}),
])
def test_existing_individual_root_maps_preserve_omitted_values(api_client, auth_headers, patch, expected):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(condition="filled_sound")).status_code == 200
    previous = {"1": {"condition": "filled_sound", "apicectomy": False},
                "2": {"condition": "post_core_defective", "apicectomy": True}}
    # Isolated fixture simulating the former individual-root contract. No
    # migration or application code rewrites existing per-root observations.
    with SessionLocal() as db:
        row = db.scalar(select(ToothCondition).where(ToothCondition.patient_id == patient_id))
        row.root_observations = previous
        db.commit()
    before_audits = audits(patient_id)
    response = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revisions={"UR6": 1}, **patch))
    assert response.status_code == 200
    assert response.json()["teeth"]["UR6"]["root_observations"] == expected
    assert response.json()["teeth"]["UR6"]["revision"] == 2
    events = audits(patient_id)
    assert events[:len(before_audits)] == before_audits
    assert events[-1][2]["teeth"]["UR6"]["root_observations"] == previous
    assert events[-1][3]["teeth"]["UR6"]["root_observations"] == expected


def test_root_validation_rejects_malformed_and_old_individual_payload_without_writes(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    all_teeth = [f"{quadrant}{position}" for quadrant in ("UR", "UL", "LR", "LL") for position in range(1, 9)]
    invalid = [payload(), payload([], condition="filled_sound"),
        payload(["UR9"], condition="filled_sound"), payload([12], condition="filled_sound"),
        payload(["UR6", " ur6 "], condition="filled_sound"),
        payload(all_teeth + ["UR6"], condition="filled_sound"),
        payload(revisions={}, condition="filled_sound"),
        payload(revisions={"UR6": 0, "LL1": 0}, condition="filled_sound"),
        payload(revisions={"UR6": 0, " ur6 ": 0}, condition="filled_sound"),
        payload(revisions={"UR6": True}, condition="filled_sound"),
        payload(revisions={"UR6": "0"}, condition="filled_sound"),
        payload(revisions={"UR6": -1}, condition="filled_sound"),
        payload(condition="healthy"), payload(apicectomy=None), payload(apicectomy="false"),
        payload(apicectomy=1), {**payload(condition="filled_sound"), "fee_pence": 2500},
        {**payload(condition="filled_sound"), "root": 1},
        {**payload(condition="filled_sound"), "dentition": "permanent"},
        {"tooth": "UR6", "root": 1, "dentition": "permanent",
         "expected_revision": 0, "condition": "filled_sound"}]
    before = _counts(patient_id)
    for item in invalid:
        assert api_client.post(root_path(patient_id), headers=auth_headers, json=item).status_code == 422
    assert _counts(patient_id) == before
    assert audits(patient_id) == []


def test_root_batch_derives_mixed_primary_and_permanent_root_counts(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], condition="deciduous")).status_code == 200
    response = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL6", "UL1", "UR4"], {"UR6": 0, "LL6": 0, "UL1": 0, "UR4": 1},
                     condition="post_core_defective", apicectomy=True))
    assert response.status_code == 200
    for tooth, count in {"UR6": 3, "LL6": 2, "UL1": 1, "UR4": 3}.items():
        assert response.json()["teeth"][tooth]["root_observations"] == roots(count, "post_core_defective", True)
        assert response.json()["teeth"][tooth]["revision"] == (2 if tooth == "UR4" else 1)
    assert response.json()["teeth"]["UR4"]["condition"] == "deciduous"
    event = audits(patient_id)[-1]
    assert event[3]["changed_teeth"] == ["LL6", "UL1", "UR4", "UR6"]
    assert event[3]["request"]["teeth"] == ["LL6", "UL1", "UR4", "UR6"]


@pytest.mark.parametrize("invalid_condition", ["missing", "implant", "unerupted"])
def test_ineligible_tooth_rejects_entire_batch_without_partial_writes(api_client, auth_headers, invalid_condition):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], condition=invalid_condition)).status_code == 200
    before = api_client.get(_path(patient_id), headers=auth_headers).json()
    before_audits = audits(patient_id)
    before_counts = _counts(patient_id)
    # LL1 sorts first: the later ineligible tooth must still prevent all writes.
    response = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["LL1", "UR6"], {"LL1": 0, "UR6": 1}, condition="filled_sound"))
    assert response.status_code == 422
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == before
    assert audits(patient_id) == before_audits
    assert _counts(patient_id) == before_counts


def test_one_stale_tooth_rejects_entire_root_batch(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(condition="filled_sound")).status_code == 200
    before = api_client.get(_path(patient_id), headers=auth_headers).json()
    before_audits = audits(patient_id)
    response = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["LL1", "UR6"], condition="post_core_defective"))
    assert response.status_code == 409
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == before
    assert audits(patient_id) == before_audits


def test_root_dentition_changes_clear_previous_maps_and_derive_new_counts(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], condition="deciduous")).status_code == 200
    primary = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR4"], {"UR4": 1}, condition="post_core_sound"))
    assert primary.status_code == 200
    assert primary.json()["teeth"]["UR4"]["root_observations"] == roots(3, "post_core_sound")
    permanent = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 2}, condition="present", dentition="permanent"))
    assert permanent.status_code == 200
    assert permanent.json()["teeth"]["UR4"]["root_observations"] == {}
    assert audits(patient_id)[-1][2]["teeth"]["UR4"]["root_observations"] == roots(3, "post_core_sound")
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR4"], {"UR4": 2}, condition="filled_sound")).status_code == 409
    recorded = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR4"], {"UR4": 3}, condition="filled_defective"))
    assert recorded.status_code == 200
    assert recorded.json()["teeth"]["UR4"]["root_observations"] == roots(2, "filled_defective")
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
        json=payload(revisions={"UR6": 1}, condition="filled_defective", apicectomy=True)).status_code == 200
    position = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], {"UR6": 2}, movement="backward"))
    assert position.status_code == 200
    assert position.json()["teeth"]["UR6"]["root_observations"] == roots(3, "filled_defective", True)
    reset = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], {"UR6": 3}, condition=condition))
    assert reset.status_code == 200
    row = reset.json()["teeth"]["UR6"]
    assert row["revision"] == 4
    assert row["root_observations"] == {}
    event = audits(patient_id)[-1]
    assert event[2]["teeth"]["UR6"]["root_observations"] == roots(3, "filled_defective", True)
    assert event[3]["teeth"]["UR6"]["root_observations"] == {}
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revisions={"UR6": 3}, condition="filled_sound")).status_code == 409


def test_root_batch_replay_noop_mixed_changes_and_cross_endpoint_collisions(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    data = payload(["UR6", "LL1"], condition="filled_sound")
    first = api_client.post(root_path(patient_id), headers=headers, json=data)
    assert first.status_code == 200
    assert api_client.post(root_path(patient_id), headers=headers, json=data).json() == first.json()
    assert len(audits(patient_id)) == 1
    assert api_client.post(root_path(patient_id), headers=headers,
        json=payload(revisions={"UR6": 1}, condition="filled_defective")).status_code == 409
    assert api_client.post(_path(patient_id), headers=headers,
        json=_action_payload(["UR6"], {"UR6": 1}, condition="unrecorded")).status_code == 409
    noop = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"], {"UR6": 1, "LL1": 1}, condition="filled_sound"))
    assert noop.status_code == 200
    assert noop.json() == first.json()
    assert audits(patient_id)[-1][3]["changed_teeth"] == []
    assert audits(patient_id)[-1][3]["changed_roots"] == {}
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(revisions={"UR6": 1}, apicectomy=True)).status_code == 200
    mixed = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"], {"UR6": 2, "LL1": 1}, apicectomy=True))
    assert mixed.status_code == 200
    assert mixed.json()["teeth"]["UR6"]["revision"] == 2
    assert mixed.json()["teeth"]["LL1"]["revision"] == 2
    assert audits(patient_id)[-1][3]["changed_teeth"] == ["LL1"]
    replay = api_client.post(root_path(patient_id), headers=headers, json=data)
    assert replay.json() == mixed.json()
    whole_headers = {**auth_headers, "Request-Id": uuid4().hex}
    assert api_client.post(_path(patient_id), headers=whole_headers,
        json=_action_payload(["UR6"], {"UR6": 2}, movement="forward")).status_code == 200
    assert api_client.post(root_path(patient_id), headers=whole_headers,
        json=payload(revisions={"UR6": 3}, apicectomy=False)).status_code == 409


@pytest.mark.parametrize("root_first", [True, False])
def test_identical_null_patch_with_same_request_id_cannot_replay_across_endpoints(api_client, auth_headers, root_first):
    patient_id = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    data = payload(condition=None)
    first_path, other_path = (root_path(patient_id), _path(patient_id)) if root_first else (_path(patient_id), root_path(patient_id))
    first = api_client.post(first_path, headers=headers, json=data)
    assert first.status_code == 200
    before_audits = audits(patient_id)
    collision = api_client.post(other_path, headers=headers, json=data)
    assert collision.status_code == 409
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == first.json()
    assert audits(patient_id) == before_audits
    assert api_client.post(first_path, headers=headers, json=data).json() == first.json()


def test_root_batch_reset_retains_explicit_neutral_entries_and_unselected_teeth(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    first = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL6", "UL1"], condition="filled_defective", apicectomy=True))
    assert first.status_code == 200
    reset = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL6"], {"UR6": 1, "LL6": 1}, condition=None, apicectomy=False))
    assert reset.status_code == 200
    assert reset.json()["teeth"]["UR6"]["root_observations"] == roots(3, None)
    assert reset.json()["teeth"]["LL6"]["root_observations"] == roots(2, None)
    assert reset.json()["teeth"]["UL1"] == first.json()["teeth"]["UL1"]
    assert reset.json()["teeth"]["UR6"]["revision"] == 2
    assert reset.json()["teeth"]["LL6"]["revision"] == 2
    event = audits(patient_id)[-1]
    assert event[2]["teeth"]["UR6"]["root_observations"] == roots(3, "filled_defective", True)
    assert event[2]["teeth"]["LL6"]["root_observations"] == roots(2, "filled_defective", True)
    noop = api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL6"], {"UR6": 2, "LL6": 2}, condition=None, apicectomy=False))
    assert noop.status_code == 200
    assert noop.json() == reset.json()


def test_root_batch_and_whole_tooth_reset_race_has_one_atomic_winner(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(root_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"], condition="filled_sound")).status_code == 200

    def root_edit():
        return api_client.post(root_path(patient_id), headers=auth_headers,
            json=payload(["UR6", "LL1"], {"UR6": 1, "LL1": 1}, apicectomy=True))

    def whole_reset():
        return api_client.post(_path(patient_id), headers=auth_headers,
            json=_action_payload(["UR6", "LL1"], {"UR6": 1, "LL1": 1}, condition="unrecorded", movement=None, rotation=None))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result() for future in [pool.submit(root_edit), pool.submit(whole_reset)]]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == winner.json()
    assert all(row["revision"] == 2 for row in winner.json()["teeth"].values())
    assert len(audits(patient_id)) == 2


def test_root_endpoint_permissions_archived_patients_and_denials_are_side_effect_free(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    data = payload(["UR6", "LL1"], condition="filled_sound")
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
        json=payload(revisions={"UR6": 1}, apicectomy=True)).status_code == 404
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
