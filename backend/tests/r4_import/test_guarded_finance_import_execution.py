from __future__ import annotations

import json

from app.scripts import r4_guarded_finance_import_execution as execution_script
from app.services.r4_import import guarded_finance_import_execution as execution_service
from app.services.r4_import.guarded_finance_import_execution import (
    GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN,
    GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
    LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
    GuardedFinanceImportExecutionError,
    build_guarded_finance_import_execution_result,
    build_guarded_finance_import_execution_packet,
)


def manifest(**overrides):
    payload = {
        "manifest_id": "finance-import-20260510-000001",
        "import_category": "opening-balance",
        "target": {"classification": LIVE_DENTAL_PMS_TARGET_CLASSIFICATION},
        "safety": {
            "real_patient_data": False,
            "real_r4_artifact": False,
        },
        "sensitive_data_policy": {
            "committed_fixture_contains_real_r4_data": False,
            "committed_fixture_contains_real_patient_data": False,
        },
        "samples": {
            "eligible_opening_balance": [
                {
                    "source_patient_code": "PRIVATE-SHOULD-NOT-PRINT",
                    "mapped_patient_id": 123,
                }
            ]
        },
    }
    payload.update(overrides)
    return payload


def safe_packet(**overrides):
    params = {
        "manifest": manifest(),
        "import_category": "opening-balance",
        "target_classification": LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
        "apply_requested": False,
        "apply_confirmation": None,
        "production_execution_gate": GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
        "no_secrets_exposed": True,
        "no_patient_data_exposed": True,
        "no_private_paths_exposed": True,
        "no_backup_contents_exposed": True,
    }
    params.update(overrides)
    return build_guarded_finance_import_execution_packet(**params)


def report(**overrides):
    payload = {
        "before_finance_counts": {
            "invoices": 0,
            "patient_ledger_entries": 0,
            "payments": 0,
        },
        "dry_run": True,
        "eligibility_summary": {
            "ambiguous_sign_would_write_count": 0,
            "component_mismatch_would_write_count": 0,
            "eligible_opening_balance": 2,
        },
        "finance_import_ready": False,
        "import_ready": False,
        "manifest": {
            "apply_mode": False,
            "no_write": True,
            "repo_sha": "test-sha",
        },
        "mapping_summary": {
            "nonzero_mapping_coverage": "1.0000",
            "unmapped_nonzero_candidates": 0,
        },
        "samples": {
            "eligible_opening_balance": [
                {
                    "amount_pence": 1000,
                    "decision": "eligible_opening_balance",
                    "mapped_patient_id": 101,
                    "proposed_pms_direction": "increase_debt",
                    "source_patient_code": "PRIVATE-SHOULD-NOT-PRINT-1",
                },
                {
                    "amount_pence": -425,
                    "decision": "eligible_opening_balance",
                    "mapped_patient_id": 102,
                    "proposed_pms_direction": "decrease_debt_or_credit",
                    "source_patient_code": "PRIVATE-SHOULD-NOT-PRINT-2",
                },
            ]
        },
        "source_summary": {"known_totals": {"total_balance": "5.75"}},
    }
    payload.update(overrides)
    return payload


def test_opening_balance_live_gate_builds_classification_only_ready_packet():
    packet = safe_packet()

    assert packet["Guarded finance/import process available"] == "yes"
    assert (
        packet["Opening-balance/live finance import execution readiness"] == "ready"
    )
    assert (
        packet["Invoice/payment/staging import execution readiness"] == "blocked"
    )
    assert packet["finance_import_ready"] is False
    assert packet["Execution performed"] == "no"
    assert packet["No secrets exposed"] == "yes"
    assert packet["No patient data exposed"] == "yes"
    assert packet["No private paths exposed"] == "yes"
    assert packet["No backup contents exposed"] == "yes"


def test_live_target_requires_production_execution_gate():
    packet = safe_packet(production_execution_gate=None)

    assert (
        packet["Opening-balance/live finance import execution readiness"] == "blocked"
    )
    assert "production_execution_gate_required" in packet["Blocker classification"]


def test_unclear_production_target_classification_is_refused():
    packet = safe_packet(target_classification="production")

    assert (
        packet["Opening-balance/live finance import execution readiness"] == "blocked"
    )
    assert "target_classification_refused" in packet["Blocker classification"]


def test_apply_mode_requires_confirmation_token():
    packet = safe_packet(apply_requested=True, apply_confirmation=None)

    assert (
        packet["Opening-balance/live finance import execution readiness"] == "blocked"
    )
    assert "apply_confirmation_required" in packet["Blocker classification"]

    accepted = safe_packet(
        apply_requested=True,
        apply_confirmation=GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN,
    )
    assert (
        accepted["Opening-balance/live finance import execution readiness"] == "ready"
    )
    assert "apply_confirmation_accepted" in accepted["Reason classification"]


