"""Explicit synthetic bridge groups and artificial crowns; no R4 access."""

from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.clinical import ToothBridgeGroup, ToothCondition
from app.schemas.clinical import BridgeCreate
from tests.patients.test_crown_conditions import crown_path, payload as crown_payload
from tests.patients.test_root_conditions import root_path, payload as root_payload
from tests.patients.test_tooth_conditions import (
    _action_payload, _counts, _patient, _path, _reset_related_snapshot,
    _seed_reset_related_records, _user_with_capabilities,
)


MEMBERS = [{"tooth": "UR5", "role": "abutment"}, {"tooth": "UR4", "role": "pontic"}, {"tooth": "UR3", "role": "wing"}]


def bridge_path(patient):
    return f"/patients/{patient}/clinical/bridges"


def payload(members=None, revisions=None, **options):
    members = MEMBERS if members is None else members
    return {"members": members, "expected_revisions": {member["tooth"]: 0 for member in members} if revisions is None else revisions, **options}


def chart(client, headers, patient):
    return client.get(_path(patient), headers=headers).json()


def revisions(data, teeth=None):
    return {tooth: row["revision"] for tooth, row in data["teeth"].items() if teeth is None or tooth in teeth}


def audit_values(patient):
    with SessionLocal() as db:
        return [(row.id, row.action, row.before_json, row.after_json) for row in db.scalars(select(AuditLog).where(
            AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient), AuditLog.action.like("clinical.%"))
            .order_by(AuditLog.id))]


def group_count(patient):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(ToothBridgeGroup).where(ToothBridgeGroup.patient_id == patient))


def test_bridge_schema_explicit_canonical_cross_midline_and_cantilever_spans():
    for members, expected in [
        ([{"tooth": "ul1", "role": "pontic"}, {"tooth": " UR1 ", "role": "wing"}], ["UR1", "UL1"]),
        ([{"tooth": "LL2", "role": "pontic"}, {"tooth": "LL1", "role": "abutment"}], ["LL1", "LL2"]),
        ([{"tooth": "LR3", "role": "pontic"}, {"tooth": "LR2", "role": "abutment"}], ["LR3", "LR2"]),
    ]:
        value = BridgeCreate(**payload(members))
        assert [member.tooth for member in value.members] == expected
    invalid = [[], [MEMBERS[0]], MEMBERS + [MEMBERS[0]],
        [{"tooth": "UR5", "role": "abutment"}, {"tooth": "UR3", "role": "pontic"}],
        [{"tooth": "UR1", "role": "abutment"}, {"tooth": "LL1", "role": "pontic"}],
        [{"tooth": "UR1", "role": "abutment"}, {"tooth": "UL1", "role": "wing"}],
        [{"tooth": "UR1", "role": "pontic"}, {"tooth": "UL1", "role": "pontic"}],
        [{"tooth": "UR1", "role": "invented"}, {"tooth": "UL1", "role": "pontic"}],
    ]
    for members in invalid:
        with pytest.raises(ValueError):
            BridgeCreate(**payload(members))
    for extra in [{"crown": None}, {"crown": {"kind": "denture_cocr", "issues": []}},
                  {"crown": {"kind": "fractured", "issues": []}}, {"unexpected": True}]:
        with pytest.raises(ValueError):
            BridgeCreate(**payload(**extra))


