"""Synthetic completed-care appearance: a read-only projection, never diagnosis writes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.clinical import ToothCondition, TreatmentPlanItem
from app.services.completed_chart import effective_tooth
from tests.patients.test_treatment_planning import setup_case, start, add, headers, payload, counts
from tests.patients.test_treatment_uncomplete import change, undo
from tests.patients.test_tooth_conditions import _user_with_capabilities


def current(client, auth, pid):
    result = client.get(f"/patients/{pid}/clinical/tooth-conditions", headers=auth)
    assert result.status_code == 200, result.text
    return result.json()


def record(client, auth, pid, snapshot, route="tooth-conditions", key=None, token=True, **patch):
    teeth = patch.get("teeth") or [target["tooth"] for target in patch.get("targets", [])] or list(patch.get("expected_revisions", {}))
    values = {"expected_revisions": {tooth: snapshot["teeth"].get(tooth, {}).get("revision", 0) for tooth in teeth}, **patch}
    if token:
        values["expected_projection_revision"] = snapshot["projection_revision"]
    return client.post(f"/patients/{pid}/clinical/{route}", headers=headers(auth, key), json=values)


def complete(client, auth, pid, item):
    result = change(client, auth, pid, item, status="completed", confirm_finance=True)
    assert result.status_code == 200, result.text
    return result.json()


def state(snapshot, tooth="UR4"):
    from types import SimpleNamespace
    raw = snapshot["teeth"].get(tooth)
    return effective_tooth(SimpleNamespace(**raw) if raw else None, tooth, snapshot)


@pytest.mark.parametrize("kind,level,material", [
    ("crown", "crown", "porcelain_bonded"), ("veneer", "crown", "composite"),
    ("denture", "crown", "denture_cocr"), ("filling", "surface", "resin"),
    ("inlay_onlay", "surface", "gold"), ("inlay_onlay", "crown", "gold"),
    ("implant", "tooth", None),
])
def test_material_persists_without_proposal_side_effects(api_client, auth_headers, kind, level, material):
    pid, quote = setup_case(api_client, auth_headers)
    frozen = start(api_client, auth_headers, pid)["plan"]["snapshot"]
    before = counts(pid)
    item = add(api_client, auth_headers, pid, quote, target={"level": level, "tooth": "UR4", "surfaces": ["O"] if level == "surface" else []},
        drawing_kind=kind, material=material)
    assert item["material"] == material
    assert counts(pid) == before
    assert current(api_client, auth_headers, pid)["completed_effects"] == []
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["snapshot"] == frozen


@pytest.mark.parametrize("kind,level,material", [("implant", "tooth", "gold"), ("crown", "crown", "resin"),
    ("filling", "surface", "composite"), ("denture", "crown", "porcelain"), ("sealant", "surface", "resin"),
    ("crown", "crown", True), ("crown", "crown", "invented")])
def test_material_mismatch_is_rejected(api_client, auth_headers, kind, level, material):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    response = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers),
        json=payload(quote, target={"level": level, "tooth": "UR4", "surfaces": ["O"] if level == "surface" else []}, drawing_kind=kind, material=material))
    assert response.status_code == 422
    assert counts(pid)[:3] == (0, 0, 0)


def test_material_patch_replay_stale_and_final_lock(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    item = add(api_client, auth_headers, pid, quote)
    key = f"material-{uuid4().hex}"
    body = {"expected_revision": 1, "material": "gold"}
    url = f"/patients/{pid}/planning/items/{item['id']}"
    first = api_client.patch(url, headers=headers(auth_headers, key), json=body)
    assert first.status_code == 200 and first.json()["revision"] == 2
    assert api_client.patch(url, headers=headers(auth_headers, key), json=body).json()["revision"] == 2
    assert api_client.patch(url, headers=headers(auth_headers), json=body).status_code == 409
    assert api_client.patch(url, headers=headers(auth_headers, key), json={**body, "material": "resin"}).status_code == 409
    assert change(api_client, auth_headers, pid, first.json(), material="gold", fee_mode="catalogue").status_code == 422
    item = complete(api_client, auth_headers, pid, first.json())
    assert change(api_client, auth_headers, pid, item, material="resin").status_code == 409
    reversed_item = undo(api_client, auth_headers, pid, item).json()
    assert reversed_item["material"] == "gold"
    assert change(api_client, auth_headers, pid, reversed_item, material="resin").json()["material"] == "resin"


def test_extraction_raw_history_undo_and_recomplete_order(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    before = current(api_client, auth_headers, pid)
    saved = record(api_client, auth_headers, pid, before, teeth=["UR4"], dentition="deciduous")
    assert saved.status_code == 200
    before = saved.json()
    frozen = start(api_client, auth_headers, pid)["plan"]["snapshot"]
    item = add(api_client, auth_headers, pid, quote, drawing_kind="extraction", target={"level": "tooth", "tooth": "UR4"})
    item = complete(api_client, auth_headers, pid, item)
    projected = current(api_client, auth_headers, pid)
    assert projected["teeth"] == before["teeth"]
    assert projected["projection_coverage"]["status"] == "available"
    effect = projected["completed_effects"][0]
    assert effect["procedure_id"] == item["completed_procedure_id"] and effect["completed_at"]
    assert state(projected).condition == "missing" and state(projected).dentition == "deciduous"
    moved = record(api_client, auth_headers, pid, projected, teeth=["UR4"], movement="forward")
    assert moved.status_code == 200, moved.text
    assert state(moved.json()).condition == "missing" and state(moved.json()).movement == "forward"
    assert moved.json()["observation_events"]["UR4"]["anatomy"] == 0
    item = undo(api_client, auth_headers, pid, item).json()
    uncompleted = current(api_client, auth_headers, pid)
    assert uncompleted["completed_effects"] == []
    assert uncompleted["teeth"] == moved.json()["teeth"]
    item = complete(api_client, auth_headers, pid, item)
    new_effect = current(api_client, auth_headers, pid)["completed_effects"][0]
    assert new_effect["event_id"] > effect["event_id"] and new_effect["procedure_id"] > effect["procedure_id"]
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["snapshot"] == frozen


def test_projection_stale_all_layers_and_noop_reset_intent(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    raw = current(api_client, auth_headers, pid)
    reset = record(api_client, auth_headers, pid, raw, teeth=["UR4"], condition="unrecorded", movement=None, rotation=None).json()
    start(api_client, auth_headers, pid)
    item = complete(api_client, auth_headers, pid, add(api_client, auth_headers, pid, quote,
        drawing_kind="extraction", target={"level": "tooth", "tooth": "UR4"}))
    assert record(api_client, auth_headers, pid, reset, teeth=["UR4"], movement="forward").status_code == 409
    now = current(api_client, auth_headers, pid)
    for route, patch in [("root-conditions", {"teeth": ["UR4"], "condition": "filled_sound"}),
        ("surface-conditions", {"targets": [{"tooth": "UR4", "surfaces": ["O"]}], "observation": {"kind": "restored", "material": "resin", "condition": "sound", "defects": []}})]:
        assert record(api_client, auth_headers, pid, reset, route, **patch).status_code == 409
        assert record(api_client, auth_headers, pid, now, route, **patch).status_code == 422
    key = f"noop-reset-{uuid4().hex}"
    response = record(api_client, auth_headers, pid, now, key=key, teeth=["UR4"], condition="unrecorded", movement=None, rotation=None)
    assert response.status_code == 200, response.text
    assert response.json()["teeth"] == reset["teeth"]  # Explicit intent with no fabricated row revision.
    assert state(response.json()).condition == "unrecorded"
    assert response.json()["observation_events"]["UR4"]["anatomy"] > now["completed_effects"][0]["event_id"]
    assert record(api_client, auth_headers, pid, now, key=key, teeth=["UR4"], condition="unrecorded", movement=None, rotation=None).status_code == 200
    assert undo(api_client, auth_headers, pid, item).status_code == 200


def test_completed_implant_allows_crown_without_rewriting_missing_baseline(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    initial = current(api_client, auth_headers, pid)
    saved = record(api_client, auth_headers, pid, initial, teeth=["UR4"], condition="missing").json()
    start(api_client, auth_headers, pid)
    complete(api_client, auth_headers, pid, add(api_client, auth_headers, pid, quote,
        drawing_kind="implant", target={"level": "tooth", "tooth": "UR4"}))
    now = current(api_client, auth_headers, pid)
    assert now["teeth"] == saved["teeth"] and state(now).condition == "implant"
    assert record(api_client, auth_headers, pid, now, teeth=["UR4"], dentition="deciduous").status_code == 422
    response = record(api_client, auth_headers, pid, now, "crown-conditions", teeth=["UR4"], kind="porcelain", issues=[])
    assert response.status_code == 200, response.text
    assert response.json()["teeth"]["UR4"]["condition"] == "missing"
    assert state(response.json()).condition == "implant"
    assert state(response.json()).crown_observation["kind"] == "porcelain"


def test_later_single_surface_overrides_only_it_and_survives_uncomplete(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    item = complete(api_client, auth_headers, pid, add(api_client, auth_headers, pid, quote, material="gold"))
    now = current(api_client, auth_headers, pid)
    assert now["teeth"] == {}
    assert set(state(now).surface_observations) == {"M", "O", "P"}
    response = record(api_client, auth_headers, pid, now, "surface-conditions", targets=[{"tooth": "UR4", "surfaces": ["O"]}],
        observation={"kind": "restored", "material": "resin", "condition": "sound", "defects": []})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert state(saved).surface_observations["O"]["material"] == "resin"
    assert state(saved).surface_observations["M"]["material"] == "gold"
    assert saved["observation_events"]["UR4"]["surfaces"]["M"] == 0
    assert undo(api_client, auth_headers, pid, item).status_code == 200
    after = current(api_client, auth_headers, pid)
    assert after["teeth"] == saved["teeth"]
    assert state(after).surface_observations == saved["teeth"]["UR4"]["surface_observations"]


def test_corrupt_active_metadata_fails_closed(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    item = complete(api_client, auth_headers, pid, add(api_client, auth_headers, pid, quote))
    with SessionLocal() as db:
        row = db.get(TreatmentPlanItem, item["id"])
        row.planning_details = {**row.planning_details, "drawing_kind": "extraction"}  # Wrong level, not guessed.
        db.commit()
    now = current(api_client, auth_headers, pid)
    assert now["projection_coverage"]["status"] == "unavailable"
    assert now["completed_effects"] == []
    assert record(api_client, auth_headers, pid, now, teeth=["UR4"], movement="forward").status_code == 422


def test_root_masks_crown_and_changed_dentition_preserve_presence(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    for kind, level, material in [("root_canal", "root", None), ("apicectomy", "root", None), ("crown", "crown", "gold")]:
        complete(api_client, auth_headers, pid, add(api_client, auth_headers, pid, quote,
            drawing_kind=kind, material=material, target={"level": level, "tooth": "UR4"}))
    now = current(api_client, auth_headers, pid)
    updated = record(api_client, auth_headers, pid, now, "root-conditions", teeth=["UR4"], condition="filled_defective")
    assert updated.status_code == 200, updated.text
    effective = state(updated.json())
    assert all(root["condition"] == "filled_defective" and root["apicectomy"] for root in effective.root_observations.values())
    assert effective.crown_observation["kind"] == "gold"
    primary = record(api_client, auth_headers, pid, updated.json(), teeth=["UR4"], dentition="deciduous")
    assert primary.status_code == 200
    assert state(primary.json()).root_observations == {} and state(primary.json()).crown_observation is None
    assert primary.json()["observation_events"]["UR4"]["anatomy"] == 0


@pytest.mark.parametrize("route,patch", [
    ("tooth-conditions", {"teeth": ["UR4"], "rotation": "clockwise"}),
    ("root-conditions", {"teeth": ["UR4"], "apicectomy": True}),
    ("crown-conditions", {"teeth": ["UR4"], "kind": "gold", "issues": []}),
    ("surface-conditions", {"targets": [{"tooth": "UR4", "surfaces": ["O"]}], "observation": {"kind": None, "material": None, "condition": None, "defects": []}}),
    ("bridges", {"members": [{"tooth": "UR4", "role": "abutment"}, {"tooth": "UR5", "role": "pontic"}], "expected_revisions": {"UR4": 0, "UR5": 0}}),
    ("bridges/999999/reset", {"expected_revisions": {"UR4": 0, "UR5": 0}}),
])
def test_all_native_routes_check_projection_before_writes(api_client, auth_headers, route, patch):
    pid, quote = setup_case(api_client, auth_headers)
    before = current(api_client, auth_headers, pid)
    start(api_client, auth_headers, pid)
    complete(api_client, auth_headers, pid, add(api_client, auth_headers, pid, quote))
    assert record(api_client, auth_headers, pid, before, route, **patch).status_code == 409
    assert current(api_client, auth_headers, pid)["teeth"] == {}


def test_projection_read_permissions_and_no_financial_details(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    complete(api_client, auth_headers, pid, add(api_client, auth_headers, pid, quote, material="gold"))
    viewer = _user_with_capabilities(["clinical.view"])
    response = current(api_client, viewer, pid)
    assert set(response["completed_effects"][0]) == {"item_id", "procedure_id", "completed_at", "event_id", "target", "drawing_kind", "material"}
    assert record(api_client, viewer, pid, response, teeth=["UR4"], movement="forward").status_code == 403
    forbidden = _user_with_capabilities(["clinical.write"])
    assert api_client.get(f"/patients/{pid}/clinical/tooth-conditions", headers=forbidden).status_code == 403


def test_response_helper_reacquires_patient_lock_after_commit(api_client, auth_headers, monkeypatch):
    from app.routers import clinical
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    item = add(api_client, auth_headers, pid, quote)
    entered, release, completing, finished = Event(), Event(), Event(), Event()
    original = clinical.projection_context

    def held_context(db, patient_id):
        if patient_id == pid:
            entered.set()
            assert release.wait(5)
        return original(db, patient_id)

    def read_after_commit():
        with SessionLocal() as db:
            db.commit()
            return clinical._tooth_conditions_out(db, pid).model_dump(mode="json")

    def finish_item():
        completing.set()
        try:
            return complete(api_client, auth_headers, pid, item)
        finally:
            finished.set()

    monkeypatch.setattr(clinical, "projection_context", held_context)
    with ThreadPoolExecutor(max_workers=2) as pool:
        read_future = pool.submit(read_after_commit)
        assert entered.wait(5)
        completion = pool.submit(finish_item)
        assert completing.wait(5)
        try:
            assert not finished.wait(0.15), "Completion must not pass the response's shared patient lock"
        finally:
            release.set()
        assert read_future.result()["completed_effects"] == []
        assert completion.result()["completed_procedure_id"]


def test_legacy_primary_identity_change_cannot_resurrect_extracted_tooth(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    baseline = record(api_client, auth_headers, pid, current(api_client, auth_headers, pid),
        teeth=["UR4"], condition="deciduous")
    assert baseline.status_code == 200
    start(api_client, auth_headers, pid)
    complete(api_client, auth_headers, pid, add(api_client, auth_headers, pid, quote,
        drawing_kind="extraction", target={"level": "tooth", "tooth": "UR4"}))
    response = record(api_client, auth_headers, pid, current(api_client, auth_headers, pid),
        teeth=["UR4"], dentition="permanent")
    assert response.status_code == 200
    assert response.json()["teeth"]["UR4"]["condition"] == "present"  # Existing legacy normalization only.
    assert response.json()["observation_events"]["UR4"]["anatomy"] == 0
    assert state(response.json()).condition == "missing"
