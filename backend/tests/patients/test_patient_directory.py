from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.patient import Patient, PatientCategory
from app.models.user import Role, User
from app.services.capabilities import replace_user_capabilities
from app.services.patient_directory import build_patient_directory

NOW = datetime(2040, 6, 10, 12, tzinfo=timezone.utc)
ALL_CAPS = {"patients.view", "appointments.view", "billing.view"}


@pytest.fixture
def directory_db(api_client):
    # Synthetic records remain in a rolled-back transaction, so list counts do
    # not depend on earlier tests or alter the separate browser test fixtures.
    del api_client
    with SessionLocal() as db:
        actor_id = db.scalar(select(User.id).where(User.role == Role.superadmin))
        assert actor_id is not None
        yield db, actor_id, uuid4().hex
        db.rollback()


def patient(fixture, *, first="Synthetic", last="Directory", **extra):
    db, actor_id, marker = fixture
    values = dict(first_name=first, last_name=last, email=f"{marker}@example.test",
        created_by_user_id=actor_id, created_at=NOW, updated_at=NOW)
    values.update(extra)
    row = Patient(**values)
    db.add(row)
    db.flush()
    return row


def appointment(fixture, owner, *, when=NOW, status=AppointmentStatus.completed,
                deleted=False, home=False):
    db, actor_id, _ = fixture
    row = Appointment(patient_id=owner.id, starts_at=when,
        ends_at=when + timedelta(minutes=30), status=status,
        location_type=AppointmentLocationType.visit if home else AppointmentLocationType.clinic,
        is_domiciliary=home, deleted_at=NOW if deleted else None,
        created_by_user_id=actor_id)
    db.add(row)
    db.flush()
    return row


def ledger(fixture, owner, amount, kind=LedgerEntryType.charge):
    db, actor_id, _ = fixture
    db.add(PatientLedgerEntry(patient_id=owner.id, amount_pence=amount,
        entry_type=kind, created_by_user_id=actor_id))
    db.flush()


def directory(fixture, caps=ALL_CAPS, **params):
    db, _, marker = fixture
    return build_patient_directory(db, caps, email=marker, now=NOW, **params)


def ids(result):
    return [item.id for item in result.items]


def test_directory_search_matches_full_partial_names_both_orders_and_normalized_phone(directory_db):
    row = patient(directory_db, first="Synthetic Ada", last="Lovelace",
        phone="+44 (0)1632 960-123")
    for query in ("synthetic ada lovelace", "  LOVELACE   Synthetic\tAda  ",
                  "Ada Love", "lace Synthetic", "lovela", "01632960123", "01632 960 123",
                  "+44 (0)1632", directory_db[2]):
        assert ids(directory(directory_db, query=query)) == [row.id]
    assert directory(directory_db, query="unmatched directory person").total == 0


def test_directory_search_treats_sql_wildcards_literally_and_combines_existing_filters(directory_db):
    row = patient(directory_db, first="Synthetic_100%", last="Directory",
        date_of_birth=date(1980, 1, 2), patient_category=PatientCategory.denplan)
    patient(directory_db, first="SyntheticX100other", last="Directory",
        date_of_birth=date(1980, 1, 2), patient_category=PatientCategory.clinic_private)
    assert ids(directory(directory_db, query="_100%")) == [row.id]
    assert ids(directory(directory_db, query="Directory", dob=date(1980, 1, 2),
        category=PatientCategory.denplan)) == [row.id]
    assert directory(directory_db, dob=date(1980, 1, 3)).total == 0
    assert directory(directory_db, category=PatientCategory.domiciliary_private).total == 0
    assert directory(directory_db, query="' OR 1=1 --").total == 0


def test_directory_active_archived_all_and_total_are_independent_of_page(directory_db):
    active = [patient(directory_db, first=f"Synthetic{i:02d}") for i in range(6)]
    archived = [patient(directory_db, first=f"Archived{i}", deleted_at=NOW) for i in range(2)]
    result = directory(directory_db, limit=2, offset=2, sort="first_name")
    assert (result.total, result.limit, result.offset) == (6, 2, 2)
    assert ids(result) == [row.id for row in active[2:4]]
    assert directory(directory_db, status="all", limit=1).total == 8
    result = directory(directory_db, status="archived")
    assert ids(result) == [row.id for row in archived]
    assert all(row.deleted_at is not None for row in result.items)
    result = directory(directory_db, offset=1000)
    assert result.items == [] and result.total == 6


@pytest.mark.parametrize("sort,direction,expected", [
    ("last_name", "asc", [0, 1, 2]), ("last_name", "desc", [2, 1, 0]),
    ("first_name", "asc", [2, 1, 0]), ("first_name", "desc", [0, 1, 2]),
    ("joined", "asc", [1, 2, 0]), ("joined", "desc", [0, 2, 1]),
    ("recently_edited", "asc", [2, 0, 1]), ("recently_edited", "desc", [1, 0, 2]),
])
def test_directory_sorts_names_joined_and_edited_dates(directory_db, sort, direction, expected):
    rows = [
        patient(directory_db, first="Zoe", last="alpha", created_at=NOW,
            updated_at=NOW - timedelta(days=1)),
        patient(directory_db, first="Beth", last="Bravo", created_at=NOW - timedelta(days=2),
            updated_at=NOW),
        patient(directory_db, first="amy", last="charlie", created_at=NOW - timedelta(days=1),
            updated_at=NOW - timedelta(days=2)),
    ]
    assert ids(directory(directory_db, sort=sort, direction=direction)) == [rows[i].id for i in expected]


