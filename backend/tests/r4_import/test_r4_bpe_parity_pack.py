from datetime import datetime, timezone

from app.scripts import r4_bpe_parity_pack as parity


def test_parse_patient_codes_csv_dedupes_and_trims():
    assert parity._parse_patient_codes_csv("1000035, 1000036,1000035") == [1000035, 1000036]


def test_parse_patient_codes_csv_rejects_empty_token():
    try:
        parity._parse_patient_codes_csv("1000035,,1000036")
    except RuntimeError as exc:
        assert "empty token" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_latest_match_uses_recorded_at_and_sextants():
    canonical = {
        "recorded_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "sextants": {
            "sextant_1": 3,
            "sextant_2": 2,
            "sextant_3": 1,
            "sextant_4": 0,
            "sextant_5": 2,
            "sextant_6": 3,
        },
    }
    sql = {
        "recorded_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "sextants": {
            "sextant_1": 3,
            "sextant_2": 2,
            "sextant_3": 1,
            "sextant_4": 0,
            "sextant_5": 2,
            "sextant_6": 3,
        },
    }
    assert parity._latest_match(canonical, sql) == {
        "recorded_at": True,
        "sextants": True,
        "all": True,
    }


def test_latest_match_reports_mismatch():
    canonical = {
        "recorded_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "sextants": {"sextant_1": 3},
    }
    sql = {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "sextants": {"sextant_1": 3},
    }
    assert parity._latest_match(canonical, sql) == {
        "recorded_at": False,
        "sextants": True,
        "all": False,
    }
