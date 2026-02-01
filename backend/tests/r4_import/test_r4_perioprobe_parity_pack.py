from datetime import datetime, timezone

from app.scripts import r4_perioprobe_parity_pack as parity


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
        {"trans_id": 10, "tooth": 3, "probing_point": 2, "depth": 4, "bleeding": 0, "plaque": 1},
        {"trans_id": 10, "tooth": 2, "probing_point": 6, "depth": 3, "bleeding": 1, "plaque": 0},
    ]
    digest = parity._digest_for_trans(rows, 10)
    assert digest[0]["tooth"] == 2
    assert digest[1]["tooth"] == 3
