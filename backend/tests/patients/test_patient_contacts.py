from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, text

from app.db.session import SessionLocal, engine
from app.models.audit_log import AuditLog
from app.schemas.patient import PatientCreate, PatientUpdate
from tests.patients.test_tooth_conditions import _counts, _user_with_capabilities


CONTACTS = {
    "phone_label": "Care home reception",
    "home_phone": "020 7946 0001",
    "home_phone_label": "Patient",
    "work_phone": "+44 20 7946 0002 ext 123",
    "work_phone_label": "Work reception",
    "mobile_phone": "07700 900123",
    "mobile_phone_label": "Daughter",
}


def _create(client, headers, **fields):
    response = client.post("/patients", headers=headers, json={
        "first_name": "Synthetic", "last_name": f"Contacts-{uuid4().hex}", **fields,
    })
    assert response.status_code == 201
    return response.json()


def _audits(patient_id):
    with SessionLocal() as db:
        return list(db.scalars(select(AuditLog).where(
            AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient_id),
        ).order_by(AuditLog.id)))


def test_labelled_contacts_create_read_edit_clear_preserve_primary_and_unrelated_data(api_client, auth_headers):
    patient = _create(api_client, auth_headers, phone=" 020 7946 0000 ",
        primary_contact_name="Existing contact", primary_contact_phone="02079460003",
        primary_contact_relationship="Relative", referral_contact_phone="02079460004",
        notes="Synthetic existing patient note", **{key: f"  {value}  " for key, value in CONTACTS.items()})
    patient_id = patient["id"]
    assert {key: patient[key] for key in CONTACTS} == CONTACTS
    # Existing phone semantics/formatting are deliberately not changed.
    assert patient["phone"] == " 020 7946 0000 "
    loaded = api_client.get(f"/patients/{patient_id}", headers=auth_headers)
    assert loaded.status_code == 200 and loaded.json() == patient
    counts = _counts(patient_id)
    initial_audits = _audits(patient_id)
    assert len(initial_audits) == 1 and initial_audits[0].action == "create"
    assert {key: initial_audits[0].after_json[key] for key in CONTACTS} == CONTACTS

    response = api_client.patch(f"/patients/{patient_id}", headers=auth_headers,
        json={"mobile_phone_label": " Son ", "work_phone": None})
    assert response.status_code == 200
    updated = response.json()
    assert updated["mobile_phone_label"] == "Son" and updated["work_phone"] is None
    # Omitted numbers/labels, the old primary contact, notes and recalls survive.
    expected_unchanged = set(patient) - {"mobile_phone_label", "work_phone", "updated_at", "updated_by"}
    assert {key: updated[key] for key in expected_unchanged} == {key: patient[key] for key in expected_unchanged}
    audit = _audits(patient_id)[-1]
    assert audit.action == "update"
    assert audit.before_json["mobile_phone_label"] == "Daughter" and audit.after_json["mobile_phone_label"] == "Son"
    assert audit.before_json["work_phone"] == CONTACTS["work_phone"] and audit.after_json["work_phone"] is None
    assert _counts(patient_id) == counts

    # Repeated normalization is a no-op, not a new audit or update timestamp.
    assert api_client.patch(f"/patients/{patient_id}", headers=auth_headers,
        json={"mobile_phone_label": " Son ", "work_phone": "   "}).json() == updated
    assert len(_audits(patient_id)) == 2


def test_old_clients_and_primary_number_do_not_infer_new_contact_data(api_client, auth_headers):
    patient = _create(api_client, auth_headers, phone="07700 900456")
    assert all(patient[key] is None for key in CONTACTS)
    response = api_client.patch(f"/patients/{patient['id']}", headers=auth_headers,
        json={"phone": "02079460005", "last_name": "Synthetic unchanged meaning"})
    assert response.status_code == 200 and response.json()["phone"] == "02079460005"
    assert all(response.json()[key] is None for key in CONTACTS)


@pytest.mark.parametrize("field", CONTACTS)
def test_new_contact_fields_validate_atomically_and_never_change_legacy_phone(api_client, auth_headers, field):
    patient = _create(api_client, auth_headers, phone="02079460006", **CONTACTS)
    maximum = 120 if field.endswith("_label") else 50
    for invalid in ("x" * (maximum + 1), 1234, True, [], {}):
        response = api_client.patch(f"/patients/{patient['id']}", headers=auth_headers,
            json={field: invalid, "phone": "must-not-be-saved"})
        assert response.status_code == 422
    assert api_client.get(f"/patients/{patient['id']}", headers=auth_headers).json() == patient
    assert len(_audits(patient["id"])) == 1
    # Create and update share the exact same validation and length bounds.
    for schema in (PatientCreate, PatientUpdate):
        names = {"first_name": "Synthetic", "last_name": "Bounds"} if schema is PatientCreate else {}
        assert getattr(schema(**names, **{field: "x" * maximum}), field) == "x" * maximum
        with pytest.raises(ValueError):
            schema(**names, **{field: "x" * (maximum + 1)})


