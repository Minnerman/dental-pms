from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.r4_import.finance_classification_policy import (
    R4FinanceClassificationResult,
    classify_finance_row,
    summarize_finance_classifications,
)
from app.services.r4_import.sqlserver_source import R4SqlServerSource

__all__ = [
    "run_cancellation_allocation_reconciliation",
]


MONEY_ZERO = "CAST(0 AS decimal(19,2))"
TOLERANCE = Decimal("0.01")


def run_cancellation_allocation_reconciliation(
    source: R4SqlServerSource,
    *,
    sample_limit: int = 10,
) -> dict[str, Any]:
    source.ensure_select_only()
    if sample_limit < 1:
        raise RuntimeError("sample_limit must be at least 1.")

    cancellation_pairing = _cancellation_pairing(source, sample_limit=sample_limit)
    cancellation_impact = _cancellation_impact(cancellation_pairing)
    refund_mismatch = _refund_allocation_mismatch(source, sample_limit=sample_limit)
    advanced_credit = _advanced_payment_credit_allocation(
        source,
        sample_limit=sample_limit,
    )
    samples = {
        "cancellation_pairing": cancellation_pairing.pop("samples"),
        "refund_allocation_mismatch": refund_mismatch.pop("samples"),
        "advanced_payment_credit_allocation": advanced_credit.pop("samples"),
    }
    classification_summary = _classification_summary(samples)
    risks = _risks(
        cancellation_pairing=cancellation_pairing,
        cancellation_impact=cancellation_impact,
        refund_mismatch=refund_mismatch,
        advanced_credit=advanced_credit,
        classification_summary=classification_summary,
    )

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "select_only": True,
        "query_shape": {
            "query_types": [
                "aggregate cancellation pairing checks",
                "bounded cancellation/refund/allocation risk samples",
                "aggregate refund/allocation overlap checks",
                "classification sample proof",
            ],
            "sources": [
                "dbo.vwPayments",
                "dbo.Adjustments",
                "dbo.PaymentAllocations",
                "dbo.vwAllocatedPayments",
            ],
        },
        "cancellation_pairing": cancellation_pairing,
        "cancellation_impact": cancellation_impact,
        "refund_allocation_mismatch": refund_mismatch,
        "advanced_payment_credit_allocation": advanced_credit,
        "classification_summary": classification_summary,
        "risks": risks,
        "samples": samples,
    }


