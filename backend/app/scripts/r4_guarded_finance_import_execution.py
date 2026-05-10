from __future__ import annotations

import argparse
import json
import os

from app.services.r4_import.guarded_finance_import_execution import (
    GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN,
    GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
    LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
    GuardedFinanceImportExecutionError,
    build_guarded_finance_import_execution_result,
    build_guarded_finance_import_execution_packet,
    compute_sha256,
    load_execution_manifest,
    load_opening_balance_report,
    write_classification_packet,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build or execute a classification-only guarded opening-balance "
            "finance import path. The command defaults to dry-run/no-write; "
            "apply mode requires explicit gates and never prints DSNs, paths, "
            "patient rows, logs, configs, or database output."
        )
    )
    parser.add_argument(
        "--manifest-json",
        required=True,
        help="Execution manifest JSON. The path is not included in output.",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Import category, for example opening-balance.",
    )
    parser.add_argument(
        "--target-classification",
        default=None,
        help=(
            "Target classification only, not a DSN or URL. Live apply requires "
            f"{LIVE_DENTAL_PMS_TARGET_CLASSIFICATION}."
        ),
    )
    parser.add_argument(
        "--opening-balance-report-json",
        default=None,
        help=(
            "Optional prior no-write opening-balance report JSON. Required for "
            "guarded execution readiness and apply."
        ),
    )
    parser.add_argument(
        "--database-url-env",
        default="DATABASE_URL",
        help=(
            "Environment variable containing the PMS database URL. The value is "
            "never printed. Only read when --apply is used."
        ),
    )
    parser.add_argument(
        "--actor-id",
        type=int,
        default=None,
        help="PMS user ID for audit fields. Required with --apply.",
    )
    parser.add_argument("--expected-report-sha256", default=None)
    parser.add_argument("--expected-total-balance", default=None)
    parser.add_argument("--expected-eligible-count", type=int, default=None)
    parser.add_argument("--expected-repo-sha", default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Request future apply/write mode. Still does not execute import here.",
    )
    parser.add_argument(
        "--confirm",
        default=os.getenv("GUARDED_FINANCE_IMPORT_APPLY_CONFIRM"),
        help=(
            "Required with --apply and must be "
            f"{GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN}."
        ),
    )
    parser.add_argument(
        "--production-execution-gate",
        default=os.getenv("GUARDED_FINANCE_IMPORT_PRODUCTION_GATE"),
        help=(
            "Required for live/default targets and must be "
            f"{GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN}."
        ),
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional destination for the classification-only packet.",
    )
    parser.add_argument("--confirm-no-secret-output", action="store_true")
    parser.add_argument("--confirm-no-patient-data-output", action="store_true")
    parser.add_argument("--confirm-no-private-path-output", action="store_true")
    parser.add_argument("--confirm-no-backup-content-output", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = load_execution_manifest(args.manifest_json)
    except GuardedFinanceImportExecutionError:
        manifest = None
    opening_balance_report = None
    report_sha256 = None
    if args.opening_balance_report_json:
        try:
            opening_balance_report = load_opening_balance_report(
                args.opening_balance_report_json
            )
            report_sha256 = compute_sha256(args.opening_balance_report_json)
        except GuardedFinanceImportExecutionError:
            opening_balance_report = None

    if args.opening_balance_report_json or args.apply:
        packet = build_guarded_finance_import_execution_result(
            manifest=manifest,
            opening_balance_report=opening_balance_report,
            target_classification=args.target_classification,
            database_url=os.getenv(args.database_url_env) if args.apply else None,
            apply_requested=args.apply,
            apply_confirmation=args.confirm,
            production_execution_gate=args.production_execution_gate,
            actor_id=args.actor_id,
            expected_report_sha256=args.expected_report_sha256,
            observed_report_sha256=report_sha256,
            expected_total_balance=args.expected_total_balance,
            expected_eligible_count=args.expected_eligible_count,
            expected_repo_sha=args.expected_repo_sha,
            no_secrets_exposed=args.confirm_no_secret_output,
            no_patient_data_exposed=args.confirm_no_patient_data_output,
            no_private_paths_exposed=args.confirm_no_private_path_output,
            no_backup_contents_exposed=args.confirm_no_backup_content_output,
        )
    else:
        packet = build_guarded_finance_import_execution_packet(
            manifest=manifest,
            import_category=args.category,
            target_classification=args.target_classification,
            apply_requested=args.apply,
            apply_confirmation=args.confirm,
            production_execution_gate=args.production_execution_gate,
            no_secrets_exposed=args.confirm_no_secret_output,
            no_patient_data_exposed=args.confirm_no_patient_data_output,
            no_private_paths_exposed=args.confirm_no_private_path_output,
            no_backup_contents_exposed=args.confirm_no_backup_content_output,
        )
    if args.output_json:
        write_classification_packet(args.output_json, packet)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
