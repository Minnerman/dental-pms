"""Synthetic current crown diagnosis; no R4, treatment or billing writes."""

from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.schemas.clinical import CrownConditionUpdate, CrownObservation
from tests.patients.test_root_conditions import payload as root_payload, root_path, roots
from tests.patients.test_tooth_conditions import (
    _action_payload, _counts, _patient, _path, _reset_related_snapshot,
    _seed_reset_related_records, _user_with_capabilities,
)


def crown_path(patient_id):
    return f"/patients/{patient_id}/clinical/crown-conditions"


def payload(teeth=None, revisions=None, kind="gold", issues=None):
    teeth = ["UR6"] if teeth is None else teeth
    return {"teeth": teeth,
            "expected_revisions": {tooth: 0 for tooth in teeth} if revisions is None else revisions,
            "kind": kind, "issues": [] if issues is None else issues}


def audits(patient_id):
    with SessionLocal() as db:
        return [(row.id, row.action, row.before_json, row.after_json) for row in db.scalars(
            select(AuditLog).where(AuditLog.entity_type == "patient",
                AuditLog.entity_id == str(patient_id),
                AuditLog.action.in_(("clinical.tooth_conditions.recorded", "clinical.root_conditions.recorded",
                                    "clinical.crown_conditions.recorded")))
            .order_by(AuditLog.id))]


@pytest.mark.parametrize("kind", ["metal", "gold", "porcelain", "composite"])
def test_crown_materials_accept_unique_canonical_issues(kind):
    value = CrownConditionUpdate(**payload(["ur6", " LL1 "], {"UR6": 0, "ll1": 2}, kind,
        ["poor_fitting", "fractured", "defective", "decayed"]))
    assert value.teeth == ["LL1", "UR6"]
    assert value.expected_revisions == {"UR6": 0, "LL1": 2}
    assert value.issues == ["decayed", "defective", "fractured", "poor_fitting"]


@pytest.mark.parametrize("kind", ["fractured", "missing", None])
def test_nonmaterial_crown_states_are_distinct_and_cannot_have_material_issues(kind):
    assert CrownObservation(kind=kind, issues=[]).model_dump() == {"kind": kind, "issues": []}
    with pytest.raises(ValueError):
        CrownObservation(kind=kind, issues=["fractured"])


