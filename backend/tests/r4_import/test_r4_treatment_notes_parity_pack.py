from datetime import datetime, timezone

from app.scripts import r4_treatment_notes_parity_pack as parity


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
        "note_id": 42,
        "tp_number": 3,
        "tp_item": 1,
        "tooth": 11,
        "surface": 1,
        "note_body": "  hello\nworld  ",
    }
    assert parity._latest_key(row) == {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "note_id": 42,
    }
    digest = parity._latest_digest(row)
    assert digest == {
        "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "tp_number": 3,
        "tp_item": 1,
        "tooth": 11,
        "surface": 1,
        "note_body": "hello world",
    }


def test_latest_sort_prefers_recorded_at_then_note_id():
    a = {"recorded_at": "2025-01-01T00:00:00+00:00", "note_id": 1}
    b = {"recorded_at": "2025-01-01T00:00:00+00:00", "note_id": 2}
    c = {"recorded_at": "2025-01-02T00:00:00+00:00", "note_id": 1}
    assert max([a, b, c], key=parity._latest_sort_tuple) == c


def test_sqlserver_rows_enrich_tooth_surface_from_plan_items():
    class DummyTreatmentNote:
        patient_code = 1001
        note_id = 42
        note_date = datetime(2025, 1, 2, tzinfo=timezone.utc)
        tp_number = 3
        tp_item = 1
        note = "hello"

    class DummyPlanItem:
        patient_code = 1001
        tp_number = 3
        tp_item = 1
        tooth = 11
        surface = 1

    class DummySource:
        def list_treatment_notes(
            self,
            patients_from=None,
            patients_to=None,
            date_from=None,
            date_to=None,
            limit=None,
        ):
            return [DummyTreatmentNote()]

        def list_treatment_plan_items(
            self,
            patients_from=None,
            patients_to=None,
            tp_from=None,
            tp_to=None,
            limit=None,
        ):
            return [DummyPlanItem()]

    rows = parity._sqlserver_rows(
        DummySource(),
        1001,
        date_from=None,
        date_to=None,
        row_limit=10,
    )

    assert rows == [
        {
            "patient_code": 1001,
            "note_id": 42,
            "recorded_at": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
            "tp_number": 3,
            "tp_item": 1,
            "tooth": 11,
            "surface": 1,
            "note_body": "hello",
        }
    ]
