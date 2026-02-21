import json
from datetime import date
from pathlib import Path

from app.scripts import r4_parity_run
from app.scripts import r4_restorative_treatments_parity_pack as restorative_pack

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "r4"
    / "restorative_parity_smoke_patients.json"
)


class _DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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


def _row(patient_code: int) -> dict[str, object]:
    return {
        "patient_code": patient_code,
        "recorded_at": "2025-01-01T00:00:00+00:00",
        "ref_id": patient_code * 10,
        "tp_item_key": patient_code * 100,
        "trans_code": patient_code * 1000,
        "code_id": 7000 + (patient_code % 1000),
        "tooth": 16,
        "surface": 20,
        "status_description": "Fillings",
        "description": "MOD composite filling",
        "complete": True,
        "completed": True,
    }


def test_restorative_parity_smoke_pinned_fixture(monkeypatch, tmp_path: Path):
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    patient_codes = [int(code) for code in payload["legacy_patient_codes"]]
    no_data_code = int(payload["no_data_legacy_patient_code"])
    assert len(patient_codes) == 5

    def _canonical_rows(_session, patient_code: int, **_kwargs):
        if patient_code == no_data_code:
            return []
        return [_row(patient_code)]

    def _sql_rows(_source, patient_code: int, **_kwargs):
        if patient_code == no_data_code:
            return []
        return [_row(patient_code)]

    monkeypatch.setattr(r4_parity_run, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(restorative_pack.R4SqlServerConfig, "from_env", staticmethod(lambda: _DummyCfg()))
    monkeypatch.setattr(restorative_pack, "R4SqlServerSource", _DummySource)
    monkeypatch.setattr(restorative_pack, "_canonical_rows", _canonical_rows)
    monkeypatch.setattr(restorative_pack, "_sqlserver_rows", _sql_rows)

    report = r4_parity_run.run_parity(
        patient_codes=patient_codes,
        domains=["restorative_treatments"],
        date_from=date(2017, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=200,
        output_dir=str(tmp_path),
    )

    assert report["overall"]["status"] == "pass"
    summary = report["domain_summaries"]["restorative_treatments"]
    assert summary["patients_total"] == 5
    assert "patients_with_data" in summary
    assert "patients_no_data" in summary
    assert summary["patients_with_data"] + summary["patients_no_data"] == 5
    assert (tmp_path / "restorative_treatments.json").exists()
