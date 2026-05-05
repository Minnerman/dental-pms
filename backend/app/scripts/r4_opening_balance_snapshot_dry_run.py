from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Sequence

from app.services.r4_import.opening_balance_snapshot_dry_run import (
    SOURCE_MODE_PATIENT_STATS_JSON,
    build_opening_balance_snapshot_dry_run_report,
    load_patient_mapping_json,
    load_patient_stats_rows_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "No-write opening-balance snapshot dry-run/report from PatientStats "
            "rows and patient mapping evidence."
        )
    )
    parser.add_argument(
        "--patient-stats-json",
        required=True,
        help="JSON list, or object containing patient_stats_rows/rows.",
    )
    parser.add_argument(
        "--patient-mapping-json",
        required=True,
        help="JSON object/list mapping R4 PatientCode values to PMS patient IDs.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write the dry-run report JSON.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="Bounded per-decision samples to include in the report.",
    )
    parser.add_argument(
        "--repo-sha",
        default=None,
        help="Repo SHA for the manifest. Defaults to git rev-parse HEAD if available.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.sample_limit < 1:
        raise RuntimeError("--sample-limit must be at least 1.")

    patient_stats_path = Path(args.patient_stats_json)
    patient_mapping_path = Path(args.patient_mapping_json)
    output_path = Path(args.output_json)

    rows = load_patient_stats_rows_json(patient_stats_path)
    patient_mapping = load_patient_mapping_json(patient_mapping_path)
    report = build_opening_balance_snapshot_dry_run_report(
        rows,
        patient_mapping,
        source_mode=SOURCE_MODE_PATIENT_STATS_JSON,
        source_artifact_path=str(patient_stats_path),
        repo_sha=args.repo_sha or _repo_sha(),
        sample_limit=args.sample_limit,
        dry_run_parameters={
            "patient_stats_json": str(patient_stats_path),
            "mapping_source": str(patient_mapping_path),
            "output_json": str(output_path),
            "sample_limit": args.sample_limit,
        },
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "output_json": str(output_path),
        "dry_run": report["dry_run"],
        "source_mode": report["source_mode"],
        "row_count": report["source_summary"]["row_count"],
        "eligible_opening_balance": report["eligibility_summary"][
            "eligible_opening_balance"
        ],
        "no_op_zero_balance": report["eligibility_summary"]["no_op_zero_balance"],
        "unmapped_nonzero_candidates": report["mapping_summary"][
            "unmapped_nonzero_candidates"
        ],
        "import_ready": report["import_ready"],
        "no_write": report["manifest"]["no_write"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _repo_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
