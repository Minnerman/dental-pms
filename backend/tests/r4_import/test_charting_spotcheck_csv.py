import csv

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


def test_surface_definitions_normalization_maps_legacy_fields():
    rows = _normalize_entity_rows(
        "surface_definitions",
        [{"tooth_id": 11, "surface_no": 2, "label": "O"}],
        patient_code=1000,
    )
    assert rows[0]["legacy_tooth_id"] == 11
    assert rows[0]["legacy_surface_no"] == 2
