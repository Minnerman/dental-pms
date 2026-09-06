"""Synthetic current surface findings, independent from treatment and finance."""

from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.clinical import ToothCondition
from app.schemas.clinical import SurfaceConditionUpdate, SurfaceObservation, ToothNoteCreate
from tests.patients.test_bridge_conditions import (
    audit_values, bridge_path, chart, group_count, payload as bridge_payload,
)
from tests.patients.test_crown_conditions import crown_path, payload as crown_payload
from tests.patients.test_root_conditions import root_path, payload as root_payload
from tests.patients.test_tooth_conditions import (
    _action_payload, _counts, _patient, _path, _reset_related_snapshot,
    _seed_reset_related_records, _user_with_capabilities,
)


MATERIALS = ["amalgam", "precious_metal", "carbon_fibre", "gold", "glass_ionomer",
             "cast_metal_alloy", "metallic", "porcelain", "resin", "stainless_steel",
             "unknown", "vmk", "combination"]
DEFECTS = ["open_contact", "cracked", "broken", "faceted", "overhang", "over_contour",
           "under_contour", "cosmetic", "leaking"]
CONDITIONS = [None, "sound", "carious_early", "carious_arrested", "carious_established", "defective"]


def surface_path(patient):
    return f"/patients/{patient}/clinical/surface-conditions"


def observation(kind="restored", material="amalgam", condition="sound", defects=None):
    return {"kind": kind, "material": material, "condition": condition,
            "defects": [] if defects is None else defects}


def neutral():
    return observation(None, None, None)


def payload(targets=None, revisions=None, value=None):
    targets = [{"tooth": "UR6", "surfaces": ["M", "O", "D"]}] if targets is None else targets
    return {"targets": targets, "observation": observation() if value is None else value,
            "expected_revisions": {target["tooth"]: 0 for target in targets} if revisions is None else revisions}


def target(tooth, *surfaces):
    return {"tooth": tooth, "surfaces": list(surfaces)}


@pytest.mark.parametrize("material", MATERIALS)
def test_surface_catalogue_preserves_each_explicit_material(material):
    for condition in CONDITIONS:
        value = observation(material=material, condition=condition,
            defects=list(reversed(DEFECTS)) if condition == "defective" else [])
        parsed = SurfaceObservation(**value)
        assert parsed.material == material and parsed.condition == condition
        assert parsed.defects == (sorted(DEFECTS) if condition == "defective" else [])


def test_surface_observation_categories_keep_unspecified_separate_from_sound():
    accepted = [neutral(), observation("defective", None, "defective"),
                observation("defective", None, "defective", ["broken", "open_contact"])]
    accepted += [observation("carious", None, condition) for condition in [None, *CONDITIONS[2:5]]]
    accepted += [observation("sealant", None, condition,
                    ["leaking"] if condition == "defective" else []) for condition in CONDITIONS]
    for value in accepted:
        assert SurfaceObservation(**value).model_dump() == value
    invalid = [observation(None, "unknown", None), observation(None, None, "sound"),
               observation("restored", None, None), observation("carious", None, "sound"),
               observation("carious", None, "defective"), observation("carious", "resin", None),
               observation("defective", None, None), observation("defective", "resin", "defective"),
               observation("sealant", "resin", None), observation(condition="sound", defects=["broken"]),
               observation(condition=None, defects=["broken"]), observation(condition="unknown"),
               observation(defects=["invented"]), observation(defects="broken"), observation(defects=[True]),
               observation(condition="defective", defects=["broken", "broken"]),
               observation(material="composite"), observation(kind="healthy"), observation(kind=True)]
    invalid += [{key: value for key, value in neutral().items() if key != field} for field in neutral()]
    for value in invalid:
        with pytest.raises(ValueError):
            SurfaceObservation(**value)


def test_surface_targets_canonicalize_without_changing_legacy_note_surfaces():
    value = SurfaceConditionUpdate(**payload(
        [target(" ur6 ", " p ", "d", "o", "m", "b"), target("ll1", "l", "i")],
        {"ur6": 2, " LL1 ": 0}))
    assert [item.model_dump() for item in value.targets] == [target("LL1", "I", "L"), target("UR6", "M", "O", "D", "B", "P")]
    assert value.expected_revisions == {"UR6": 2, "LL1": 0}
    # Existing historical/procedure L notation remains accepted for upper teeth.
    assert ToothNoteCreate(tooth="UR6", surface="L", note="Synthetic").surface == "L"
    with pytest.raises(ValueError):
        ToothNoteCreate(tooth="UR6", surface="P", note="Synthetic")


