from datetime import datetime, timezone

from app.scripts import r4_bpe_furcation_parity_pack as parity


def test_parse_patient_codes_csv_dedupes_and_trims():
    assert parity._parse_patient_codes_csv("1000035, 1000036,1000035") == [1000035, 1000036]


def test_parse_patient_codes_csv_rejects_empty_token():
    try:
        parity._parse_patient_codes_csv("1000035,,1000036")
    except RuntimeError as exc:
        assert "empty token" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_latest_key_and_digest_shape():
    row = {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "bpe_id": 42,
        "furcation_1": 0,
        "furcation_2": 1,
        "furcation_3": 2,
        "furcation_4": 0,
        "furcation_5": 1,
        "furcation_6": 2,
    }
    assert parity._latest_key(row) == {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "bpe_id": 42,
    }
    assert parity._latest_digest(row) == {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "furcation_1": 0,
        "furcation_2": 1,
        "furcation_3": 2,
        "furcation_4": 0,
        "furcation_5": 1,
        "furcation_6": 2,
    }


def test_latest_sort_prefers_date_then_bpe_id():
    a = {"recorded_at": "2025-01-01T00:00:00+00:00", "bpe_id": 1}
    b = {"recorded_at": "2025-01-01T00:00:00+00:00", "bpe_id": 2}
    c = {"recorded_at": "2025-01-02T00:00:00+00:00", "bpe_id": 1}
    assert max([a, b, c], key=parity._latest_sort_tuple) == c
