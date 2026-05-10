from __future__ import annotations

import json

from app.scripts import r4_guarded_finance_import_execution as execution_script
from app.services.r4_import.guarded_finance_import_execution import (
    GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN,
    GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
    build_guarded_finance_import_execution_packet,
)


def manifest(**overrides):
    payload = {
        "manifest_id": "finance-import-20260510-000001",
        "import_category": "opening-balance",
        "target": {"classification": "production"},
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
        "target_classification": "production",
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


def test_opening_balance_production_gate_builds_classification_only_ready_packet():
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
                "production",
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
                "production",
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