def test_bridge_preserves_omitted_crowns_biology_roots_and_history(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], condition="missing")).status_code == 200
    crown = api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR5", "UR3"], kind="porcelain_bonded", issues=["poor_fitting"]))
    assert crown.status_code == 200
    assert api_client.post(root_path(patient), headers=auth_headers,
        json=root_payload(["UR5"], {"UR5": 1}, condition="filled_sound")).status_code == 200
    _seed_reset_related_records(patient, crown.json()["teeth"]["UR5"]["updated_by"]["id"], ["UR5", "UR4", "UR3"])
    before, related, counts, old_audits = chart(api_client, auth_headers, patient), _reset_related_snapshot(patient), _counts(patient), audit_values(patient)
    response = api_client.post(bridge_path(patient), headers=auth_headers,
        json=payload(revisions=revisions(before)))
    assert response.status_code == 200
    result = response.json()
    group = result["bridges"][0]
    assert group == {"id": group["id"], "arch": "upper", "span_start": "UR5", "span_end": "UR3", "members": MEMBERS}
    for member in MEMBERS:
        tooth = member["tooth"]
        row, previous = result["teeth"][tooth], before["teeth"][tooth]
        assert row["bridge_group_id"] == group["id"] and row["bridge_role"] == member["role"]
        assert row["revision"] == previous["revision"] + 1
        for field in ("condition", "root_observations", "crown_observation", "movement", "rotation"):
            assert row[field] == previous[field]
    assert _counts(patient) == counts and _reset_related_snapshot(patient) == related
    assert audit_values(patient)[:len(old_audits)] == old_audits
    event = audit_values(patient)[-1]
    assert event[1] == "clinical.bridge.created" and event[2]["bridge"] is None
    assert event[3]["bridge"] == group
    assert all(value["bridge_group_id"] is None for value in event[2]["teeth"].values())


def test_bridge_material_replacement_and_complete_reset_are_audited_and_preserve_other_data(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    initial = api_client.post(bridge_path(patient), headers=auth_headers,
        json=payload(crown={"kind": "porcelain_bonded", "issues": ["defective"]}))
    assert initial.status_code == 200
    first = initial.json()
    group_id = first["bridges"][0]["id"]
    assert all(row["crown_observation"] == {"kind": "porcelain_bonded", "issues": ["defective"]} for row in first["teeth"].values())
    _seed_reset_related_records(patient, first["teeth"]["UR5"]["updated_by"]["id"], ["UR5", "UR4"])
    root = api_client.post(root_path(patient), headers=auth_headers,
        json=root_payload(["UR5"], {"UR5": 1}, condition="filled_defective", apicectomy=True))
    assert root.status_code == 200
    before, related, counts = chart(api_client, auth_headers, patient), _reset_related_snapshot(patient), _counts(patient)
    path = f"{bridge_path(patient)}/{group_id}/reset"
    assert api_client.post(path, headers=auth_headers, json={"expected_revisions": {"UR5": 2, "UR4": 1}}).status_code == 422
    assert api_client.post(path, headers=auth_headers, json={"expected_revisions": revisions(first)}).status_code == 409
    assert chart(api_client, auth_headers, patient) == before
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    reset = api_client.post(path, headers=headers, json={"expected_revisions": revisions(before)})
    assert reset.status_code == 200
    result = reset.json()
    assert result["bridges"] == [] and group_count(patient) == 0
    for tooth, row in result["teeth"].items():
        assert row["bridge_group_id"] is None and row["bridge_role"] is None
        assert row["crown_observation"] == {"kind": None, "issues": []}
        assert row["revision"] == before["teeth"][tooth]["revision"] + 1
        assert row["condition"] == before["teeth"][tooth]["condition"]
        assert row["root_observations"] == before["teeth"][tooth]["root_observations"]
    assert _counts(patient) == counts and _reset_related_snapshot(patient) == related
    event = audit_values(patient)[-1]
    assert event[2]["bridge"] == first["bridges"][0] and event[3]["bridge"] is None
    assert api_client.post(path, headers=headers, json={"expected_revisions": revisions(before)}).json() == result
    assert api_client.post(f"{bridge_path(patient)}/{group_id + 1000}/reset", headers=headers,
        json={"expected_revisions": revisions(before)}).status_code == 409


def test_bridge_member_edits_keep_identity_and_reject_partial_dismantling(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], condition="missing")).status_code == 200
    created = api_client.post(bridge_path(patient), headers=auth_headers,
        json=payload(revisions={"UR5": 0, "UR4": 1, "UR3": 0}))
    assert created.status_code == 200
    group = created.json()["bridges"][0]
    material = api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR4"], {"UR4": 2}, "gold", ["fractured"]))
    assert material.status_code == 200 and material.json()["bridges"] == [group]
    for kind in (None, "missing", "denture_cocr", "denture_acrylic"):
        assert api_client.post(crown_path(patient), headers=auth_headers,
            json=crown_payload(["UR4"], {"UR4": 3}, kind)).status_code == 422
    for condition in ("unrecorded", "missing", "present", "implant", "deciduous"):
        assert api_client.post(_path(patient), headers=auth_headers,
            json=_action_payload(["UR5"], {"UR5": 1}, condition=condition)).status_code == 422
    assert api_client.post(root_path(patient), headers=auth_headers,
        json=root_payload(["UR4"], {"UR4": 3}, condition=None, apicectomy=False)).status_code == 422
    # A genuinely unchanged condition is allowed and does not unlink members.
    noop = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR5"], {"UR5": 1}, condition=None))
    assert noop.status_code == 200 and noop.json()["teeth"]["UR5"]["revision"] == 1
    position = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR5"], {"UR5": 1}, movement="forward", rotation="clockwise"))
    assert position.status_code == 200 and position.json()["bridges"] == [group]
    assert position.json()["teeth"]["UR4"]["crown_observation"] == {"kind": "gold", "issues": ["fractured"]}


