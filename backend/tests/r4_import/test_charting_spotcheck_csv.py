import csv
import json
from datetime import datetime, timezone

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.scripts import r4_charting_spotcheck
from app.scripts.r4_charting_spotcheck import (
    ENTITY_ALIASES,
    ENTITY_COLUMNS,
    ENTITY_SORT_KEYS,
    _normalize_entity_rows,
    _parse_entities,
    _sqlserver_treatment_notes,
    _rows_for_csv,
    _write_csv,
)


def test_csv_headers_and_deterministic_order(tmp_path):
    rows = [
        {
            "patient_code": 1000,
            "legacy_trans_id": 12,
            "recorded_at": "2024-01-02T00:00:00+00:00",
            "tooth": 14,
            "probing_point": 3,
            "depth": 5,
            "bleeding": 1,
            "plaque": 0,
            "legacy_probe_key": "12:14:3",
        },
        {
            "patient_code": 1000,
            "legacy_trans_id": 11,
            "recorded_at": "2024-01-01T00:00:00+00:00",
            "tooth": 13,
            "probing_point": 2,
            "depth": 4,
            "bleeding": 0,
            "plaque": 1,
            "legacy_probe_key": "11:13:2",
        },
    ]
    columns = ENTITY_COLUMNS["perio_probes"]
    sort_keys = ENTITY_SORT_KEYS["perio_probes"]
    path = tmp_path / "perio.csv"
    _write_csv(path, rows, columns, sort_keys)

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == columns
        records = list(reader)

    assert records[0]["legacy_trans_id"] == "11"
    assert records[1]["legacy_trans_id"] == "12"


def test_patient_code_in_csv_rows_for_both_sources():
    patient_code = 1000
    sqlserver_rows = _normalize_entity_rows(
        "perio_probes",
        [
            {
                "trans_id": 10,
                "tooth": 12,
                "probing_point": 1,
                "recorded_at": "2024-01-01T00:00:00+00:00",
                "patient_code": patient_code,
            }
        ],
        patient_code,
    )
    postgres_rows = _normalize_entity_rows(
        "perio_probes",
        [
            {
                "legacy_trans_id": 10,
                "legacy_probe_key": "10:12:1",
                "tooth": 12,
                "probing_point": 1,
                "recorded_at": "2024-01-01T00:00:00+00:00",
                "patient_code": patient_code,
            }
        ],
        patient_code,
    )

    columns = ENTITY_COLUMNS["perio_probes"]
    sqlserver_csv = _rows_for_csv(sqlserver_rows, columns, patient_code)
    postgres_csv = _rows_for_csv(postgres_rows, columns, patient_code)

    assert len(sqlserver_csv) == 1
    assert len(postgres_csv) == 1
    assert sqlserver_csv[0]["patient_code"] == patient_code
    assert postgres_csv[0]["patient_code"] == patient_code


