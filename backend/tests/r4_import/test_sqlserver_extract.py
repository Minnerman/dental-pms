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


def test_get_distinct_perioprobe_patient_codes_dedupes_and_orders(monkeypatch):
    class DummyConfig:
        def require_enabled(self):
            return None

        def require_readonly(self):
            return None

    class DummyProbe:
        def __init__(self, patient_code, recorded_at):
            self.patient_code = patient_code
            self.recorded_at = recorded_at

    class DummyExtractor:
        def __init__(self, _config):
            self._config = _config

        def _iter_perio_probes(
            self,
            *,
            patients_from,
            patients_to,
            patient_codes,
            limit,
        ):
            assert patients_from is None
            assert patients_to is None
            assert patient_codes is None
            assert limit is None
            return [
                DummyProbe(1000003, datetime(2016, 12, 31, 10, 0, 0)),  # out of range
                DummyProbe(1000000, datetime(2025, 1, 1, 10, 0, 0)),
                DummyProbe(1000001, None),  # undated rows are included
                DummyProbe(1000000, datetime(2025, 1, 2, 10, 0, 0)),  # duplicate code
            ]

    monkeypatch.setattr(extract.R4SqlServerConfig, "from_env", lambda: DummyConfig())
    monkeypatch.setattr(extract, "SqlServerChartingExtractor", DummyExtractor)

    result = extract.get_distinct_perioprobe_patient_codes("2017-01-01", "2026-02-01", limit=5)

    assert result == [1000000, 1000001]


def test_get_distinct_patient_notes_patient_codes_dedupes_and_orders(monkeypatch):
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
            if table != "PatientNotes":
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
                {"patient_code": 101},
                {"patient_code": 102},
                {"patient_code": 101},
            ]

    monkeypatch.setattr(extract.R4SqlServerConfig, "from_env", lambda: DummyConfig())
    monkeypatch.setattr(extract, "R4SqlServerSource", DummySource)

    result = extract.get_distinct_patient_notes_patient_codes("2017-01-01", "2026-02-01", limit=5)
    assert result == [101, 102]
    assert "FROM dbo.PatientNotes" in captured["query"]
    assert captured["params"][0] == 5


def test_get_distinct_treatment_notes_patient_codes_dedupes_and_orders(monkeypatch):
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
            if table != "TreatmentNotes":
                return None
            for candidate in candidates:
                if candidate == "PatientCode":
                    return "PatientCode"
                if candidate in {"DateAdded", "Date"}:
                    return "DateAdded"
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

    result = extract.get_distinct_treatment_notes_patient_codes("2017-01-01", "2026-02-01", limit=5)
    assert result == [201, 202]
    assert "FROM dbo.TreatmentNotes" in captured["query"]
    assert captured["params"][0] == 5