def _cancellation_pairing(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> dict[str, Any]:
    vw_cancelled = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS cancelled_row_count, "
                    f"{_sum_money('Amount', 'cancelled_total_amount')}, "
                    "SUM(CASE WHEN [IsPayment] = 1 THEN 1 ELSE 0 END) "
                    "AS cancelled_payment_count, "
                    "SUM(CASE WHEN [IsRefund] = 1 THEN 1 ELSE 0 END) "
                    "AS cancelled_refund_count, "
                    "SUM(CASE WHEN [IsCredit] = 1 THEN 1 ELSE 0 END) "
                    "AS cancelled_credit_count "
                    "FROM dbo.vwPayments WITH (NOLOCK) "
                    "WHERE [IsCancelled] = 1"
                ),
            )
        )
    )
    adjustment_pairing = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS cancellation_of_count, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS original_found_count, "
                    "SUM(CASE WHEN o.[RefId] IS NULL THEN 1 ELSE 0 END) "
                    "AS original_missing_count, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL AND "
                    f"{_same_text_expr('c.PatientCode', 'o.PatientCode')} "
                    "THEN 1 ELSE 0 END) AS patient_match_count, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL AND NOT "
                    f"{_same_text_expr('c.PatientCode', 'o.PatientCode')} "
                    "THEN 1 ELSE 0 END) AS patient_mismatch_count, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL AND "
                    "ABS(CAST(ISNULL(c.[Amount], 0) AS decimal(19,2)) + "
                    "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2))) <= 0.01 "
                    "THEN 1 ELSE 0 END) AS opposite_amount_match_count, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL AND "
                    "ABS(CAST(ISNULL(c.[Amount], 0) AS decimal(19,2)) - "
                    "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2))) <= 0.01 "
                    "THEN 1 ELSE 0 END) AS same_amount_match_count, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL AND c.[At] >= o.[At] "
                    "THEN 1 ELSE 0 END) AS cancellation_after_or_same_count, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL AND c.[At] < o.[At] "
                    "THEN 1 ELSE 0 END) AS cancellation_before_original_count, "
                    "SUM(CAST(ISNULL(c.[Amount], 0) AS decimal(19,2))) "
                    "AS cancellation_total_amount, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL THEN "
                    "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2)) ELSE "
                    f"{MONEY_ZERO} END) AS paired_original_total_amount, "
                    "SUM(CASE WHEN o.[RefId] IS NOT NULL THEN "
                    "CAST(ISNULL(c.[Amount], 0) AS decimal(19,2)) + "
                    "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2)) ELSE "
                    f"{MONEY_ZERO} END) AS paired_net_amount "
                    "FROM dbo.Adjustments c WITH (NOLOCK) "
                    "LEFT JOIN dbo.Adjustments o WITH (NOLOCK) "
                    "ON c.[CancellationOf] = o.[RefId] "
                    "WHERE c.[CancellationOf] IS NOT NULL"
                ),
            )
        )
    )
    return {
        "vw_payments_cancelled": vw_cancelled,
        "adjustments_cancellation_of": adjustment_pairing,
        "interpretation": (
            "Cancelled/reversal rows remain excluded or manual-review until "
            "their originals are paired and amount/patient/date relationships "
            "are proven."
        ),
        "samples": {
            "matched_pairs": _adjustment_pair_sample(
                source,
                where_sql="o.[RefId] IS NOT NULL",
                order_sql="c.[At] DESC, c.[RefId] DESC",
                sample_limit=sample_limit,
            ),
            "unmatched_cancellations": _adjustment_pair_sample(
                source,
                where_sql="o.[RefId] IS NULL",
                order_sql="c.[At] DESC, c.[RefId] DESC",
                sample_limit=sample_limit,
            ),
            "suspicious_pairs": _adjustment_pair_sample(
                source,
                where_sql=(
                    "o.[RefId] IS NOT NULL AND (NOT "
                    f"{_same_text_expr('c.PatientCode', 'o.PatientCode')} OR "
                    "c.[At] < o.[At] OR ("
                    "ABS(CAST(ISNULL(c.[Amount], 0) AS decimal(19,2)) + "
                    "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2))) > 0.01 AND "
                    "ABS(CAST(ISNULL(c.[Amount], 0) AS decimal(19,2)) - "
                    "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2))) > 0.01))"
                ),
                order_sql="c.[At] DESC, c.[RefId] DESC",
                sample_limit=sample_limit,
            ),
        },
    }


def _cancellation_impact(cancellation_pairing: dict[str, Any]) -> dict[str, Any]:
    adjustments = cancellation_pairing["adjustments_cancellation_of"]
    paired_net = _decimal(adjustments.get("paired_net_amount"))
    paired_net_zero = _decimal_close(paired_net, Decimal("0"))
    return {
        "policy_decision": (
            "Cancellation/reversal rows must not be imported as independent "
            "finance records until paired originals and net effect are proven."
        ),
        "vw_payments_cancelled_row_count": _to_int(
            cancellation_pairing["vw_payments_cancelled"].get("cancelled_row_count")
        ),
        "vw_payments_cancelled_total_amount": cancellation_pairing[
            "vw_payments_cancelled"
        ].get("cancelled_total_amount"),
        "adjustments_cancellation_of_count": _to_int(
            adjustments.get("cancellation_of_count")
        ),
        "paired_original_count": _to_int(adjustments.get("original_found_count")),
        "unpaired_original_count": _to_int(adjustments.get("original_missing_count")),
        "cancellation_total_amount": adjustments.get("cancellation_total_amount"),
        "paired_original_total_amount": adjustments.get(
            "paired_original_total_amount"
        ),
        "paired_net_amount": adjustments.get("paired_net_amount"),
        "paired_net_zero_within_tolerance": paired_net_zero,
        "recommended_handling": "manual_review_or_excluded_until_reconciled",
    }