@pytest.mark.parametrize("sort", ["last_name", "first_name", "joined", "recently_edited", "last_visit"])
def test_directory_tied_sorts_use_stable_patient_id_pagination(directory_db, sort):
    rows = [patient(directory_db) for _ in range(3)]
    for direction in ("asc", "desc"):
        result = directory(directory_db, sort=sort, direction=direction, limit=1, offset=1)
        assert ids(result) == [rows[1].id]
        assert result.total == 3


def test_directory_balances_match_signed_native_ledger_and_debt_filter_counts(directory_db):
    debtor = patient(directory_db, last="A")
    credit = patient(directory_db, last="B")
    cleared = patient(directory_db, last="C")
    empty = patient(directory_db, last="D")
    ledger(directory_db, debtor, 10000)
    ledger(directory_db, debtor, -2000, LedgerEntryType.payment)
    ledger(directory_db, debtor, -500, LedgerEntryType.adjustment)
    ledger(directory_db, credit, -1250, LedgerEntryType.payment)
    ledger(directory_db, cleared, 500)
    ledger(directory_db, cleared, -500, LedgerEntryType.payment)
    # Multiple visits must never multiply aggregate ledger balances.
    appointment(directory_db, debtor)
    appointment(directory_db, debtor, when=NOW - timedelta(days=2))
    result = directory(directory_db)
    assert {row.id: row.balance_pence for row in result.items} == {
        debtor.id: 7500, credit.id: -1250, cleared.id: 0, empty.id: 0,
    }
    result = directory(directory_db, with_debt=True, limit=1)
    assert result.total == 1 and ids(result) == [debtor.id]
    result = directory(directory_db, with_debt=True, offset=1)
    assert result.total == 1 and result.items == []


def test_directory_last_visit_is_completed_non_deleted_past_including_home_and_nulls_last(directory_db):
    recent = patient(directory_db, last="Recent")
    old = patient(directory_db, last="Old")
    empty = patient(directory_db, last="Empty")
    appointment(directory_db, old, when=NOW - timedelta(days=10))
    appointment(directory_db, recent, when=NOW - timedelta(days=3))
    appointment(directory_db, recent, when=NOW, home=True)
    for owner in (old, empty):
        for status in AppointmentStatus:
            if status != AppointmentStatus.completed:
                appointment(directory_db, owner, when=NOW, status=status)
        appointment(directory_db, owner, when=NOW, deleted=True)
        appointment(directory_db, owner, when=NOW + timedelta(seconds=1))
    result = directory(directory_db, sort="last_visit", direction="desc")
    assert ids(result) == [recent.id, old.id, empty.id]
    assert [row.last_visit_at for row in result.items] == [NOW, NOW - timedelta(days=10), None]
    assert ids(directory(directory_db, sort="last_visit", direction="asc")) == [old.id, recent.id, empty.id]


@pytest.mark.parametrize("params", [
    {}, {"with_debt": True}, {"sort": "last_visit"},
    {"with_debt": True, "sort": "last_visit"},
])
def test_directory_enriches_only_page_ids_unless_domain_is_required_for_filter_or_sort(directory_db, params):
    db, _, _ = directory_db
    owners = [patient(directory_db) for _ in range(3)]
    for index, owner in enumerate(owners):
        ledger(directory_db, owner, 100 + index)
        appointment(directory_db, owner)
    captured = []
    connection = db.connection()
    def capture(_conn, _cursor, statement, parameters, _context, _executemany):
        captured.append((statement.lower(), parameters))
    event.listen(connection, "before_cursor_execute", capture)
    try:
        result = directory(directory_db, limit=1, offset=1, **params)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert result.total == 3
    assert ids(result) == [owners[1].id]
    assert result.items[0].balance_pence == 101
    assert result.items[0].last_visit_at == NOW
    for table, deferred in (
        ("patient_ledger_entries", not params.get("with_debt")),
        ("appointments", params.get("sort") != "last_visit"),
    ):
        queries = [(sql, values) for sql, values in captured if table in sql]
        assert queries
        if deferred:
            assert len(queries) == 1
            sql, values = queries[0]
            assert f"{table}.patient_id in (" in sql
            bound_ids = {value for key, value in values.items() if key.startswith("patient_id_")}
            assert bound_ids == {owners[1].id}
        else:
            # A filter or sort needs its domain before LIMIT, across all
            # matching patients; it must not accidentally use the page subset.
            assert all(f"{table}.patient_id in (" not in sql for sql, _ in queries)