def test_crown_batch_persists_independently_with_exact_audit_and_no_finance_effects(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    first = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6", "LL4"], condition="unrecorded", movement="forward", rotation="clockwise"))
    assert first.status_code == 200
    assert all(row["crown_observation"] is None for row in first.json()["teeth"].values())
    actor_id = first.json()["teeth"]["UR6"]["updated_by"]["id"]
    _seed_reset_related_records(patient_id, actor_id, ["UR6", "LL4"])
    root = api_client.post(root_path(patient_id), headers=auth_headers,
        json=root_payload(["UR6", "LL4"], {"UR6": 1, "LL4": 1}, condition="filled_sound", apicectomy=True))
    assert root.status_code == 200
    before_related, before_counts, before_audits = _reset_related_snapshot(patient_id), _counts(patient_id), audits(patient_id)
    crown = api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL4"], {"UR6": 2, "LL4": 2}, "porcelain", ["poor_fitting", "fractured"]))
    assert crown.status_code == 200
    expected = {"kind": "porcelain", "issues": ["fractured", "poor_fitting"]}
    for tooth in ("UR6", "LL4"):
        row = crown.json()["teeth"][tooth]
        assert row["crown_observation"] == expected
        assert row["root_observations"] == root.json()["teeth"][tooth]["root_observations"]
        assert (row["condition"], row["movement"], row["rotation"], row["revision"]) == ("unrecorded", "forward", "clockwise", 3)
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == crown.json()
    assert _counts(patient_id) == before_counts
    assert _reset_related_snapshot(patient_id) == before_related
    events = audits(patient_id)
    assert events[:len(before_audits)] == before_audits
    event = events[-1]
    assert event[1] == "clinical.crown_conditions.recorded"
    assert event[3]["changed_teeth"] == ["LL4", "UR6"]
    for tooth in ("UR6", "LL4"):
        assert event[2]["teeth"][tooth]["crown_observation"] is None
        assert event[3]["teeth"][tooth]["crown_observation"] == expected
        assert event[2]["teeth"][tooth]["root_observations"] == event[3]["teeth"][tooth]["root_observations"]


def test_crown_reset_is_explicit_not_healthy_and_keeps_roots_notes_and_history(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    first = api_client.post(root_path(patient_id), headers=auth_headers,
        json=root_payload(["UR6", "LL1"], condition="post_core_defective", apicectomy=True))
    assert first.status_code == 200
    _seed_reset_related_records(patient_id, first.json()["teeth"]["UR6"]["updated_by"]["id"], ["UR6", "LL1"])
    before_related = _reset_related_snapshot(patient_id)
    first_crown = api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"], {"UR6": 1, "LL1": 1}, "metal", ["decayed"]))
    assert first_crown.status_code == 200
    reset = api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"], {"UR6": 2, "LL1": 2}, None))
    assert reset.status_code == 200
    for tooth in ("UR6", "LL1"):
        row = reset.json()["teeth"][tooth]
        assert row["crown_observation"] == {"kind": None, "issues": []}
        assert row["condition"] is None
        assert row["root_observations"] == first.json()["teeth"][tooth]["root_observations"]
        assert row["revision"] == 3
    assert _reset_related_snapshot(patient_id) == before_related
    assert audits(patient_id)[-1][2]["teeth"]["UR6"]["crown_observation"] == {"kind": "metal", "issues": ["decayed"]}
    with SessionLocal() as db:
        assert db.scalar(text("SELECT count(*) FROM tooth_conditions WHERE patient_id = :patient AND crown_observation IS NOT NULL"),
            {"patient": patient_id}) == 2


@pytest.mark.parametrize("kind,issues", [("missing", []), ("composite", ["fractured"])])
def test_crown_fracture_missing_and_material_fracture_remain_distinct(api_client, auth_headers, kind, issues):
    patient_id = _patient(api_client, auth_headers)
    response = api_client.post(crown_path(patient_id), headers=auth_headers, json=payload(kind=kind, issues=issues))
    assert response.status_code == 200
    row = response.json()["teeth"]["UR6"]
    assert row["crown_observation"] == {"kind": kind, "issues": issues}
    assert row["condition"] is None  # missing crown never means missing tooth
    assert row["root_observations"] == {}


def test_crown_validation_rejects_malformed_partial_and_duplicate_inputs_without_writes(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    invalid = [
        {key: value for key, value in payload().items() if key != "kind"},
        {key: value for key, value in payload().items() if key != "issues"},
        payload([], kind="metal"), payload(["UR9"]), payload(["UR6", " ur6 "]),
        payload([12]), payload(revisions={}), payload(revisions={"UR6": 0, "LL1": 0}),
        payload(revisions={"UR6": 0, " ur6 ": 0}), payload(revisions={"UR6": True}),
        payload(revisions={"UR6": -1}), payload(revisions={"UR6": "0"}),
        payload(kind="healthy"), payload(kind=True), payload(issues=["decayed", "decayed"]),
        payload(issues=["unknown"]), payload(issues=[True]), payload(kind=None, issues=["decayed"]),
        payload(kind="missing", issues=["poor_fitting"]), payload(kind="fractured", issues=["fractured"]),
        {**payload(), "issues": None}, {**payload(), "issues": "decayed"},
        {**payload(), "tooth": "UR6"}, {**payload(), "fee_pence": 5000},
        {**payload(), "condition": "present"},
    ]
    before_counts = _counts(patient_id)
    for item in invalid:
        assert api_client.post(crown_path(patient_id), headers=auth_headers, json=item).status_code == 422
    assert _counts(patient_id) == before_counts
    assert audits(patient_id) == []


def test_crown_batch_includes_native_implants_and_primary_teeth(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], condition="implant")).status_code == 200
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["LL4"], condition="deciduous")).status_code == 200
    response = api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL4", "UL1"], {"UR6": 1, "LL4": 1, "UL1": 0}, "porcelain", ["defective"]))
    assert response.status_code == 200
    assert response.json()["teeth"]["UR6"]["condition"] == "implant"
    assert response.json()["teeth"]["LL4"]["condition"] == "deciduous"
    for tooth in ("UR6", "LL4", "UL1"):
        assert response.json()["teeth"][tooth]["crown_observation"] == {"kind": "porcelain", "issues": ["defective"]}
        assert response.json()["teeth"][tooth]["revision"] == (1 if tooth == "UL1" else 2)


@pytest.mark.parametrize("unavailable", ["missing", "unerupted"])
def test_ineligible_tooth_rejects_entire_crown_batch_before_writes(api_client, auth_headers, unavailable):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], condition=unavailable)).status_code == 200
    before = api_client.get(_path(patient_id), headers=auth_headers).json()
    before_audits, before_counts = audits(patient_id), _counts(patient_id)
    rejected = api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["LL1", "UR6"], {"LL1": 0, "UR6": 1}))
    assert rejected.status_code == 422
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == before
    assert audits(patient_id) == before_audits
    assert _counts(patient_id) == before_counts


def test_one_stale_revision_rejects_entire_crown_batch(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(crown_path(patient_id), headers=auth_headers, json=payload()).status_code == 200
    before = api_client.get(_path(patient_id), headers=auth_headers).json()
    before_audits = audits(patient_id)
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["LL1", "UR6"], kind="porcelain")).status_code == 409
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == before
    assert audits(patient_id) == before_audits


