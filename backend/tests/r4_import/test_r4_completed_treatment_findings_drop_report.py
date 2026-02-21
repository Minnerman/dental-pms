from datetime import date, datetime

from app.scripts import r4_completed_treatment_findings_drop_report as drop_report
from app.services.r4_import.types import R4CompletedTreatmentFinding


class _DummyCfg:
    def require_enabled(self):
        return None

    def require_readonly(self):
        return None


class _DummySource:
    def __init__(self, _cfg):
        self._cfg = _cfg

    def ensure_select_only(self):
        return None

    def list_completed_treatment_findings(self, **kwargs):
        return [
            R4CompletedTreatmentFinding(
                patient_code=1001,
                completed_date=datetime(2025, 1, 1, 9, 0, 0),
                tooth=11,
                code_id=500,
                treatment_label="Soft Tissue Examination",
                ref_id=100,
            ),
            R4CompletedTreatmentFinding(
                patient_code=1001,
                completed_date=datetime(2025, 1, 2, 9, 0, 0),
                tooth=11,
                code_id=501,
                treatment_label="Crown",
                ref_id=101,
            ),
            R4CompletedTreatmentFinding(
                patient_code=1001,
                completed_date=datetime(2025, 1, 3, 9, 0, 0),
                tooth=11,
                code_id=None,
                treatment_label="Soft Tissue Examination",
                ref_id=102,
            ),
            R4CompletedTreatmentFinding(
                patient_code=1001,
                completed_date=datetime(2025, 1, 4, 9, 0, 0),
                tooth=12,
                code_id=502,
                treatment_label="Soft Tissue Examination",
                ref_id=100,
            ),
        ]


class _DummyRecord:
    def __init__(self, recorded_at, payload, status=None):
        self.recorded_at = recorded_at
        self.payload = payload
        self.status = status


class _DummyScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _DummyExecResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _DummyScalarResult(self._rows)


class _DummySession:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _stmt):
        return _DummyExecResult(self._rows)


def test_build_drop_report_counts_sql_and_pg_and_reasons(monkeypatch):
    monkeypatch.setattr(drop_report.R4SqlServerConfig, "from_env", staticmethod(lambda: _DummyCfg()))
    monkeypatch.setattr(drop_report, "R4SqlServerSource", _DummySource)

    def _fake_canonical_report(*_args, **_kwargs):
        class _Stats:
            def as_dict(self):
                return {"created": 0, "updated": 0, "skipped": 0, "unmapped_patients": 0, "total": 1}

        return _Stats(), {
            "total_records": 1,
            "dropped": {
                "restorative_classified": 1,
                "missing_code_id": 1,
                "duplicate_key": 1,
            },
        }

    monkeypatch.setattr(drop_report, "import_r4_charting_canonical_report", _fake_canonical_report)
    monkeypatch.setattr(drop_report, "SqlServerChartingExtractor", lambda _cfg: object())

    session = _DummySession(
        [
            _DummyRecord(
                datetime(2025, 1, 1, 9, 0, 0),
                {
                    "treatment_label": "Soft Tissue Examination",
                    "status": "completed",
                },
                status="completed",
            )
        ]
    )
    payload = drop_report.build_drop_report(
        session,
        patient_code=1001,
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
    )

    assert payload["sql_count"] == 1
    assert payload["pg_count"] == 1
    assert payload["delta_sql_minus_pg"] == 0
    assert payload["sql_dropped_reasons"]["restorative_classified"] == 1
    assert payload["sql_dropped_reasons"]["missing_code_id"] == 1
    assert payload["sql_dropped_reasons"]["duplicate_key"] == 1
    assert payload["dropped_reasons"]["restorative_classified"] == 1
    assert payload["dropped_reasons"]["missing_code_id"] == 1
    assert payload["dropped_reasons"]["duplicate_key"] == 1
    assert payload["pg_rows_by_status"]["completed"] == 1
    assert payload["pg_rows_by_type"]["other"] == 1
