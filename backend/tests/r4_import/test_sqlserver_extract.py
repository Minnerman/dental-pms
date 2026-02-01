from datetime import date
from datetime import datetime

from app.services.r4_charting import sqlserver_extract as extract


def test_get_distinct_bpe_patient_codes_dedupes_and_orders(monkeypatch):
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
            if table != "BPE":
                return None
            for candidate in candidates:
                if candidate == "PatientCode":
                    return "PatientCode"
                if candidate == "Date":
                    return "Date"
            return None

        def _query(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return [
                {"patient_code": 1000035},
                {"patient_code": 1000036},
                {"patient_code": 1000035},  # duplicate to verify output dedupe safety
                {"patient_code": None},
                {"patient_code": 1000037},
            ]

    monkeypatch.setattr(extract.R4SqlServerConfig, "from_env", lambda: DummyConfig())
    monkeypatch.setattr(extract, "R4SqlServerSource", DummySource)

    result = extract.get_distinct_bpe_patient_codes("2017-01-01", "2026-02-01", limit=5)

    assert result == [1000035, 1000036, 1000037]
    assert all(isinstance(code, int) for code in result)
    assert "GROUP BY PatientCode" in captured["query"]
    assert "ORDER BY MAX(Date) DESC, PatientCode ASC" in captured["query"]
    assert captured["params"][0] == 5
    assert captured["params"][1] == date(2017, 1, 1)
    assert captured["params"][2] == date(2026, 2, 1)


def test_get_distinct_bpe_patient_codes_rejects_invalid_window(monkeypatch):
    class DummyConfig:
        def require_enabled(self):
            return None

        def require_readonly(self):
            return None

    monkeypatch.setattr(extract.R4SqlServerConfig, "from_env", lambda: DummyConfig())
    try:
        extract.get_distinct_bpe_patient_codes("2026-02-01", "2017-01-01", limit=50)
    except ValueError as exc:
        assert "charting_to" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for invalid date window")


class DummyNote:
    def __init__(self, patient_code, note_number, note_date, note):
        self.patient_code = patient_code
        self.note_number = note_number
        self.note_date = note_date
        self.note = note
        self.tooth = None
        self.surface = None
        self.category_number = None
        self.fixed_note_code = None
        self.user_code = None

    def model_dump(self):
        return {
            "patient_code": self.patient_code,
            "note_number": self.note_number,
            "note_date": self.note_date,
            "note": self.note,
            "tooth": self.tooth,
            "surface": self.surface,
            "category_number": self.category_number,
            "fixed_note_code": self.fixed_note_code,
            "user_code": self.user_code,
        }


class DummySourceForNotes:
    def list_bpe_entries(self, patients_from=None, patients_to=None, limit=None):
        return []

    def list_perio_probes(self, patients_from=None, patients_to=None, limit=None):
        return []

    def list_patient_notes(self, patients_from=None, patients_to=None, limit=None):
        assert patients_from is not None
        assert patients_to is not None
        assert patients_from == patients_to
        rows = [
            DummyNote(
                patients_from,
                7,
                datetime(2025, 1, 10, 10, 0, 0),
                "in range",
            ),
            DummyNote(
                patients_from,
                8,
                datetime(2001, 1, 1, 10, 0, 0),
                "out of range",
            ),
        ]
        if limit is None:
            return rows
        return rows[:limit]


def test_collect_canonical_records_includes_patient_notes_with_date_bounds():
    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = DummySourceForNotes()
    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1016312],
        date_from=date(2010, 1, 1),
        date_to=date(2026, 2, 1),
        limit=10,
    )
    assert len(records) == 1
    row = records[0]
    assert row.domain == "patient_note"
    assert row.r4_source == "dbo.PatientNotes"
    assert row.r4_source_id == "7"
    assert dropped["out_of_range"] == 1


def test_collect_canonical_records_patient_note_source_id_fallback_when_note_number_missing():
    class MissingNumberSource(DummySourceForNotes):
        def list_patient_notes(self, patients_from=None, patients_to=None, limit=None):
            return [
                DummyNote(
                    patients_from,
                    None,
                    datetime(2023, 5, 1, 9, 0, 0),
                    "fallback note id",
                )
            ]

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = MissingNumberSource()
    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1016312],
        date_from=date(2010, 1, 1),
        date_to=date(2026, 2, 1),
        limit=10,
    )
    assert len(records) == 1
    assert records[0].r4_source_id.startswith("1016312:2023-05-01 09:00:00:")
    assert dropped["missing_date"] == 0