def test_crown_noop_replay_and_partial_batch_changes_preserve_revisions(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    data = payload(["UR6", "LL1"], kind="metal", issues=["poor_fitting", "decayed"])
    first = api_client.post(crown_path(patient_id), headers=headers, json=data)
    assert first.status_code == 200
    canonical_replay = {**data, "teeth": ["ll1", "ur6"], "issues": ["decayed", "poor_fitting"]}
    assert api_client.post(crown_path(patient_id), headers=headers, json=canonical_replay).json() == first.json()
    assert len(audits(patient_id)) == 1
    assert api_client.post(crown_path(patient_id), headers=headers,
        json=payload(["UR6", "LL1"], {"UR6": 1, "LL1": 1}, "gold")).status_code == 409
    noop = api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"], {"UR6": 1, "LL1": 1}, "metal", ["decayed", "poor_fitting"]))
    assert noop.status_code == 200
    assert noop.json() == first.json()
    assert audits(patient_id)[-1][3]["changed_teeth"] == []
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(revisions={"UR6": 1}, kind="gold")).status_code == 200
    mixed = api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"], {"UR6": 2, "LL1": 1}, "gold"))
    assert mixed.status_code == 200
    assert all(row["revision"] == 2 for row in mixed.json()["teeth"].values())
    assert audits(patient_id)[-1][3]["changed_teeth"] == ["LL1"]
    assert api_client.post(crown_path(patient_id), headers=headers, json=data).json() == mixed.json()


@pytest.mark.parametrize("other", ["root", "tooth"])
@pytest.mark.parametrize("crown_first", [True, False])
def test_crown_request_id_collisions_reject_across_all_observation_endpoints(api_client, auth_headers, other, crown_first):
    patient_id = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    other_path = root_path(patient_id) if other == "root" else _path(patient_id)
    other_payload = root_payload(condition=None) if other == "root" else _action_payload(["UR6"], condition=None)
    first_path, first_data, second_path, second_data = (
        (crown_path(patient_id), payload(kind=None), other_path, other_payload) if crown_first
        else (other_path, other_payload, crown_path(patient_id), payload(kind=None)))
    first = api_client.post(first_path, headers=headers, json=first_data)
    assert first.status_code == 200
    before_audits = audits(patient_id)
    assert api_client.post(second_path, headers=headers, json=second_data).status_code == 409
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == first.json()
    assert audits(patient_id) == before_audits


@pytest.mark.parametrize("target", ["unrecorded", "missing", "implant", "unerupted", "deciduous"])
def test_whole_tooth_changes_clear_crown_and_roots_atomically_with_audit(api_client, auth_headers, target):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], condition="unrecorded")).status_code == 200
    root = api_client.post(root_path(patient_id), headers=auth_headers,
        json=root_payload(["UR4"], {"UR4": 1}, condition="filled_sound", apicectomy=True))
    assert root.status_code == 200
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR4"], {"UR4": 2}, "gold")).status_code == 200
    _seed_reset_related_records(patient_id, root.json()["teeth"]["UR4"]["updated_by"]["id"], ["UR4"])
    before_related = _reset_related_snapshot(patient_id)
    reset = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 3}, condition=target))
    assert reset.status_code == 200
    row = reset.json()["teeth"]["UR4"]
    assert (row["revision"], row["root_observations"], row["crown_observation"]) == (4, {}, None)
    event = audits(patient_id)[-1]
    assert event[2]["teeth"]["UR4"]["crown_observation"] == {"kind": "gold", "issues": []}
    assert event[2]["teeth"]["UR4"]["root_observations"] == roots(2, "filled_sound", True)
    assert event[3]["teeth"]["UR4"]["crown_observation"] is None
    assert _reset_related_snapshot(patient_id) == before_related
    with SessionLocal() as db:
        assert db.scalar(text("SELECT crown_observation IS NULL FROM tooth_conditions WHERE patient_id = :patient"),
            {"patient": patient_id}) is True
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR4"], {"UR4": 3}, "metal")).status_code == 409


def test_explicit_crown_reset_and_primary_to_permanent_transition_are_clearable(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], condition="deciduous")).status_code == 200
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR4"], {"UR4": 1}, None)).status_code == 200
    changed = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 2}, condition="present", dentition="permanent"))
    assert changed.status_code == 200
    assert changed.json()["teeth"]["UR4"]["crown_observation"] is None
    assert changed.json()["teeth"]["UR4"]["revision"] == 3
    assert api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 3}, condition="unrecorded")).status_code == 200
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR4"], {"UR4": 4}, None)).status_code == 200
    # Repeating the same whole-tooth reset still clears a non-null crown reset.
    reset = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 5}, condition="unrecorded"))
    assert reset.status_code == 200
    assert reset.json()["teeth"]["UR4"]["revision"] == 6
    assert reset.json()["teeth"]["UR4"]["crown_observation"] is None