def _refund_allocation_mismatch(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> dict[str, Any]:
    vw_refunds = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS refund_count, "
                    f"{_sum_money('Amount', 'refund_total_amount')}, "
                    "SUM(CASE WHEN [IsCancelled] = 1 THEN 1 ELSE 0 END) "
                    "AS cancelled_refund_count "
                    "FROM dbo.vwPayments WITH (NOLOCK) "
                    "WHERE [IsRefund] = 1"
                ),
            )
        )
    )
    payment_allocations = _allocation_refund_summary(source, "PaymentAllocations")
    allocated_view = _allocation_refund_summary(source, "vwAllocatedPayments")
    overlap = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS allocation_refund_count, "
                    "SUM(CASE WHEN p.[RefId] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS matching_vw_refund_count, "
                    "SUM(CASE WHEN p.[RefId] IS NULL THEN 1 ELSE 0 END) "
                    "AS without_matching_vw_refund_count, "
                    "SUM(CASE WHEN p.[RefId] IS NOT NULL AND "
                    f"{_same_text_expr('a.PatientCode', 'p.PatientCode')} "
                    "THEN 1 ELSE 0 END) AS patient_match_count, "
                    "SUM(CASE WHEN p.[RefId] IS NOT NULL AND NOT "
                    f"{_same_text_expr('a.PatientCode', 'p.PatientCode')} "
                    "THEN 1 ELSE 0 END) AS patient_mismatch_count, "
                    "SUM(CASE WHEN p.[RefId] IS NOT NULL AND "
                    "ABS(CAST(ISNULL(a.[Cost], 0) AS decimal(19,2)) - "
                    "CAST(ISNULL(p.[Amount], 0) AS decimal(19,2))) <= 0.01 "
                    "THEN 1 ELSE 0 END) AS same_amount_match_count, "
                    "SUM(CASE WHEN p.[RefId] IS NOT NULL AND "
                    "ABS(CAST(ISNULL(a.[Cost], 0) AS decimal(19,2)) + "
                    "CAST(ISNULL(p.[Amount], 0) AS decimal(19,2))) <= 0.01 "
                    "THEN 1 ELSE 0 END) AS opposite_amount_match_count "
                    "FROM dbo.PaymentAllocations a WITH (NOLOCK) "
                    "LEFT JOIN dbo.vwPayments p WITH (NOLOCK) "
                    "ON a.[PaymentID] = p.[RefId] AND p.[IsRefund] = 1 "
                    "WHERE a.[IsRefund] = 1"
                ),
            )
        )
    )
    vw_without_allocation = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS vw_refunds_without_allocation_count "
                    "FROM dbo.vwPayments p WITH (NOLOCK) "
                    "WHERE p.[IsRefund] = 1 AND NOT EXISTS ("
                    "SELECT 1 FROM dbo.PaymentAllocations a WITH (NOLOCK) "
                    "WHERE a.[IsRefund] = 1 AND a.[PaymentID] = p.[RefId])"
                ),
            )
        )
    )
    return {
        "vw_payments_refunds": vw_refunds,
        "payment_allocations_refunds": payment_allocations,
        "vw_allocated_payments_refunds": allocated_view,
        "overlap_by_payment_id_refid": overlap,
        "vw_refunds_without_allocation": vw_without_allocation,
        "interpretation": (
            "Refund rows are reconciled by PaymentAllocations.PaymentID to "
            "vwPayments.RefId where possible. Count differences remain a blocker "
            "until unmatched rows are explained."
        ),
        "samples": {
            "matched_refund_allocations": _refund_overlap_sample(
                source,
                where_sql="p.[RefId] IS NOT NULL",
                order_sql="a.[PaymentID] DESC",
                sample_limit=sample_limit,
            ),
            "allocation_refunds_without_vw_refund": _refund_overlap_sample(
                source,
                where_sql="p.[RefId] IS NULL",
                order_sql="a.[PaymentID] DESC",
                sample_limit=sample_limit,
            ),
            "vw_refunds_without_allocation": _vw_refund_without_allocation_sample(
                source,
                sample_limit=sample_limit,
            ),
        },
    }


