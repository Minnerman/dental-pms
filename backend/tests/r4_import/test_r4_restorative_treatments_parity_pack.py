from datetime import datetime

from app.scripts import r4_restorative_treatments_parity_pack as pack


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
                "recorded_at": "2025-01-01T00:00:00+00:00",
                "ref_id": 100,
                "tp_item_key": 200,
                "trans_code": 300,
                "tooth": 16,
                "surface": 20,
                "code_id": 400,
                "status_description": "Fillings",
                "description": "Composite filling",
                "complete": True,
                "completed": True,
            }
        ],
    )
    monkeypatch.setattr(
        pack,
        "_sqlserver_rows",
        lambda *args, **kwargs: [
            {
                "patient_code": 1001,
                "recorded_at": "2025-01-01T00:00:00+00:00",
                "ref_id": 100,
                "tp_item_key": 200,
                "trans_code": 300,
                "tooth": 16,
                "surface": 20,
                "code_id": 400,
                "status_description": "Fillings",
                "description": "Composite filling",
                "complete": True,
                "completed": True,
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
    assert patient["canonical_latest_key"]["ref_id"] == 100
    assert patient["sqlserver_latest_key"]["ref_id"] == 100
