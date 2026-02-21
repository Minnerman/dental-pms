from datetime import date, datetime

from app.scripts import r4_completed_treatment_findings_parity_pack as pack
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


def test_build_parity_report_includes_overall_summary(monkeypatch):
    monkeypatch.setattr(pack.R4SqlServerConfig, "from_env", staticmethod(lambda: _DummyCfg()))
    monkeypatch.setattr(pack, "R4SqlServerSource", _DummySource)

    def _canonical_rows(_session, patient_code, **_kwargs):
        if patient_code == 1001:
            return [
                {
                    "patient_code": 1001,
                    "recorded_at": "2025-01-01T09:00:00+00:00",
                    "source_id": "ref:10",
                    "ref_id": 10,
                    "tp_number": 1,
                    "tp_item": 2,
                    "code_id": 500,
                    "tooth": 11,
                    "treatment_label": "Soft Tissue Examination",
                }
            ]
        return []

    def _sql_rows(_source, patient_code, **_kwargs):
        if patient_code == 1001:
            return [
                {
                    "patient_code": 1001,
                    "recorded_at": "2025-01-01T09:00:00+00:00",
                    "source_id": "ref:10",
                    "ref_id": 10,
                    "tp_number": 1,
                    "tp_item": 2,
                    "code_id": 500,
                    "tooth": 11,
                    "treatment_label": "Soft Tissue Examination",
                }
            ], {"included": 1}, 1
        return [], {"out_of_window": 2}, 2

    monkeypatch.setattr(pack, "_canonical_rows", _canonical_rows)
    monkeypatch.setattr(pack, "_sqlserver_rows", _sql_rows)

    report = pack.build_parity_report(
        session=object(),
        patient_codes=[1001, 1002],
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
        include_sqlserver=True,
    )

    assert report["patients_with_data"] == 1
    assert report["patients_no_data"] == 1
    assert report["overall"]["status"] == "pass"
    assert report["overall"]["latest_match"]["matched"] == 1
    assert report["overall"]["latest_digest_match"]["matched"] == 1


def test_sqlserver_rows_applies_missing_code_and_duplicate_filters_regression():
    class _Source:
        def list_completed_treatment_findings(self, **_kwargs):
            return [
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2025, 1, 2, 9, 0, 0),
                    tooth=11,
                    code_id=501,
                    treatment_label="Soft Tissue Examination",
                    ref_id=20,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2025, 1, 2, 10, 0, 0),
                    tooth=12,
                    code_id=502,
                    treatment_label="Soft Tissue Examination",
                    ref_id=20,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2025, 1, 3, 9, 0, 0),
                    tooth=13,
                    code_id=None,
                    treatment_label="Soft Tissue Examination",
                    ref_id=21,
                ),
            ]

    rows, dropped, candidates = pack._sqlserver_rows(
        _Source(),
        patient_code=1001,
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
    )

    assert candidates == 3
    assert len(rows) == 1
    assert rows[0]["source_id"] == "ref:20"
    assert dropped["missing_code_id"] == 1
    assert dropped["duplicate_key"] == 1
    assert dropped["included"] == 1
