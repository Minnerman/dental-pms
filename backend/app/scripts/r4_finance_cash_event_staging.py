from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.r4_import.finance_cash_event_staging import (
    run_cash_event_staging_proof,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SELECT-only R4 finance cash-event staging proof report."
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="Bounded cash-event/refund/cancellation sample rows to include.",
    )
    parser.add_argument(
        "--top-limit",
        type=int,
        default=10,
        help="Bounded payment method/type distribution rows to include.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write cash-event staging proof JSON.",
    )
    args = parser.parse_args()
    if args.sample_limit < 1:
        raise RuntimeError("--sample-limit must be at least 1.")
    if args.top_limit < 1:
        raise RuntimeError("--top-limit must be at least 1.")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    report = run_cash_event_staging_proof(
        source,
        sample_limit=args.sample_limit,
        top_limit=args.top_limit,
    )

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    candidate_population = report["candidate_population"]
    cancellation_pairing = report["cancellation_pairing"]
    refund_handling = report["refund_handling"]
    credit_handling = report["credit_handling"]
    summary = {
        "output_json": str(output_path),
        "select_only": report["select_only"],
        "candidate_population": {
            "vw_payments_rows": candidate_population["vw_payments_summary"].get(
                "row_count"
            ),
            "adjustments_rows": candidate_population["adjustments_summary"].get(
                "row_count"
            ),
            "eligible_cash_event_candidates": candidate_population.get(
                "eligible_cash_event_candidate_count"
            ),
            "manual_review": candidate_population.get("manual_review_count"),
            "excluded": candidate_population.get("excluded_count"),
            "cancellation_or_reversal": candidate_population.get(
                "cancellation_or_reversal_count"
            ),
        },
        "cancellation_pairing": {
            "adjustments_cancellation_of": cancellation_pairing["summary"].get(
                "cancellation_of_count"
            ),
            "paired_originals": cancellation_pairing["summary"].get(
                "original_found_count"
            ),
            "missing_originals": cancellation_pairing["summary"].get(
                "original_missing_count"
            ),
            "paired_net_amount": cancellation_pairing["summary"].get(
                "paired_net_amount"
            ),
        },
        "refund_handling": {
            "vw_refunds": refund_handling["vw_payments_refunds"].get(
                "refund_row_count"
            ),
            "refund_candidates": refund_handling["vw_payments_refunds"].get(
                "refund_candidate_count"
            ),
            "allocation_refunds": refund_handling["allocation_refund_overlap"].get(
                "allocation_refund_count"
            ),
            "allocation_refunds_without_vw_refund": refund_handling[
                "allocation_refund_overlap"
            ].get("allocation_refunds_without_vw_refund_count"),
            "vw_refunds_without_allocation": refund_handling[
                "vw_refunds_without_allocation"
            ].get("vw_refunds_without_allocation_count"),
        },
        "credit_handling": {
            "vw_credits": credit_handling["vw_payments_credits"].get(
                "credit_row_count"
            ),
            "credit_candidates": credit_handling["vw_payments_credits"].get(
                "credit_candidate_count"
            ),
            "advanced_payment_allocations": credit_handling[
                "advanced_payment_allocations"
            ].get("advanced_payment_allocation_count"),
        },
        "import_readiness": report["import_readiness"],
        "risks": report["risks"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