def test_surface_malformed_payloads_reject_without_any_writes(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    invalid = [payload([]), payload([target("UR9", "O")]), payload([target("UR6")]),
        payload([target("UR6", "O"), target(" ur6 ", "M")]),
        payload([target("UR6", "M", "m")]), payload([target("UR6", "I")]),
        payload([target("UL1", "O")]), payload([target("UR6", "L")]),
        payload([target("LR6", "P")]), payload([target("UR6", "Q")]),
        payload([target("UR6", "M", "O", "I", "D", "B", "P")]),
        payload([target("UR6", "MOD")]), payload([target("UR6", True)]),
        payload([{"tooth": "UR6", "surfaces": "MOD"}]), payload([target(None, "O")]),
        payload([target(6, "O")]), payload(revisions={}), payload(revisions={"UR6": True}),
        payload(revisions={"UR6": -1}), payload(revisions={"UR6": "0"}),
        payload(revisions={"UR6": 0, " UR6 ": 0}), payload(revisions={"UR6": 0, "LL1": 0}),
        {**payload(), "fee_pence": 100}, {**payload(), "observation": None},
        payload([{**target("UR6", "O"), "dentition": "permanent"}]),
        payload(value={**observation(), "extra": "unsupported"}),
    ]
    invalid += [{key: value for key, value in payload().items() if key != field} for field in payload()]
    invalid += [payload(value={key: value for key, value in observation().items() if key != field}) for field in observation()]
    before, counts = chart(api_client, auth_headers, patient), _counts(patient)
    for data in invalid:
        assert api_client.post(surface_path(patient), headers=auth_headers, json=data).status_code == 422
    assert chart(api_client, auth_headers, patient) == before
    assert _counts(patient) == counts and audit_values(patient) == []


def test_surface_batch_is_independent_and_audited_without_treatment_or_finance_effects(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    teeth = ["UR6", "LL1"]
    first = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(teeth, condition="unrecorded", movement="forward", rotation="clockwise"))
    assert first.status_code == 200
    assert all(row["surface_observations"] == {} for row in first.json()["teeth"].values())
    _seed_reset_related_records(patient, first.json()["teeth"]["UR6"]["updated_by"]["id"], teeth)
    assert api_client.post(root_path(patient), headers=auth_headers,
        json=root_payload(teeth, {tooth: 1 for tooth in teeth}, condition="filled_sound", apicectomy=True)).status_code == 200
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(teeth, {tooth: 2 for tooth in teeth}, "porcelain")).status_code == 200
    before = chart(api_client, auth_headers, patient)
    related, counts, previous_audits = _reset_related_snapshot(patient), _counts(patient), audit_values(patient)
    selected = [target("UR6", "D", "M", "O"), target("LL1", "I", "L")]
    data = payload(selected, {tooth: 3 for tooth in teeth}, observation(condition="defective", defects=["leaking", "broken"]))
    result = api_client.post(surface_path(patient), headers=auth_headers, json=data)
    assert result.status_code == 200
    value = {**data["observation"], "defects": ["broken", "leaking"]}
    for item in selected:
        row = result.json()["teeth"][item["tooth"]]
        assert row["surface_observations"] == {key: value for key in item["surfaces"]}
        assert row["revision"] == 4
        for field in ("condition", "root_observations", "crown_observation", "movement", "rotation", "bridge_group_id", "bridge_role"):
            assert row[field] == before["teeth"][item["tooth"]][field]
    assert _counts(patient) == counts and _reset_related_snapshot(patient) == related
    assert chart(api_client, auth_headers, patient) == result.json()
    events = audit_values(patient)
    assert events[:-1] == previous_audits
    event = events[-1]
    assert event[1] == "clinical.surface_conditions.recorded"
    assert event[3]["changed_teeth"] == ["LL1", "UR6"]
    assert event[3]["changed_surfaces"] == {"LL1": ["I", "L"], "UR6": ["M", "O", "D"]}
    for tooth in teeth:
        assert event[2]["teeth"][tooth]["surface_observations"] == {}
        assert event[3]["teeth"][tooth]["surface_observations"] == result.json()["teeth"][tooth]["surface_observations"]