def _advanced_payment_credit_allocation(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> dict[str, Any]:
    credits = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS credit_count, "
                    f"{_sum_money('Amount', 'credit_total_amount')}, "
                    "SUM(CASE WHEN [IsCancelled] = 1 THEN 1 ELSE 0 END) "
                    "AS cancelled_credit_count "
                    "FROM dbo.vwPayments WITH (NOLOCK) "
                    "WHERE [IsCredit] = 1"
                ),
            )
        )
    )
    payment_allocations = _allocation_application_summary(source, "PaymentAllocations")
    allocated_view = _allocation_application_summary(source, "vwAllocatedPayments")
    return {
        "vw_payments_credits": credits,
        "payment_allocations": payment_allocations,
        "vw_allocated_payments": allocated_view,
        "invoice_application_policy": (
            "Allocations are reconciliation inputs only. Invoice application is "
            "blocked unless reliable charge references are present and proven."
        ),
        "samples": {
            "advanced_payment_allocations": _allocation_sample(
                source,
                table="PaymentAllocations",
                where_sql="[IsAdvancedPayment] = 1",
                order_sql="[PaymentID] DESC",
                sample_limit=sample_limit,
            ),
            "missing_charge_ref_allocations": _allocation_sample(
                source,
                table="PaymentAllocations",
                where_sql=_missing_charge_ref_predicate(),
                order_sql="[PaymentID] DESC",
                sample_limit=sample_limit,
            ),
            "credit_rows": _vw_payment_sample(
                source,
                where_sql="p.[IsCredit] = 1",
                order_sql="p.[At] DESC, p.[RefId] DESC",
                sample_limit=sample_limit,
            ),
        },
    }


