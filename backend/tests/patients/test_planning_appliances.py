"""Synthetic grouped appliances: one price, one atomic completion, explicit members."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.clinical import Procedure, TreatmentPlanItem
from app.models.ledger import PatientLedgerEntry
from app.models.treatment import Treatment, FeeType
from app.models.treatment_planning import PatientTreatmentPlan
from tests.patients.test_treatment_planning import setup_case, start, headers, payload, counts
from tests.patients.test_treatment_uncomplete import change, undo
from tests.patients.test_completed_chart import current, record, complete, state

BRIDGE = {"kind": "bridge", "arch": "upper", "members": [
    {"tooth": "UL6", "role": "abutment"}, {"tooth": "UL7", "role": "pontic"}, {"tooth": "UL8", "role": "abutment"}]}
DENTURE = {"kind": "denture", "arch": "lower", "members": [
    {"tooth": "LL3", "role": "denture"}, {"tooth": "LL7", "role": "denture"}]}


def prepared(client, auth, *, kind="bridge", price=3500, fee_type=FeeType.fixed):
    pid, old_quote = setup_case(client, auth, price=price, fee_type=fee_type)
    with SessionLocal() as db:
        row = db.get(Treatment, old_quote["id"])
        row.level = "crown"
        row.planning_defaults = {"drawing_kind": kind, "material": None}
        row.planning_defaults_revision = 1
        db.commit()
    quote = client.get(f"/patients/{pid}/planning/catalogue", params={"q": old_quote["code"]}, headers=auth).json()["items"][0]
    frozen = start(client, auth, pid)["plan"]["snapshot"]
    return pid, quote, frozen


def create_group(client, auth, pid, quote, appliance=None, **options):
    appliance = appliance or BRIDGE
    value = payload(quote, target={"level": "crown", "tooth": None, "surfaces": []}, drawing_kind=appliance["kind"],
        appliance=appliance, material="porcelain_bonded" if appliance["kind"] == "bridge" else "denture_acrylic", **options)
    return client.post(f"/patients/{pid}/planning/items", headers=headers(auth), json=value)


def missing_members(client, auth, pid, appliance):
    teeth = [member["tooth"] for member in appliance["members"] if member["role"] in {"pontic", "denture"}]
    result = record(client, auth, pid, current(client, auth, pid), teeth=teeth, condition="missing")
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize("appliance,amount,quantity", [(BRIDGE, 10500, 3), (DENTURE, 3500, 1)])
def test_one_appliance_fee_completion_undo_history_and_recomplete(api_client, auth_headers, appliance, amount, quantity):
    pid, quote, frozen = prepared(api_client, auth_headers, kind=appliance["kind"])
    before = counts(pid)
    response = create_group(api_client, auth_headers, pid, quote, appliance)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["appliance"] == appliance and item["target"]["tooth"] is None and item["tooth"] is None
    assert item["fee_pence"] == amount and item["pricing"]["quantity"] == quantity
    assert item["pricing"]["unit_fee_pence"] == 3500 and item["pricing"]["total_fee_pence"] == amount
    assert item["catalogue_snapshot"]["fee"]["amount_pence"] == amount
    assert item["catalogue_snapshot"]["unit_fee"] == quote["fee"]
    assert counts(pid) == before  # Proposal is neither care nor accounting.
    assert change(api_client, auth_headers, pid, item, status="completed", confirm_finance=True).status_code == 422
    baseline = missing_members(api_client, auth_headers, pid, appliance)
    item = complete(api_client, auth_headers, pid, item)
    now = current(api_client, auth_headers, pid)
    assert now["teeth"] == baseline["teeth"] and now["completed_effects"][0]["appliance"] == appliance
    assert counts(pid)[:3] == (1, 1, 0)
    for member in appliance["members"]:
        history = api_client.get(f"/patients/{pid}/tooth-history", params={"tooth": member["tooth"]}, headers=auth_headers).json()
        assert len(history["procedures"]) == 1 and history["procedures"][0]["appliance"] == appliance
        journal = api_client.get(f"/patients/{pid}/clinical-journal", params={"tooth": member["tooth"]}, headers=auth_headers).json()
        assert {entry["source_kind"] for entry in journal["items"]} >= {"procedure", "treatment_plan"}
        assert all(entry["details"]["appliance"] == appliance for entry in journal["items"] if entry["source_kind"] in {"procedure", "treatment_plan"})
    assert api_client.get(f"/patients/{pid}/tooth-history", params={"tooth": "UR1"}, headers=auth_headers).json()["procedures"] == []
    with SessionLocal() as db:
        procedure = db.get(Procedure, item["completed_procedure_id"])
        assert procedure.tooth is None and procedure.fee_pence == amount
    reversed_item = undo(api_client, auth_headers, pid, item)
    assert reversed_item.status_code == 200, reversed_item.text
    assert current(api_client, auth_headers, pid)["completed_effects"] == []
    assert current(api_client, auth_headers, pid)["teeth"] == baseline["teeth"]
    journal = api_client.get(f"/patients/{pid}/clinical-journal", params={"tooth": appliance["members"][0]["tooth"]}, headers=auth_headers).json()
    assert any(entry["source_kind"] == "procedure" and entry["details"]["status"] == "voided" and entry["details"]["appliance"] == appliance for entry in journal["items"])
    complete(api_client, auth_headers, pid, reversed_item.json())
    with SessionLocal() as db:
        assert sum(row.amount_pence for row in db.scalars(select(PatientLedgerEntry).where(PatientLedgerEntry.patient_id == pid))) == amount
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["snapshot"] == frozen


@pytest.mark.parametrize("edit", [
    {"members": [{"tooth": "UL6", "role": "abutment"}, {"tooth": "UL8", "role": "pontic"}]},
    {"members": [{"tooth": "UL6", "role": "abutment"}, {"tooth": "UL6", "role": "pontic"}]},
    {"members": [{"tooth": "UL6", "role": "abutment"}, {"tooth": "LL7", "role": "pontic"}]},
    {"members": [{"tooth": "UL6", "role": "abutment"}, {"tooth": "UL7", "role": "wing"}]},
    {"members": [{"tooth": "UL6", "role": "pontic"}, {"tooth": "UL7", "role": "pontic"}]},
    {"members": [{"tooth": "UL6", "role": "denture"}, {"tooth": "UL7", "role": "pontic"}]},
    {"arch": "lower"}, {"unexpected": True},
])
def test_invalid_groups_are_atomic(api_client, auth_headers, edit):
    pid, quote, _ = prepared(api_client, auth_headers)
    response = create_group(api_client, auth_headers, pid, quote, {**deepcopy(BRIDGE), **edit})
    assert response.status_code == 422
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["items"] == []


@pytest.mark.parametrize("fee_mode,fee_pence,reason,expected", [
    ("override", 10001, "Agreed appliance discount", 10001), ("waived", 0, "No charge", 0),
    ("override", 10001, None, None), ("catalogue", 3500, None, None),
])
def test_total_fee_override_never_invents_fractional_unit_prices(api_client, auth_headers, fee_mode, fee_pence, reason, expected):
    pid, quote, _ = prepared(api_client, auth_headers)
    response = create_group(api_client, auth_headers, pid, quote, fee_mode=fee_mode, fee_pence=fee_pence, fee_reason=reason)
    assert response.status_code == (201 if expected is not None else 422), response.text
    if expected is None:
        return
    item = response.json()
    assert item["fee_pence"] == expected and item["pricing"]["unit_fee_pence"] == 3500
    edited = change(api_client, auth_headers, pid, item, fee_mode="catalogue", fee_reason=None)
    assert edited.status_code == 200 and edited.json()["fee_pence"] == 10500
    assert edited.json()["pricing"]["total_fee_pence"] == 10500


def test_scaled_range_and_saved_quote_do_not_follow_later_fees(api_client, auth_headers):
    pid, quote, _ = prepared(api_client, auth_headers, fee_type=FeeType.range)
    item = create_group(api_client, auth_headers, pid, quote, fee_mode="agreed", fee_pence=4000).json()
    assert item["fee_pence"] == 4000 and item["pricing"]["unit_fee_pence"] is None
    assert item["catalogue_snapshot"]["fee"]["min_amount_pence"] == 3000
    assert item["catalogue_snapshot"]["fee"]["max_amount_pence"] == 6000
    assert change(api_client, auth_headers, pid, item, fee_mode="agreed", fee_pence=7000).status_code == 422
    assert api_client.put(f"/treatments/{quote['id']}/fees", headers=auth_headers,
        json=[{"patient_category": "CLINIC_PRIVATE", "fee_type": "FIXED", "amount_pence": 9999}]).status_code == 200
    assert change(api_client, auth_headers, pid, item, fee_mode="agreed", fee_pence=5000).json()["fee_pence"] == 5000


def test_whole_group_concurrent_completion_and_reversal_replay(api_client, auth_headers):
    pid, quote, _ = prepared(api_client, auth_headers)
    item = create_group(api_client, auth_headers, pid, quote).json()
    missing_members(api_client, auth_headers, pid, BRIDGE)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: change(api_client, auth_headers, pid, item, status="completed", confirm_finance=True), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    item = next(response.json() for response in responses if response.status_code == 200)
    assert counts(pid)[:3] == (1, 1, 0)
    key = f"group-undo-{uuid4().hex}"
    response = undo(api_client, auth_headers, pid, item, key=key)
    assert response.status_code == 200
    assert undo(api_client, auth_headers, pid, item, key=key).status_code == 200
    assert counts(pid)[:3] == (1, 2, 0)


def test_complete_rejects_missing_support_and_implant_wing_atomically(api_client, auth_headers):
    pid, quote, _ = prepared(api_client, auth_headers)
    group = deepcopy(BRIDGE)
    group["members"][0]["role"] = "wing"
    item = create_group(api_client, auth_headers, pid, quote, group).json()
    before = missing_members(api_client, auth_headers, pid, group)
    for condition in ("missing", "implant", "unerupted"):
        changed = record(api_client, auth_headers, pid, before, teeth=["UL6"], condition=condition)
        assert changed.status_code == 200
        before = changed.json()
        result = change(api_client, auth_headers, pid, item, status="completed", confirm_finance=True)
        assert result.status_code == 422
        assert counts(pid)[:3] == (0, 0, 0)
        assert current(api_client, auth_headers, pid)["teeth"] == before["teeth"]


def test_pontic_identity_survives_later_crown_material_without_native_bridge(api_client, auth_headers):
    pid, quote, _ = prepared(api_client, auth_headers)
    item = create_group(api_client, auth_headers, pid, quote).json()
    before = missing_members(api_client, auth_headers, pid, BRIDGE)
    complete(api_client, auth_headers, pid, item)
    now = current(api_client, auth_headers, pid)
    assert state(now, "UL7").bridge_role == "pontic"
    revised = record(api_client, auth_headers, pid, now, "crown-conditions", teeth=["UL7"], kind="gold", issues=[])
    assert revised.status_code == 200, revised.text
    assert state(revised.json(), "UL7").bridge_role == "pontic"
    assert state(revised.json(), "UL7").crown_observation["kind"] == "gold"
    assert revised.json()["bridges"] == before["bridges"] == []
    assert revised.json()["teeth"]["UL7"]["bridge_group_id"] is None


@pytest.mark.parametrize("key,count,material,valid", [
    ("routine-v1:crown:3", 3, "denture_acrylic", True), ("routine-v1:crown:3", 4, "denture_acrylic", False),
    ("routine-v1:crown:4", 3, "denture_acrylic", False), ("routine-v1:crown:4", 4, "denture_acrylic", True),
    ("routine-v1:crown:5", 2, "denture_cocr", True), ("routine-v1:crown:5", 2, "denture_acrylic", False),
    ("routine-v1:crown:3", 2, None, False), (None, 2, "denture_cocr", True),
])
def test_owned_denture_fee_suitability_is_explicit(key, count, material, valid):
    from fastapi import HTTPException
    from app.schemas.treatment_planning import PlanningAppliance
    from app.services.treatment_planning import validate_routine_appliance
    appliance = PlanningAppliance(kind="denture", arch="lower", members=[{"tooth": f"LL{index}", "role": "denture"} for index in range(1, count + 1)])
    if valid:
        validate_routine_appliance(key, appliance, material)
    else:
        with pytest.raises(HTTPException) as error:
            validate_routine_appliance(key, appliance, material)
        assert error.value.status_code == 422


def test_zero_price_group_completion_has_no_fabricated_charge(api_client, auth_headers):
    pid, quote, _ = prepared(api_client, auth_headers, price=0)
    item = create_group(api_client, auth_headers, pid, quote).json()
    assert item["fee_pence"] == 0
    missing_members(api_client, auth_headers, pid, BRIDGE)
    item = complete(api_client, auth_headers, pid, item)
    assert counts(pid)[:3] == (1, 0, 0)
    assert undo(api_client, auth_headers, pid, item).status_code == 200
    assert counts(pid)[:3] == (1, 0, 0)


def test_group_material_cannot_clear_or_change_frozen_known_denture_type(api_client, auth_headers):
    pid, quote, _ = prepared(api_client, auth_headers, kind="denture")
    item = create_group(api_client, auth_headers, pid, quote, DENTURE).json()
    assert change(api_client, auth_headers, pid, item, material=None).status_code == 422
    with SessionLocal() as db:
        row = db.get(TreatmentPlanItem, item["id"])
        # Synthetic historical quote: the old acrylic routine identity survives
        # even though today's independently stored catalogue profile is custom.
        row.planning_details = {**row.planning_details, "catalogue_snapshot": {
            **row.planning_details["catalogue_snapshot"], "routine_key": "routine-v1:crown:3"}}
        db.commit()
    assert change(api_client, auth_headers, pid, item, material="denture_cocr").status_code == 422
    missing_members(api_client, auth_headers, pid, DENTURE)
    complete(api_client, auth_headers, pid, item)


@pytest.mark.parametrize("legacy,wing", [({"missing": True, "restorations": []}, False),
    ({"extracted": True, "restorations": []}, False),
    ({"restorations": [{"type": "denture"}]}, False),
    ({"restorations": [{"type": "implant"}]}, True)])
def test_unresolved_captured_absent_or_implant_support_needs_native_review(api_client, auth_headers, legacy, wing):
    pid, quote, _ = prepared(api_client, auth_headers)
    group = deepcopy(BRIDGE)
    if wing:
        group["members"][0]["role"] = "wing"
    with SessionLocal() as db:
        plan = db.scalar(select(PatientTreatmentPlan).where(PatientTreatmentPlan.patient_id == pid))
        plan.snapshot = {**plan.snapshot, "legacy": {"teeth": {"26": legacy}}}
        db.commit()
    item = create_group(api_client, auth_headers, pid, quote, group).json()
    missing_members(api_client, auth_headers, pid, group)
    assert change(api_client, auth_headers, pid, item, status="completed", confirm_finance=True).status_code == 422
    assert counts(pid)[:3] == (0, 0, 0)
    explicit = record(api_client, auth_headers, pid, current(api_client, auth_headers, pid), teeth=["UL6"], condition="present")
    assert explicit.status_code == 200
    complete(api_client, auth_headers, pid, item)


def test_group_scaled_fee_limit_and_null_material_are_rejected(api_client, auth_headers):
    pid, quote, _ = prepared(api_client, auth_headers, price=50_000_000)
    assert create_group(api_client, auth_headers, pid, quote).status_code == 422
    response = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers), json=payload(quote,
        target={"level": "crown", "tooth": None, "surfaces": []}, drawing_kind="bridge", appliance=BRIDGE, material=None))
    assert response.status_code == 422
    assert counts(pid)[:3] == (0, 0, 0)