def test_surface_all_32_positions_and_primary_molars_use_explicit_valid_keys(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    primary = ["UR4", "LL5"]
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(primary, condition="deciduous")).status_code == 200
    selected = [target(f"{quadrant}{n}", "M", "I" if n <= 3 else "O", "D", "B", "P" if quadrant[0] == "U" else "L")
                for quadrant in ("UR", "UL", "LR", "LL") for n in range(1, 9)]
    result = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload(selected, {item["tooth"]: 1 if item["tooth"] in primary else 0 for item in selected}))
    assert result.status_code == 200
    assert len(result.json()["teeth"]) == 32
    for item in selected:
        row = result.json()["teeth"][item["tooth"]]
        assert set(row["surface_observations"]) == set(item["surfaces"])
        assert row["condition"] == ("deciduous" if item["tooth"] in primary else None)


def test_surface_reset_preserves_unselected_surfaces_and_explicit_unknown(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    first = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR6", "M", "O", "D"), target("LL1", "I")], value=observation(material="unknown", condition=None)))
    assert first.status_code == 200
    reset = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR6", "O", "P")], {"UR6": 1}, neutral()))
    assert reset.status_code == 200
    result = reset.json()
    expected = {**first.json()["teeth"]["UR6"]["surface_observations"], "O": neutral(), "P": neutral()}
    assert result["teeth"]["UR6"]["surface_observations"] == expected
    assert result["teeth"]["LL1"] == first.json()["teeth"]["LL1"]
    assert result["teeth"]["UR6"]["condition"] is None
    event = audit_values(patient)[-1]
    assert event[2]["teeth"]["UR6"]["surface_observations"] == first.json()["teeth"]["UR6"]["surface_observations"]
    assert event[3]["changed_surfaces"] == {"UR6": ["O", "P"]}


def test_surface_noop_replay_and_mixed_batch_changes_preserve_revisions(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    data = payload([target("UR6", "D", "M"), target("LL1", "I")])
    first = api_client.post(surface_path(patient), headers=headers, json=data)
    assert first.status_code == 200
    canonical = {**data, "targets": [target("ll1", "i"), target("ur6", "m", "d")]}
    assert api_client.post(surface_path(patient), headers=headers, json=canonical).json() == first.json()
    assert len(audit_values(patient)) == 1
    noop_data = {**data, "expected_revisions": {"UR6": 1, "LL1": 1}}
    assert api_client.post(surface_path(patient), headers=auth_headers, json=noop_data).json() == first.json()
    assert audit_values(patient)[-1][3]["changed_surfaces"] == {}
    assert api_client.post(surface_path(patient), headers=headers, json=noop_data).status_code == 409
    mixed_data = payload([target("UR6", "M", "D", "O"), target("LL1", "I")], {"UR6": 1, "LL1": 1})
    changed = api_client.post(surface_path(patient), headers=auth_headers, json=mixed_data)
    assert changed.status_code == 200
    assert changed.json()["teeth"]["UR6"]["revision"] == 2
    assert changed.json()["teeth"]["LL1"] == first.json()["teeth"]["LL1"]
    assert audit_values(patient)[-1][3]["changed_surfaces"] == {"UR6": ["O"]}
    assert api_client.post(surface_path(patient), headers=headers, json=data).json() == changed.json()
    before_audits = audit_values(patient)
    stale = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("LL1", "L"), target("UR6", "P")], {"UR6": 1, "LL1": 1}))
    assert stale.status_code == 409
    assert chart(api_client, auth_headers, patient) == changed.json() and audit_values(patient) == before_audits


@pytest.mark.parametrize("condition", ["missing", "unerupted", "implant"])
def test_surface_ineligible_biology_rejects_entire_batch(api_client, auth_headers, condition):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR6"], condition=condition)).status_code == 200
    before, old_audits = chart(api_client, auth_headers, patient), audit_values(patient)
    result = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("LL1", "I"), target("UR6", "O")], {"LL1": 0, "UR6": 1}))
    assert result.status_code == 422
    assert chart(api_client, auth_headers, patient) == before and audit_values(patient) == old_audits


