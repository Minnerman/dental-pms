"""Opt-in practice picker scope preserves unclassified catalogue and saved plans."""
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.treatment import Treatment
from app.services.treatment_fees import LEVELS
from tests.patients.test_clinical_reliability import _create_user_headers, _set_capabilities
from tests.patients.test_treatment_planning import setup_case, start, add
from tests.patients.test_treatment_index import fee_change
from tests.patients.test_treatment_uncomplete import change


@pytest.fixture
def scoped_catalogue(api_client, auth_headers):
    pid, old = setup_case(api_client, auth_headers)
    prefix = f"Scope-{uuid4().hex[:12]}"
    rows = []
    names = ("Simple extraction", "Root canal", "White crown", "White filling", "Examination")
    for level, name in zip(LEVELS, names):
        result = api_client.post("/treatments", headers=auth_headers,
            json={"name": f"{prefix} {name}", "level": level, "display_order": 10})
        assert result.status_code == 201
        rows.append(result.json())
    # More than one old-client page must not consume the classified page.
    with SessionLocal() as db:
        actor_id = db.get(Treatment, old["id"]).created_by_user_id
        db.add_all(Treatment(name=f"{prefix} Simple demo {i}", created_by_user_id=actor_id,
            updated_by_user_id=actor_id) for i in range(55))
        db.add(Treatment(name=f"{prefix} Inactive", level="tooth", is_active=False,
            created_by_user_id=actor_id, updated_by_user_id=actor_id))
        db.commit()
    assert fee_change(api_client, auth_headers, rows[2]["id"], amount_pence=9876).status_code == 200
    return pid, prefix, rows


def fetch(client, auth, pid, prefix, **params):
    response = client.get(f"/patients/{pid}/planning/catalogue", headers=auth,
        params={"q": prefix, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_classified_picker_includes_all_five_groups_and_unpriced_treatments(scoped_catalogue, api_client, auth_headers):
    pid, prefix, rows = scoped_catalogue
    result = fetch(api_client, auth_headers, pid, prefix, classified_only=True)
    assert result["total"] == 5
    assert [row["id"] for row in result["items"]] == [row["id"] for row in rows]
    assert [row["level"] for row in result["items"]] == list(LEVELS)
    assert result["items"][0]["fee"]["type"] == "UNAVAILABLE"
    assert result["items"][0]["fee"]["amount_pence"] is None
    assert result["items"][2]["fee"]["amount_pence"] == 9876
    match = fetch(api_client, auth_headers, pid, prefix + " sim", classified_only=True)
    assert match["total"] == 1 and match["items"][0]["id"] == rows[0]["id"]
    # Opt-in filtering is read-only; all unclassified records stay stored.
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Treatment).where(Treatment.name.startswith(prefix), Treatment.level.is_(None))))) == 55


def test_classification_precedes_count_paging_and_optional_selected_level(scoped_catalogue, api_client, auth_headers):
    pid, prefix, rows = scoped_catalogue
    pages = [fetch(api_client, auth_headers, pid, prefix, classified_only=True, limit=2, offset=offset) for offset in (0, 2, 4, 6)]
    assert all(page["total"] == 5 for page in pages)
    assert [row["id"] for page in pages for row in page["items"]] == [row["id"] for row in rows]
    result = fetch(api_client, auth_headers, pid, prefix, level="crown", include_unassigned=True, classified_only=True)
    assert result["total"] == 1 and result["items"][0]["id"] == rows[2]["id"]


def test_old_catalogue_default_and_explicit_unassigned_contract_unchanged(scoped_catalogue, api_client, auth_headers):
    pid, prefix, rows = scoped_catalogue
    for params in ({}, {"classified_only": False}, {"include_unassigned": False}):
        result = fetch(api_client, auth_headers, pid, prefix, **params)
        assert result["total"] == 60 and len(result["items"]) == 50
    result = fetch(api_client, auth_headers, pid, prefix, level="crown", include_unassigned=True)
    assert result["total"] == 56
    assert fetch(api_client, auth_headers, pid, prefix, level="crown")["total"] == 1


def test_classified_picker_uses_existing_clinical_view_permission(scoped_catalogue, api_client, auth_headers):
    pid, prefix, _ = scoped_catalogue
    uid, restricted = _create_user_headers(api_client)
    _set_capabilities(uid, ["clinical.view"])
    assert fetch(api_client, restricted, pid, prefix, classified_only=True)["total"] == 5
    _set_capabilities(uid, ["clinical.write"])
    assert api_client.get(f"/patients/{pid}/planning/catalogue", headers=restricted,
        params={"classified_only": True}).status_code == 403


def test_scoped_picker_does_not_change_saved_unassigned_quotes_or_fee_edits(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers, price=1234)
    start(api_client, auth_headers, pid)
    item = add(api_client, auth_headers, pid, quote)
    assert quote["level"] is None
    assert fetch(api_client, auth_headers, pid, quote["code"], classified_only=True)["items"] == []
    workspace = api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()
    assert workspace["plan"]["items"][0] == item
    changed = change(api_client, auth_headers, pid, item, fee_mode="override", fee_pence=1300, fee_reason="Synthetic patient agreement")
    assert changed.status_code == 200 and changed.json()["fee_pence"] == 1300
    assert changed.json()["catalogue_snapshot"] == item["catalogue_snapshot"]
    # Default old-client lookup and the underlying catalogue remain available.
    assert fetch(api_client, auth_headers, pid, quote["code"])["items"][0] == quote
    with SessionLocal() as db:
        row = db.get(Treatment, quote["id"])
        assert row.is_active and row.level is None
