from datetime import date

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