def _classification_summary(samples: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    rows: list[tuple[str, dict[str, Any]]] = []
    cancellation_samples = samples["cancellation_pairing"]
    for row in cancellation_samples.get("matched_pairs", [])[:5]:
        rows.append(("Adjustments", _adjustment_cancellation_row(row)))
        rows.append(("Adjustments", _adjustment_original_row(row)))
    for row in cancellation_samples.get("unmatched_cancellations", [])[:5]:
        rows.append(("Adjustments", _adjustment_cancellation_row(row)))

    refund_samples = samples["refund_allocation_mismatch"]
    for row in refund_samples.get("matched_refund_allocations", [])[:5]:
        rows.append(("PaymentAllocations", _allocation_row(row)))
        if row.get("payment_ref_id") is not None:
            rows.append(("vwPayments", _vw_payment_row_from_refund_overlap(row)))
    for row in refund_samples.get("allocation_refunds_without_vw_refund", [])[:5]:
        rows.append(("PaymentAllocations", _allocation_row(row)))
    for row in refund_samples.get("vw_refunds_without_allocation", [])[:5]:
        rows.append(("vwPayments", _vw_payment_row(row)))

    advanced_samples = samples["advanced_payment_credit_allocation"]
    for row in advanced_samples.get("advanced_payment_allocations", [])[:5]:
        rows.append(("PaymentAllocations", _allocation_row(row)))
    for row in advanced_samples.get("missing_charge_ref_allocations", [])[:5]:
        rows.append(("PaymentAllocations", _allocation_row(row)))
    for row in advanced_samples.get("credit_rows", [])[:5]:
        rows.append(("vwPayments", _vw_payment_row(row)))

    results = [classify_finance_row(source, row) for source, row in rows]
    report = summarize_finance_classifications(results)
    raw_sign_counts = Counter(result.raw_sign.value for result in results)
    pms_direction_counts = Counter(
        result.proposed_pms_direction.value
        for result in results
        if result.proposed_pms_direction is not None
    )
    return {
        "policy": (
            "Classification is applied to bounded proof samples only. Raw R4 "
            "signs are preserved, and proposed PMS direction remains proof-only."
        ),
        "sample_size": report.total,
        "classification_counts": report.classification_counts,
        "safety_decision_counts": report.safety_decision_counts,
        "reason_counts": report.reason_counts,
        "raw_sign_counts": dict(sorted(raw_sign_counts.items())),
        "proposed_pms_direction_counts": dict(sorted(pms_direction_counts.items())),
        "sample_classifications": [_classification_to_json(result) for result in results],
    }


def _risks(
    *,
    cancellation_pairing: dict[str, Any],
    cancellation_impact: dict[str, Any],
    refund_mismatch: dict[str, Any],
    advanced_credit: dict[str, Any],
    classification_summary: dict[str, Any],
) -> list[str]:
    risks = [
        "proof is report-only and must not create PMS finance records",
        "cancellations and reversals remain manual-review/excluded until paired",
        "allocations are reconciliation inputs, not import truth",
    ]
    adjustment_pairing = cancellation_pairing["adjustments_cancellation_of"]
    if _to_int(adjustment_pairing.get("original_missing_count")):
        risks.append("some Adjustment CancellationOf rows do not resolve to originals")
    if _to_int(adjustment_pairing.get("patient_mismatch_count")):
        risks.append("some cancellation/original pairs have PatientCode mismatches")
    if _to_int(adjustment_pairing.get("cancellation_before_original_count")):
        risks.append("some cancellation rows predate their original rows")
    if cancellation_impact.get("paired_net_zero_within_tolerance") is False:
        risks.append("paired cancellation/original rows do not obviously net to zero")

    payment_refunds = _to_int(refund_mismatch["vw_payments_refunds"].get("refund_count"))
    allocation_refunds = _to_int(
        refund_mismatch["payment_allocations_refunds"].get("refund_count")
    )
    if payment_refunds != allocation_refunds:
        risks.append("vwPayments refund count differs from PaymentAllocations refund count")
    overlap = refund_mismatch["overlap_by_payment_id_refid"]
    if _to_int(overlap.get("without_matching_vw_refund_count")):
        risks.append("some allocation refund rows do not match vwPayments refund rows")
    if _to_int(
        refund_mismatch["vw_refunds_without_allocation"].get(
            "vw_refunds_without_allocation_count"
        )
    ):
        risks.append("some vwPayments refund rows do not match allocation refund rows")
    if _to_int(overlap.get("patient_mismatch_count")):
        risks.append("some matched refund/allocation rows have PatientCode mismatches")

    allocation_summary = advanced_credit["payment_allocations"]
    if _to_int(allocation_summary.get("missing_charge_ref_count")):
        risks.append("invoice application remains blocked by missing charge refs")
    if _to_int(
        classification_summary.get("safety_decision_counts", {}).get("manual_review")
    ):
        risks.append("classification sample contains manual-review rows")
    return risks


def _allocation_refund_summary(source: R4SqlServerSource, table: str) -> dict[str, Any]:
    return _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS refund_count, "
                    f"{_sum_money('Cost', 'refund_total_cost')}, "
                    "SUM(CASE WHEN [PaymentID] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS linked_payment_count, "
                    f"SUM(CASE WHEN {_missing_charge_ref_predicate()} THEN 1 ELSE 0 END) "
                    "AS missing_charge_ref_count "
                    f"FROM dbo.{table} WITH (NOLOCK) "
                    "WHERE [IsRefund] = 1"
                ),
            )
        )
    )


