from __future__ import annotations

import argparse
import json
import os

from app.services.r4_import.guarded_finance_import_execution import (
    GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN,
    GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN,
    GuardedFinanceImportExecutionError,
    build_guarded_finance_import_execution_packet,
    load_execution_manifest,
    write_classification_packet,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a classification-only guarded finance/import execution "
            "readiness packet. The command defaults to dry-run/no-write, does "
            "not connect to databases, and does not run import."
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
            "Target classification only, not a DSN or URL. Live/default targets "
            "require the production execution gate."
        ),
    )
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
