"""Independent native identity: synthetic fixtures only, no preview/R4 access."""

from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.db.session import engine
from tests.patients.test_bridge_conditions import audit_values, bridge_path, chart, payload as bridge_payload
from tests.patients.test_crown_conditions import crown_path, payload as crown_payload
from tests.patients.test_root_conditions import root_path, payload as root_payload, roots
from tests.patients.test_surface_conditions import surface_path, payload as surface_payload, target
from tests.patients.test_tooth_conditions import (
    _action_payload, _counts, _patient, _path, _reset_related_snapshot,
    _seed_reset_related_records, _user_with_capabilities,
)


@pytest.mark.parametrize("condition", ["unerupted", "missing", "impacted", "present", None])
def test_legacy_deciduous_then_status_retains_explicit_identity_after_reload(api_client, auth_headers, condition):
    patient = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    original = _action_payload(["UR2", "LL4"], condition="deciduous")
    first = api_client.post(_path(patient), headers=headers, json=original)
    assert first.status_code == 200
    for row in first.json()["teeth"].values():
        assert row["condition"] == "deciduous" and row["dentition"] == "deciduous"
    _seed_reset_related_records(patient, first.json()["teeth"]["UR2"]["updated_by"]["id"], ["UR2", "LL4"])
    counts, related, old_audits = _counts(patient), _reset_related_snapshot(patient), audit_values(patient)
    changed = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR2", "LL4"], {"UR2": 1, "LL4": 1}, condition=condition))
    assert changed.status_code == 200
    for row in changed.json()["teeth"].values():
        assert (row["condition"], row["dentition"], row["revision"]) == (condition, "deciduous", 2)
    assert chart(api_client, auth_headers, patient) == changed.json()
    assert _counts(patient) == counts and _reset_related_snapshot(patient) == related
    events = audit_values(patient)
    assert events[:-1] == old_audits
    for tooth in ("UR2", "LL4"):
        assert events[-1][2]["teeth"][tooth]["dentition"] == "deciduous"
        assert events[-1][3]["teeth"][tooth]["dentition"] == "deciduous"
    # Old payload replay remains compatible and returns latest state, never the
    # old primary/present shorthand over the new eruption/presence status.
    assert api_client.post(_path(patient), headers=headers, json=original).json() == changed.json()
    assert audit_values(patient) == events


@pytest.mark.parametrize("condition", ["unerupted", "missing", "impacted"])
def test_identity_only_after_status_does_not_replace_the_status(api_client, auth_headers, condition):
    patient = _patient(api_client, auth_headers)
    first = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR2"], condition=condition))
    assert first.status_code == 200 and first.json()["teeth"]["UR2"]["dentition"] is None
    data = _action_payload(["UR2"], {"UR2": 1}, dentition="deciduous")
    changed = api_client.post(_path(patient), headers=auth_headers, json=data)
    assert changed.status_code == 200
    row = changed.json()["teeth"]["UR2"]
    assert (row["condition"], row["dentition"], row["revision"]) == (condition, "deciduous", 2)
    assert chart(api_client, auth_headers, patient) == changed.json()
    assert audit_values(patient)[-1][3]["request"] == data
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR2"], {"UR2": 2}, dentition="deciduous")).json() == changed.json()


def test_identity_only_primary_controls_root_counts_without_inventing_presence(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    teeth = ["UR4", "UL5", "LR4", "LL5", "UR2"]
    first = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(teeth, dentition="deciduous"))
    assert first.status_code == 200
    assert all(row["condition"] is None for row in first.json()["teeth"].values())
    result = api_client.post(root_path(patient), headers=auth_headers,
        json=root_payload(teeth, {tooth: 1 for tooth in teeth}, condition="filled_sound"))
    assert result.status_code == 200
    for tooth, count in {"UR4": 3, "UL5": 3, "LR4": 2, "LL5": 2, "UR2": 1}.items():
        row = result.json()["teeth"][tooth]
        assert row["condition"] is None and row["dentition"] == "deciduous"
        assert row["root_observations"] == roots(count, "filled_sound")
    moved = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(teeth, {tooth: 2 for tooth in teeth}, movement="forward", rotation="clockwise"))
    assert moved.status_code == 200
    for tooth in teeth:
        assert moved.json()["teeth"][tooth]["dentition"] == "deciduous"
        assert moved.json()["teeth"][tooth]["root_observations"] == result.json()["teeth"][tooth]["root_observations"]