def test_directory_empty_page_skips_all_optional_domain_enrichment(directory_db):
    db, _, _ = directory_db
    owner = patient(directory_db)
    ledger(directory_db, owner, 100)
    appointment(directory_db, owner)
    statements = []
    connection = db.connection()
    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())
    event.listen(connection, "before_cursor_execute", capture)
    try:
        result = directory(directory_db, offset=100)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert result.total == 1 and result.items == []
    assert len(statements) == 2
    assert all("appointments" not in sql and "patient_ledger_entries" not in sql for sql in statements)


@pytest.mark.parametrize("caps", [
    {"patients.view"}, {"patients.view", "billing.view"}, {"patients.view", "appointments.view"},
])
def test_directory_permissions_do_not_query_or_leak_forbidden_domains(directory_db, caps):
    db, _, _ = directory_db
    owner = patient(directory_db, phone="01632 960123", notes="SYNTHETIC PRIVATE NOTE",
        medical_alerts="SYNTHETIC PRIVATE ALERT")
    ledger(directory_db, owner, 7654321)
    appointment(directory_db, owner)
    statements = []
    connection = db.connection()
    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())
    event.listen(connection, "before_cursor_execute", capture)
    try:
        result = directory(directory_db, caps)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert len(result.items) == 1
    row = result.items[0]
    assert row.id == owner.id and row.phone == owner.phone
    assert result.metadata.do_not_contact == "unavailable"
    assert "do_not_contact" not in row.model_dump()
    assert "SYNTHETIC PRIVATE" not in result.model_dump_json()
    assert all("patients.notes" not in statement and "patients.medical_alerts" not in statement for statement in statements)
    assert all(statement.lstrip().startswith("select") and "r4_" not in statement for statement in statements)
    if "billing.view" not in caps:
        assert row.balance_pence is None and result.metadata.finance == "forbidden"
        assert all("patient_ledger_entries" not in statement for statement in statements)
        assert "7654321" not in result.model_dump_json()
    else:
        assert row.balance_pence == 7654321 and result.metadata.finance == "available"
    if "appointments.view" not in caps:
        assert row.last_visit_at is None and result.metadata.last_visit == "forbidden"
        assert all("appointments" not in statement for statement in statements)
    else:
        assert row.last_visit_at == NOW and result.metadata.last_visit == "available"


@pytest.mark.parametrize("caps,params", [
    (set(), {}), ({"billing.view", "appointments.view"}, {}),
    ({"patients.view"}, {"with_debt": True}),
    ({"patients.view"}, {"sort": "last_visit"}),
])
def test_directory_rejects_forbidden_identity_filters_and_sort_before_data_queries(caps, params):
    with pytest.raises(HTTPException) as error:
        build_patient_directory(None, caps, **params)
    assert error.value.status_code == 403


def test_directory_endpoint_route_authentication_projection_limits_and_old_contract(api_client, auth_headers):
    assert api_client.get("/patients/directory").status_code == 401
    response = api_client.get("/patients/directory", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["limit"] == 50 and data["offset"] == 0
    assert response.headers["cache-control"] == "no-store"
    assert data["metadata"] == {"finance": "available", "last_visit": "available", "do_not_contact": "unavailable"}
    assert len(data["items"]) <= 50
    for row in data["items"]:
        assert set(row) == {"id", "first_name", "last_name", "phone", "date_of_birth", "patient_category",
            "created_at", "updated_at", "deleted_at", "balance_pence", "last_visit_at"}
    assert api_client.get("/patients/directory?limit=100", headers=auth_headers).status_code == 200
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"status": "deleted"},
                   {"sort": "email"}, {"direction": "up"}, {"dob": "invalid"}, {"category": "unknown"}):
        assert api_client.get("/patients/directory", params=params, headers=auth_headers).status_code == 422
    original = api_client.get("/patients?limit=1", headers=auth_headers)
    assert original.status_code == 200 and isinstance(original.json(), list)


def test_directory_endpoint_capabilities_apply_without_role_bypass(api_client):
    with SessionLocal() as db:
        # Direct synthetic user fixture avoids default grants; no password is
        # usable and the short-lived test token is never printed.
        user = User(email=f"directory-viewer-{uuid4().hex}@example.test", full_name="Synthetic Viewer",
            hashed_password="synthetic-not-a-password-hash", role=Role.superadmin)
        db.add(user)
        db.flush()
        user_id = user.id
        replace_user_capabilities(db, user_id, ["patients.view"])
        token = create_access_token(subject=str(user_id), secret=settings.secret_key,
            alg=settings.jwt_alg, expires_minutes=5)
    headers = {"Authorization": f"Bearer {token}"}
    response = api_client.get("/patients/directory", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["finance"] == data["metadata"]["last_visit"] == "forbidden"
    assert all(row["balance_pence"] is None and row["last_visit_at"] is None for row in data["items"])
    for params in ({"with_debt": "true"}, {"sort": "last_visit"}):
        assert api_client.get("/patients/directory", params=params, headers=headers).status_code == 403
    with SessionLocal() as db:
        replace_user_capabilities(db, user_id, ["billing.view", "appointments.view"])
    assert api_client.get("/patients/directory", headers=headers).status_code == 403