@pytest.mark.parametrize("condition", ["present", "deciduous", "impacted", "implant", "unerupted"])
def test_pontic_rejects_explicit_biological_teeth_without_partial_writes(api_client, auth_headers, condition):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], condition=condition)).status_code == 200
    before, old_audits = chart(api_client, auth_headers, patient), audit_values(patient)
    assert api_client.post(bridge_path(patient), headers=auth_headers,
        json=payload(revisions={"UR5": 0, "UR4": 1, "UR3": 0})).status_code == 422
    assert chart(api_client, auth_headers, patient) == before
    assert audit_values(patient) == old_audits and group_count(patient) == 0


@pytest.mark.parametrize("role,condition,expected", [("abutment", "missing", 422), ("wing", "unerupted", 422),
    ("wing", "implant", 422), ("abutment", "implant", 200)])
def test_bridge_support_eligibility(api_client, auth_headers, role, condition, expected):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR5"], condition=condition)).status_code == 200
    members = [{"tooth": "UR5", "role": role}, {"tooth": "UR4", "role": "pontic"}]
    response = api_client.post(bridge_path(patient), headers=auth_headers,
        json=payload(members, {"UR5": 1, "UR4": 0}))
    assert response.status_code == expected
    assert group_count(patient) == (1 if expected == 200 else 0)


@pytest.mark.parametrize("root_patch,allowed", [({"condition": None, "apicectomy": False}, True),
    ({"condition": "filled_sound"}, False), ({"apicectomy": True}, False)])
def test_artificial_pontic_and_denture_require_no_meaningful_roots(api_client, auth_headers, root_patch, allowed):
    for denture in (False, True):
        patient = _patient(api_client, auth_headers)
        assert api_client.post(root_path(patient), headers=auth_headers,
            json=root_payload(["UR4"], **root_patch)).status_code == 200
        before = chart(api_client, auth_headers, patient)
        response = (api_client.post(crown_path(patient), headers=auth_headers,
            json=crown_payload(["UR4"], {"UR4": 1}, "denture_cocr")) if denture else
            api_client.post(bridge_path(patient), headers=auth_headers,
                json=payload(revisions={"UR5": 0, "UR4": 1, "UR3": 0})))
        assert response.status_code == (200 if allowed else 422)
        assert chart(api_client, auth_headers, patient)["teeth"]["UR4"]["root_observations"] == before["teeth"]["UR4"]["root_observations"]
        if not allowed:
            assert chart(api_client, auth_headers, patient) == before