def _allocation_application_summary(
    source: R4SqlServerSource,
    table: str,
) -> dict[str, Any]:
    return _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS row_count, "
                    f"{_sum_money('Cost', 'total_cost')}, "
                    "SUM(CASE WHEN [IsRefund] = 1 THEN 1 ELSE 0 END) "
                    "AS refund_count, "
                    "SUM(CASE WHEN [IsAdvancedPayment] = 1 THEN 1 ELSE 0 END) "
                    "AS advanced_payment_count, "
                    "SUM(CASE WHEN [PaymentID] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS linked_payment_count, "
                    f"SUM(CASE WHEN NOT {_missing_charge_ref_predicate()} THEN 1 ELSE 0 END) "
                    "AS charge_ref_count, "
                    f"SUM(CASE WHEN {_missing_charge_ref_predicate()} THEN 1 ELSE 0 END) "
                    "AS missing_charge_ref_count "
                    f"FROM dbo.{table} WITH (NOLOCK)"
                ),
            )
        )
    )


def _adjustment_pair_sample(
    source: R4SqlServerSource,
    *,
    where_sql: str,
    order_sql: str,
    sample_limit: int,
) -> list[dict[str, Any]]:
    rows = _read_only_query(
        source,
        (
            "SELECT TOP (?) "
            "c.[RefId] AS cancellation_ref_id, "
            "c.[CancellationOf] AS cancellation_of, "
            "c.[PatientCode] AS cancellation_patient_code, "
            "c.[At] AS cancellation_at, "
            "c.[Amount] AS cancellation_amount, "
            "c.[AdjustmentType] AS cancellation_adjustment_type, "
            "c.[PaymentType] AS cancellation_payment_type, "
            "c.[Status] AS cancellation_status, "
            "o.[RefId] AS original_ref_id, "
            "o.[PatientCode] AS original_patient_code, "
            "o.[At] AS original_at, "
            "o.[Amount] AS original_amount, "
            "o.[AdjustmentType] AS original_adjustment_type, "
            "o.[PaymentType] AS original_payment_type, "
            "o.[Status] AS original_status, "
            "CAST(ISNULL(c.[Amount], 0) AS decimal(19,2)) + "
            "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2)) AS net_amount "
            "FROM dbo.Adjustments c WITH (NOLOCK) "
            "LEFT JOIN dbo.Adjustments o WITH (NOLOCK) "
            "ON c.[CancellationOf] = o.[RefId] "
            f"WHERE c.[CancellationOf] IS NOT NULL AND {where_sql} "
            f"ORDER BY {order_sql}"
        ),
        [sample_limit],
    )
    return [_json_row(row) for row in rows]


def _refund_overlap_sample(
    source: R4SqlServerSource,
    *,
    where_sql: str,
    order_sql: str,
    sample_limit: int,
) -> list[dict[str, Any]]:
    rows = _read_only_query(
        source,
        (
            "SELECT TOP (?) "
            "a.[PaymentID] AS allocation_payment_id, "
            "a.[PatientCode] AS allocation_patient_code, "
            "a.[Cost] AS allocation_cost, "
            "a.[IsRefund] AS allocation_is_refund, "
            "a.[IsAdvancedPayment] AS allocation_is_advanced_payment, "
            "a.[ChargeTransactionRefID] AS allocation_charge_transaction_ref_id, "
            "a.[ChargeAdjustmentRefID] AS allocation_charge_adjustment_ref_id, "
            "p.[RefId] AS payment_ref_id, "
            "p.[PatientCode] AS payment_patient_code, "
            "p.[At] AS payment_at, "
            "p.[Amount] AS payment_amount, "
            "p.[Type] AS payment_type, "
            "p.[IsPayment] AS payment_is_payment, "
            "p.[IsRefund] AS payment_is_refund, "
            "p.[IsCredit] AS payment_is_credit, "
            "p.[IsCancelled] AS payment_is_cancelled "
            "FROM dbo.PaymentAllocations a WITH (NOLOCK) "
            "LEFT JOIN dbo.vwPayments p WITH (NOLOCK) "
            "ON a.[PaymentID] = p.[RefId] AND p.[IsRefund] = 1 "
            f"WHERE a.[IsRefund] = 1 AND {where_sql} "
            f"ORDER BY {order_sql}"
        ),
        [sample_limit],
    )
    return [_json_row(row) for row in rows]


