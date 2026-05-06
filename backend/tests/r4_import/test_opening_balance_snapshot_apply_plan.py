from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from app.services.r4_import.opening_balance_snapshot_apply_plan import (
    OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
    OPENING_BALANCE_APPLY_REPRESENTATION,
    build_opening_balance_snapshot_apply_plan,
)
from app.services.r4_import.opening_balance_snapshot_dry_run import (
    build_opening_balance_snapshot_dry_run_report,
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


def build_report(rows=None, mapping=None):
    rows = rows or [
        patient_stats_row(PatientCode="P1"),
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
    mapping = mapping if mapping is not None else {"P1": 101, "P2": 102}
    return build_opening_balance_snapshot_dry_run_report(
        rows,
        mapping,
        generated_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        repo_sha="test-sha",
        sample_limit=3,
        dry_run_parameters={"mapping_source": "scratch_patient_mapping.json"},
    )


def build_plan(report=None, **overrides):
    params = {
        "dry_run_report": report or build_report(),
        "database_target": "dental_pms_opening_balance_apply_scratch",
        "confirmation_token": OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
        "manifest_id": "ob-20260506101010-abcdef123456",
        "before_finance_counts": {
            "patient_ledger_entries": 0,
            "invoices": 0,
            "payments": 0,
        },
    }
    params.update(overrides)
    return build_opening_balance_snapshot_apply_plan(**params)


def test_happy_path_plans_scratch_only_ledger_adjustments_without_execution():
    plan = build_plan()

    assert plan["is_safe_to_apply_in_scratch"] is True
    assert plan["finance_import_ready"] is False
    assert plan["database_target_decision"]["scratch_or_test_allowed"] is True
    assert plan["confirmation_decision"]["token_accepted"] is True
    assert plan["dry_run_report_decision"]["dry_run"] is True
    assert plan["dry_run_report_decision"]["manifest_no_write"] is True
    assert plan["dry_run_report_decision"]["manifest_apply_mode"] is False
    assert plan["mapping_decision"]["all_nonzero_candidates_mapped"] is True
    assert plan["eligibility_decision"]["eligible_count"] == 2
    assert plan["eligibility_decision"]["no_op_count"] == 1
    assert plan["write_plan_summary"] == {
        "representation": OPENING_BALANCE_APPLY_REPRESENTATION,
        "requested_representation": OPENING_BALANCE_APPLY_REPRESENTATION,
        "representation_supported": True,
        "would_create": 2,
        "would_skip": 0,
        "would_refuse": 0,
        "would_create_invoices": 0,
        "would_create_payments": 0,
        "would_create_staging_models": 0,
        "would_mutate_balances_outside_selected_representation": False,
        "apply_execution": False,
        "reason_codes": (
            "patient_ledger_entry_adjustment_representation_selected",
        ),
    }
    assert plan["sample_planned_rows"][0]["ledger_entry_type"] == "adjustment"
    assert plan["sample_planned_rows"][0]["related_invoice_id"] is None
    assert (
        plan["sample_planned_rows"][0]["reference"]
        == "R4OB:ob-20260506101010-abcdef123456:P1"
    )


def test_default_dental_pms_database_is_refused():
    plan = build_plan(database_target="dental_pms")

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert plan["database_target_decision"]["default_or_live_refused"] is True
    assert "default_dental_pms_database_refused" in plan["reason_codes"]


def test_database_name_without_scratch_or_test_is_refused():
    plan = build_plan(database_target="dental_pms_opening_balance_apply")

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert "database_target_not_scratch_or_test" in plan["reason_codes"]


def test_missing_database_target_is_refused():
    plan = build_plan(database_target=None)

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert plan["database_target_decision"]["missing_or_unknown_refused"] is True
    assert "missing_database_target" in plan["reason_codes"]


def test_wrong_confirmation_token_is_refused():
    plan = build_plan(confirmation_token="APPLY")

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert plan["confirmation_decision"]["token_accepted"] is False
    assert "invalid_confirmation_token" in plan["reason_codes"]


def test_missing_confirmation_token_is_refused():
    plan = build_plan(confirmation_token=None)

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert "missing_confirmation_token" in plan["reason_codes"]


def test_dry_run_false_is_refused():
    report = build_report()
    report["dry_run"] = False

    plan = build_plan(report)

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert "dry_run_true_required" in plan["reason_codes"]


def test_manifest_no_write_false_is_refused():
    report = build_report()
    report["manifest"]["no_write"] = False

    plan = build_plan(report)

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert "manifest_no_write_true_required" in plan["reason_codes"]


def test_import_ready_true_is_refused():
    report = build_report()
    report["import_ready"] = True

    plan = build_plan(report)

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert "import_ready_true_refused" in plan["reason_codes"]
    assert plan["finance_import_ready"] is False


def test_unmapped_nonzero_candidates_are_refused():
    report = build_report([patient_stats_row(PatientCode="P1")], {})

    plan = build_plan(report)

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert plan["mapping_decision"]["unmapped_nonzero_candidates"] == 1
    assert "nonzero_mapping_coverage_incomplete" in plan["reason_codes"]


def test_component_mismatch_among_would_write_rows_is_refused():
    report = build_report()
    report["eligibility_summary"]["component_mismatch_would_write_count"] = 1

    plan = build_plan(report)

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert (
        plan["dry_run_report_decision"]["component_mismatch_would_write_count"]
        == 1
    )
    assert (
        "component_mismatch_among_would_write_rows_refused"
        in plan["reason_codes"]
    )


def test_source_drift_requires_explicit_acknowledgement():
    report = build_report()
    report["source_drift"] = {"total_balance_delta": "-400.00"}

    refused = build_plan(report)
    accepted = build_plan(report, source_drift_acknowledged=True)

    assert refused["is_safe_to_apply_in_scratch"] is False
    assert "source_drift_acknowledgement_required" in refused["reason_codes"]
    assert accepted["is_safe_to_apply_in_scratch"] is True
    assert "source_drift_acknowledged" in accepted["dry_run_report_decision"]["reason_codes"]


def test_unsupported_representation_is_refused():
    plan = build_plan(representation="invoice")

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert plan["write_plan_summary"]["representation_supported"] is False
    assert "unsupported_write_representation" in plan["reason_codes"]


def test_invoice_payment_staging_and_balance_write_intents_are_refused():
    plan = build_plan(
        write_intent={
            "create_invoices": 1,
            "create_payments": True,
            "create_staging_models": True,
            "mutate_patient_balances": True,
        }
    )

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert "invoice_creation_refused" in plan["reason_codes"]
    assert "payment_creation_refused" in plan["reason_codes"]
    assert "staging_model_creation_refused" in plan["reason_codes"]
    assert "patient_balance_mutation_refused" in plan["reason_codes"]


def test_existing_manifest_rows_plan_idempotent_skip():
    report = build_report()
    manifest_id = "ob-20260506101010-abcdef123456"
    existing_rows = [
        {
            "manifest_id": manifest_id,
            "entry_type": "adjustment",
            "representation": OPENING_BALANCE_APPLY_REPRESENTATION,
            "reference": f"R4OB:{manifest_id}:P1",
        },
        {
            "manifest_id": manifest_id,
            "entry_type": "adjustment",
            "representation": OPENING_BALANCE_APPLY_REPRESENTATION,
            "reference": f"R4OB:{manifest_id}:P2",
        },
    ]

    plan = build_plan(
        report,
        manifest_id=manifest_id,
        existing_manifest_rows=existing_rows,
        existing_manifest_ids=[manifest_id],
    )

    assert plan["is_safe_to_apply_in_scratch"] is True
    assert plan["write_plan_summary"]["would_create"] == 0
    assert plan["write_plan_summary"]["would_skip"] == 2
    assert plan["idempotency_plan"]["rerun_expectation"] == {
        "created": 0,
        "updated": 0,
        "skipped": 2,
    }


def test_partial_duplicate_manifest_rows_fail_closed():
    report = build_report()
    manifest_id = "ob-20260506101010-abcdef123456"

    plan = build_plan(
        report,
        manifest_id=manifest_id,
        existing_manifest_rows=[
            {"manifest_id": manifest_id, "reference": f"R4OB:{manifest_id}:P1"}
        ],
        existing_manifest_ids=[manifest_id],
    )

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert plan["write_plan_summary"]["would_create"] == 0
    assert "partial_existing_manifest_rows_refused" in plan["reason_codes"]


def test_existing_opening_balance_marker_fails_closed():
    plan = build_plan(
        existing_opening_balance_markers=[
            {"reference": "R4OB:prior-manifest:P1", "patient_id": 101}
        ]
    )

    assert plan["is_safe_to_apply_in_scratch"] is False
    assert plan["write_plan_summary"]["would_create"] == 0
    assert "existing_opening_balance_marker_refused" in plan["reason_codes"]


def test_rollback_plan_is_manifest_scoped_and_refuses_broad_ledger_deletion():
    safe_plan = build_plan()
    refused_plan = build_plan(write_intent={"broad_ledger_deletion": True})

    assert safe_plan["rollback_plan"]["manifest_scoped_only"] is True
    assert safe_plan["rollback_plan"]["no_broad_ledger_deletion"] is True
    assert (
        safe_plan["rollback_plan"]["target_reference_prefix"]
        == "R4OB:ob-20260506101010-abcdef123456:"
    )
    assert refused_plan["is_safe_to_apply_in_scratch"] is False
    assert "broad_ledger_deletion_refused" in refused_plan["reason_codes"]


def test_apply_plan_helper_has_no_db_r4_cli_or_write_dependency():
    backend_root = Path(__file__).resolve().parents[2]
    source_text = (
        backend_root
        / "app/services/r4_import/opening_balance_snapshot_apply_plan.py"
    ).read_text(encoding="utf-8")

    assert "SessionLocal" not in source_text
    assert "get_db" not in source_text
    assert "R4SqlServerSource" not in source_text
    assert "sqlalchemy" not in source_text.lower()
    assert "PatientLedgerEntry(" not in source_text
    assert "Invoice(" not in source_text
    assert "Payment(" not in source_text
    assert "commit(" not in source_text
    assert "flush(" not in source_text


def test_input_report_is_not_mutated():
    report = build_report()
    before = deepcopy(report)

    build_plan(report)

    assert report == before