def test_status_present_preserves_primary_anatomy_but_identity_change_invalidates_it(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], condition="deciduous")).status_code == 200
    assert api_client.post(root_path(patient), headers=auth_headers,
        json=root_payload(["UR4"], {"UR4": 1}, condition="filled_sound")).status_code == 200
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR4"], {"UR4": 2})).status_code == 200
    first = api_client.post(surface_path(patient), headers=auth_headers,
        json=surface_payload([target("UR4", "O")], {"UR4": 3}))
    assert first.status_code == 200
    before = first.json()["teeth"]["UR4"]
    changed = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 4}, condition="present"))
    assert changed.status_code == 200
    row = changed.json()["teeth"]["UR4"]
    assert row["condition"] == "present" and row["dentition"] == "deciduous"
    for field in ("root_observations", "crown_observation", "surface_observations"):
        assert row[field] == before[field]
    permanent = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 5}, dentition="permanent"))
    assert permanent.status_code == 200
    row = permanent.json()["teeth"]["UR4"]
    assert (row["condition"], row["dentition"], row["revision"]) == ("present", "permanent", 6)
    assert row["root_observations"] == {} and row["surface_observations"] == {} and row["crown_observation"] is None
    event = audit_values(patient)[-1]
    assert event[2]["teeth"]["UR4"]["root_observations"] == roots(3, "filled_sound")
    assert event[2]["teeth"]["UR4"]["surface_observations"] == before["surface_observations"]
    assert event[3]["teeth"]["UR4"]["dentition"] == "permanent"
    roots_changed = api_client.post(root_path(patient), headers=auth_headers,
        json=root_payload(["UR4"], {"UR4": 6}, condition="filled_sound"))
    assert roots_changed.status_code == 200
    assert roots_changed.json()["teeth"]["UR4"]["root_observations"] == roots(2, "filled_sound")


@pytest.mark.parametrize("identity,expected_condition", [("permanent", "present"), (None, None)])
def test_identity_change_normalizes_old_deciduous_shorthand(api_client, auth_headers, identity, expected_condition):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR2"], condition="deciduous")).status_code == 200
    changed = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR2"], {"UR2": 1}, dentition=identity))
    assert changed.status_code == 200
    row = changed.json()["teeth"]["UR2"]
    assert (row["condition"], row["dentition"]) == (expected_condition, identity)


@pytest.mark.parametrize("condition", ["unrecorded", "implant"])
def test_reset_or_implant_clears_identity_to_unspecified_with_all_anatomy(api_client, auth_headers, condition):
    patient = _patient(api_client, auth_headers)
    teeth = ["UR2", "LL4"]
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(teeth, dentition="deciduous", movement="forward", rotation="clockwise")).status_code == 200
    first = api_client.post(surface_path(patient), headers=auth_headers,
        json=surface_payload([target("UR2", "I"), target("LL4", "O")], {tooth: 1 for tooth in teeth}))
    assert first.status_code == 200
    _seed_reset_related_records(patient, first.json()["teeth"]["UR2"]["updated_by"]["id"], teeth)
    counts, related = _counts(patient), _reset_related_snapshot(patient)
    changed = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(teeth, {tooth: 2 for tooth in teeth}, condition=condition, movement=None, rotation=None))
    assert changed.status_code == 200
    for row in changed.json()["teeth"].values():
        assert row["condition"] == condition and row["dentition"] is None
        assert row["root_observations"] == {} and row["surface_observations"] == {} and row["crown_observation"] is None
        assert row["movement"] is None and row["rotation"] is None and row["revision"] == 3
    assert _counts(patient) == counts and _reset_related_snapshot(patient) == related
    assert chart(api_client, auth_headers, patient) == changed.json()


def test_dentition_validation_and_stale_batch_have_no_partial_writes(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    invalid = [_action_payload(["UR6"], dentition="deciduous"),
        _action_payload(["UR2"], dentition="primary"), _action_payload(["UR2"], dentition=True),
        _action_payload(["UR2"], condition="deciduous", dentition="permanent"),
        _action_payload(["UR2"], condition="deciduous", dentition=None),
        _action_payload(["UR2"], condition="implant", dentition="deciduous"),
        _action_payload(["UR2"], condition="implant", dentition="permanent"),
        _action_payload(["UR2"], condition="unrecorded", dentition="deciduous")]
    for data in invalid:
        assert api_client.post(_path(patient), headers=auth_headers, json=data).status_code == 422
    assert chart(api_client, auth_headers, patient)["teeth"] == {} and audit_values(patient) == []
    first = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR2"], condition="implant"))
    assert first.status_code == 200
    old_audits = audit_values(patient)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR2", "LL4"], {"UR2": 1, "LL4": 0}, dentition="deciduous")).status_code == 422
    assert chart(api_client, auth_headers, patient) == first.json() and audit_values(patient) == old_audits
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR2", "LL4"], dentition="permanent")).status_code == 409
    assert chart(api_client, auth_headers, patient) == first.json() and audit_values(patient) == old_audits


def test_bridge_identity_changes_are_rejected_but_identity_noop_preserves_group(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR5"], dentition="deciduous")).status_code == 200
    first = api_client.post(bridge_path(patient), headers=auth_headers,
        json=bridge_payload(revisions={"UR5": 1, "UR4": 0, "UR3": 0}))
    assert first.status_code == 200
    before_audits = audit_values(patient)
    for identity in ("permanent", None):
        assert api_client.post(_path(patient), headers=auth_headers,
            json=_action_payload(["UR5"], {"UR5": 2}, dentition=identity)).status_code == 422
    assert chart(api_client, auth_headers, patient) == first.json() and audit_values(patient) == before_audits
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR5"], {"UR5": 2}, dentition="deciduous")).json() == first.json()


@pytest.mark.parametrize("other", ["root", "crown", "surface"])
def test_dentition_change_races_share_the_same_atomic_revision(api_client, auth_headers, other):
    patient = _patient(api_client, auth_headers)
    teeth = ["UR4", "LL4"]
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(teeth, dentition="deciduous")).status_code == 200
    revisions = {tooth: 1 for tooth in teeth}
    if other == "root":
        other_path, data = root_path(patient), root_payload(teeth, revisions, condition="filled_sound")
    elif other == "crown":
        other_path, data = crown_path(patient), crown_payload(teeth, revisions)
    else:
        other_path, data = surface_path(patient), surface_payload([target(tooth, "O") for tooth in teeth], revisions)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(api_client.post, _path(patient), headers=auth_headers,
                    json=_action_payload(teeth, revisions, dentition="permanent")),
                   pool.submit(api_client.post, other_path, headers=auth_headers, json=data)]
        results = [future.result() for future in futures]
    assert sorted(result.status_code for result in results) == [200, 409]
    winner = next(result for result in results if result.status_code == 200)
    assert chart(api_client, auth_headers, patient) == winner.json()
    assert all(row["revision"] == 2 for row in winner.json()["teeth"].values())
    assert len(audit_values(patient)) == 2