def _vw_refund_without_allocation_sample(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> list[dict[str, Any]]:
    return _vw_payment_sample(
        source,
        where_sql=(
            "p.[IsRefund] = 1 AND NOT EXISTS ("
            "SELECT 1 FROM dbo.PaymentAllocations a WITH (NOLOCK) "
            "WHERE a.[IsRefund] = 1 AND a.[PaymentID] = p.[RefId])"
        ),
        order_sql="p.[At] DESC, p.[RefId] DESC",
        sample_limit=sample_limit,
    )


def _vw_payment_sample(
    source: R4SqlServerSource,
    *,
    where_sql: str,
    order_sql: str,
    sample_limit: int,
) -> list[dict[str, Any]]:
    rows = _read_only_query(
        source,
        (
            "SELECT TOP (?) p.[RefId] AS RefId, p.[PatientCode] AS PatientCode, "
            "p.[At] AS At, p.[Amount] AS Amount, p.[Type] AS Type, "
            "p.[IsPayment] AS IsPayment, p.[IsRefund] AS IsRefund, "
            "p.[IsCredit] AS IsCredit, p.[IsCancelled] AS IsCancelled "
            "FROM dbo.vwPayments p WITH (NOLOCK) "
            f"WHERE {where_sql} "
            f"ORDER BY {order_sql}"
        ),
        [sample_limit],
    )
    return [_json_row(row) for row in rows]


def _allocation_sample(
    source: R4SqlServerSource,
    *,
    table: str,
    where_sql: str,
    order_sql: str,
    sample_limit: int,
) -> list[dict[str, Any]]:
    rows = _read_only_query(
        source,
        (
            "SELECT TOP (?) [PaymentID] AS PaymentID, [PatientCode] AS PatientCode, "
            "[Cost] AS Cost, [IsRefund] AS IsRefund, "
            "[IsAdvancedPayment] AS IsAdvancedPayment, "
            "[IsAllocationAdjustment] AS IsAllocationAdjustment, "
            "[IsBalancingEntry] AS IsBalancingEntry, "
            "[ChargeTransactionRefID] AS ChargeTransactionRefID, "
            "[ChargeAdjustmentRefID] AS ChargeAdjustmentRefID "
            f"FROM dbo.{table} WITH (NOLOCK) "
            f"WHERE {where_sql} "
            f"ORDER BY {order_sql}"
        ),
        [sample_limit],
    )
    return [_json_row(row) for row in rows]


def _classification_to_json(
    result: R4FinanceClassificationResult,
) -> dict[str, Any]:
    return {
        "source_name": result.source_name,
        "classification": result.classification.value,
        "safety_decision": result.safety_decision.value,
        "reason_codes": list(result.reason_codes),
        "raw_amount": str(result.raw_amount) if result.raw_amount is not None else None,
        "raw_sign": result.raw_sign.value,
        "proposed_pms_direction": (
            result.proposed_pms_direction.value
            if result.proposed_pms_direction is not None
            else None
        ),
        "patient_code_present": result.patient_code_present,
        "can_create_finance_record": result.can_create_finance_record,
    }


def _adjustment_cancellation_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "PatientCode": row.get("cancellation_patient_code"),
        "Amount": row.get("cancellation_amount"),
        "AdjustmentType": row.get("cancellation_adjustment_type"),
        "PaymentType": row.get("cancellation_payment_type"),
        "Status": row.get("cancellation_status"),
        "CancellationOf": row.get("cancellation_of"),
    }


