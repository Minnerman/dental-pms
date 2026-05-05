from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.scripts import r4_opening_balance_snapshot_dry_run
from app.services.r4_import.opening_balance_snapshot_dry_run import (
    build_opening_balance_snapshot_dry_run_report,
    load_patient_mapping_json,
    load_patient_stats_rows_json,
)


def patient_stats_row(**overrides):
    row = {
        "PatientCode": "R4001",
        "Balance": "125.50",
        "TreatmentBalance": "100.00",
        "SundriesBalance": "25.50",
        "NHSBalance": "0.00",
        "PrivateBalance": "100.00",
        "DPBBalance": "0.00",
        "AgeDebtor30To60": "0.00",
        "AgeDebtor60To90": "0.00",
        "AgeDebtor90Plus": "0.00",
    }
    row.update(overrides)
    return row


def build_report(rows, mapping=None, **kwargs):
    return build_opening_balance_snapshot_dry_run_report(
        rows,
        mapping or {},
        generated_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        repo_sha="test-sha",
        sample_limit=2,
        dry_run_parameters={"mapping_source": "test-mapping.json"},
        **kwargs,
    )


def test_happy_path_reports_mapped_positive_negative_and_zero_rows():
    rows = [
        patient_stats_row(
            PatientCode="P1",
            Balance="10.00",
            TreatmentBalance="10.00",
            SundriesBalance="0.00",
            PrivateBalance="10.00",
        ),
        patient_stats_row(
            PatientCode="P2",
            Balance="-4.25",
            TreatmentBalance="-4.25",
            SundriesBalance="0.00",
            NHSBalance="0.00",
            PrivateBalance="-4.25",
            DPBBalance="0.00",
        ),
        patient_stats_row(
            PatientCode="P3",
            Balance="0.00",
            TreatmentBalance="0.00",
            SundriesBalance="0.00",
            NHSBalance="0.00",
            PrivateBalance="0.00",
            DPBBalance="0.00",
        ),
    ]

    report = build_report(rows, {"P1": 101, "P2": 102})

    assert report["generated_at"] == "2026-05-05T12:00:00+00:00"
    assert report["dry_run"] is True
    assert report["select_only"] is False
    assert report["import_ready"] is False
    assert report["finance_import_ready"] is False
    assert report["source_summary"]["row_count"] == 3
    assert report["source_summary"]["nonzero_count"] == 2
    assert report["source_summary"]["zero_no_op_count"] == 1
    assert report["mapping_summary"]["mapped_nonzero_candidates"] == 2
    assert report["mapping_summary"]["unmapped_nonzero_candidates"] == 0
    assert report["mapping_summary"]["nonzero_mapping_coverage"] == "1.0000"
    assert report["eligibility_summary"]["eligible_opening_balance"] == 2
    assert report["eligibility_summary"]["no_op_zero_balance"] == 1
    assert report["sign_summary"]["positive"] == 1
    assert report["sign_summary"]["negative"] == 1
    assert report["sign_summary"]["zero"] == 1
    assert report["sign_summary"]["increase_debt"] == 1
    assert report["sign_summary"]["decrease_debt_or_credit"] == 1
    assert report["sign_summary"]["no_action"] == 1
    assert report["component_consistency_summary"]["component_pass_count"] == 3
    assert report["component_consistency_summary"]["mismatch_count"] == 0
    assert report["manifest"]["repo_sha"] == "test-sha"
    assert report["manifest"]["no_write"] is True
    assert report["manifest"]["apply_mode"] is False


def test_missing_mapping_for_nonzero_row_is_refused_and_reported():
    report = build_report([patient_stats_row()], {})

    assert report["eligibility_summary"]["missing_patient_mapping"] == 1
    assert report["mapping_summary"]["mapped_nonzero_candidates"] == 0
    assert report["mapping_summary"]["unmapped_nonzero_candidates"] == 1
    assert report["mapping_summary"]["nonzero_mapping_coverage"] == "0.0000"
    assert report["refusal_reasons"] == {"missing_patient_mapping": 1}
    assert any("missing patient mappings" in risk for risk in report["risks"])
    assert report["samples"]["missing_patient_mapping"][0]["amount_pence"] == 12550
    assert (
        report["samples"]["missing_patient_mapping"][0]["can_create_finance_record"]
        is False
    )


def test_missing_patient_code_is_refused():
    report = build_report([patient_stats_row(PatientCode=" ")], {"R4001": 101})

    assert report["eligibility_summary"]["invalid_patient_code"] == 1
    assert report["refusal_reasons"] == {"missing_patient_code": 1}
    assert report["samples"]["invalid_patient_code"][0]["source_patient_code"] is None


def test_component_mismatch_is_refused():
    report = build_report([patient_stats_row(SundriesBalance="20.00")], {"R4001": 101})

    assert report["eligibility_summary"]["component_mismatch"] == 1
    assert report["component_consistency_summary"]["mismatch_count"] == 1
    assert report["refusal_reasons"] == {"balance_component_mismatch": 1}