def test_get_distinct_bpe_furcation_patient_codes_dedupes_and_orders(monkeypatch):
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
            if table == "BPE":
                for candidate in candidates:
                    if candidate == "PatientCode":
                        return "PatientCode"
                    if candidate == "Date":
                        return "Date"
                    if candidate in {"BPEID", "ID"}:
                        return "ID"
            if table == "BPEFurcation":
                for candidate in candidates:
                    if candidate == "BPEID":
                        return "BPEID"
            return None

        def _query(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return [
                {"patient_code": 1000035},
                {"patient_code": 1000036},
                {"patient_code": 1000035},
            ]

    monkeypatch.setattr(extract.R4SqlServerConfig, "from_env", lambda: DummyConfig())
    monkeypatch.setattr(extract, "R4SqlServerSource", DummySource)

    result = extract.get_distinct_bpe_furcation_patient_codes(
        "2017-01-01", "2026-02-01", limit=5
    )

    assert result == [1000035, 1000036]
    assert "FROM dbo.BPE b" in captured["query"]
    assert "JOIN dbo.BPEFurcation f" in captured["query"]
    assert "GROUP BY b.PatientCode" in captured["query"]
    assert captured["params"][0] == 5


def test_get_distinct_treatment_plan_items_patient_codes_uses_parent_plan_date(monkeypatch):
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
            if table == "TreatmentPlanItems":
                for candidate in candidates:
                    if candidate == "PatientCode":
                        return "PatientCode"
                    if candidate in {"TPNumber", "TPNum", "TPNo"}:
                        return "TPNumber"
            if table == "TreatmentPlans":
                for candidate in candidates:
                    if candidate == "PatientCode":
                        return "PatientCode"
                    if candidate in {"TPNumber", "TPNum", "TPNo"}:
                        return "TPNumber"
                    if candidate in {"CreationDate", "Date", "PlanDate"}:
                        return "CreationDate"
            return None

        def _query(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return [{"patient_code": 401}, {"patient_code": 402}, {"patient_code": 401}]

    monkeypatch.setattr(extract.R4SqlServerConfig, "from_env", lambda: DummyConfig())
    monkeypatch.setattr(extract, "R4SqlServerSource", DummySource)

    result = extract.get_distinct_treatment_plan_items_patient_codes(
        "2017-01-01", "2026-02-01", limit=5
    )

    assert result == [401, 402]
    assert "FROM dbo.TreatmentPlanItems ti" in captured["query"]
    assert "JOIN dbo.TreatmentPlans tp" in captured["query"]
    assert "MAX(tp.CreationDate)" in captured["query"]
    assert captured["params"][0] == 5


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

    def list_treatment_notes(
        self,
        patients_from=None,
        patients_to=None,
        date_from=None,
        date_to=None,
        limit=None,
    ):
        return []

    def list_treatment_plan_items(
        self,
        patients_from=None,
        patients_to=None,
        date_from=None,
        date_to=None,
        limit=None,
    ):
        return []

    def list_treatment_plans(
        self,
        patients_from=None,
        patients_to=None,
        date_from=None,
        date_to=None,
        include_undated=True,
        limit=None,
    ):
        return []


def test_collect_canonical_records_treatment_plan_items_use_plan_creation_date():
    class DummyItem:
        def __init__(
            self,
            patient_code,
            tp_number,
            tp_item,
            *,
            tp_item_key=None,
            item_date=None,
            completed_date=None,
            plan_creation_date=None,
        ):
            self.patient_code = patient_code
            self.tp_number = tp_number
            self.tp_item = tp_item
            self.tp_item_key = tp_item_key
            self.code_id = None
            self.tooth = None
            self.surface = None
            self.completed = False
            self.material = None
            self.arch_code = None
            self.item_date = item_date
            self.completed_date = completed_date
            self.plan_creation_date = plan_creation_date

        def model_dump(self):
            return {
                "patient_code": self.patient_code,
                "tp_number": self.tp_number,
                "tp_item": self.tp_item,
                "tp_item_key": self.tp_item_key,
                "item_date": self.item_date,
                "completed_date": self.completed_date,
                "plan_creation_date": self.plan_creation_date,
            }

    class ItemSource(DummySourceForNotes):
        def list_patient_notes(self, patients_from=None, patients_to=None, limit=None):
            return []

        def list_treatment_notes(
            self,
            patients_from=None,
            patients_to=None,
            date_from=None,
            date_to=None,
            limit=None,
        ):
            return []

        def list_treatment_plan_items(
            self,
            patients_from=None,
            patients_to=None,
            date_from=None,
            date_to=None,
            limit=None,
        ):
            assert date_from == date(2017, 1, 1)
            assert date_to == date(2026, 2, 1)
            return [
                DummyItem(
                    patients_from,
                    1,
                    1,
                    tp_item_key=9001,
                    item_date=datetime(2001, 5, 1, 9, 0, 0),
                    plan_creation_date=datetime(2025, 5, 1, 9, 0, 0),
                )
            ]

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = ItemSource()
    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1016312],
        date_from=date(2017, 1, 1),
        date_to=date(2026, 2, 1),
        limit=10,
    )

    items = [r for r in records if r.domain == "treatment_plan_item"]
    assert len(items) == 1
    assert items[0].recorded_at == datetime(2025, 5, 1, 9, 0, 0)
    assert dropped["out_of_range"] == 0


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


class DummyTreatmentNote:
    def __init__(self, patient_code, note_id, note_date, note):
        self.patient_code = patient_code
        self.note_id = note_id
        self.note_date = note_date
        self.note = note
        self.tp_number = 1
        self.tp_item = 1
        self.user_code = None

    def model_dump(self):
        return {
            "patient_code": self.patient_code,
            "note_id": self.note_id,
            "note_date": self.note_date,
            "note": self.note,
            "tp_number": self.tp_number,
            "tp_item": self.tp_item,
            "user_code": self.user_code,
        }


def test_collect_canonical_records_includes_treatment_notes_with_date_bounds():
    class TreatmentSource(DummySourceForNotes):
        def list_patient_notes(self, patients_from=None, patients_to=None, limit=None):
            return []

        def list_treatment_notes(
            self,
            patients_from=None,
            patients_to=None,
            date_from=None,
            date_to=None,
            limit=None,
        ):
            assert date_from == date(2010, 1, 1)
            assert date_to == date(2026, 2, 1)
            return [
                DummyTreatmentNote(
                    patients_from,
                    11,
                    datetime(2023, 5, 1, 9, 0, 0),
                    "in range",
                ),
            ]

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = TreatmentSource()
    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1016312],
        date_from=date(2010, 1, 1),
        date_to=date(2026, 2, 1),
        limit=10,
    )
    treatment = [r for r in records if r.r4_source == "dbo.TreatmentNotes"]
    assert len(treatment) == 1
    assert treatment[0].domain == "treatment_note"
    assert treatment[0].r4_source_id == "11"
    assert dropped["out_of_range"] == 0