@pytest.mark.parametrize("clear_value", [None, "", "  \t  "])
def test_explicit_clear_is_separate_from_omitted_contact_fields(api_client, auth_headers, clear_value):
    patient = _create(api_client, auth_headers, **CONTACTS)
    response = api_client.patch(f"/patients/{patient['id']}", headers=auth_headers,
        json={"home_phone_label": clear_value})
    assert response.status_code == 200 and response.json()["home_phone_label"] is None
    assert all(response.json()[key] == value for key, value in CONTACTS.items() if key != "home_phone_label")


def test_contact_permissions_and_archived_record_guards(api_client, auth_headers):
    patient = _create(api_client, auth_headers, **CONTACTS)
    patient_id = patient["id"]
    no_access = _user_with_capabilities([])
    readonly = _user_with_capabilities(["patients.view"])
    writer = _user_with_capabilities(["patients.view", "patients.write"])
    for headers in (no_access, readonly):
        assert api_client.patch(f"/patients/{patient_id}", headers=headers,
            json={"home_phone": "02079460007"}).status_code == 403
        assert api_client.post("/patients", headers=headers,
            json={"first_name": "Synthetic", "last_name": "Denied", **CONTACTS}).status_code == 403
    denied = api_client.get(f"/patients/{patient_id}", headers=no_access)
    assert denied.status_code == 403 and all(value not in denied.text for value in CONTACTS.values())
    assert api_client.get(f"/patients/{patient_id}", headers=readonly).json()["mobile_phone_label"] == "Daughter"
    assert len(_audits(patient_id)) == 1
    # Contact editing does not require or grant messaging/recall capabilities.
    assert api_client.patch(f"/patients/{patient_id}", headers=writer,
        json={"home_phone_label": "Care home"}).status_code == 200
    assert api_client.post(f"/patients/{patient_id}/archive", headers=auth_headers).status_code == 200
    audits = len(_audits(patient_id))
    assert api_client.patch(f"/patients/{patient_id}", headers=auth_headers,
        json={"mobile_phone": "07700900999"}).status_code == 404
    assert len(_audits(patient_id)) == audits
    assert api_client.post(f"/patients/{patient_id}/restore", headers=auth_headers).status_code == 200
    restored = api_client.get(f"/patients/{patient_id}", headers=auth_headers).json()
    assert restored["mobile_phone"] == CONTACTS["mobile_phone"] and restored["home_phone_label"] == "Care home"


def test_contact_migration_no_backfill_and_lossless_downgrade_guards(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0057_labelled_patient_phones.py"
    spec = spec_from_file_location("labelled_patient_phones_migration", path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    # Connection-local synthetic table exercises actual migration DDL without
    # modifying the shared isolated fixture schema or any existing records.
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TEMP TABLE patients (id integer, phone text, primary_contact_phone text, marker text) ON COMMIT DROP")
        connection.exec_driver_sql("INSERT INTO patients VALUES (1, '07700 900123', '02079460000', 'retained'), (2, NULL, NULL, 'unknown')")
        before = [dict(row) for row in connection.execute(text("SELECT * FROM patients ORDER BY id")).mappings()]
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        after = [dict(row) for row in connection.execute(text("SELECT * FROM patients ORDER BY id")).mappings()]
        assert after == [{**row, **dict.fromkeys(CONTACTS)} for row in before]
        migration.downgrade()
        assert [dict(row) for row in connection.execute(text("SELECT * FROM patients ORDER BY id")).mappings()] == before
        migration.upgrade()
        for field in CONTACTS:
            connection.execute(text(f"UPDATE patients SET {field} = 'recorded' WHERE id = 1"))
            with pytest.raises(RuntimeError, match="labelled patient contact data exists"):
                migration.downgrade()
            assert connection.scalar(text(f"SELECT {field} FROM patients WHERE id = 1")) == "recorded"
            connection.execute(text(f"UPDATE patients SET {field} = NULL WHERE id = 1"))
