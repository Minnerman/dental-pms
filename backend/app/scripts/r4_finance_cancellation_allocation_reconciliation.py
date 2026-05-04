from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.r4_import.finance_cancellation_allocation_reconciliation import (
    run_cancellation_allocation_reconciliation,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "SELECT-only R4 finance cancellation/refund/allocation reconciliation "
            "proof report."
        )
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="Bounded cancellation/refund/allocation risk/sample rows to include.",
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
    report = run_cancellation_allocation_reconciliation(
        source,
        sample_limit=args.sample_limit,
    )

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    cancellation_pairing = report["cancellation_pairing"]
    refund_mismatch = report["refund_allocation_mismatch"]
    advanced_credit = report["advanced_payment_credit_allocation"]
    summary = {
        "output_json": str(output_path),
        "select_only": report["select_only"],
        "cancellation_pairing": {
            "vw_payments_cancelled": cancellation_pairing[
                "vw_payments_cancelled"
            ].get("cancelled_row_count"),
            "adjustments_cancellation_of": cancellation_pairing[
                "adjustments_cancellation_of"
            ].get("cancellation_of_count"),
            "paired_originals": cancellation_pairing["adjustments_cancellation_of"].get(
                "original_found_count"
            ),
            "missing_originals": cancellation_pairing["adjustments_cancellation_of"].get(
                "original_missing_count"
            ),
        },
        "refund_allocation_mismatch": {
            "vw_payments_refunds": refund_mismatch["vw_payments_refunds"].get(
                "refund_count"
            ),
            "payment_allocations_refunds": refund_mismatch[
                "payment_allocations_refunds"
            ].get("refund_count"),
            "matching_allocation_refunds": refund_mismatch[
                "overlap_by_payment_id_refid"
            ].get("matching_vw_refund_count"),
            "allocation_refunds_without_vw_refund": refund_mismatch[
                "overlap_by_payment_id_refid"
            ].get("without_matching_vw_refund_count"),
            "vw_refunds_without_allocation": refund_mismatch[
                "vw_refunds_without_allocation"
            ].get("vw_refunds_without_allocation_count"),
        },
        "advanced_payment_credit_allocation": {
            "vw_payments_credits": advanced_credit["vw_payments_credits"].get(
                "credit_count"
            ),
            "advanced_payment_allocations": advanced_credit["payment_allocations"].get(
                "advanced_payment_count"
            ),
            "missing_charge_ref_allocations": advanced_credit[
                "payment_allocations"
            ].get("missing_charge_ref_count"),
        },
        "risks": report["risks"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