@pytest.mark.parametrize("kind", ["denture_cocr", "denture_acrylic"])
def test_denture_missing_tooth_reset_and_new_material_roundtrip(api_client, auth_headers, kind):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], condition="missing")).status_code == 200
    response = api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR4"], {"UR4": 1}, kind))
    assert response.status_code == 200
    assert response.json()["teeth"]["UR4"]["condition"] == "missing"
    assert response.json()["teeth"]["UR4"]["crown_observation"] == {"kind": kind, "issues": []}
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR4"], {"UR4": 2}, "metal")).status_code == 422
    assert api_client.post(root_path(patient), headers=auth_headers,
        json=root_payload(["UR4"], {"UR4": 2}, condition="filled_sound")).status_code == 422
    reset = api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR4"], {"UR4": 2}, None))
    assert reset.status_code == 200 and reset.json()["teeth"]["UR4"]["condition"] == "missing"
    assert reset.json()["teeth"]["UR4"]["crown_observation"] == {"kind": None, "issues": []}
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["LL1"], kind="porcelain_bonded", issues=["decayed"])).status_code == 200


@pytest.mark.parametrize("condition", ["present", "deciduous", "impacted", "implant", "unerupted"])
def test_denture_rejects_natural_or_implant_biology(api_client, auth_headers, condition):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], condition=condition)).status_code == 200
    before = chart(api_client, auth_headers, patient)
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR4"], {"UR4": 1}, "denture_acrylic")).status_code == 422
    assert chart(api_client, auth_headers, patient) == before


def test_existing_denture_requires_explicit_replacement_and_no_contradictory_biology(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR5"], kind="denture_acrylic")).status_code == 200
    before = chart(api_client, auth_headers, patient)
    for condition in ("present", "impacted"):
        assert api_client.post(_path(patient), headers=auth_headers,
            json=_action_payload(["UR5"], {"UR5": 1}, condition=condition)).status_code == 422
    assert api_client.post(bridge_path(patient), headers=auth_headers,
        json=payload(revisions={"UR5": 1, "UR4": 0, "UR3": 0})).status_code == 422
    assert chart(api_client, auth_headers, patient) == before
    replaced = api_client.post(bridge_path(patient), headers=auth_headers,
        json=payload(revisions={"UR5": 1, "UR4": 0, "UR3": 0}, crown={"kind": "metal", "issues": []}))
    assert replaced.status_code == 200
    assert replaced.json()["teeth"]["UR5"]["condition"] is None
    assert replaced.json()["teeth"]["UR5"]["crown_observation"] == {"kind": "metal", "issues": []}


def test_retired_standalone_fracture_is_readable_but_not_authorable(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    first = api_client.post(crown_path(patient), headers=auth_headers, json=crown_payload(kind="metal"))
    assert first.status_code == 200
    with SessionLocal() as db:
        row = db.scalar(select(ToothCondition).where(ToothCondition.patient_id == patient))
        row.crown_observation = {"kind": "fractured", "issues": []}  # prior-version synthetic record
        db.commit()
    before = chart(api_client, auth_headers, patient)
    assert before["teeth"]["UR6"]["crown_observation"] == {"kind": "fractured", "issues": []}
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(revisions={"UR6": 1}, kind="fractured")).status_code == 422
    assert chart(api_client, auth_headers, patient) == before
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(revisions={"UR6": 1}, kind="porcelain_bonded", issues=["fractured"])).status_code == 200