def test_identity_permissions_and_cross_endpoint_replay_protection(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    data = _action_payload(["UR2"], dentition="deciduous")
    for codes in ([], ["clinical.view"], ["clinical.write"]):
        headers = _user_with_capabilities(codes)
        assert api_client.post(_path(patient), headers=headers, json=data).status_code == 403
    assert audit_values(patient) == []
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    first = api_client.post(_path(patient), headers=headers, json=data)
    assert first.status_code == 200
    assert api_client.post(root_path(patient), headers=headers,
        json=root_payload(["UR2"], {"UR2": 1}, condition="filled_sound")).status_code == 409
    assert api_client.post(_path(patient), headers=headers,
        json=_action_payload(["UR2"], {"UR2": 1}, dentition="permanent")).status_code == 409
    assert chart(api_client, auth_headers, patient) == first.json() and len(audit_values(patient)) == 1


def test_dentition_migration_copies_only_explicit_identity_and_guards_independent_data(monkeypatch):
    migration_path = Path(__file__).resolve().parents[2] / "alembic/versions/0056_independent_dentition.py"
    spec = spec_from_file_location("native_dentition_migration", migration_path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    # A connection-local temporary relation shadows the disposable test table.
    # This exercises actual migration SQL without changing other test fixtures,
    # and is removed automatically at transaction end.
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TEMP TABLE tooth_conditions (id integer, tooth text, condition text, revision integer, root_observations jsonb, actor text) ON COMMIT DROP")
        connection.exec_driver_sql("INSERT INTO tooth_conditions VALUES (1, 'UR2', 'deciduous', 7, '{}', 'synthetic-existing'), (2, 'LL4', 'missing', 4, '{}', 'synthetic-existing'), (3, 'UR6', 'present', 8, '{}', 'synthetic-existing'), (4, 'UL1', NULL, 2, '{}', 'synthetic-existing')")
        before = [dict(row) for row in connection.execute(text("SELECT * FROM tooth_conditions ORDER BY id")).mappings()]
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        rows = [dict(row) for row in connection.execute(text("SELECT * FROM tooth_conditions ORDER BY id")).mappings()]
        assert rows == [{**row, "dentition": "deciduous" if row["condition"] == "deciduous" else None} for row in before]
        migration.downgrade()  # old shorthand alone is losslessly representable
        assert [dict(row) for row in connection.execute(text("SELECT * FROM tooth_conditions ORDER BY id")).mappings()] == before
        migration.upgrade()
        connection.exec_driver_sql("UPDATE tooth_conditions SET condition = 'unerupted' WHERE id = 1")
        with pytest.raises(RuntimeError, match="independent native dentition exists"):
            migration.downgrade()
        assert connection.scalar(text("SELECT dentition FROM tooth_conditions WHERE id = 1")) == "deciduous"
        connection.exec_driver_sql("UPDATE tooth_conditions SET condition = 'deciduous' WHERE id = 1")
        connection.exec_driver_sql("UPDATE tooth_conditions SET dentition = 'permanent' WHERE id = 3")
        with pytest.raises(RuntimeError, match="independent native dentition exists"):
            migration.downgrade()
        assert connection.scalar(text("SELECT dentition FROM tooth_conditions WHERE id = 3")) == "permanent"