@pytest.mark.parametrize("crown", ["denture_cocr", "denture_acrylic", "fractured"])
def test_surface_artificial_or_absent_crown_rejects_atomically(api_client, auth_headers, crown):
    patient = _patient(api_client, auth_headers)
    first = api_client.post(crown_path(patient), headers=auth_headers, json=crown_payload(["UR6"], kind=None))
    assert first.status_code == 200
    if crown == "fractured":
        with SessionLocal() as db:
            row = db.scalar(select(ToothCondition).where(ToothCondition.patient_id == patient))
            row.crown_observation = {"kind": "fractured", "issues": []}  # prior-version synthetic record
            db.commit()
    else:
        assert api_client.post(crown_path(patient), headers=auth_headers,
            json=crown_payload(["UR6"], {"UR6": 1}, crown)).status_code == 200
    before, old_audits = chart(api_client, auth_headers, patient), audit_values(patient)
    result = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("LL1", "I"), target("UR6", "O")], {"LL1": 0, "UR6": before["teeth"]["UR6"]["revision"]}))
    assert result.status_code == 422
    assert chart(api_client, auth_headers, patient) == before and audit_values(patient) == old_audits


@pytest.mark.parametrize("condition", ["unrecorded", "missing", "implant", "unerupted", "deciduous"])
def test_whole_tooth_clear_includes_surface_map_even_for_same_condition(api_client, auth_headers, condition):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], condition="unrecorded")).status_code == 200
    value = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR4", "O")], {"UR4": 1}, neutral()))
    assert value.status_code == 200
    _seed_reset_related_records(patient, value.json()["teeth"]["UR4"]["updated_by"]["id"], ["UR4"])
    old_related = _reset_related_snapshot(patient)
    cleared = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 2}, condition=condition))
    assert cleared.status_code == 200
    assert cleared.json()["teeth"]["UR4"]["surface_observations"] == {}
    assert cleared.json()["teeth"]["UR4"]["revision"] == 3
    assert audit_values(patient)[-1][2]["teeth"]["UR4"]["surface_observations"] == {"O": neutral()}
    assert audit_values(patient)[-1][3]["teeth"]["UR4"]["surface_observations"] == {}
    assert _reset_related_snapshot(patient) == old_related
    assert api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR4", "O")], {"UR4": 2})).status_code == 409


def test_primary_transition_and_other_layers_preserve_only_compatible_surface_state(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], condition="deciduous")).status_code == 200
    first = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR4", "O")], {"UR4": 1}))
    assert first.status_code == 200
    expected = first.json()["teeth"]["UR4"]["surface_observations"]
    actions = [(_path(patient), _action_payload(["UR4"], {"UR4": 2}, movement="backward", rotation="clockwise")),
               (root_path(patient), root_payload(["UR4"], {"UR4": 3}, condition="filled_sound")),
               (crown_path(patient), crown_payload(["UR4"], {"UR4": 4}, "missing")),
               (crown_path(patient), crown_payload(["UR4"], {"UR4": 5}, None))]
    for path, data in actions:
        result = api_client.post(path, headers=auth_headers, json=data)
        assert result.status_code == 200
        assert result.json()["teeth"]["UR4"]["surface_observations"] == expected
        assert audit_values(patient)[-1][3]["teeth"]["UR4"]["surface_observations"] == expected
    # Stump surfaces remain chartable; no implicit material or biological state.
    assert api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR4"], {"UR4": 6}, "missing")).status_code == 200
    assert api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR4", "B")], {"UR4": 7})).status_code == 200
    changed = api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR4"], {"UR4": 8}, condition="present"))
    assert changed.status_code == 200 and changed.json()["teeth"]["UR4"]["surface_observations"] == {}


@pytest.mark.parametrize("artificial", ["bridge", "denture_cocr", "denture_acrylic"])
def test_artificial_site_rejects_meaningful_surfaces_but_preserves_explicit_resets(api_client, auth_headers, artificial):
    patient = _patient(api_client, auth_headers)
    first = api_client.post(surface_path(patient), headers=auth_headers, json=payload([target("UR4", "O")]))
    assert first.status_code == 200
    before, old_audits = first.json(), audit_values(patient)
    if artificial == "bridge":
        path = bridge_path(patient)
        data = bridge_payload(revisions={"UR5": 0, "UR4": 1, "UR3": 0}, crown={"kind": "porcelain", "issues": []})
    else:
        path, data = crown_path(patient), crown_payload(["UR4"], {"UR4": 1}, artificial)
    assert api_client.post(path, headers=auth_headers, json=data).status_code == 422
    assert chart(api_client, auth_headers, patient) == before and audit_values(patient) == old_audits
    assert group_count(patient) == 0
    assert api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR4", "O")], {"UR4": 1}, neutral())).status_code == 200
    data["expected_revisions"]["UR4"] = 2
    allowed = api_client.post(path, headers=auth_headers, json=data)
    assert allowed.status_code == 200
    assert allowed.json()["teeth"]["UR4"]["surface_observations"] == {"O": neutral()}
    assert allowed.json()["teeth"]["UR4"]["condition"] is None
    assert api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR4", "O")], {"UR4": 3})).status_code == 422


