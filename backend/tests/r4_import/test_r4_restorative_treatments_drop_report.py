import json
import sys
from datetime import date, datetime, timezone

from app.scripts import r4_restorative_treatments_drop_report as drop_report


class _DummyItem:
    def __init__(self, recorded_at=None, completion_date=None, transaction_date=None, creation_date=None):
        self.recorded_at = recorded_at
        self.completion_date = completion_date
        self.transaction_date = transaction_date
        self.creation_date = creation_date


def test_sqlserver_restorative_count_respects_date_window():
    class _DummySource:
        def list_restorative_treatments(self, **kwargs):
            assert kwargs["patients_from"] == 1000487
            assert kwargs["patients_to"] == 1000487
            assert kwargs["include_not_completed"] is True
            assert kwargs["require_tooth"] is False
            assert kwargs["status_descriptions"] is None
            return [
                _DummyItem(recorded_at=datetime(2020, 1, 2, tzinfo=timezone.utc)),
                _DummyItem(completion_date=datetime(2015, 6, 1, tzinfo=timezone.utc)),
                _DummyItem(recorded_at=None),
            ]

    count = drop_report._sqlserver_restorative_count(
        _DummySource(),
        patient_code=1000487,
        date_from=date(2017, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
    )
    assert count == 1


def test_postgres_rows_breakdown_groups_status_and_type():
    class _DummyRecord:
        def __init__(self, *, recorded_at, payload=None, status=None, code_id=None):
            self.recorded_at = recorded_at
            self.payload = payload
            self.status = status
            self.code_id = code_id

    class _DummyResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _DummySession:
        def execute(self, _stmt):
            return _DummyResult(
                [
                    (
                        _DummyRecord(
                            recorded_at=datetime(2021, 3, 4, tzinfo=timezone.utc),
                            payload={"status_description": "Fillings"},
                            status=None,
                            code_id=11,
                        ),
                        "MOD composite filling",
                    ),
                    (
                        _DummyRecord(
                            recorded_at=datetime(2021, 3, 5, tzinfo=timezone.utc),
                            payload={},
                            status="Completed",
                            code_id=22,
                        ),
                        "Root canal treatment",
                    ),
                ]
            )

    count, by_status, by_type = drop_report._postgres_rows_breakdown(
        _DummySession(),
        patient_code=1000487,
        date_from=date(2017, 1, 1),
        date_to=date(2026, 2, 1),
    )
    assert count == 2
    assert by_status == {"completed": 1, "fillings": 1}
    assert by_type["filling"] == 1
    assert by_type["root_canal"] == 1


def test_build_drop_report_filters_non_numeric_dropped(monkeypatch):
    class _DummyCfg:
        def require_enabled(self):
            return None

        def require_readonly(self):
            return None

    class _DummySource:
        def __init__(self, cfg):
            self.cfg = cfg

        def ensure_select_only(self):
            return None

    monkeypatch.setattr(drop_report.R4SqlServerConfig, "from_env", staticmethod(lambda: _DummyCfg()))
    monkeypatch.setattr(drop_report, "R4SqlServerSource", _DummySource)
    monkeypatch.setattr(drop_report, "SqlServerChartingExtractor", lambda source: object())
    monkeypatch.setattr(
        drop_report,
        "_sqlserver_restorative_count",
        lambda *_args, **_kwargs: 45,
    )
    monkeypatch.setattr(
        drop_report,
        "_postgres_rows_breakdown",
        lambda *_args, **_kwargs: (
            28,
            {"fillings": 20, "completed": 8},
            {"filling": 24, "root_canal": 4},
        ),
    )
    monkeypatch.setattr(
        drop_report,
        "import_r4_charting_canonical_report",
        lambda *_args, **_kwargs: (
            object(),
            {
                "total_records": 30,
                "dropped": {
                    "restorative_missing_tooth": 7,
                    "restorative_missing_code_id": 5,
                    "duplicate_unique_key": 2,
                    "duplicate_unique_key_examples": ["x", "y"],
                },
            },
        ),
    )

    payload = drop_report.build_drop_report(
        session=object(),
        patient_code=1000487,
        date_from=date(2017, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=5000,
    )
    assert payload["sql_count"] == 45
    assert payload["pg_count"] == 28
    assert payload["canonical_dry_run_candidates"] == 30
    assert payload["dropped_reasons"] == {
        "duplicate_unique_key": 2,
        "restorative_missing_code_id": 5,
        "restorative_missing_tooth": 7,
    }


def test_main_writes_output_json(tmp_path, monkeypatch, capsys):
    output_path = tmp_path / "drop_report.json"

    class _DummySession:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(drop_report, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(
        drop_report,
        "build_drop_report",
        lambda *_args, **_kwargs: {
            "patient_code": 1000487,
            "sql_count": 45,
            "pg_count": 28,
            "dropped_reasons": {"restorative_missing_tooth": 7},
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_restorative_treatments_drop_report.py",
            "--patient-code",
            "1000487",
            "--date-from",
            "2017-01-01",
            "--date-to",
            "2026-02-01",
            "--output-json",
            str(output_path),
        ],
    )

    assert drop_report.main() == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["patient_code"] == 1000487
    assert payload["sql_count"] == 45
    assert payload["pg_count"] == 28

    printed = capsys.readouterr().out
    assert '"patient_code": 1000487' in printed
