"""Synthetic practice index and date-effective prices; no legacy-system access."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from uuid import uuid4
import subprocess

import pytest
from sqlalchemy import event, func, select, text

from app.db.session import SessionLocal, engine
from app.models.audit_log import AuditLog
from app.models.clinical import ToothCondition
from app.models.patient import PatientCategory
from app.models.treatment import Treatment, TreatmentFee, TreatmentFeeVersion
from app.services import treatment_fees as service
from tests.patients.test_clinical_reliability import _create_user_headers, _set_capabilities
from tests.patients.test_treatment_planning import setup_case, start, add, headers, payload, counts
from tests.patients.test_planning_custom_items import custom_patient, custom
from tests.patients.test_treatment_uncomplete import change

CATEGORY = "CLINIC_PRIVATE"


def fee_change(client, auth, tid, revision=0, key=None, **patch):
    return client.post(f"/treatments/{tid}/fee-changes", headers=headers(auth, key), json={
        "patient_category": CATEGORY, "fee_type": "FIXED", "amount_pence": 2000,
        "effective_from": service.practice_today().isoformat(), "expected_revision": revision, **patch})


def index_item(client, auth, tid):
    response = client.get("/treatments/index", headers=auth, params={"patient_category": CATEGORY, "include_inactive": True})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["id"] == tid)


def quote_for(client, auth, pid, code):
    response = client.get(f"/patients/{pid}/planning/catalogue", headers=auth, params={"q": code})
    assert response.status_code == 200
    return next(row for row in response.json()["items"] if row["code"] == code)


@pytest.mark.parametrize("instant,expected", [
    ("2026-01-01T23:30:00+00:00", "2026-01-01"),
    ("2026-07-01T23:30:00+00:00", "2026-07-02"),
    ("2026-03-29T00:30:00+00:00", "2026-03-29"),
    ("2026-03-29T23:30:00+00:00", "2026-03-30"),
    ("2026-10-25T00:30:00+00:00", "2026-10-25"),
    ("2026-10-25T23:30:00+00:00", "2026-10-25"),
])
def test_practice_date_uses_london_across_dst(instant, expected):
    assert service.practice_today(datetime.fromisoformat(instant)).isoformat() == expected


def test_current_future_decrease_same_date_correction_and_history(api_client, auth_headers, monkeypatch):
    today = date(2027, 7, 1)
    monkeypatch.setattr(service, "practice_today", lambda: today)
    pid, quote = setup_case(api_client, auth_headers, price=1234)
    tid = quote["id"]
    baseline = index_item(api_client, auth_headers, tid)["current_fee"]
    assert baseline["source"] == "legacy" and baseline["effective_from"] is None and baseline["recorded_by"] is None
    for revision, day, amount in [(0, 0, 2000), (1, 5, 2500), (2, 10, 1800), (3, 5, 2300)]:
        result = fee_change(api_client, auth_headers, tid, revision, effective_from=(today + timedelta(days=day)).isoformat(), amount_pence=amount)
        assert result.status_code == 200, result.text
    row = result.json()
    assert row["current_fee"]["amount_pence"] == 2000 and row["fee_revision"] == 4
    assert [item["amount_pence"] for item in row["scheduled_fees"]] == [2300, 1800]
    assert [item["revision"] for item in row["scheduled_fees"]] == [4, 3]
    first = api_client.get(f"/treatments/{tid}/fee-history", headers=auth_headers, params={"patient_category": CATEGORY, "limit": 2}).json()
    assert [item["revision"] for item in first["items"]] == [4, 3] and first["next_before_revision"] == 3
    assert first["baseline_fee"] == baseline
    assert all(item["recorded_at"] and item["recorded_by"]["id"] for item in first["items"])
    second = api_client.get(f"/treatments/{tid}/fee-history", headers=auth_headers, params={"patient_category": CATEGORY, "before_revision": 3}).json()
    assert [item["revision"] for item in second["items"]] == [2, 1] and second["next_before_revision"] is None
    today += timedelta(days=5)
    assert index_item(api_client, auth_headers, tid)["current_fee"]["amount_pence"] == 2300
    assert api_client.get(f"/treatments/{tid}/fees", headers=auth_headers).json()[0]["amount_pence"] == 2300
    assert quote_for(api_client, auth_headers, pid, quote["code"])["fee"]["amount_pence"] == 2300
    today += timedelta(days=5)
    assert index_item(api_client, auth_headers, tid)["current_fee"]["amount_pence"] == 1800
    with SessionLocal() as db:
        assert db.scalar(select(TreatmentFee).where(TreatmentFee.treatment_id == tid)).amount_pence == 1234


def test_future_only_does_not_invalidate_current_quote_but_effective_change_does(api_client, auth_headers, monkeypatch):
    today = date(2027, 8, 1)
    monkeypatch.setattr(service, "practice_today", lambda: today)
    pid, quote = setup_case(api_client, auth_headers, price=1400)
    start(api_client, auth_headers, pid)
    assert fee_change(api_client, auth_headers, quote["id"], effective_from=(today + timedelta(days=1)).isoformat()).status_code == 200
    assert quote_for(api_client, auth_headers, pid, quote["code"])["quote_token"] == quote["quote_token"]
    item = add(api_client, auth_headers, pid, quote)
    today += timedelta(days=1)
    stale = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers), json=payload(quote))
    assert stale.status_code == 409
    current = quote_for(api_client, auth_headers, pid, quote["code"])
    assert current["fee"]["version_id"] is not None and current["fee"]["effective_from"] == today.isoformat()
    new = add(api_client, auth_headers, pid, current)
    assert new["fee_pence"] == 2000 and item["fee_pence"] == 1400
    completed = change(api_client, auth_headers, pid, item, status="completed", confirm_finance=True)
    assert completed.status_code == 200 and completed.json()["fee_pence"] == 1400
    assert completed.json()["catalogue_snapshot"] == item["catalogue_snapshot"]


def test_unset_and_old_put_preserve_baseline_and_future_history(api_client, auth_headers, monkeypatch):
    today = date(2027, 9, 1)
    monkeypatch.setattr(service, "practice_today", lambda: today)
    pid, quote = setup_case(api_client, auth_headers, price=555)
    tid = quote["id"]
    assert fee_change(api_client, auth_headers, tid, effective_from=(today + timedelta(days=2)).isoformat()).status_code == 200
    old = api_client.put(f"/treatments/{tid}/fees", headers=auth_headers, json=[{"patient_category": CATEGORY, "fee_type": "FIXED", "amount_pence": 0}])
    assert old.status_code == 200 and old.json()[0]["amount_pence"] == 0
    assert index_item(api_client, auth_headers, tid)["scheduled_fees"][0]["amount_pence"] == 2000
    assert api_client.put(f"/treatments/{tid}/fees", headers=auth_headers, json=[]).status_code == 200
    row = index_item(api_client, auth_headers, tid)
    assert row["current_fee"]["fee_type"] is None and row["fee_revision"] == 3
    assert api_client.get(f"/treatments/{tid}/fees", headers=auth_headers).json() == []
    assert quote_for(api_client, auth_headers, pid, quote["code"])["fee"]["type"] == "UNAVAILABLE"
    today += timedelta(days=2)
    assert index_item(api_client, auth_headers, tid)["current_fee"]["amount_pence"] == 2000
    with SessionLocal() as db:
        assert db.scalar(select(TreatmentFee).where(TreatmentFee.treatment_id == tid)).amount_pence == 555
        assert db.scalar(select(func.count(TreatmentFeeVersion.id)).where(TreatmentFeeVersion.treatment_id == tid)) == 3


@pytest.mark.parametrize("patch", [
    {"amount_pence": None}, {"amount_pence": -1}, {"amount_pence": True}, {"amount_pence": 2.5},
    {"amount_pence": 100_000_001}, {"amount_pence": "2"}, {"min_amount_pence": 1},
    {"fee_type": "RANGE"}, {"fee_type": "RANGE", "amount_pence": None, "min_amount_pence": 2, "max_amount_pence": 1},
    {"fee_type": "N_A"}, {"fee_type": None}, {"expected_revision": True}, {"expected_revision": -1},
    {"effective_from": "2001-01-01"}, {"effective_from": "bad"}, {"notes": "x" * 2001},
    {"unexpected": 1}, {"patient_category": "invalid"},
])
def test_invalid_fees_do_not_create_history(api_client, auth_headers, patch):
    _, quote = setup_case(api_client, auth_headers)
    result = fee_change(api_client, auth_headers, quote["id"], **patch)
    assert result.status_code == 422, result.text
    assert index_item(api_client, auth_headers, quote["id"])["fee_revision"] == 0


@pytest.mark.parametrize("values", [
    {"fee_type": "FIXED", "amount_pence": 0},
    {"fee_type": "RANGE", "amount_pence": None, "min_amount_pence": 0, "max_amount_pence": 100_000_000},
    {"fee_type": "N_A", "amount_pence": None}, {"fee_type": None, "amount_pence": None},
])
def test_explicit_zero_range_na_and_unset_are_distinct(api_client, auth_headers, values):
    _, quote = setup_case(api_client, auth_headers)
    response = fee_change(api_client, auth_headers, quote["id"], **values)
    assert response.status_code == 200, response.text
    assert all(response.json()["current_fee"][key] == value for key, value in values.items())


def test_revision_replay_and_concurrent_schedule_changes(api_client, auth_headers):
    _, quote = setup_case(api_client, auth_headers)
    tid, key = quote["id"], f"fee-{uuid4().hex}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: fee_change(api_client, auth_headers, tid, key=key), range(2)))
    assert [item.status_code for item in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert fee_change(api_client, auth_headers, tid, key=key, amount_pence=2100).status_code == 409
    assert fee_change(api_client, auth_headers, tid).status_code == 409
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda price: fee_change(api_client, auth_headers, tid, revision=1, amount_pence=price), [2200, 2300]))
    assert sorted(item.status_code for item in results) == [200, 409]
    with SessionLocal() as db:
        assert db.scalar(select(func.count(TreatmentFeeVersion.id)).where(TreatmentFeeVersion.treatment_id == tid)) == 2
        assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "treatment.fee.changed", AuditLog.entity_id == str(tid))) == 2


def test_admin_permissions_and_clinical_read_picker_remain_separate(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    uid, restricted = _create_user_headers(api_client)
    _set_capabilities(uid, ["clinical.view", "clinical.write", "billing.view"])
    for path in ("/treatments/index", f"/treatments/{quote['id']}/fees", f"/treatments/{quote['id']}/fee-history?patient_category={CATEGORY}"):
        assert api_client.get(path, headers=restricted).status_code == 403
    assert fee_change(api_client, restricted, quote["id"]).status_code == 403
    assert api_client.post("/treatments/routine-defaults", headers=restricted, json={}).status_code == 403
    assert api_client.get(f"/patients/{pid}/planning/catalogue", headers=restricted).status_code == 200


def test_routine_initialization_preserves_and_orders_native_entries(api_client, auth_headers, monkeypatch):
    suffix = uuid4().hex[:12]
    routines = {level: tuple(f"{name} {suffix}" for name in names) for level, names in service.ROUTINE_DEFAULTS.items()}
    monkeypatch.setattr(service, "ROUTINE_DEFAULTS", routines)
    # A single exact name is classified without replacement or price inference.
    pid, quote = setup_case(api_client, auth_headers, price=4321)
    old = api_client.patch(f"/treatments/{quote['id']}", headers=auth_headers,
        json={"name": routines["root"][1], "is_active": False}).json()
    with SessionLocal() as db:
        before_count = db.scalar(select(func.count(Treatment.id)))
        # Prior test runs may have initialized keys; isolate this test's keys.
        saved_keys = [(row.id, row.routine_key) for row in db.scalars(select(Treatment).where(Treatment.routine_key.is_not(None)))]
        for rid, key in saved_keys:
            db.get(Treatment, rid).routine_key = None
        db.commit()
    try:
        index_item(api_client, auth_headers, quote["id"])
        with SessionLocal() as db:
            assert db.scalar(select(func.count(Treatment.id))) == before_count  # GET never initializes.
        first = api_client.post("/treatments/routine-defaults", headers=auth_headers, json={})
        assert first.status_code == 200 and first.json() == {"created": 19, "existing": 1, "total": 20}
        adopted = index_item(api_client, auth_headers, quote["id"])
        assert adopted["id"] == old["id"] and adopted["code"] == old["code"] and adopted["name"] == old["name"]
        assert adopted["level"] == "root" and adopted["display_order"] == 20 and not adopted["is_active"]
        assert adopted["current_fee"]["amount_pence"] == 4321
        second = api_client.post("/treatments/routine-defaults", headers=auth_headers, json={})
        assert second.json() == {"created": 0, "existing": 20, "total": 20}
        with SessionLocal() as db:
            routine_rows = list(db.scalars(select(Treatment).where(Treatment.routine_key.is_not(None))))
            assert len(routine_rows) == 20
            assert db.scalar(select(func.count(TreatmentFee.id)).where(TreatmentFee.treatment_id.in_([row.id for row in routine_rows if row.id != quote["id"]]))) == 0
    finally:
        with SessionLocal() as db:
            for row in db.scalars(select(Treatment).where(Treatment.routine_key.is_not(None))):
                row.routine_key = None
            db.flush()
            for rid, key in saved_keys:
                db.get(Treatment, rid).routine_key = key
            db.commit()


def test_ambiguous_routine_names_reject_entire_initialization(api_client, auth_headers, monkeypatch):
    name = f"Ambiguous routine {uuid4().hex}"
    monkeypatch.setattr(service, "ROUTINE_DEFAULTS", {"root": (name,)})
    for _ in range(2):
        assert api_client.post("/treatments", headers=auth_headers, json={"name": name}).status_code == 201
    with SessionLocal() as db:
        before = db.scalar(select(func.count(Treatment.id)))
    response = api_client.post("/treatments/routine-defaults", headers=auth_headers, json={})
    assert response.status_code == 422 and "Review existing" in response.text
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Treatment.id))) == before


def test_catalogue_group_filter_and_explicit_target_mismatch(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    path = f"/patients/{pid}/planning/catalogue"
    assert api_client.get(path, headers=auth_headers, params={"q": quote["code"], "level": "root"}).json()["items"] == []
    assert len(api_client.get(path, headers=auth_headers, params={"q": quote["code"], "level": "root", "include_unassigned": True}).json()["items"]) == 1
    assert api_client.patch(f"/treatments/{quote['id']}", headers=auth_headers, json={"level": "root", "display_order": 20}).status_code == 200
    current = quote_for(api_client, auth_headers, pid, quote["code"])
    assert current["level"] == "root" and current["display_order"] == 20
    response = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers), json=payload(current))
    assert response.status_code == 422
    assert add(api_client, auth_headers, pid, current, drawing_kind="root_canal", target={"level": "root", "tooth": "UR4"})["target"]["level"] == "root"


@pytest.mark.parametrize("level", service.LEVELS)
def test_other_treatment_supports_explicit_anatomical_targets(api_client, auth_headers, level):
    pid = custom_patient(api_client, auth_headers)
    target = {"level": level, "tooth": None if level == "general" else "UR4", "surfaces": ["P", "M"] if level == "surface" else []}
    baseline = api_client.get(f"/patients/{pid}/clinical/tooth-conditions", headers=auth_headers).json()
    result = custom(api_client, auth_headers, pid, target=target)
    assert result.status_code == 201, result.text
    item = result.json()
    assert item["drawing_kind"] == "other" and item["procedure_code"] == "MISCELLANEOUS"
    assert item["treatment_id"] is None and item["catalogue_snapshot"] == {"source": "custom"}
    assert item["target"]["level"] == level
    assert item["surface"] == ("ML" if level == "surface" else None)
    assert counts(pid) == (0, 0, 0, 0)
    assert api_client.get(f"/patients/{pid}/clinical/tooth-conditions", headers=auth_headers).json() == baseline


def test_other_root_and_surface_respect_frozen_missing_tooth(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    response = api_client.post(f"/patients/{pid}/clinical/tooth-conditions", headers=headers(auth_headers),
        json={"teeth": ["UR4"], "condition": "missing", "expected_revisions": {"UR4": 0}})
    assert response.status_code == 200
    start(api_client, auth_headers, pid)
    for level in ("root", "surface"):
        assert custom(api_client, auth_headers, pid, target={"level": level, "tooth": "UR4", "surfaces": ["O"] if level == "surface" else []}).status_code == 422
    assert counts(pid) == (0, 0, 0, 0)


def test_index_bulk_fee_queries_and_populated_downgrade_refusal(api_client, auth_headers):
    _, quote = setup_case(api_client, auth_headers)
    assert fee_change(api_client, auth_headers, quote["id"]).status_code == 200
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if "treatment_fee" in statement.lower() and statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        index_item(api_client, auth_headers, quote["id"])
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 2
    result = subprocess.run(["alembic", "downgrade", "0060_treatment_completion_reversals"], capture_output=True, text=True)
    assert result.returncode != 0 and "Cannot downgrade: effective treatment fee history" in result.stderr
    with SessionLocal() as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0061_treatment_index_effective_fees"
        assert db.scalar(select(func.count(TreatmentFeeVersion.id)).where(TreatmentFeeVersion.treatment_id == quote["id"])) == 1
