import json
import sys

from app.scripts import r4_import as r4_import_script


def test_parse_charting_domains_accepts_old_patient_notes():
    assert r4_import_script._parse_charting_domains_arg("old_patient_notes") == [
        "old_patient_notes"
    ]


def test_cli_charting_canonical_old_patient_notes_stats_shape(tmp_path, monkeypatch):
    class DummyStats:
        def as_dict(self):
            return {
                "created": 2,
                "updated": 0,
                "skipped": 0,
                "unmapped_patients": 0,
                "total": 2,
            }

    class DummySession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    captured = {}

    def fake_import(*_args, **kwargs):
        captured["domains"] = kwargs.get("domains")
        captured["patient_codes"] = kwargs.get("patient_codes")
        return DummyStats(), {
            "total_records": 2,
            "distinct_patients": 1,
            "missing_source_id": 0,
            "missing_patient_code": 0,
            "by_source": {"dbo.OldPatientNotes": {"fetched": 2}},
            "stats": DummyStats().as_dict(),
            "dropped": {
                "missing_date": 1,
                "out_of_range": 3,
            },
        }

    stats_path = tmp_path / "stats.json"
    monkeypatch.setattr(r4_import_script, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(r4_import_script, "resolve_actor_id", lambda _session: 1)
    monkeypatch.setattr(r4_import_script, "FixtureSource", lambda: object())
    monkeypatch.setattr(r4_import_script, "import_r4_charting_canonical_report", fake_import)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--entity",
            "charting_canonical",
            "--patient-codes",
            "1000001",
            "--domains",
            "old_patient_notes",
            "--stats-out",
            str(stats_path),
        ],
    )

    assert r4_import_script.main() == 0
    assert captured["domains"] == ["old_patient_notes"]
    assert captured["patient_codes"] == [1000001]

    payload = json.loads(stats_path.read_text(encoding="utf-8"))
    stats = payload["stats"]
    assert stats["imported_created_total"] == 2
    assert stats["candidates_total"] == 6
    assert stats["dropped_reasons"] == {
        "missing_date": 1,
        "out_of_range": 3,
    }
