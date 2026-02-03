from datetime import datetime

from app.scripts import r4_treatment_plans_parity_pack as pack


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


def test_build_parity_report_latest_key_and_digest_match(monkeypatch):
    monkeypatch.setattr(pack.R4SqlServerConfig, "from_env", staticmethod(lambda: _DummyCfg()))
    monkeypatch.setattr(pack, "R4SqlServerSource", _DummySource)
    monkeypatch.setattr(
        pack,
        "_canonical_rows",
        lambda *args, **kwargs: [
            {
                "patient_code": 1001,
                "tp_number": 1,
                "treatment_plan_id": 100,
                "recorded_at": "2025-01-01T00:00:00+00:00",
                "accepted_at": None,
                "completed_at": None,
                "status_code": 10,
                "is_current": True,
                "is_accepted": False,
                "is_master": True,
            },
            {
                "patient_code": 1001,
                "tp_number": 2,
                "treatment_plan_id": 101,
                "recorded_at": "2025-02-01T00:00:00+00:00",
                "accepted_at": "2025-02-02T00:00:00+00:00",
                "completed_at": None,
                "status_code": 20,
                "is_current": True,
                "is_accepted": True,
                "is_master": False,
            },
        ],
    )
    monkeypatch.setattr(
        pack,
        "_sqlserver_rows",
        lambda *args, **kwargs: [
            {
                "patient_code": 1001,
                "tp_number": 2,
                "treatment_plan_id": 101,
                "recorded_at": "2025-02-01T00:00:00+00:00",
                "accepted_at": "2025-02-02T00:00:00+00:00",
                "completed_at": None,
                "status_code": 20,
                "is_current": True,
                "is_accepted": True,
                "is_master": False,
            }
        ],
    )

    report = pack.build_parity_report(
        session=object(),
        patient_codes=[1001],
        date_from=datetime(2024, 1, 1).date(),
        date_to=datetime(2026, 1, 1).date(),
        row_limit=100,
        include_sqlserver=True,
    )

    patient = report["patients"][0]
    assert patient["latest_match"] is True
    assert patient["latest_digest_match"] is True
    assert patient["canonical_latest_key"]["treatment_plan_id"] == 101
    assert patient["sqlserver_latest_key"]["treatment_plan_id"] == 101
