import json
import sys
from datetime import date

from app.scripts import r4_cohort_select
from app.scripts import r4_import as r4_import_script
from app.scripts import r4_parity_run


TARGET_DOMAINS = [
    "perio_plaque",
    "completed_questionnaire_notes",
    "old_patient_notes",
]


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


def _domain_report_for(codes: list[int]) -> dict[str, object]:
    return {
        "patients": [
            {
                "patient_code": code,
                "sqlserver_total_rows": 1,
                "latest_match": True,
                "latest_digest_match": True,
            }
            for code in codes
        ]
    }


def test_live_charting_scaleout_path_batches_target_domains(
    monkeypatch,
    tmp_path,
):
    domain_codes = {
        "perio_plaque": list(range(3001, 3025)),
        "completed_questionnaire_notes": list(range(3010, 3040)),
        "old_patient_notes": list(range(3035, 3070)),
    }

    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **_kwargs: domain_codes[domain],
    )

    exclusions = {3001, 3010, 3035, 3069}
    first = r4_cohort_select.select_cohort(
        domains=TARGET_DOMAINS,
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=24,
        mode="union",
        excluded_patient_codes=exclusions,
        order="hashed",
        seed=558,
    )
    repeat = r4_cohort_select.select_cohort(
        domains=TARGET_DOMAINS,
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=24,
        mode="union",
        excluded_patient_codes=exclusions,
        order="hashed",
        seed=558,
    )

    assert first["patient_codes"] == repeat["patient_codes"]
    assert first["domains"] == TARGET_DOMAINS
    assert first["domain_counts"] == {
        "perio_plaque": 24,
        "completed_questionnaire_notes": 30,
        "old_patient_notes": 35,
    }
    assert first["candidates_before_exclude"] == 69
    assert first["excluded_candidates_count"] == 4
    assert first["remaining_after_exclude"] == 65
    assert first["selected_count"] == 24
    assert exclusions.isdisjoint(set(first["patient_codes"]))

    selected_codes = list(first["patient_codes"])
    codes_file = tmp_path / "target_scaleout_codes.txt"
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
        count = len(batch_codes) * len(TARGET_DOMAINS)
        return _DummyStats(count=count), {
            "total_records": count,
            "distinct_patients": len(batch_codes),
            "missing_source_id": 0,
            "missing_patient_code": 0,
            "by_source": {
                "dbo.PerioPlaque": {"fetched": len(batch_codes)},
                "dbo.CompletedQuestionnaire": {"fetched": len(batch_codes)},
                "dbo.OldPatientNotes": {"fetched": len(batch_codes)},
            },
            "stats": _DummyStats(count=count).as_dict(),
            "dropped": {},
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
            ",".join(TARGET_DOMAINS),
            "--charting-from",
            "2017-01-01",
            "--charting-to",
            "2026-02-01",
            "--batch-size",
            "10",
            "--stats-out",
            str(stats_path),
            "--run-summary-out",
            str(summary_path),
        ],
    )

    assert r4_import_script.main() == 0
    assert [len(call["patient_codes"]) for call in import_calls] == [10, 10, 4]
    assert all(call["domains"] == TARGET_DOMAINS for call in import_calls)
    assert all(call["date_from"] == date(2017, 1, 1) for call in import_calls)
    assert all(call["date_to"] == date(2026, 2, 1) for call in import_calls)

    stats_payload = json.loads(stats_path.read_text(encoding="utf-8"))
    assert stats_payload["stats"]["batches_total"] == 3
    assert stats_payload["stats"]["batches_completed"] == 3
    assert stats_payload["stats"]["imported_created_total"] == 72
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["domains"] == TARGET_DOMAINS
    assert summary_payload["patient_filter_mode"] == "codes"
    assert summary_payload["patient_codes_count"] == 24
    assert summary_payload["totals"]["candidates_total"] == 72

    monkeypatch.setattr(r4_parity_run, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(
        r4_parity_run.r4_perio_plaque_parity_pack,
        "build_parity_report",
        lambda session, *, patient_codes, **_kwargs: _domain_report_for(patient_codes),
    )
    monkeypatch.setattr(
        r4_parity_run.r4_completed_questionnaire_notes_parity_pack,
        "build_parity_report",
        lambda session, *, patient_codes, **_kwargs: _domain_report_for(patient_codes),
    )
    monkeypatch.setattr(
        r4_parity_run.r4_old_patient_notes_parity_pack,
        "build_parity_report",
        lambda session, *, patient_codes, **_kwargs: _domain_report_for(patient_codes),
    )

    parity_dir = tmp_path / "parity"
    parity_report = r4_parity_run.run_parity(
        patient_codes=selected_codes,
        domains=TARGET_DOMAINS,
        date_from=date(2017, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
        output_dir=str(parity_dir),
    )

    assert parity_report["overall"] == {
        "status": "pass",
        "has_data": True,
        "domains_requested": 3,
        "domains_failed": 0,
        "domains_no_data": 0,
    }
    for domain in TARGET_DOMAINS:
        summary = parity_report["domain_summaries"][domain]
        assert summary["patients_total"] == 24
        assert summary["patients_with_data"] == 24
        assert summary["latest_match"] == {"matched": 24, "total": 24}
        assert (parity_dir / f"{domain}.json").exists()