def test_bridge_overlap_stale_replay_and_cross_endpoint_collisions_are_atomic(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    data = payload()
    first = api_client.post(bridge_path(patient), headers=headers, json=data)
    assert first.status_code == 200
    assert api_client.post(bridge_path(patient), headers=headers, json=payload(list(reversed(MEMBERS)))).json() == first.json()
    assert group_count(patient) == 1
    before_audits = audit_values(patient)
    assert api_client.post(bridge_path(patient), headers=auth_headers, json=data).status_code == 409
    overlap = [{"tooth": "UR3", "role": "abutment"}, {"tooth": "UR2", "role": "pontic"}]
    assert api_client.post(bridge_path(patient), headers=auth_headers,
        json=payload(overlap, {"UR3": 1, "UR2": 0})).status_code == 409
    assert api_client.post(crown_path(patient), headers=headers,
        json=crown_payload(["UR5"], {"UR5": 1}, "gold")).status_code == 409
    assert chart(api_client, auth_headers, patient) == first.json() and audit_values(patient) == before_audits
    reset_path = f"{bridge_path(patient)}/{first.json()['bridges'][0]['id']}/reset"
    assert api_client.post(reset_path, headers=headers, json={"expected_revisions": revisions(first.json())}).status_code == 409
    reset = api_client.post(reset_path, headers=auth_headers, json={"expected_revisions": revisions(first.json())})
    assert reset.status_code == 200
    assert api_client.post(bridge_path(patient), headers=headers, json=data).json() == reset.json()


def test_bridge_creation_race_has_one_atomic_winner(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(api_client.post, bridge_path(patient), headers={**auth_headers, "Request-Id": uuid4().hex},
                              json=payload()) for _ in range(2)]
        responses = [future.result() for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert group_count(patient) == 1
    assert chart(api_client, auth_headers, patient) == next(response.json() for response in responses if response.status_code == 200)


def test_bridge_permissions_patient_boundaries_and_database_identity_constraints(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(bridge_path(patient), json=payload()).status_code == 401
    for codes in ([], ["clinical.view"], ["clinical.write"]):
        headers = _user_with_capabilities(codes)
        assert api_client.post(bridge_path(patient), headers=headers, json=payload()).status_code == 403
        assert api_client.post(f"{bridge_path(patient)}/1/reset", headers=headers,
            json={"expected_revisions": {"UR5": 0, "UR4": 0, "UR3": 0}}).status_code == 403
    assert group_count(patient) == 0 and audit_values(patient) == []
    allowed = _user_with_capabilities(["clinical.view", "clinical.write"])
    response = api_client.post(bridge_path(patient), headers=allowed, json=payload())
    assert response.status_code == 200
    group_id = response.json()["bridges"][0]["id"]
    other = _patient(api_client, auth_headers)
    assert api_client.post(f"{bridge_path(other)}/{group_id}/reset", headers=auth_headers,
        json={"expected_revisions": revisions(response.json())}).status_code == 404
    row = api_client.post(crown_path(other), headers=auth_headers, json=crown_payload())
    assert row.status_code == 200
    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE tooth_conditions SET bridge_group_id=:group_id, bridge_role='abutment' WHERE patient_id=:patient"),
                {"group_id": group_id, "patient": other})
            db.commit()
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE tooth_conditions SET bridge_role='wing' WHERE patient_id=:patient"), {"patient": other})
            db.commit()
        db.rollback()
    assert api_client.post(f"/patients/{patient}/archive", headers=auth_headers).status_code == 200
    assert api_client.post(f"{bridge_path(patient)}/{group_id}/reset", headers=allowed,
        json={"expected_revisions": revisions(response.json())}).status_code == 404


@pytest.mark.parametrize("record", ["bridge", "porcelain_bonded", "denture_cocr", "denture_acrylic"])
def test_bridge_migration_refuses_groups_and_extended_crown_data(api_client, auth_headers, monkeypatch, record):
    patient = _patient(api_client, auth_headers)
    response = (api_client.post(bridge_path(patient), headers=auth_headers, json=payload()) if record == "bridge" else
                api_client.post(crown_path(patient), headers=auth_headers, json=crown_payload(kind=record)))
    assert response.status_code == 200
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0054_tooth_bridge_groups.py"
    spec = spec_from_file_location("bridge_migration", path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    def forbid_ddl(*_args, **_kwargs):
        pytest.fail("Downgrade must refuse before DDL")

    with SessionLocal() as db:
        monkeypatch.setattr(migration.op, "get_bind", lambda: db.connection())
        monkeypatch.setattr(migration.op, "drop_constraint", forbid_ddl)
        with pytest.raises(RuntimeError, match="native bridge groups or extended crown observations exist"):
            migration.downgrade()
    assert chart(api_client, auth_headers, patient) == response.json()
