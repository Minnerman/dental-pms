from datetime import date, datetime, timezone

from app.scripts import r4_perio_plaque_parity_pack as parity
from app.services.r4_import.types import R4PerioPlaque


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


def test_parse_patient_codes_csv_dedupes_and_trims():
    assert parity._parse_patient_codes_csv("1000035, 1000036,1000035") == [1000035, 1000036]


def test_parse_patient_codes_csv_rejects_empty_token():
    try:
        parity._parse_patient_codes_csv("1000035,,1000036")
    except RuntimeError as exc:
        assert "empty token" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_latest_key_prefers_date_plus_transid_when_available():
    row = {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "trans_id": 123,
    }
    assert parity._latest_key(row) == {
        "mode": "recorded_at+trans_id",
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "trans_id": 123,
    }


def test_latest_sort_falls_back_to_transid_when_undated():
    rows = [
        {"recorded_at": None, "trans_id": 100},
        {"recorded_at": None, "trans_id": 105},
    ]
    latest = max(rows, key=parity._latest_sort_tuple)
    assert latest["trans_id"] == 105


def test_digest_for_trans_is_sorted_and_stable():
    rows = [
        {"trans_id": 10, "tooth": 3, "plaque": 1, "bleeding": 0},
        {"trans_id": 10, "tooth": 2, "plaque": 0, "bleeding": 1},
    ]
    digest = parity._digest_for_trans(rows, 10)
    assert digest[0]["tooth"] == 2
    assert digest[1]["tooth"] == 3


def test_digest_for_trans_dedupes_duplicate_unique_keys():
    rows = [
        {"trans_id": 10, "tooth": 2, "plaque": 0, "bleeding": 1},
        {"trans_id": 10, "tooth": 2, "plaque": 0, "bleeding": 1},
        {"trans_id": 10, "tooth": 3, "plaque": 1, "bleeding": 0},
    ]
    digest = parity._digest_for_trans(rows, 10)
    assert len(digest) == 2
    assert digest[0]["tooth"] == 2
    assert digest[1]["tooth"] == 3


def test_sqlserver_rows_applies_date_window_and_maps_fields():
    class _Source:
        def list_perio_plaque(self, **_kwargs):
            return [
                R4PerioPlaque(
                    trans_id=20,
                    patient_code=1001,
                    tooth=11,
                    plaque=1,
                    bleeding=0,
                    recorded_at=datetime(2025, 1, 2, 9, 0, tzinfo=timezone.utc),
                ),
                R4PerioPlaque(
                    trans_id=21,
                    patient_code=1001,
                    tooth=12,
                    plaque=0,
                    bleeding=1,
                    recorded_at=datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc),
                ),
                R4PerioPlaque(
                    trans_id=22,
                    patient_code=1001,
                    tooth=13,
                    plaque=1,
                    bleeding=1,
                    recorded_at=None,
                ),
            ]

    rows = parity._sqlserver_rows(
        _Source(),
        patient_code=1001,
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
    )

    assert rows == [
        {
            "recorded_at": datetime(2025, 1, 2, 9, 0, tzinfo=timezone.utc).isoformat(),
            "trans_id": 20,
            "tooth": 11,
            "plaque": 1,
            "bleeding": 0,
        },
        {
            "recorded_at": None,
            "trans_id": 22,
            "tooth": 13,
            "plaque": 1,
            "bleeding": 1,
        },
    ]


def test_build_parity_report_compares_latest_key_and_digest(monkeypatch):
    monkeypatch.setattr(parity.R4SqlServerConfig, "from_env", staticmethod(lambda: _DummyCfg()))
    monkeypatch.setattr(parity, "R4SqlServerSource", _DummySource)

    def _canonical_rows(_session, patient_code, **_kwargs):
        if patient_code == 1001:
            return [
                {
                    "recorded_at": "2025-01-01T09:00:00+00:00",
                    "trans_id": 10,
                    "tooth": 11,
                    "plaque": 1,
                    "bleeding": 0,
                }
            ]
        return [
            {
                "recorded_at": "2025-01-02T09:00:00+00:00",
                "trans_id": 11,
                "tooth": 12,
                "plaque": 1,
                "bleeding": 0,
            }
        ]

    def _sql_rows(_source, patient_code, **_kwargs):
        if patient_code == 1001:
            return [
                {
                    "recorded_at": "2025-01-01T09:00:00+00:00",
                    "trans_id": 10,
                    "tooth": 11,
                    "plaque": 1,
                    "bleeding": 0,
                }
            ]
        return [
            {
                "recorded_at": "2025-01-02T09:00:00+00:00",
                "trans_id": 11,
                "tooth": 12,
                "plaque": 0,
                "bleeding": 0,
            }
        ]

    monkeypatch.setattr(parity, "_canonical_rows", _canonical_rows)
    monkeypatch.setattr(parity, "_sqlserver_rows", _sql_rows)

    report = parity.build_parity_report(
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
