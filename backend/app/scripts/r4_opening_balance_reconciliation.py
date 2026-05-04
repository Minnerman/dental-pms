from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.r4_import.opening_balance_reconciliation import (
    run_opening_balance_reconciliation,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SELECT-only R4 opening balance reconciliation proof report."
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="Bounded PatientStats risk/sample rows to include.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write reconciliation JSON.",
    )
    args = parser.parse_args()
    if args.sample_limit < 1:
        raise RuntimeError("--sample-limit must be at least 1.")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    report = run_opening_balance_reconciliation(
        source,
        sample_limit=args.sample_limit,
    )

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    patient_summary = report["patient_stats_consistency"]["summary"]
    aged_summary = report["aged_debt"]["summary"]
    summary = {
        "output_json": str(output_path),
        "select_only": report["select_only"],
        "patient_stats": {
            "row_count": patient_summary.get("row_count"),
            "nonzero_balance_count": patient_summary.get("nonzero_balance_count"),
            "total_balance": patient_summary.get("total_balance"),
            "balance_component_mismatch_count": patient_summary.get(
                "balance_component_mismatch_count"
            ),
            "treatment_split_mismatch_count": patient_summary.get(
                "treatment_split_mismatch_count"
            ),
        },
        "aged_debt": {
            "total_aged_debt": aged_summary.get("total_aged_debt"),
            "rows_with_aged_debt": aged_summary.get("rows_with_aged_debt"),
            "aged_debt_with_zero_balance_count": aged_summary.get(
                "aged_debt_with_zero_balance_count"
            ),
            "balance_without_aged_debt_count": aged_summary.get(
                "balance_without_aged_debt_count"
            ),
        },
        "patient_linkage": report["patient_linkage"],
        "risks": report["risks"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
