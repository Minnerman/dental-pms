from datetime import datetime, timezone

from app.scripts import r4_patient_notes_parity_pack as parity


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
        "note_date": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "note_number": 42,
        "note": "x",
        "tooth": 16,
        "surface": 2,
    }
    assert parity._latest_key(row) == {
        "note_date": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "note_number": 42,
    }
    assert parity._latest_digest(row) == {"note": "x", "tooth": 16, "surface": 2}


def test_latest_sort_prefers_date_then_note_number():
    a = {"note_date": "2025-01-01T00:00:00+00:00", "note_number": 1}
    b = {"note_date": "2025-01-01T00:00:00+00:00", "note_number": 2}
    c = {"note_date": "2025-01-02T00:00:00+00:00", "note_number": 1}
    assert max([a, b, c], key=parity._latest_sort_tuple) == c