def test_invalid_amount_and_non_pence_amounts_are_refused():
    report = build_report(
        [
            patient_stats_row(PatientCode="P1", Balance="not money"),
            patient_stats_row(PatientCode="P2", Balance="10.005"),
        ],
        {"P1": 1, "P2": 2},
    )

    assert report["eligibility_summary"]["invalid_amount"] == 2
    assert report["refusal_reasons"] == {
        "balance_amount_missing_or_invalid": 1,
        "balance_amount_not_exact_pence": 1,
    }
    assert report["sign_summary"]["unknown"] == 1


def test_ambiguous_sign_and_unknown_source_are_fail_closed():
    report = build_report(
        [
            patient_stats_row(PatientCode="P1", RawSign="negative"),
            patient_stats_row(PatientCode="P2", source_name="Transactions"),
        ],
        {"P1": 1, "P2": 2},
    )

    assert report["eligibility_summary"]["ambiguous_sign"] == 1
    assert report["eligibility_summary"]["excluded"] == 1
    assert report["refusal_reasons"] == {
        "raw_sign_conflicts_with_balance": 1,
        "unsupported_source": 1,
    }


def test_aged_debt_metadata_is_summarised_without_driving_eligibility():
    rows = [
        patient_stats_row(AgeDebtor30To60="12.00"),
        patient_stats_row(
            PatientCode="P2",
            Balance="0.00",
            TreatmentBalance="0.00",
            SundriesBalance="0.00",
            NHSBalance="0.00",
            PrivateBalance="0.00",
            DPBBalance="0.00",
            AgeDebtor90Plus="3.50",
        ),
        patient_stats_row(PatientCode="P3"),
    ]

    report = build_report(rows, {"R4001": 1, "P3": 3})

    assert report["aged_debt_summary"] == {
        "aged_debt_present_count": 2,
        "balance_without_aged_debt_count": 1,
        "aged_debt_with_zero_balance_count": 1,
        "total_aged_debt": "15.50",
    }


def test_report_contains_expected_top_level_sections():
    report = build_report([patient_stats_row()], {"R4001": 101})

    assert set(report) == {
        "generated_at",
        "dry_run",
        "select_only",
        "source_mode",
        "import_ready",
        "finance_import_ready",
        "source_summary",
        "mapping_summary",
        "eligibility_summary",
        "sign_summary",
        "component_consistency_summary",
        "aged_debt_summary",
        "refusal_reasons",
        "samples",
        "risks",
        "manifest",
    }


def test_json_loaders_accept_mapping_object_and_row_container(tmp_path):
    rows_path = tmp_path / "rows.json"
    mapping_path = tmp_path / "mapping.json"
    rows_path.write_text(
        json.dumps({"patient_stats_rows": [patient_stats_row()]}),
        encoding="utf-8",
    )
    mapping_path.write_text(
        json.dumps({"mappings": {" R4001 ": 101, "blank": None}}),
        encoding="utf-8",
    )

    assert load_patient_stats_rows_json(rows_path)[0]["PatientCode"] == "R4001"
    assert load_patient_mapping_json(mapping_path) == {"R4001": 101}


def test_mapping_loader_accepts_list_shape(tmp_path):
    mapping_path = tmp_path / "mapping-list.json"
    mapping_path.write_text(
        json.dumps([{"PatientCode": "R4001", "mapped_patient_id": "pms-101"}]),
        encoding="utf-8",
    )

    assert load_patient_mapping_json(mapping_path) == {"R4001": "pms-101"}


def test_cli_writes_json_report_and_stdout_summary(tmp_path, capsys):
    rows_path = tmp_path / "rows.json"
    mapping_path = tmp_path / "mapping.json"
    output_path = tmp_path / "report.json"
    rows_path.write_text(json.dumps([patient_stats_row()]), encoding="utf-8")
    mapping_path.write_text(json.dumps({"R4001": 101}), encoding="utf-8")

    assert (
        r4_opening_balance_snapshot_dry_run.main(
            [
                "--patient-stats-json",
                str(rows_path),
                "--patient-mapping-json",
                str(mapping_path),
                "--output-json",
                str(output_path),
                "--repo-sha",
                "test-sha",
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["import_ready"] is False
    assert payload["manifest"]["no_write"] is True
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["output_json"] == str(output_path)
    assert stdout["eligible_opening_balance"] == 1
    assert stdout["no_write"] is True


def test_cli_has_no_apply_mode():
    parser = r4_opening_balance_snapshot_dry_run.build_parser()

    assert "--apply" not in parser.format_help()
    with pytest.raises(SystemExit):
        parser.parse_args(["--apply"])


def test_dry_run_files_do_not_contain_db_session_or_write_paths():
    backend_root = Path(__file__).resolve().parents[2]
    files = [
        backend_root / "app/services/r4_import/opening_balance_snapshot_dry_run.py",
        backend_root / "app/scripts/r4_opening_balance_snapshot_dry_run.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "SessionLocal" not in combined
    assert "get_db" not in combined
    assert "R4SqlServerSource(" not in combined
    assert "PatientLedgerEntry(" not in combined
    assert "Invoice(" not in combined
    assert "Payment(" not in combined
    assert "commit(" not in combined
    assert "flush(" not in combined