def test_bridge_natural_support_surfaces_survive_group_and_crown_resets(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR5"], condition="unrecorded")).status_code == 200
    first = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR5", "O")], {"UR5": 1}))
    assert first.status_code == 200
    expected = first.json()["teeth"]["UR5"]["surface_observations"]
    group = api_client.post(bridge_path(patient), headers=auth_headers,
        json=bridge_payload(revisions={"UR5": 2, "UR4": 0, "UR3": 0}))
    assert group.status_code == 200
    assert group.json()["teeth"]["UR5"]["surface_observations"] == expected
    # Same unrecorded condition is not a harmless no-op when it clears surfaces.
    assert api_client.post(_path(patient), headers=auth_headers,
        json=_action_payload(["UR5"], {"UR5": 3}, condition="unrecorded")).status_code == 422
    # Both natural support roles remain surface-chartable.
    surface = api_client.post(surface_path(patient), headers=auth_headers,
        json=payload([target("UR5", "B"), target("UR3", "I")], {"UR5": 3, "UR3": 1}))
    assert surface.status_code == 200
    crown = api_client.post(crown_path(patient), headers=auth_headers,
        json=crown_payload(["UR5"], {"UR5": 4}, "gold"))
    assert crown.status_code == 200
    group_id = group.json()["bridges"][0]["id"]
    reset = api_client.post(f"{bridge_path(patient)}/{group_id}/reset", headers=auth_headers,
        json={"expected_revisions": {"UR5": 5, "UR4": 1, "UR3": 2}})
    assert reset.status_code == 200
    for tooth in ("UR5", "UR3"):
        assert reset.json()["teeth"][tooth]["surface_observations"] == surface.json()["teeth"][tooth]["surface_observations"]
    assert reset.json()["bridges"] == []


@pytest.mark.parametrize("other", ["root", "tooth", "crown", "bridge", "bridge_reset"])
@pytest.mark.parametrize("surface_first", [True, False])
def test_surface_request_id_cannot_cross_other_diagnosis_endpoints(api_client, auth_headers, other, surface_first):
    patient = _patient(api_client, auth_headers)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    revision = 0
    if other == "root":
        other_path, other_data = root_path(patient), root_payload(["UR5"], condition=None)
    elif other == "tooth":
        other_path, other_data = _path(patient), _action_payload(["UR5"], condition=None)
    elif other == "crown":
        other_path, other_data = crown_path(patient), crown_payload(["UR5"], kind=None)
    elif other == "bridge":
        other_path, other_data = bridge_path(patient), bridge_payload()
    else:
        setup = api_client.post(bridge_path(patient), headers=auth_headers, json=bridge_payload())
        assert setup.status_code == 200
        revision = 1
        other_path = f"{bridge_path(patient)}/{setup.json()['bridges'][0]['id']}/reset"
        other_data = {"expected_revisions": {"UR5": 1, "UR4": 1, "UR3": 1}}
    surface_data = payload([target("UR5", "O")], {"UR5": revision}, neutral())
    first_path, first_data, second_path, second_data = (
        (surface_path(patient), surface_data, other_path, other_data) if surface_first
        else (other_path, other_data, surface_path(patient), surface_data))
    first = api_client.post(first_path, headers=headers, json=first_data)
    assert first.status_code == 200
    before_audits = audit_values(patient)
    assert api_client.post(second_path, headers=headers, json=second_data).status_code == 409
    assert chart(api_client, auth_headers, patient) == first.json() and audit_values(patient) == before_audits


@pytest.mark.parametrize("other", ["root", "crown", "reset"])
def test_surface_and_other_layer_races_have_one_atomic_winner(api_client, auth_headers, other):
    patient = _patient(api_client, auth_headers)
    targets = [target("UR6", "O"), target("LL1", "I")]
    first = api_client.post(surface_path(patient), headers=auth_headers, json=payload(targets))
    assert first.status_code == 200
    revisions = {"UR6": 1, "LL1": 1}
    if other == "root":
        other_path, other_data = root_path(patient), root_payload(list(revisions), revisions, condition="filled_sound")
    elif other == "crown":
        other_path, other_data = crown_path(patient), crown_payload(list(revisions), revisions)
    else:
        other_path, other_data = _path(patient), _action_payload(list(revisions), revisions, condition="unrecorded")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(api_client.post, surface_path(patient), headers=auth_headers,
                    json=payload(targets, revisions, observation("carious", None, "carious_early"))),
                   pool.submit(api_client.post, other_path, headers=auth_headers, json=other_data)]
        results = [future.result() for future in futures]
    assert sorted(result.status_code for result in results) == [200, 409]
    winner = next(result for result in results if result.status_code == 200)
    assert chart(api_client, auth_headers, patient) == winner.json()
    assert all(row["revision"] == 2 for row in winner.json()["teeth"].values())
    assert len(audit_values(patient)) == 2


