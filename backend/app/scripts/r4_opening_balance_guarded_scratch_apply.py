from __future__ import annotations

import argparse
import json

from app.services.r4_import.opening_balance_snapshot_apply_plan import (
    OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
)
from app.services.r4_import.opening_balance_snapshot_guarded_apply import (
    run_opening_balance_scratch_apply,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Guarded scratch-only R4 opening-balance apply prototype. The command "
            "validates a prior no-write opening-balance dry-run report, refuses "
            "non-scratch targets, defaults to no writes, and only writes "
            "PatientLedgerEntry adjustment rows when --apply and the confirmation "
            "token are both supplied."
        )
    )
    parser.add_argument(
        "--dry-run-report-json",
        required=True,
        help="Path to the prior opening-balance dry-run JSON report.",
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help=(
            "Explicit scratch/test PMS database URL. The command refuses default, "
            "live, production-looking, or ambiguous targets."
        ),
    )
    parser.add_argument(
        "--manifest-id",
        required=True,
        help="Manifest/run ID used in ledger references and idempotency guards.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write validation/apply JSON output.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write guarded scratch ledger adjustment rows.",
    )
    parser.add_argument(
        "--confirm",
        default=None,
        help=(
            "Second write guard. Required with --apply and must be "
            f"{OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN}."
        ),
    )
    parser.add_argument(
        "--actor-id",
        type=int,
        default=None,
        help="PMS user ID for audit fields; required with --apply.",
    )
    parser.add_argument(
        "--expected-report-sha256",
        default=None,
        help="Optional expected SHA256 for the dry-run report file.",
    )
    parser.add_argument(
        "--expected-total-balance",
        default=None,
        help="Optional expected source_summary.known_totals.total_balance value.",
    )
    parser.add_argument(
        "--expected-eligible-count",
        type=int,
        default=None,
        help="Optional expected eligible_opening_balance count.",
    )
    parser.add_argument(
        "--expected-repo-sha",
        default=None,
        help="Optional expected dry-run manifest repo SHA.",
    )
    parser.add_argument(
        "--acknowledge-source-drift",
        action="store_true",
        help="Allow planning/apply when the dry-run report records source drift.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=5,
        help="Maximum sample planned rows to include in preflight output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.sample_limit < 1:
        parser.error("--sample-limit must be at least 1.")
    if args.apply and args.confirm != OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN:
        parser.error(
            "Refusing scratch apply without --confirm "
            f"{OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN}."
        )
    if args.apply and args.actor_id is None:
        parser.error("Refusing scratch apply without --actor-id.")

    payload = run_opening_balance_scratch_apply(
        dry_run_report_path=args.dry_run_report_json,
        database_url=args.database_url,
        manifest_id=args.manifest_id,
        apply=args.apply,
        confirmation_token=args.confirm,
        actor_id=args.actor_id,
        output_json=args.output_json,
        expected_report_sha256=args.expected_report_sha256,
        expected_total_balance=args.expected_total_balance,
        expected_eligible_count=args.expected_eligible_count,
        expected_repo_sha=args.expected_repo_sha,
        acknowledge_source_drift=args.acknowledge_source_drift,
        sample_limit=args.sample_limit,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