def test_invoice_payment_staging_categories_fail_closed():
    for category in ("invoice", "payment", "staging"):
        packet = safe_packet(import_category=category)

        assert (
            packet["Opening-balance/live finance import execution readiness"]
            == "blocked"
        )
        assert category in packet["Blocker classification"]
        assert (
            packet["Invoice/payment/staging import execution readiness"] == "blocked"
        )


def test_missing_or_sensitive_manifest_fails_closed():
    missing = safe_packet(manifest={})
    sensitive = safe_packet(
        manifest=manifest(
            sensitive_data_policy={
                "committed_fixture_contains_real_r4_data": True,
                "committed_fixture_contains_real_patient_data": False,
            }
        )
    )

    assert "manifest_missing_or_unclear" in missing["Blocker classification"]
    assert (
        "manifest_declares_sensitive_committed_data"
        in sensitive["Blocker classification"]
    )


def test_cli_prints_classification_only_without_manifest_path_or_sample_values(
    tmp_path,
    capsys,
):
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "packet.json"
    manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")

    assert (
        execution_script.main(
            [
                "--manifest-json",
                str(manifest_path),
                "--category",
                "opening-balance",
                "--target-classification",
                LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
                "--production-execution-gate",
                GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
                "--output-json",
                str(output_path),
                "--confirm-no-secret-output",
                "--confirm-no-patient-data-output",
                "--confirm-no-private-path-output",
                "--confirm-no-backup-content-output",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    packet = json.loads(stdout)
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert packet == saved
    assert packet["Guarded finance/import process available"] == "yes"
    assert str(manifest_path) not in stdout
    assert str(output_path) not in stdout
    assert "PRIVATE-SHOULD-NOT-PRINT" not in stdout
    assert "mapped_patient_id" not in stdout


def test_cli_missing_manifest_fails_closed_without_path_traceback(tmp_path, capsys):
    missing_path = tmp_path / "missing.json"

    assert (
        execution_script.main(
            [
                "--manifest-json",
                str(missing_path),
                "--category",
                "opening-balance",
                "--target-classification",
                LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
                "--production-execution-gate",
                GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
                "--confirm-no-secret-output",
                "--confirm-no-patient-data-output",
                "--confirm-no-private-path-output",
                "--confirm-no-backup-content-output",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    packet = json.loads(stdout)
    assert (
        packet["Opening-balance/live finance import execution readiness"] == "blocked"
    )
    assert "manifest_missing_or_unclear" in packet["Blocker classification"]
    assert str(missing_path) not in stdout
    assert "Traceback" not in stdout


def test_opening_balance_execution_preflight_requires_full_report_and_keeps_no_write():
    packet = build_guarded_finance_import_execution_result(
        manifest=manifest(),
        opening_balance_report=report(),
        target_classification=LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
        apply_requested=False,
        production_execution_gate=GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
        expected_total_balance="5.75",
        expected_eligible_count=2,
        expected_repo_sha="test-sha",
        no_secrets_exposed=True,
        no_patient_data_exposed=True,
        no_private_paths_exposed=True,
        no_backup_contents_exposed=True,
    )

    assert (
        packet["Opening-balance/live finance import execution readiness"] == "ready"
    )
    assert packet["Opening-balance/live finance import execution result"] == "not checked"
    assert packet["Invoice/payment/staging import execution result"] == "blocked"
    assert packet["finance_import_ready"] is False
    assert packet["Result counts classification"] == {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "refused": 0,
    }


def test_mapped_only_scope_defers_expected_missing_target_rows(monkeypatch):
    def fake_mapped_only_scope(**kwargs):
        return execution_service._MappedOnlyScope(
            adjustments=kwargs["adjustments"][:1],
            missing_target_mapping_count=1,
        )

    monkeypatch.setattr(
        execution_service,
        "_prepare_target_present_mapped_only_scope",
        fake_mapped_only_scope,
    )

    packet = build_guarded_finance_import_execution_result(
        manifest=manifest(),
        opening_balance_report=report(),
        target_classification=LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
        database_url="safe-test-db-url",
        apply_requested=False,
        production_execution_gate=GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
        expected_total_balance="5.75",
        expected_eligible_count=2,
        expected_repo_sha="test-sha",
        defer_missing_target_mappings=True,
        expected_missing_target_mapping_count=1,
        no_secrets_exposed=True,
        no_patient_data_exposed=True,
        no_private_paths_exposed=True,
        no_backup_contents_exposed=True,
    )

    assert packet["Guarded mapped-only scope available"] == "yes"
    assert packet["Missing target mapping count"] == 1
    assert packet["Rows deferred/excluded"] == 1
    assert packet["Rows eligible for mapped-only guarded import"] == 1
    assert (
        packet["Opening-balance/live finance import execution readiness"] == "ready"
    )
    assert packet["Opening-balance/live finance import execution result"] == "not checked"
    assert packet["Mapped patient target remediation status"] == "partially remediated"
    assert packet["finance_import_ready"] is False
    assert (
        "target_present_mapped_only_scope_prepared"
        in packet["Reason classification"]
    )


def test_mapped_only_scope_refuses_missing_target_count_mismatch(monkeypatch):
    def fake_mapped_only_scope(**kwargs):
        return execution_service._MappedOnlyScope(
            adjustments=kwargs["adjustments"][:1],
            missing_target_mapping_count=2,
        )

    monkeypatch.setattr(
        execution_service,
        "_prepare_target_present_mapped_only_scope",
        fake_mapped_only_scope,
    )

    packet = build_guarded_finance_import_execution_result(
        manifest=manifest(),
        opening_balance_report=report(),
        target_classification=LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
        database_url="safe-test-db-url",
        apply_requested=False,
        production_execution_gate=GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
        expected_total_balance="5.75",
        expected_eligible_count=2,
        expected_repo_sha="test-sha",
        defer_missing_target_mappings=True,
        expected_missing_target_mapping_count=1,
        no_secrets_exposed=True,
        no_patient_data_exposed=True,
        no_private_paths_exposed=True,
        no_backup_contents_exposed=True,
    )

    assert packet["Guarded mapped-only scope available"] == "no"
    assert packet["Missing target mapping count"] == 2
    assert (
        packet["Opening-balance/live finance import execution readiness"] == "blocked"
    )
    assert "missing_target_mapping_count_mismatch" in packet["Blocker classification"]
    assert packet["finance_import_ready"] is False


def test_opening_balance_execution_blocks_incomplete_report_source():
    incomplete = report(
        eligibility_summary={
            "ambiguous_sign_would_write_count": 0,
            "component_mismatch_would_write_count": 0,
            "eligible_opening_balance": 3,
        }
    )

    packet = build_guarded_finance_import_execution_result(
        manifest=manifest(),
        opening_balance_report=incomplete,
        target_classification=LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
        apply_requested=False,
        production_execution_gate=GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
        no_secrets_exposed=True,
        no_patient_data_exposed=True,
        no_private_paths_exposed=True,
        no_backup_contents_exposed=True,
    )

    assert (
        packet["Opening-balance/live finance import execution readiness"] == "blocked"
    )
    assert "full_eligible_row_source_required" in packet["Blocker classification"]


def test_apply_execution_requires_database_env_actor_and_confirmation():
    packet = build_guarded_finance_import_execution_result(
        manifest=manifest(),
        opening_balance_report=report(),
        target_classification=LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
        apply_requested=True,
        apply_confirmation=GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN,
        production_execution_gate=GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
        no_secrets_exposed=True,
        no_patient_data_exposed=True,
        no_private_paths_exposed=True,
        no_backup_contents_exposed=True,
    )

    assert (
        packet["Opening-balance/live finance import execution result"] == "blocked"
    )
    assert "actor_id_required" in packet["Blocker classification"]
    assert "database_url_env_missing" in packet["Blocker classification"]


def test_apply_target_coverage_blocks_before_write(monkeypatch):
    def fake_target_coverage(**_kwargs):
        raise GuardedFinanceImportExecutionError("mapped_patient_missing_in_target")

    def fake_apply(**_kwargs):  # pragma: no cover - should not be reached
        raise AssertionError("apply should not run before target coverage passes")

    monkeypatch.setattr(
        execution_service,
        "_check_opening_balance_target_patient_coverage",
        fake_target_coverage,
    )
    monkeypatch.setattr(
        execution_service,
        "_apply_opening_balance_adjustments",
        fake_apply,
    )

    packet = build_guarded_finance_import_execution_result(
        manifest=manifest(),
        opening_balance_report=report(),
        target_classification=LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
        database_url="safe-test-db-url",
        apply_requested=True,
        apply_confirmation=GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN,
        production_execution_gate=GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
        actor_id=1,
        expected_total_balance="5.75",
        expected_eligible_count=2,
        expected_repo_sha="test-sha",
        no_secrets_exposed=True,
        no_patient_data_exposed=True,
        no_private_paths_exposed=True,
        no_backup_contents_exposed=True,
    )

    assert (
        packet["Opening-balance/live finance import execution readiness"] == "blocked"
    )
    assert (
        packet["Opening-balance/live finance import execution result"] == "blocked"
    )
    assert "mapped_patient_missing_in_target" in packet["Blocker classification"]
    assert packet["Import write-state after failed run"] == "no writes"
    assert packet["Rollback required"] == "no"
    assert packet["Rollback executed"] == "not required"
    assert packet["Mapped patient target remediation status"] == "blocked"


def test_apply_success_requires_target_coverage_first(monkeypatch):
    calls = []

    def fake_target_coverage(**_kwargs):
        calls.append("coverage")

    def fake_apply(**_kwargs):
        calls.append("apply")
        return 2, 0

    monkeypatch.setattr(
        execution_service,
        "_check_opening_balance_target_patient_coverage",
        fake_target_coverage,
    )
    monkeypatch.setattr(
        execution_service,
        "_apply_opening_balance_adjustments",
        fake_apply,
    )

    packet = build_guarded_finance_import_execution_result(
        manifest=manifest(),
        opening_balance_report=report(),
        target_classification=LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
        database_url="safe-test-db-url",
        apply_requested=True,
        apply_confirmation=GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN,
        production_execution_gate=GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
        actor_id=1,
        expected_total_balance="5.75",
        expected_eligible_count=2,
        expected_repo_sha="test-sha",
        no_secrets_exposed=True,
        no_patient_data_exposed=True,
        no_private_paths_exposed=True,
        no_backup_contents_exposed=True,
    )

    assert calls == ["coverage", "apply"]
    assert packet["Opening-balance/live finance import execution result"] == "pass"
    assert packet["Mapped patient target remediation status"] == "remediated"
    assert packet["finance_import_ready"] is True


def test_cli_with_report_prints_classification_only_without_paths_or_rows(
    tmp_path,
    capsys,
):
    manifest_path = tmp_path / "manifest.json"
    report_path = tmp_path / "report.json"
    manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
    report_path.write_text(json.dumps(report()), encoding="utf-8")

    assert (
        execution_script.main(
            [
                "--manifest-json",
                str(manifest_path),
                "--opening-balance-report-json",
                str(report_path),
                "--category",
                "opening-balance",
                "--target-classification",
                LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
                "--production-execution-gate",
                GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
                "--expected-total-balance",
                "5.75",
                "--expected-eligible-count",
                "2",
                "--expected-repo-sha",
                "test-sha",
                "--confirm-no-secret-output",
                "--confirm-no-patient-data-output",
                "--confirm-no-private-path-output",
                "--confirm-no-backup-content-output",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    packet = json.loads(stdout)
    assert (
        packet["Opening-balance/live finance import execution readiness"] == "ready"
    )
    assert str(manifest_path) not in stdout
    assert str(report_path) not in stdout
    assert "PRIVATE-SHOULD-NOT-PRINT" not in stdout
    assert "mapped_patient_id" not in stdout


def test_cli_mapped_only_scope_smoke_outputs_counts_only(
    tmp_path,
    capsys,
    monkeypatch,
):
    def fake_mapped_only_scope(**kwargs):
        return execution_service._MappedOnlyScope(
            adjustments=kwargs["adjustments"][:1],
            missing_target_mapping_count=1,
        )

    monkeypatch.setattr(
        execution_service,
        "_prepare_target_present_mapped_only_scope",
        fake_mapped_only_scope,
    )
    monkeypatch.setenv("SAFE_DATABASE_URL", "safe-test-db-url")
    manifest_path = tmp_path / "manifest.json"
    report_path = tmp_path / "report.json"
    manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
    report_path.write_text(json.dumps(report()), encoding="utf-8")

    assert (
        execution_script.main(
            [
                "--manifest-json",
                str(manifest_path),
                "--opening-balance-report-json",
                str(report_path),
                "--category",
                "opening-balance",
                "--target-classification",
                LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
                "--production-execution-gate",
                GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
                "--expected-total-balance",
                "5.75",
                "--expected-eligible-count",
                "2",
                "--expected-repo-sha",
                "test-sha",
                "--database-url-env",
                "SAFE_DATABASE_URL",
                "--defer-missing-target-mappings",
                "--expected-missing-target-mapping-count",
                "1",
                "--confirm-no-secret-output",
                "--confirm-no-patient-data-output",
                "--confirm-no-private-path-output",
                "--confirm-no-backup-content-output",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    packet = json.loads(stdout)
    assert packet["Guarded mapped-only scope available"] == "yes"
    assert packet["Missing target mapping count"] == 1
    assert packet["Rows deferred/excluded"] == 1
    assert packet["Rows eligible for mapped-only guarded import"] == 1
    assert str(manifest_path) not in stdout
    assert str(report_path) not in stdout
    assert "PRIVATE-SHOULD-NOT-PRINT" not in stdout
    assert "mapped_patient_id" not in stdout
    assert "safe-test-db-url" not in stdout