def test_treatment_notes_call_uses_keyword_filters():
    class StubSource:
        def __init__(self):
            self.args = None
            self.kwargs = None

        def list_treatment_notes(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            return []

    source = StubSource()
    rows = _sqlserver_treatment_notes(source, patient_code=1015947, limit=50)

    assert rows == []
    assert source.args == ()
    assert source.kwargs == {
        "patients_from": 1015947,
        "patients_to": 1015947,
        "date_from": None,
        "date_to": None,
        "limit": 50,
    }


def test_surface_definitions_alias_parsing_is_backward_compatible():
    entities = _parse_entities("tooth_surfaces,surface_definitions", ENTITY_ALIASES)
    assert entities == ["surface_definitions"]


def test_treatment_plan_entity_aliases_parse_to_canonical_names():
    entities = _parse_entities(
        "treatment_plans,treatment_plan_item,treatment_plan_items",
        ENTITY_ALIASES,
    )
    assert entities == ["treatment_plans", "treatment_plan_items"]


def test_restorative_treatments_alias_parsing_is_backward_compatible():
    entities = _parse_entities(
        "restorative_treatment,restorative_treatments",
        ENTITY_ALIASES,
    )
    assert entities == ["restorative_treatments"]


def test_surface_definitions_normalization_maps_legacy_fields():
    rows = _normalize_entity_rows(
        "surface_definitions",
        [{"tooth_id": 11, "surface_no": 2, "label": "O"}],
        patient_code=1000,
    )
    assert rows[0]["legacy_tooth_id"] == 11
    assert rows[0]["legacy_surface_no"] == 2


def test_restorative_treatments_normalization_sets_recorded_at_fallback():
    rows = _normalize_entity_rows(
        "restorative_treatments",
        [{"completion_date": "2025-01-02T00:00:00+00:00", "patient_code": 1000}],
        patient_code=1000,
    )
    assert rows[0]["recorded_at"] == "2025-01-02T00:00:00+00:00"


def test_spotcheck_json_reads_tp_tpi_postgres_from_canonical_records(monkeypatch, capsys):
    patient_code = 991014496
    session = SessionLocal()
    try:
        session.execute(
            delete(R4ChartingCanonicalRecord).where(
                R4ChartingCanonicalRecord.unique_key.like("test-stage151-%")
            )
        )
        session.add(
            R4ChartingCanonicalRecord(
                unique_key=f"test-stage151-plan-{patient_code}-1",
                domain="treatment_plan",
                r4_source="dbo.TreatmentPlans",
                r4_source_id=f"{patient_code}:1",
                legacy_patient_code=patient_code,
                recorded_at=datetime(2019, 4, 1, 14, 44, 14, tzinfo=timezone.utc),
                entered_at=datetime(2019, 4, 1, 15, 1, 25, tzinfo=timezone.utc),
                payload={
                    "patient_code": patient_code,
                    "tp_number": 1,
                    "treatment_plan_id": 23849,
                    "plan_index": 1,
                    "is_master": False,
                    "is_current": False,
                    "is_accepted": False,
                    "creation_date": "2019-04-01T14:44:14+00:00",
                    "acceptance_date": "2019-04-01T15:01:25+00:00",
                    "completion_date": "2019-08-01T12:37:37+00:00",
                    "status_code": 2,
                    "reason_id": None,
                    "tp_group": 1,
                },
            )
        )
        session.add_all(
            [
                R4ChartingCanonicalRecord(
                    unique_key=f"test-stage151-item-{patient_code}-59603",
                    domain="treatment_plan_item",
                    r4_source="dbo.TreatmentPlanItems",
                    r4_source_id="59603",
                    legacy_patient_code=patient_code,
                    recorded_at=datetime(2019, 4, 1, 15, 1, 14, tzinfo=timezone.utc),
                    payload={
                        "patient_code": patient_code,
                        "tp_number": 1,
                        "tp_item": 1,
                        "tp_item_key": 59603,
                        "code_id": 3599,
                        "tooth": 15,
                        "surface": 0,
                        "completed": False,
                        "completed_date": None,
                    },
                ),
                R4ChartingCanonicalRecord(
                    unique_key=f"test-stage151-item-{patient_code}-59604",
                    domain="treatment_plan_item",
                    r4_source="dbo.TreatmentPlanItems",
                    r4_source_id="59604",
                    legacy_patient_code=patient_code,
                    recorded_at=datetime(2019, 4, 1, 15, 1, 14, tzinfo=timezone.utc),
                    payload={
                        "patient_code": patient_code,
                        "tp_number": 1,
                        "tp_item": 2,
                        "tp_item_key": 59604,
                        "code_id": 3599,
                        "tooth": 16,
                        "surface": 0,
                        "completed": False,
                        "completed_date": None,
                    },
                ),
                R4ChartingCanonicalRecord(
                    unique_key=f"test-stage151-item-{patient_code}-59605",
                    domain="treatment_plan_item",
                    r4_source="dbo.TreatmentPlanItems",
                    r4_source_id="59605",
                    legacy_patient_code=patient_code,
                    recorded_at=datetime(2019, 4, 1, 15, 1, 21, tzinfo=timezone.utc),
                    payload={
                        "patient_code": patient_code,
                        "tp_number": 1,
                        "tp_item": 3,
                        "tp_item_key": 59605,
                        "code_id": 3600,
                        "tooth": 0,
                        "surface": 0,
                        "completed": True,
                        "completed_date": None,
                    },
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    class _DummyConfig:
        @staticmethod
        def from_env():
            return _DummyConfig()

        def require_enabled(self):
            return None

    class _DummySource:
        def __init__(self, _config):
            pass

        def list_treatment_plans(self, **_kwargs):
            return []

        def list_treatment_plan_items(self, **_kwargs):
            return []

    monkeypatch.setattr(r4_charting_spotcheck, "R4SqlServerConfig", _DummyConfig)
    monkeypatch.setattr(r4_charting_spotcheck, "R4SqlServerSource", _DummySource)
    monkeypatch.setattr(r4_charting_spotcheck, "mapping_exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "r4_charting_spotcheck.py",
            "--patient-code",
            str(patient_code),
            "--entities",
            "treatment_plans,treatment_plan_items",
            "--format",
            "json",
            "--limit",
            "5000",
        ],
    )

    try:
        assert r4_charting_spotcheck.main() == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["postgres"]["treatment_plans"]) == 1
        assert len(payload["postgres"]["treatment_plan_items"]) == 3
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.execute(
                delete(R4ChartingCanonicalRecord).where(
                    R4ChartingCanonicalRecord.unique_key.like("test-stage151-%")
                )
            )
            cleanup.commit()
        finally:
            cleanup.close()