def _adjustment_original_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "PatientCode": row.get("original_patient_code"),
        "Amount": row.get("original_amount"),
        "AdjustmentType": row.get("original_adjustment_type"),
        "PaymentType": row.get("original_payment_type"),
        "Status": row.get("original_status"),
    }


def _allocation_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "PatientCode": row.get("PatientCode") or row.get("allocation_patient_code"),
        "Cost": row.get("Cost") or row.get("allocation_cost"),
        "PaymentID": row.get("PaymentID") or row.get("allocation_payment_id"),
        "IsRefund": row.get("IsRefund") or row.get("allocation_is_refund"),
        "IsAdvancedPayment": row.get("IsAdvancedPayment")
        or row.get("allocation_is_advanced_payment"),
        "IsAllocationAdjustment": row.get("IsAllocationAdjustment"),
        "IsBalancingEntry": row.get("IsBalancingEntry"),
        "ChargeTransactionRefID": row.get("ChargeTransactionRefID")
        or row.get("allocation_charge_transaction_ref_id"),
        "ChargeAdjustmentRefID": row.get("ChargeAdjustmentRefID")
        or row.get("allocation_charge_adjustment_ref_id"),
    }


def _vw_payment_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "PatientCode": row.get("PatientCode"),
        "Amount": row.get("Amount"),
        "Type": row.get("Type"),
        "IsPayment": row.get("IsPayment"),
        "IsRefund": row.get("IsRefund"),
        "IsCredit": row.get("IsCredit"),
        "IsCancelled": row.get("IsCancelled"),
    }


def _vw_payment_row_from_refund_overlap(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "PatientCode": row.get("payment_patient_code"),
        "Amount": row.get("payment_amount"),
        "Type": row.get("payment_type"),
        "IsPayment": row.get("payment_is_payment"),
        "IsRefund": row.get("payment_is_refund"),
        "IsCredit": row.get("payment_is_credit"),
        "IsCancelled": row.get("payment_is_cancelled"),
    }


def _read_only_query(
    source: R4SqlServerSource,
    sql: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    source.ensure_select_only()
    stripped = sql.lstrip().upper()
    if not stripped.startswith("SELECT "):
        raise RuntimeError("R4 cancellation/allocation proof only permits SELECT queries.")
    padded = f" {stripped} "
    blocked = (" INSERT ", " UPDATE ", " DELETE ", " MERGE ", " DROP ", " ALTER ", " EXEC ")
    if any(token in padded for token in blocked):
        raise RuntimeError(
            "R4 cancellation/allocation proof refused a non-read-only query."
        )
    return source._query(sql, params or [])  # noqa: SLF001


def _one(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _json_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in row.items()}


def _json_value(value: Any | None) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _money_expr(column: str) -> str:
    return f"CAST(ISNULL([{column}], 0) AS decimal(19,2))"


def _sum_money(column: str, alias: str) -> str:
    return f"SUM({_money_expr(column)}) AS {alias}"


def _text_expr(qualified_column: str) -> str:
    return f"LTRIM(RTRIM(CONVERT(varchar(255), {qualified_column})))"


def _same_text_expr(left: str, right: str) -> str:
    return (
        f"ISNULL({_text_expr(left)}, '') = "
        f"ISNULL({_text_expr(right)}, '')"
    )


def _missing_charge_ref_predicate() -> str:
    return (
        "NULLIF([ChargeTransactionRefID], 0) IS NULL AND "
        "NULLIF([ChargeAdjustmentRefID], 0) IS NULL"
    )


def _to_int(value: Any | None) -> int:
    if value is None:
        return 0
    return int(value)


def _decimal(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _decimal_diff(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None or right is None:
        return None
    return left - right


def _decimal_close(left: Decimal | None, right: Decimal | None) -> bool | None:
    difference = _decimal_diff(left, right)
    if difference is None:
        return None
    return abs(difference) <= TOLERANCE