def test_surface_permissions_archived_patient_and_cross_patient_boundaries(api_client, auth_headers):
    patient, other = _patient(api_client, auth_headers), _patient(api_client, auth_headers)
    assert api_client.post(surface_path(patient), json=payload()).status_code == 401
    for codes in ([], ["clinical.view"], ["clinical.write"]):
        headers = _user_with_capabilities(codes)
        assert api_client.post(surface_path(patient), headers=headers, json=payload()).status_code == 403
        assert api_client.post(surface_path(2000000000), headers=headers, json=payload()).status_code == 403
    assert audit_values(patient) == [] and _counts(patient)["tooth_conditions"] == 0
    allowed = _user_with_capabilities(["clinical.view", "clinical.write"])
    first = api_client.post(surface_path(patient), headers=allowed, json=payload())
    assert first.status_code == 200
    assert chart(api_client, auth_headers, other)["teeth"] == {}
    # A revision from a different patient cannot identify or mutate their tooth.
    assert api_client.post(surface_path(other), headers=allowed, json=payload(revisions={"UR6": 1})).status_code == 409
    before_audits = audit_values(patient)
    assert api_client.post(f"/patients/{patient}/archive", headers=auth_headers).status_code == 200
    assert api_client.post(surface_path(patient), headers=allowed,
        json=payload(revisions={"UR6": 1}, value=neutral())).status_code == 404
    assert audit_values(patient) == before_audits


@pytest.mark.parametrize("value", [observation(), neutral()])
def test_surface_migration_refuses_findings_and_explicit_reset_before_ddl(api_client, auth_headers, monkeypatch, value):
    patient = _patient(api_client, auth_headers)
    first = api_client.post(surface_path(patient), headers=auth_headers, json=payload(value=value))
    assert first.status_code == 200
    migration_path = Path(__file__).resolve().parents[2] / "alembic/versions/0055_surface_observations.py"
    spec = spec_from_file_location("native_surface_migration", migration_path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    def forbid_ddl(*_args, **_kwargs):
        pytest.fail("Surface downgrade must refuse before attempting DDL")

    with SessionLocal() as db:
        monkeypatch.setattr(migration.op, "get_bind", lambda: db.connection())
        monkeypatch.setattr(migration.op, "drop_constraint", forbid_ddl)
        monkeypatch.setattr(migration.op, "drop_column", forbid_ddl)
        with pytest.raises(RuntimeError, match="native surface observations exist"):
            migration.downgrade()
    assert chart(api_client, auth_headers, patient) == first.json()


def test_surface_database_rejects_nonobject_and_unsupported_map_keys(api_client, auth_headers):
    patient = _patient(api_client, auth_headers)
    first = api_client.post(surface_path(patient), headers=auth_headers, json=payload())
    assert first.status_code == 200
    for invalid in ("[]", '{"Q": {}}', "null"):
        with SessionLocal() as db:
            with pytest.raises(IntegrityError):
                db.execute(text("UPDATE tooth_conditions SET surface_observations = CAST(:value AS jsonb) WHERE patient_id = :patient"),
                    {"value": invalid, "patient": patient})
                db.flush()
            db.rollback()
    assert chart(api_client, auth_headers, patient) == first.json()