def test_root_and_position_updates_preserve_crown_and_share_its_revision(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(kind="porcelain", issues=["defective"])).status_code == 200
    root = api_client.post(root_path(patient_id), headers=auth_headers,
        json=root_payload(revisions={"UR6": 1}, condition="filled_defective"))
    assert root.status_code == 200
    expected = {"kind": "porcelain", "issues": ["defective"]}
    assert root.json()["teeth"]["UR6"]["crown_observation"] == expected
    assert audits(patient_id)[-1][2]["teeth"]["UR6"]["crown_observation"] == expected
    assert audits(patient_id)[-1][3]["teeth"]["UR6"]["crown_observation"] == expected
    position = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR6"], {"UR6": 2}, movement="backward", rotation="anticlockwise"))
    assert position.status_code == 200
    assert position.json()["teeth"]["UR6"]["crown_observation"] == expected
    assert position.json()["teeth"]["UR6"]["root_observations"] == roots(3, "filled_defective")
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(revisions={"UR6": 1}, kind="missing")).status_code == 409


@pytest.mark.parametrize("other", ["root", "tooth"])
def test_crown_and_other_observations_race_has_one_atomic_winner(api_client, auth_headers, other):
    patient_id = _patient(api_client, auth_headers)
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"])).status_code == 200
    revisions = {"UR6": 1, "LL1": 1}

    def crown_edit():
        return api_client.post(crown_path(patient_id), headers=auth_headers,
            json=payload(["UR6", "LL1"], revisions, "composite", ["fractured"]))

    def other_edit():
        if other == "root":
            return api_client.post(root_path(patient_id), headers=auth_headers,
                json=root_payload(["UR6", "LL1"], revisions, condition="post_core_sound"))
        return api_client.post(_path(patient_id), headers=auth_headers,
            json=_action_payload(["UR6", "LL1"], revisions, condition="unrecorded"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result() for future in [pool.submit(crown_edit), pool.submit(other_edit)]]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == winner.json()
    assert all(row["revision"] == 2 for row in winner.json()["teeth"].values())
    assert len(audits(patient_id)) == 2


def test_crown_permissions_archived_patients_and_denials_have_no_side_effects(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    data = payload(["UR6", "LL1"])
    assert api_client.post(crown_path(patient_id), json=data).status_code == 401
    for codes in ([], ["clinical.view"], ["clinical.write"]):
        headers = _user_with_capabilities(codes)
        assert api_client.post(crown_path(patient_id), headers=headers, json=data).status_code == 403
        assert api_client.post(crown_path(2000000000), headers=headers, json=data).status_code == 403
    assert audits(patient_id) == []
    assert _counts(patient_id)["tooth_conditions"] == 0
    allowed = _user_with_capabilities(["clinical.view", "clinical.write"])
    assert api_client.post(crown_path(patient_id), headers=allowed, json=data).status_code == 200
    before, before_audits = api_client.get(_path(patient_id), headers=auth_headers).json(), audits(patient_id)
    assert api_client.post(f"/patients/{patient_id}/archive", headers=auth_headers).status_code == 200
    assert api_client.post(crown_path(patient_id), headers=auth_headers,
        json=payload(["UR6", "LL1"], {"UR6": 1, "LL1": 1}, None)).status_code == 404
    assert audits(patient_id) == before_audits
    assert before["teeth"]["UR6"]["revision"] == 1


@pytest.mark.parametrize("kind", ["metal", None])
def test_crown_migration_refuses_loss_of_findings_or_explicit_reset(api_client, auth_headers, monkeypatch, kind):
    patient_id = _patient(api_client, auth_headers)
    response = api_client.post(crown_path(patient_id), headers=auth_headers, json=payload(kind=kind))
    assert response.status_code == 200
    migration_path = Path(__file__).resolve().parents[2] / "alembic/versions/0053_crown_observation.py"
    spec = spec_from_file_location("native_crown_migration", migration_path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    def forbid_ddl(*_args, **_kwargs):
        pytest.fail("Crown downgrade must refuse before attempting DDL")

    with SessionLocal() as db:
        monkeypatch.setattr(migration.op, "get_bind", lambda: db.connection())
        monkeypatch.setattr(migration.op, "drop_constraint", forbid_ddl)
        monkeypatch.setattr(migration.op, "drop_column", forbid_ddl)
        with pytest.raises(RuntimeError, match="native crown observations exist"):
            migration.downgrade()
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == response.json()
