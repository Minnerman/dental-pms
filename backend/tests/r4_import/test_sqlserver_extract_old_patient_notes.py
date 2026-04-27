from datetime import date, datetime

from app.services.r4_charting import sqlserver_extract as extract
from app.services.r4_import.types import R4OldPatientNote


def test_collect_canonical_records_old_patient_notes_filters_and_maps():
    class DummySource:
        def list_old_patient_notes(self, patients_from=None, patients_to=None, limit=None):
            rows = [
                R4OldPatientNote(
                    patient_code=1001,
                    note_number=7,
                    note_date=datetime(2025, 1, 4, 9, 0, 0),
                    note="Old note",
                    tooth=16,
                    surface=2,
                    category_number=10,
                    fixed_note_code=500,
                    user_code=700,
                ),
                R4OldPatientNote(
                    patient_code=1001,
                    note_number=8,
                    note_date=datetime(2001, 1, 4, 9, 0, 0),
                    note="Out of range",
                ),
                R4OldPatientNote(
                    patient_code=1002,
                    note_number=None,
                    note_date=datetime(2025, 1, 5, 9, 0, 0),
                    note="Fallback source id",
                ),
                R4OldPatientNote(
                    patient_code=1002,
                    note_number=9,
                    note_date=None,
                    note="Missing date",
                ),
            ]
            if patients_from is not None and patients_to is not None:
                rows = [
                    row
                    for row in rows
                    if row.patient_code is not None and patients_from <= row.patient_code <= patients_to
                ]
            if limit is not None:
                rows = rows[:limit]
            return rows

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = DummySource()

    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1001, 1002],
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        domains=["old_patient_notes"],
        limit=100,
    )

    assert len(records) == 2
    first = next(record for record in records if record.legacy_patient_code == 1001)
    assert first.domain == "old_patient_note"
    assert first.r4_source == "dbo.OldPatientNotes"
    assert first.r4_source_id == "7"
    assert first.recorded_at == datetime(2025, 1, 4, 9, 0, 0)
    assert first.tooth == 16
    assert first.surface == 2
    assert first.code_id == 500
    assert first.payload["category_number"] == 10
    assert first.payload["user_code"] == 700

    second = next(record for record in records if record.legacy_patient_code == 1002)
    assert second.r4_source_id.startswith("1002:2025-01-05 09:00:00:")
    assert second.payload["note"] == "Fallback source id"

    assert dropped["out_of_range"] == 1
    assert dropped["missing_date"] == 1


def test_collect_canonical_records_old_patient_notes_domain_alias():
    class DummySource:
        def list_old_patient_notes(self, **_kwargs):
            return [
                R4OldPatientNote(
                    patient_code=1003,
                    note_number=77,
                    note_date=datetime(2025, 2, 1, 10, 0, 0),
                    note="Old patient note",
                )
            ]

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = DummySource()

    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1003],
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        domains=["old_patient_note"],
        limit=10,
    )

    assert len(records) == 1
    assert records[0].domain == "old_patient_note"
    assert dropped["missing_date"] == 0


def test_get_distinct_old_patient_notes_patient_codes_dedupes_and_orders(monkeypatch):
    captured = {}

    class DummyConfig:
        def require_enabled(self):
            return None

        def require_readonly(self):
            return None

    class DummySource:
        def __init__(self, _config):
            self._config = _config

        def ensure_select_only(self):
            return None

        def _pick_column(self, table, candidates):
            if table != "OldPatientNotes":
                return None
            for candidate in candidates:
                if candidate == "PatientCode":
                    return "PatientCode"
                if candidate in {"Date", "NoteDate"}:
                    return "Date"
            return None

        def _query(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return [
                {"patient_code": 201},
                {"patient_code": 202},
                {"patient_code": 201},
            ]

    monkeypatch.setattr(extract.R4SqlServerConfig, "from_env", lambda: DummyConfig())
    monkeypatch.setattr(extract, "R4SqlServerSource", DummySource)

    result = extract.get_distinct_old_patient_notes_patient_codes(
        "2017-01-01", "2026-02-01", limit=5
    )
    assert result == [201, 202]
    assert "FROM dbo.OldPatientNotes" in captured["query"]
    assert captured["params"][0] == 5
