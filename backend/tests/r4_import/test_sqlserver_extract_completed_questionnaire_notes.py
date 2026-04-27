from datetime import date, datetime

from app.services.r4_charting import sqlserver_extract as extract
from app.services.r4_import.types import R4CompletedQuestionnaireNote


def test_collect_canonical_records_completed_questionnaire_notes_filters_and_maps():
    class DummySource:
        def __init__(self, _config=None):
            self._config = _config

        def list_completed_questionnaire_notes(
            self, patients_from=None, patients_to=None, limit=None
        ):
            rows = [
                R4CompletedQuestionnaireNote(
                    patient_code=None,
                    source_row_id=1,
                    note="valid but missing patient",
                    completed_at=datetime(2025, 1, 2, 9, 0, 0),
                ),
                R4CompletedQuestionnaireNote(
                    patient_code=1001,
                    source_row_id=2,
                    note="missing date",
                    completed_at=None,
                ),
                R4CompletedQuestionnaireNote(
                    patient_code=1001,
                    source_row_id=3,
                    note="out of window",
                    completed_at=datetime(2026, 2, 1, 0, 0, 0),
                ),
                R4CompletedQuestionnaireNote(
                    patient_code=1001,
                    source_row_id=4,
                    note="   ",
                    completed_at=datetime(2025, 1, 3, 9, 0, 0),
                ),
                R4CompletedQuestionnaireNote(
                    patient_code=1001,
                    source_row_id=5,
                    note="First questionnaire note",
                    completed_at=datetime(2025, 1, 4, 9, 0, 0),
                ),
                R4CompletedQuestionnaireNote(
                    patient_code=1001,
                    source_row_id=5,
                    note="Duplicate source row id",
                    completed_at=datetime(2025, 1, 4, 10, 0, 0),
                ),
                R4CompletedQuestionnaireNote(
                    patient_code=1002,
                    source_row_id=None,
                    note="Second questionnaire note",
                    completed_at=datetime(2025, 1, 5, 9, 0, 0),
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
        domains=["completed_questionnaire_notes"],
        limit=100,
    )

    assert len(records) == 2
    assert {record.legacy_patient_code for record in records} == {1001, 1002}
    for record in records:
        assert record.domain == "completed_questionnaire_note"
        assert record.r4_source == "dbo.CompletedQuestionnaire"
        assert isinstance(record.payload, dict)
        assert record.payload["note"]
        assert record.payload["note"] == record.payload["note"].strip()

    first = next(record for record in records if record.legacy_patient_code == 1001)
    assert first.r4_source_id == "rowid:5"
    assert first.payload["source_row_id"] == 5

    second = next(record for record in records if record.legacy_patient_code == 1002)
    assert second.payload["source_row_id"] is None
    assert second.r4_source_id.startswith("1002:")

    assert dropped["missing_patient_code"] == 0
    assert dropped["missing_date"] == 1
    assert dropped["out_of_window"] == 1
    assert dropped["blank_note"] == 1
    assert dropped["duplicate_key"] == 1
    assert dropped["accepted_nonblank_note"] == 2
    assert dropped["accepted_blank_note"] == 1
    assert dropped["included"] == 2


def test_collect_canonical_records_completed_questionnaire_notes_domain_alias():
    class DummySource:
        def __init__(self, _config=None):
            self._config = _config

        def list_completed_questionnaire_notes(self, **_kwargs):
            return [
                R4CompletedQuestionnaireNote(
                    patient_code=1003,
                    source_row_id=77,
                    note="Completed questionnaire note",
                    completed_at=datetime(2025, 2, 1, 10, 0, 0),
                )
            ]

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = DummySource()

    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1003],
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        domains=["completed_questionnaire_note"],
        limit=10,
    )

    assert len(records) == 1
    assert records[0].domain == "completed_questionnaire_note"
    assert dropped["included"] == 1


def test_get_distinct_completed_questionnaire_notes_patient_codes_filters_nonblank(
    monkeypatch,
):
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
            if table != "CompletedQuestionnaire":
                return None
            for candidate in candidates:
                if candidate in {"PatientCode", "patientcode"}:
                    return "PatientCode"
                if candidate in {"DateTime", "Date"}:
                    return "DateTime"
                if candidate in {"Notes", "Note"}:
                    return "Notes"
            return None

        def _query(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return [
                {"patient_code": 3001},
                {"patient_code": 3002},
                {"patient_code": 3001},
            ]

    monkeypatch.setattr(extract.R4SqlServerConfig, "from_env", lambda: DummyConfig())
    monkeypatch.setattr(extract, "R4SqlServerSource", DummySource)

    result = extract.get_distinct_completed_questionnaire_notes_patient_codes(
        "2017-01-01", "2026-02-01", limit=5
    )

    assert result == [3001, 3002]
    assert "FROM dbo.CompletedQuestionnaire" in captured["query"]
    assert "LEN(LTRIM(RTRIM(CAST(Notes AS NVARCHAR(MAX))))) > 0" in captured["query"]
    assert captured["params"][0] == 5
