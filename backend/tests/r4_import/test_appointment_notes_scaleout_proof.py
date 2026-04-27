import json
import sys
from datetime import date

from app.scripts import r4_cohort_select
from app.scripts import r4_import as r4_import_script
from app.scripts import r4_parity_run


class _DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class _DummyStats:
    def __init__(self, *, count: int):
        self.count = count

    def as_dict(self):
        return {
            "created": self.count,
            "updated": 0,
            "skipped": 0,
            "unmapped_patients": 0,
            "total": self.count,
        }


def _appointment_notes_report_for(codes: list[int]) -> dict[str, object]:
    return {
        "patients": [
            {
                "patient_code": code,
                "sqlserver_total_rows": 2,
                "latest_match": True,
                "latest_digest_match": True,
            }
            for code in codes
        ]
    }


def test_appointment_notes_scaleout_continuation_path(monkeypatch, tmp_path):
    accepted_pool = list(range(700001, 701137))

    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **_kwargs: accepted_pool if domain == "appointment_notes" else [],
    )

    first_chunk = r4_cohort_select.select_cohort(
        domains=["appointment_notes"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=200,
        mode="union",
        excluded_patient_codes=set(),
        order="hashed",
        seed=17,
    )
    continuation = r4_cohort_select.select_cohort(
        domains=["appointment_notes"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=200,
        mode="union",
        excluded_patient_codes=set(first_chunk["patient_codes"]),
        order="hashed",
        seed=17,
    )
    repeat = r4_cohort_select.select_cohort(
        domains=["appointment_notes"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=200,
        mode="union",
        excluded_patient_codes=set(first_chunk["patient_codes"]),
        order="hashed",
        seed=17,
    )

    assert first_chunk["domain_counts"] == {"appointment_notes": 1136}
    assert first_chunk["selected_count"] == 200
    assert continuation["patient_codes"] == repeat["patient_codes"]
    assert continuation["domain_counts"] == {"appointment_notes": 1136}
    assert continuation["candidates_before_exclude"] == 1136
    assert continuation["exclude_input_count"] == 200
    assert continuation["excluded_candidates_count"] == 200
    assert continuation["remaining_after_exclude"] == 936
    assert continuation["selected_count"] == 200
    assert set(first_chunk["patient_codes"]).isdisjoint(continuation["patient_codes"])

    selected_codes = list(continuation["patient_codes"])
    codes_file = tmp_path / "stage163h_chunk2_codes.txt"
    codes_file.write_text("\n".join(str(code) for code in selected_codes), encoding="utf-8")

    import_calls: list[dict[str, object]] = []

    def fake_import(*_args, **kwargs):
        batch_codes = list(kwargs["patient_codes"])
        import_calls.append(
            {
                "patient_codes": batch_codes,
                "domains": kwargs.get("domains"),
                "date_from": kwargs.get("date_from"),
                "date_to": kwargs.get("date_to"),
            }
        )
        count = len(batch_codes) * 2
        dropped = {
            "blank_note": len(batch_codes),
            "out_of_window": len(batch_codes),
            "accepted_nonblank_note": count,
            "accepted_blank_note": len(batch_codes),
            "included": count,
        }
        return _DummyStats(count=count), {
            "total_records": count,
            "distinct_patients": len(batch_codes),
            "missing_source_id": 0,
            "missing_patient_code": 0,
            "by_source": {
                "dbo.vwAppointmentDetails": {"fetched": count + len(batch_codes) * 2}
            },
            "stats": _DummyStats(count=count).as_dict(),
            "dropped": dropped,
        }

    stats_path = tmp_path / "import_stats.json"
    summary_path = tmp_path / "import_summary.json"
    monkeypatch.setattr(r4_import_script, "SessionLocal", lambda: _DummySession())
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
            "--patient-codes-file",
            str(codes_file),
            "--domains",
            "appointment_notes",
            "--charting-from",
            "2017-01-01",
            "--charting-to",
            "2026-02-01",
            "--batch-size",
            "75",
            "--stats-out",
            str(stats_path),
            "--run-summary-out",
            str(summary_path),
        ],
    )

    assert r4_import_script.main() == 0
    assert [len(call["patient_codes"]) for call in import_calls] == [75, 75, 50]
    assert all(call["domains"] == ["appointment_notes"] for call in import_calls)
    assert all(call["date_from"] == date(2017, 1, 1) for call in import_calls)
    assert all(call["date_to"] == date(2026, 2, 1) for call in import_calls)

    stats_payload = json.loads(stats_path.read_text(encoding="utf-8"))
    assert stats_payload["stats"]["batches_total"] == 3
    assert stats_payload["stats"]["batches_completed"] == 3
    assert stats_payload["stats"]["imported_created_total"] == 400
    assert stats_payload["stats"]["dropped_reasons"] == {
        "blank_note": 200,
        "out_of_window": 200,
    }
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["domains"] == ["appointment_notes"]
    assert summary_payload["patient_filter_mode"] == "codes"
    assert summary_payload["patient_codes_count"] == 200
    assert summary_payload["totals"]["candidates_total"] == 800

    monkeypatch.setattr(r4_parity_run, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(
        r4_parity_run.r4_appointment_notes_parity_pack,
        "build_parity_report",
        lambda session, *, patient_codes, **_kwargs: _appointment_notes_report_for(
            patient_codes
        ),
    )

    parity_dir = tmp_path / "parity"
    parity_report = r4_parity_run.run_parity(
        patient_codes=selected_codes,
        domains=["appointment_notes"],
        date_from=date(2017, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
        output_dir=str(parity_dir),
    )

    assert parity_report["overall"] == {
        "status": "pass",
        "has_data": True,
        "domains_requested": 1,
        "domains_failed": 0,
        "domains_no_data": 0,
    }
    assert parity_report["domain_summaries"]["appointment_notes"]["patients_total"] == 200
    assert parity_report["domain_summaries"]["appointment_notes"]["patients_with_data"] == 200
    assert parity_report["domain_summaries"]["appointment_notes"]["latest_match"] == {
        "matched": 200,
        "total": 200,
    }
    assert (parity_dir / "appointment_notes.json").exists()
