from datetime import date, datetime, timezone

from app.scripts import r4_chart_healing_actions_parity_pack as pack
from app.services.r4_import.types import R4ChartHealingAction


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


def test_latest_key_and_digest_shape():
    row = {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "action_id": 42,
        "tp_number": 3,
        "tp_item": 1,
        "code_id": 200,
        "tooth": 11,
        "surface": 2,
        "status": "open",
        "action_type": "review",
        "notes": "ignored",
    }

    assert pack._latest_key(row) == {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "action_id": 42,
    }
    assert pack._latest_digest(row) == {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "tp_number": 3,
        "tp_item": 1,
        "code_id": 200,
        "tooth": 11,
        "surface": 2,
        "status": "open",
        "action_type": "review",
    }


def test_sqlserver_rows_applies_date_window_and_maps_fields():
    class _Source:
        def list_chart_healing_actions(self, **_kwargs):
            return [
                R4ChartHealingAction(
                    action_id=20,
                    patient_code=1001,
                    tp_number=3,
                    tp_item=1,
                    code_id=200,
                    action_date=datetime(2025, 1, 2, 9, 0, tzinfo=timezone.utc),
                    action_type="review",
                    tooth=11,
                    surface=2,
                    status="open",
                ),
                R4ChartHealingAction(
                    action_id=21,
                    patient_code=1001,
                    tp_number=3,
                    tp_item=2,
                    code_id=201,
                    action_date=datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc),
                    action_type="out-of-window",
                    tooth=12,
                    surface=1,
                    status="closed",
                ),
                R4ChartHealingAction(
                    action_id=22,
                    patient_code=1001,
                    action_date=None,
                    action_type="undated",
                ),
            ]

    rows = pack._sqlserver_rows(
        _Source(),
        patient_code=1001,
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
    )

    assert rows == [
        {
            "patient_code": 1001,
            "action_id": 20,
            "recorded_at": datetime(2025, 1, 2, 9, 0, tzinfo=timezone.utc).isoformat(),
            "tp_number": 3,
            "tp_item": 1,
            "code_id": 200,
            "tooth": 11,
            "surface": 2,
            "status": "open",
            "action_type": "review",
        }
    ]


def test_build_parity_report_compares_latest_key_and_digest(monkeypatch):
    monkeypatch.setattr(pack.R4SqlServerConfig, "from_env", staticmethod(lambda: _DummyCfg()))
    monkeypatch.setattr(pack, "R4SqlServerSource", _DummySource)

    def _canonical_rows(_session, patient_code, **_kwargs):
        if patient_code == 1001:
            return [
                {
                    "patient_code": 1001,
                    "action_id": 10,
                    "recorded_at": "2025-01-01T09:00:00+00:00",
                    "tp_number": 1,
                    "tp_item": 2,
                    "code_id": 300,
                    "tooth": 11,
                    "surface": 1,
                    "status": "open",
                    "action_type": "review",
                }
            ]
        return [
            {
                "patient_code": 1002,
                "action_id": 11,
                "recorded_at": "2025-01-02T09:00:00+00:00",
                "tp_number": 1,
                "tp_item": 3,
                "code_id": 301,
                "tooth": 12,
                "surface": 2,
                "status": "open",
                "action_type": "heal",
            }
        ]

    def _sql_rows(_source, patient_code, **_kwargs):
        if patient_code == 1001:
            return [
                {
                    "patient_code": 1001,
                    "action_id": 10,
                    "recorded_at": "2025-01-01T09:00:00+00:00",
                    "tp_number": 1,
                    "tp_item": 2,
                    "code_id": 300,
                    "tooth": 11,
                    "surface": 1,
                    "status": "open",
                    "action_type": "review",
                }
            ]
        return [
            {
                "patient_code": 1002,
                "action_id": 11,
                "recorded_at": "2025-01-02T09:00:00+00:00",
                "tp_number": 1,
                "tp_item": 3,
                "code_id": 301,
                "tooth": 12,
                "surface": 2,
                "status": "closed",
                "action_type": "heal",
            }
        ]

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

    patients = {patient["patient_code"]: patient for patient in report["patients"]}

    assert patients[1001]["latest_match"] is True
    assert patients[1001]["latest_digest_match"] is True
    assert patients[1002]["latest_match"] is True
    assert patients[1002]["latest_digest_match"] is False
