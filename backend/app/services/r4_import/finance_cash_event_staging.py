from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.r4_import.finance_classification_policy import (
    R4FinanceClassification,
    R4FinanceClassificationResult,
    R4FinanceSafetyDecision,
    classify_finance_row,
)
from app.services.r4_import.sqlserver_source import R4SqlServerSource

__all__ = [
    "run_cash_event_staging_proof",
]


MONEY_ZERO = "CAST(0 AS decimal(19,2))"
TOLERANCE = Decimal("0.01")


def run_cash_event_staging_proof(
    source: R4SqlServerSource,
    *,
    sample_limit: int = 10,
    top_limit: int = 10,
) -> dict[str, Any]:
    source.ensure_select_only()
    if sample_limit < 1:
        raise RuntimeError("sample_limit must be at least 1.")
    if top_limit < 1:
        raise RuntimeError("top_limit must be at least 1.")

    candidate_population = _candidate_population(source, top_limit=top_limit)
    cancellation_pairing = _cancellation_pairing(source, sample_limit=sample_limit)
    refund_handling = _refund_handling(source, sample_limit=sample_limit)
    credit_handling = _credit_handling(source, sample_limit=sample_limit)
    payment_type_mapping = _payment_type_mapping(source, top_limit=top_limit)
    classification_summary = _classification_summary(
        candidate_population["classification_rollup"]
    )
    import_readiness = _import_readiness(
        candidate_population=candidate_population,
        cancellation_pairing=cancellation_pairing,
        refund_handling=refund_handling,
        credit_handling=credit_handling,
        classification_summary=classification_summary,
    )
    risks = _risks(
        candidate_population=candidate_population,
        cancellation_pairing=cancellation_pairing,
        refund_handling=refund_handling,
        credit_handling=credit_handling,
        import_readiness=import_readiness,
    )
    samples = {
        "cash_event_candidates": candidate_population.pop("samples"),
        "cancellation_pairing": cancellation_pairing.pop("samples"),
        "refund_handling": refund_handling.pop("samples"),
        "credit_handling": credit_handling.pop("samples"),
    }

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "select_only": True,
        "query_shape": {
            "query_types": [
                "aggregate cash-event classification buckets",
                "aggregate vwPayments and Adjustments summaries",
                "aggregate cancellation pairing checks",
                "aggregate refund/allocation overlap indicators",
                "bounded payment/refund/credit/cancellation samples",
                "payment type and description distributions",
            ],
            "sources": [
                "dbo.vwPayments",
                "dbo.Adjustments",
                "dbo.PaymentAllocations",
            ],
            "source_roles": {
                "dbo.vwPayments": "cash-event candidate source",
                "dbo.Adjustments": "base-table cancellation/status/key cross-check",
                "dbo.PaymentAllocations": "refund/advanced-payment reconciliation only",
            },
        },
        "candidate_population": candidate_population,
        "cancellation_pairing": cancellation_pairing,
        "refund_handling": refund_handling,
        "credit_handling": credit_handling,
        "payment_type_mapping": payment_type_mapping,
        "classification_summary": classification_summary,
        "import_readiness": import_readiness,
        "risks": risks,
        "samples": samples,
    }


def _candidate_population(
    source: R4SqlServerSource,
    *,
    top_limit: int,
) -> dict[str, Any]:
    vw_summary = _vw_payments_summary(source)
    adjustments_summary = _adjustments_summary(source)
    rollup = _classification_rollup(source)
    decision_counts = Counter()
    candidate_by_classification = Counter()
    manual_review_reasons = Counter()
    excluded_reasons = Counter()
    for row in rollup:
        count = _to_int(row["row_count"])
        decision_counts[row["cash_event_decision"]] += count
        if (
            row["source_name"] == "vwPayments"
            and row["cash_event_decision"] == "candidate"
        ):
            candidate_by_classification[row["classification"]] += count
        reasons = row["cash_event_reason_codes"]
        if row["cash_event_decision"] == "manual_review":
            manual_review_reasons.update(dict.fromkeys(reasons, count))
        if row["cash_event_decision"] == "excluded":
            excluded_reasons.update(dict.fromkeys(reasons, count))

    return {
        "policy": (
            "Only vwPayments payment/refund/credit rows can be cash-event "
            "candidates in this proof. Adjustments are base-table cross-check "
            "evidence, not independent cash-event import rows."
        ),
        "vw_payments_summary": vw_summary,
        "adjustments_summary": adjustments_summary,
        "cash_event_decision_counts": dict(sorted(decision_counts.items())),
        "candidate_rows_by_classification": dict(
            sorted(candidate_by_classification.items())
        ),
        "eligible_cash_event_candidate_count": _to_int(decision_counts.get("candidate")),
        "excluded_count": _to_int(decision_counts.get("excluded")),
        "manual_review_count": _to_int(decision_counts.get("manual_review")),
        "cancellation_or_reversal_count": _to_int(
            decision_counts.get("cancellation_or_reversal")
        ),
        "payment_candidate_count": _to_int(
            candidate_by_classification.get(
                R4FinanceClassification.PAYMENT_CANDIDATE.value
            )
        ),
        "refund_candidate_count": _to_int(
            candidate_by_classification.get(
                R4FinanceClassification.REFUND_CANDIDATE.value
            )
        ),
        "credit_candidate_count": _to_int(
            candidate_by_classification.get(
                R4FinanceClassification.CREDIT_CANDIDATE.value
            )
        ),
        "manual_review_reason_counts": dict(sorted(manual_review_reasons.items())),
        "excluded_reason_counts": dict(sorted(excluded_reasons.items())),
        "ambiguous_type_status_sign_count": _reason_total(
            rollup,
            {
                "ambiguous_payment_refund_credit_flags",
                "payment_type_flag_conflict",
                "unknown_payment_type",
                "payment_amount_sign_unexpected",
                "refund_amount_sign_unexpected",
                "credit_amount_sign_unexpected",
                "adjustment_status_not_current",
                "unknown_adjustment_type",
                "missing_payment_type_flags",
                "adjustment_type_requires_policy",
            },
        ),
        "missing_patient_code_count": _reason_total(rollup, {"missing_patient_code"}),
        "missing_or_invalid_date_count": _reason_total(
            rollup,
            {"cash_event_date_missing"},
        )
        + _to_int(vw_summary.get("missing_date_count"))
        + _to_int(adjustments_summary.get("missing_date_count")),
        "missing_amount_count": _reason_total(
            rollup,
            {
                "payment_amount_sign_unexpected",
                "refund_amount_sign_unexpected",
                "credit_amount_sign_unexpected",
            },
            amount_states={"missing"},
        ),
        "zero_amount_count": _reason_total(
            rollup,
            {
                "payment_amount_sign_unexpected",
                "refund_amount_sign_unexpected",
                "credit_amount_sign_unexpected",
            },
            amount_states={"zero"},
        ),
        "classification_rollup": rollup,
        "samples": {
            "payment_candidates": _vw_payment_sample(
                source,
                where_sql=(
                    "[IsPayment] = 1 AND [IsCancelled] = 0 AND "
                    "[At] IS NOT NULL AND [Amount] < 0 AND "
                    f"NOT ({_blank_predicate('PatientCode')})"
                ),
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=top_limit,
            ),
            "refund_candidates": _vw_payment_sample(
                source,
                where_sql=(
                    "[IsRefund] = 1 AND [IsCancelled] = 0 AND "
                    "[At] IS NOT NULL AND [Amount] > 0 AND "
                    f"NOT ({_blank_predicate('PatientCode')})"
                ),
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=top_limit,
            ),
            "credit_candidates": _vw_payment_sample(
                source,
                where_sql=(
                    "[IsCredit] = 1 AND [IsCancelled] = 0 AND "
                    "[At] IS NOT NULL AND [Amount] < 0 AND "
                    f"NOT ({_blank_predicate('PatientCode')})"
                ),
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=top_limit,
            ),
            "manual_review_rows": _vw_payment_sample(
                source,
                where_sql=(
                    "[IsCancelled] = 0 AND ("
                    f"{_blank_predicate('PatientCode')} OR [At] IS NULL OR "
                    "[Amount] IS NULL OR [Amount] = 0 OR "
                    "([IsPayment] + [IsRefund] + [IsCredit]) <> 1)"
                ),
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=top_limit,
            ),
            "cancelled_rows": _vw_payment_sample(
                source,
                where_sql="[IsCancelled] = 1",
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=top_limit,
            ),
        },
    }


def _vw_payments_summary(source: R4SqlServerSource) -> dict[str, Any]:
    return _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS row_count, "
                    "COUNT(DISTINCT NULLIF(LTRIM(RTRIM(CONVERT(varchar(255), [PatientCode]))), '')) "
                    "AS distinct_patient_code_count, "
                    f"SUM(CASE WHEN {_blank_predicate('PatientCode')} THEN 1 ELSE 0 END) "
                    "AS null_blank_patient_code_count, "
                    "MIN([At]) AS min_at, MAX([At]) AS max_at, "
                    "SUM(CASE WHEN [At] IS NULL THEN 1 ELSE 0 END) AS missing_date_count, "
                    "SUM(CASE WHEN [Amount] IS NULL THEN 1 ELSE 0 END) AS missing_amount_count, "
                    "SUM(CASE WHEN [Amount] IS NOT NULL AND [Amount] = 0 THEN 1 ELSE 0 END) "
                    "AS zero_amount_count, "
                    f"{_sum_money('Amount', 'total_amount')}, "
                    "SUM(CASE WHEN [IsPayment] = 1 THEN 1 ELSE 0 END) AS payment_flag_count, "
                    "SUM(CASE WHEN [IsRefund] = 1 THEN 1 ELSE 0 END) AS refund_flag_count, "
                    "SUM(CASE WHEN [IsCredit] = 1 THEN 1 ELSE 0 END) AS credit_flag_count, "
                    "SUM(CASE WHEN [IsCancelled] = 1 THEN 1 ELSE 0 END) AS cancellation_count, "
                    "SUM(CASE WHEN ([IsPayment] + [IsRefund] + [IsCredit]) > 1 THEN 1 ELSE 0 END) "
                    "AS ambiguous_flag_count, "
                    "SUM(CASE WHEN ([IsPayment] + [IsRefund] + [IsCredit]) = 0 THEN 1 ELSE 0 END) "
                    "AS missing_flag_count "
                    "FROM dbo.vwPayments WITH (NOLOCK)"
                ),
            )
        )
    )


def _adjustments_summary(source: R4SqlServerSource) -> dict[str, Any]:
    return _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS row_count, "
                    "COUNT(DISTINCT NULLIF(LTRIM(RTRIM(CONVERT(varchar(255), [PatientCode]))), '')) "
                    "AS distinct_patient_code_count, "
                    f"SUM(CASE WHEN {_blank_predicate('PatientCode')} THEN 1 ELSE 0 END) "
                    "AS null_blank_patient_code_count, "
                    "MIN([At]) AS min_at, MAX([At]) AS max_at, "
                    "SUM(CASE WHEN [At] IS NULL THEN 1 ELSE 0 END) AS missing_date_count, "
                    "SUM(CASE WHEN [Amount] IS NULL THEN 1 ELSE 0 END) AS missing_amount_count, "
                    "SUM(CASE WHEN [Amount] IS NOT NULL AND [Amount] = 0 THEN 1 ELSE 0 END) "
                    "AS zero_amount_count, "
                    f"{_sum_money('Amount', 'total_amount')}, "
                    "SUM(CASE WHEN [CancellationOf] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS cancellation_of_count, "
                    "SUM(CASE WHEN LOWER(LTRIM(RTRIM(CONVERT(varchar(255), [Status])))) = 'current' "
                    "THEN 1 ELSE 0 END) AS current_status_count, "
                    "SUM(CASE WHEN [Status] IS NOT NULL AND "
                    "LOWER(LTRIM(RTRIM(CONVERT(varchar(255), [Status])))) <> 'current' "
                    "THEN 1 ELSE 0 END) AS non_current_status_count "
                    "FROM dbo.Adjustments WITH (NOLOCK)"
                ),
            )
        )
    )


def _classification_rollup(source: R4SqlServerSource) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in _vw_payment_classification_buckets(source):
        rows.append(_classified_bucket("vwPayments", bucket))
    for bucket in _adjustment_classification_buckets(source):
        rows.append(_classified_bucket("Adjustments", bucket))
    return rows


def _vw_payment_classification_buckets(source: R4SqlServerSource) -> list[dict[str, Any]]:
    patient_present = _patient_present_expr("PatientCode")
    date_present = "CASE WHEN [At] IS NULL THEN 0 ELSE 1 END"
    amount_state = _amount_state_expr("Amount")
    type_bucket = _bucket_expr("Type")
    cancellation_of_present = "CASE WHEN [CancellationOf] IS NULL THEN 0 ELSE 1 END"
    rows = _read_only_query(
        source,
        (
            "SELECT 'vwPayments' AS source_name, "
            f"{patient_present} AS patient_code_present, "
            f"{date_present} AS date_present, "
            f"{amount_state} AS amount_state, "
            f"{type_bucket} AS type, "
            "[IsPayment] AS is_payment, [IsRefund] AS is_refund, "
            "[IsCredit] AS is_credit, [IsCancelled] AS is_cancelled, "
            f"{cancellation_of_present} AS cancellation_of_present, "
            "COUNT(1) AS row_count, "
            f"{_sum_money('Amount', 'total_amount')}, "
            "MIN([At]) AS min_at, MAX([At]) AS max_at "
            "FROM dbo.vwPayments WITH (NOLOCK) "
            f"GROUP BY {patient_present}, {date_present}, {amount_state}, "
            f"{type_bucket}, [IsPayment], [IsRefund], [IsCredit], [IsCancelled], "
            f"{cancellation_of_present} "
            "ORDER BY COUNT(1) DESC"
        ),
    )
    return [_json_row(row) for row in rows]


def _adjustment_classification_buckets(source: R4SqlServerSource) -> list[dict[str, Any]]:
    patient_present = _patient_present_expr("PatientCode")
    date_present = "CASE WHEN [At] IS NULL THEN 0 ELSE 1 END"
    amount_state = _amount_state_expr("Amount")
    status_bucket = _bucket_expr("Status")
    adjustment_type_bucket = _bucket_expr("AdjustmentType")
    payment_type_bucket = _bucket_expr("PaymentType")
    cancellation_of_present = "CASE WHEN [CancellationOf] IS NULL THEN 0 ELSE 1 END"
    rows = _read_only_query(
        source,
        (
            "SELECT 'Adjustments' AS source_name, "
            f"{patient_present} AS patient_code_present, "
            f"{date_present} AS date_present, "
            f"{amount_state} AS amount_state, "
            f"{status_bucket} AS status, "
            f"{adjustment_type_bucket} AS adjustment_type, "
            f"{payment_type_bucket} AS payment_type, "
            f"{cancellation_of_present} AS cancellation_of_present, "
            "COUNT(1) AS row_count, "
            f"{_sum_money('Amount', 'total_amount')}, "
            "MIN([At]) AS min_at, MAX([At]) AS max_at "
            "FROM dbo.Adjustments WITH (NOLOCK) "
            f"GROUP BY {patient_present}, {date_present}, {amount_state}, "
            f"{status_bucket}, {adjustment_type_bucket}, {payment_type_bucket}, "
            f"{cancellation_of_present} "
            "ORDER BY COUNT(1) DESC"
        ),
    )
    return [_json_row(row) for row in rows]


def _classified_bucket(source_name: str, bucket: dict[str, Any]) -> dict[str, Any]:
    row = (
        _vw_payment_representative(bucket)
        if source_name == "vwPayments"
        else _adjustment_representative(bucket)
    )
    result = classify_finance_row(source_name, row)
    decision, reasons = _cash_event_decision(
        source_name=source_name,
        bucket=bucket,
        classification=result,
    )
    return {
        "source_name": source_name,
        "row_count": _to_int(bucket.get("row_count")),
        "total_amount": bucket.get("total_amount"),
        "classification": result.classification.value,
        "safety_decision": result.safety_decision.value,
        "cash_event_decision": decision,
        "reason_codes": list(result.reason_codes),
        "cash_event_reason_codes": reasons,
        "raw_sign": result.raw_sign.value,
        "proposed_pms_direction": (
            result.proposed_pms_direction.value
            if result.proposed_pms_direction is not None
            else None
        ),
        "amount_state": bucket.get("amount_state"),
        "date_present": _truthy_int(bucket.get("date_present")),
        "patient_code_present": _truthy_int(bucket.get("patient_code_present")),
        "bucket": bucket,
        "sample_classification": _classification_to_json(result),
    }


def _cash_event_decision(
    *,
    source_name: str,
    bucket: dict[str, Any],
    classification: R4FinanceClassificationResult,
) -> tuple[str, list[str]]:
    reasons = list(classification.reason_codes)
    if classification.safety_decision == R4FinanceSafetyDecision.EXCLUDED:
        return "excluded", reasons
    if classification.classification == R4FinanceClassification.CANCELLATION_OR_REVERSAL:
        return "cancellation_or_reversal", reasons
    if source_name != "vwPayments":
        reasons.append("adjustments_base_cross_check_only")
        return "manual_review", reasons
    if classification.safety_decision == R4FinanceSafetyDecision.CANDIDATE:
        if not _truthy_int(bucket.get("date_present")):
            reasons.append("cash_event_date_missing")
            return "manual_review", reasons
        return "candidate", reasons
    return "manual_review", reasons


def _cancellation_pairing(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> dict[str, Any]:
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
    paired_net = _decimal(adjustment_pairing.get("paired_net_amount"))
    return {
        "source": "dbo.Adjustments",
        "policy": (
            "Paired CancellationOf rows are reversal metadata or exclusion "
            "evidence, not independent import rows."
        ),
        "summary": adjustment_pairing,
        "paired_net_zero_within_tolerance": _decimal_close(paired_net, Decimal("0")),
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
                    "c.[At] < o.[At] OR "
                    "ABS(CAST(ISNULL(c.[Amount], 0) AS decimal(19,2)) + "
                    "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2))) > 0.01)"
                ),
                order_sql="c.[At] DESC, c.[RefId] DESC",
                sample_limit=sample_limit,
            ),
        },
    }


def _refund_handling(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> dict[str, Any]:
    vw_refunds = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS refund_row_count, "
                    f"{_sum_money('Amount', 'refund_total_amount')}, "
                    "SUM(CASE WHEN [IsCancelled] = 0 AND [Amount] > 0 AND "
                    "[At] IS NOT NULL AND "
                    f"NOT ({_blank_predicate('PatientCode')}) THEN 1 ELSE 0 END) "
                    "AS refund_candidate_count, "
                    "SUM(CASE WHEN [IsCancelled] = 1 THEN 1 ELSE 0 END) "
                    "AS cancelled_refund_count, "
                    "SUM(CASE WHEN [Amount] IS NULL OR [Amount] <= 0 THEN 1 ELSE 0 END) "
                    "AS unexpected_sign_or_missing_amount_count, "
                    "SUM(CASE WHEN [At] IS NULL THEN 1 ELSE 0 END) AS missing_date_count, "
                    f"SUM(CASE WHEN {_blank_predicate('PatientCode')} THEN 1 ELSE 0 END) "
                    "AS null_blank_patient_code_count "
                    "FROM dbo.vwPayments WITH (NOLOCK) "
                    "WHERE [IsRefund] = 1"
                ),
            )
        )
    )
    allocation_overlap = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS allocation_refund_count, "
                    "SUM(CASE WHEN p.[RefId] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS matching_vw_refund_count, "
                    "SUM(CASE WHEN p.[RefId] IS NULL THEN 1 ELSE 0 END) "
                    "AS allocation_refunds_without_vw_refund_count, "
                    "SUM(CASE WHEN p.[RefId] IS NOT NULL AND "
                    f"{_same_text_expr('a.PatientCode', 'p.PatientCode')} "
                    "THEN 1 ELSE 0 END) AS patient_match_count, "
                    "SUM(CASE WHEN p.[RefId] IS NOT NULL AND NOT "
                    f"{_same_text_expr('a.PatientCode', 'p.PatientCode')} "
                    "THEN 1 ELSE 0 END) AS patient_mismatch_count, "
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
        "policy": (
            "vwPayments refund rows are cash-event proof candidates; "
            "PaymentAllocations refund rows remain reconciliation-only."
        ),
        "vw_payments_refunds": vw_refunds,
        "allocation_refund_overlap": allocation_overlap,
        "vw_refunds_without_allocation": vw_without_allocation,
        "manual_review": {
            "count": _to_int(vw_refunds.get("cancelled_refund_count"))
            + _to_int(vw_refunds.get("unexpected_sign_or_missing_amount_count"))
            + _to_int(vw_refunds.get("missing_date_count"))
            + _to_int(vw_refunds.get("null_blank_patient_code_count")),
            "reasons": [
                "cancelled_refund",
                "refund_amount_sign_unexpected",
                "cash_event_date_missing",
                "missing_patient_code",
            ],
        },
        "samples": {
            "refund_candidates": _vw_payment_sample(
                source,
                where_sql=(
                    "[IsRefund] = 1 AND [IsCancelled] = 0 AND [Amount] > 0 AND "
                    "[At] IS NOT NULL AND "
                    f"NOT ({_blank_predicate('PatientCode')})"
                ),
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=sample_limit,
            ),
            "refund_manual_review": _vw_payment_sample(
                source,
                where_sql=(
                    "[IsRefund] = 1 AND ([IsCancelled] = 1 OR [Amount] IS NULL OR "
                    f"[Amount] <= 0 OR [At] IS NULL OR {_blank_predicate('PatientCode')})"
                ),
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=sample_limit,
            ),
        },
    }


def _credit_handling(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> dict[str, Any]:
    vw_credits = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS credit_row_count, "
                    f"{_sum_money('Amount', 'credit_total_amount')}, "
                    "SUM(CASE WHEN [IsCancelled] = 0 AND [Amount] < 0 AND "
                    "[At] IS NOT NULL AND "
                    f"NOT ({_blank_predicate('PatientCode')}) THEN 1 ELSE 0 END) "
                    "AS credit_candidate_count, "
                    "SUM(CASE WHEN [IsCancelled] = 1 THEN 1 ELSE 0 END) "
                    "AS cancelled_credit_count, "
                    "SUM(CASE WHEN [Amount] IS NULL OR [Amount] >= 0 THEN 1 ELSE 0 END) "
                    "AS unexpected_sign_or_missing_amount_count "
                    "FROM dbo.vwPayments WITH (NOLOCK) "
                    "WHERE [IsCredit] = 1"
                ),
            )
        )
    )
    advanced_allocations = _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS advanced_payment_allocation_count, "
                    f"{_sum_money('Cost', 'advanced_payment_total_cost')}, "
                    "SUM(CASE WHEN [PaymentID] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS linked_payment_count "
                    "FROM dbo.PaymentAllocations WITH (NOLOCK) "
                    "WHERE [IsAdvancedPayment] = 1"
                ),
            )
        )
    )
    return {
        "policy": (
            "vwPayments credits are future proof candidates; advanced payment "
            "allocations remain reconciliation-only."
        ),
        "vw_payments_credits": vw_credits,
        "advanced_payment_allocations": advanced_allocations,
        "manual_review": {
            "count": _to_int(vw_credits.get("cancelled_credit_count"))
            + _to_int(vw_credits.get("unexpected_sign_or_missing_amount_count")),
            "reasons": [
                "cancelled_credit",
                "credit_amount_sign_unexpected",
            ],
        },
        "samples": {
            "credit_candidates": _vw_payment_sample(
                source,
                where_sql=(
                    "[IsCredit] = 1 AND [IsCancelled] = 0 AND [Amount] < 0 AND "
                    "[At] IS NOT NULL AND "
                    f"NOT ({_blank_predicate('PatientCode')})"
                ),
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=sample_limit,
            ),
            "credit_manual_review": _vw_payment_sample(
                source,
                where_sql=(
                    "[IsCredit] = 1 AND ([IsCancelled] = 1 OR [Amount] IS NULL OR "
                    f"[Amount] >= 0 OR [At] IS NULL OR {_blank_predicate('PatientCode')})"
                ),
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=sample_limit,
            ),
        },
    }


def _payment_type_mapping(
    source: R4SqlServerSource,
    *,
    top_limit: int,
) -> dict[str, Any]:
    return {
        "policy": (
            "Payment method/type mapping is proof-only. Current buckets do not "
            "create PMS PaymentMethod values."
        ),
        "vw_payments_by_type": _top_distribution(
            source,
            table="vwPayments",
            column="Type",
            amount_column="Amount",
            top_limit=top_limit,
        ),
        "vw_payments_by_payment_type_description": _top_distribution(
            source,
            table="vwPayments",
            column="PaymentTypeDescription",
            amount_column="Amount",
            top_limit=top_limit,
        ),
        "vw_payments_by_adjustment_type_description": _top_distribution(
            source,
            table="vwPayments",
            column="AdjustmentTypeDescription",
            amount_column="Amount",
            top_limit=top_limit,
        ),
        "vw_payment_method_family": _payment_method_family_distribution(
            source,
            top_limit=top_limit,
        ),
        "adjustments_by_type_payment_status": _adjustment_distribution(
            source,
            top_limit=top_limit,
        ),
    }


def _classification_summary(rollup: list[dict[str, Any]]) -> dict[str, Any]:
    classification_counts = Counter()
    safety_decision_counts = Counter()
    reason_counts = Counter()
    raw_sign_counts = Counter()
    pms_direction_counts = Counter()
    sample_classifications: list[dict[str, Any]] = []
    for row in rollup:
        count = _to_int(row["row_count"])
        classification_counts[row["classification"]] += count
        safety_decision_counts[row["safety_decision"]] += count
        raw_sign_counts[row["raw_sign"]] += count
        if row["proposed_pms_direction"] is not None:
            pms_direction_counts[row["proposed_pms_direction"]] += count
        for reason in row["cash_event_reason_codes"]:
            reason_counts[reason] += count
        if len(sample_classifications) < 25:
            sample_classifications.append(row["sample_classification"])
    return {
        "policy": (
            "Grouped vwPayments and Adjustments buckets are classified with "
            "finance_classification_policy.py. Raw R4 signs are preserved and "
            "PMS direction remains proof-only."
        ),
        "classification_counts": dict(sorted(classification_counts.items())),
        "safety_decision_counts": dict(sorted(safety_decision_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "raw_sign_counts": dict(sorted(raw_sign_counts.items())),
        "proposed_pms_direction_counts": dict(sorted(pms_direction_counts.items())),
        "sample_classifications": sample_classifications,
    }


def _import_readiness(
    *,
    candidate_population: dict[str, Any],
    cancellation_pairing: dict[str, Any],
    refund_handling: dict[str, Any],
    credit_handling: dict[str, Any],
    classification_summary: dict[str, Any],
) -> dict[str, Any]:
    blockers = [
        "finance import remains blocked; this proof does not create staging models",
        "PaymentAllocations remain reconciliation-only and cannot apply invoices",
        "allocation charge refs are absent in current evidence",
        "vwPayments cancelled rows outside proven Adjustment CancellationOf pairs remain excluded/manual-review",
        "payment method mapping is not yet import-ready",
        "explicit invoice/statement/charge-ref source is still unproven",
    ]
    if _to_int(refund_handling["vw_refunds_without_allocation"].get(
        "vw_refunds_without_allocation_count"
    )):
        blockers.append("some vwPayments refunds have no allocation refund row")
    if _to_int(refund_handling["allocation_refund_overlap"].get(
        "allocation_refunds_without_vw_refund_count"
    )):
        blockers.append("many allocation refunds do not match vwPayments refunds")
    return {
        "cash_event_candidate_population_available": _to_int(
            candidate_population.get("eligible_cash_event_candidate_count")
        )
        > 0,
        "candidate_population_clean_enough_for_future_staging_proof": True,
        "finance_import_ready": False,
        "pms_db_write_path_authorized": False,
        "r4_write_path_authorized": False,
        "candidate_count": candidate_population.get(
            "eligible_cash_event_candidate_count"
        ),
        "manual_review_count": candidate_population.get("manual_review_count"),
        "excluded_count": candidate_population.get("excluded_count"),
        "cancellation_pairing_net_zero": cancellation_pairing.get(
            "paired_net_zero_within_tolerance"
        ),
        "refund_candidate_count": refund_handling["vw_payments_refunds"].get(
            "refund_candidate_count"
        ),
        "credit_candidate_count": credit_handling["vw_payments_credits"].get(
            "credit_candidate_count"
        ),
        "manual_review_reason_counts": classification_summary.get("reason_counts", {}),
        "blockers": blockers,
        "remaining_fail_closed_rules": [
            "unknown or ambiguous payment/refund/credit flags remain manual-review",
            "missing patient code is excluded",
            "missing dates or unexpected signs remain manual-review",
            "cancelled/reversal rows remain manual-review or excluded",
            "Adjustments remain cross-check evidence unless a later proof selects base-table staging",
            "PaymentAllocations cannot create PMS finance records",
        ],
    }


def _risks(
    *,
    candidate_population: dict[str, Any],
    cancellation_pairing: dict[str, Any],
    refund_handling: dict[str, Any],
    credit_handling: dict[str, Any],
    import_readiness: dict[str, Any],
) -> list[str]:
    risks = [
        "proof is report-only and must not create PMS finance records",
        "finance import-readiness remains false",
        "Adjustments are base-table cross-check evidence, not independent import rows",
        "PaymentAllocations remain reconciliation-only",
        "invoice application remains blocked by missing charge refs",
        "payment method mapping remains proof-only",
    ]
    if _to_int(candidate_population.get("manual_review_count")):
        risks.append("cash-event proof includes manual-review rows")
    if not cancellation_pairing.get("paired_net_zero_within_tolerance"):
        risks.append("paired cancellations do not net to zero within tolerance")
    if _to_int(
        refund_handling["allocation_refund_overlap"].get(
            "allocation_refunds_without_vw_refund_count"
        )
    ):
        risks.append("allocation refunds without vwPayments refund remain unresolved")
    if _to_int(
        refund_handling["vw_refunds_without_allocation"].get(
            "vw_refunds_without_allocation_count"
        )
    ):
        risks.append("vwPayments refunds without allocation rows require policy proof")
    if _to_int(credit_handling["advanced_payment_allocations"].get(
        "advanced_payment_allocation_count"
    )):
        risks.append("advanced payment allocations remain reconciliation-only")
    if not import_readiness.get("finance_import_ready"):
        risks.append("no finance import may start from this proof")
    return risks


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
            "SELECT TOP (?) [RefId] AS ref_id, [PatientCode] AS patient_code, "
            "[At] AS at, [Amount] AS amount, [Type] AS type, "
            "[IsPayment] AS is_payment, [IsRefund] AS is_refund, "
            "[IsCredit] AS is_credit, [IsCancelled] AS is_cancelled, "
            "[PaymentTypeDescription] AS payment_type_description, "
            "[AdjustmentTypeDescription] AS adjustment_type_description "
            "FROM dbo.vwPayments WITH (NOLOCK) "
            f"WHERE {where_sql} "
            f"ORDER BY {order_sql}"
        ),
        [sample_limit],
    )
    return [_json_row(row) for row in rows]


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
            "SELECT TOP (?) c.[RefId] AS cancellation_ref_id, "
            "c.[CancellationOf] AS cancellation_of, "
            "c.[PatientCode] AS cancellation_patient_code, "
            "c.[At] AS cancellation_at, c.[Amount] AS cancellation_amount, "
            "c.[AdjustmentType] AS cancellation_adjustment_type, "
            "c.[PaymentType] AS cancellation_payment_type, "
            "c.[Status] AS cancellation_status, "
            "o.[RefId] AS original_ref_id, o.[PatientCode] AS original_patient_code, "
            "o.[At] AS original_at, o.[Amount] AS original_amount, "
            "o.[AdjustmentType] AS original_adjustment_type, "
            "o.[PaymentType] AS original_payment_type, o.[Status] AS original_status, "
            "CASE WHEN o.[RefId] IS NOT NULL THEN "
            "CAST(ISNULL(c.[Amount], 0) AS decimal(19,2)) + "
            "CAST(ISNULL(o.[Amount], 0) AS decimal(19,2)) ELSE NULL END "
            "AS net_amount "
            "FROM dbo.Adjustments c WITH (NOLOCK) "
            "LEFT JOIN dbo.Adjustments o WITH (NOLOCK) "
            "ON c.[CancellationOf] = o.[RefId] "
            "WHERE c.[CancellationOf] IS NOT NULL AND "
            f"{where_sql} "
            f"ORDER BY {order_sql}"
        ),
        [sample_limit],
    )
    return [_json_row(row) for row in rows]


def _top_distribution(
    source: R4SqlServerSource,
    *,
    table: str,
    column: str,
    amount_column: str,
    top_limit: int,
) -> list[dict[str, Any]]:
    bucket = _bucket_expr(column)
    rows = _read_only_query(
        source,
        (
            f"SELECT TOP (?) {bucket} AS value, COUNT(1) AS row_count, "
            f"{_sum_money(amount_column, 'total_amount')} "
            f"FROM dbo.{table} WITH (NOLOCK) "
            f"GROUP BY {bucket} "
            f"ORDER BY COUNT(1) DESC, {bucket} ASC"
        ),
        [top_limit],
    )
    return [_json_row(row) for row in rows]


def _payment_method_family_distribution(
    source: R4SqlServerSource,
    *,
    top_limit: int,
) -> list[dict[str, Any]]:
    description = "LOWER(LTRIM(RTRIM(CONVERT(varchar(255), [PaymentTypeDescription]))))"
    family = (
        "CASE "
        f"WHEN {description} LIKE '%cash%' THEN 'cash' "
        f"WHEN {description} LIKE '%cheque%' THEN 'cheque' "
        f"WHEN {description} LIKE '%card%' THEN 'card' "
        f"WHEN {description} LIKE '%credit%' THEN 'credit_or_overpayment' "
        f"WHEN {description} = '' OR {description} IS NULL THEN '<blank>' "
        "ELSE 'other_or_unknown' END"
    )
    rows = _read_only_query(
        source,
        (
            f"SELECT TOP (?) {family} AS method_family, COUNT(1) AS row_count, "
            f"{_sum_money('Amount', 'total_amount')} "
            "FROM dbo.vwPayments WITH (NOLOCK) "
            f"GROUP BY {family} "
            "ORDER BY COUNT(1) DESC"
        ),
        [top_limit],
    )
    return [_json_row(row) for row in rows]


def _adjustment_distribution(
    source: R4SqlServerSource,
    *,
    top_limit: int,
) -> list[dict[str, Any]]:
    status_bucket = _bucket_expr("Status")
    rows = _read_only_query(
        source,
        (
            "SELECT TOP (?) [AdjustmentType] AS adjustment_type, "
            "[PaymentType] AS payment_type, "
            f"{status_bucket} AS status, COUNT(1) AS row_count, "
            f"{_sum_money('Amount', 'total_amount')} "
            "FROM dbo.Adjustments WITH (NOLOCK) "
            f"GROUP BY [AdjustmentType], [PaymentType], {status_bucket} "
            "ORDER BY COUNT(1) DESC, [AdjustmentType] ASC, [PaymentType] ASC"
        ),
        [top_limit],
    )
    return [_json_row(row) for row in rows]


def _read_only_query(
    source: R4SqlServerSource,
    sql: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    source.ensure_select_only()
    stripped = sql.lstrip().upper()
    if not stripped.startswith("SELECT "):
        raise RuntimeError("R4 finance cash-event proof only permits SELECT queries.")
    padded = f" {stripped} "
    blocked = (" INSERT ", " UPDATE ", " DELETE ", " MERGE ", " DROP ", " ALTER ", " EXEC ")
    if any(token in padded for token in blocked):
        raise RuntimeError("R4 finance cash-event proof refused a non-read-only query.")
    return source._query(sql, params or [])  # noqa: SLF001


def _vw_payment_representative(bucket: dict[str, Any]) -> dict[str, Any]:
    return {
        "PatientCode": "P001" if _truthy_int(bucket.get("patient_code_present")) else None,
        "At": datetime(2026, 1, 1) if _truthy_int(bucket.get("date_present")) else None,
        "Amount": _amount_for_state(bucket.get("amount_state")),
        "Type": _blank_to_none(bucket.get("type")),
        "IsPayment": _truthy_int(bucket.get("is_payment")),
        "IsRefund": _truthy_int(bucket.get("is_refund")),
        "IsCredit": _truthy_int(bucket.get("is_credit")),
        "IsCancelled": _truthy_int(bucket.get("is_cancelled")),
        "CancellationOf": 1 if _truthy_int(bucket.get("cancellation_of_present")) else None,
    }


def _adjustment_representative(bucket: dict[str, Any]) -> dict[str, Any]:
    return {
        "PatientCode": "P001" if _truthy_int(bucket.get("patient_code_present")) else None,
        "At": datetime(2026, 1, 1) if _truthy_int(bucket.get("date_present")) else None,
        "Amount": _amount_for_state(bucket.get("amount_state")),
        "AdjustmentType": _blank_to_none(bucket.get("adjustment_type")),
        "PaymentType": _blank_to_none(bucket.get("payment_type")),
        "Status": _blank_to_none(bucket.get("status")),
        "CancellationOf": 1 if _truthy_int(bucket.get("cancellation_of_present")) else None,
    }


def _classification_to_json(result: R4FinanceClassificationResult) -> dict[str, Any]:
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


def _reason_total(
    rollup: list[dict[str, Any]],
    reason_codes: set[str],
    *,
    amount_states: set[str] | None = None,
) -> int:
    total = 0
    for row in rollup:
        if amount_states is not None and row.get("amount_state") not in amount_states:
            continue
        if reason_codes.intersection(row.get("cash_event_reason_codes", [])):
            total += _to_int(row.get("row_count"))
    return total


def _json_value(value: Any | None) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _json_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in row.items()}


def _one(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return _json_row(rows[0]) if rows else {}


def _to_int(value: Any | None) -> int:
    if value is None:
        return 0
    return int(value)


def _decimal(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _decimal_close(left: Decimal | None, right: Decimal) -> bool:
    if left is None:
        return False
    return abs(left - right) <= TOLERANCE


def _truthy_int(value: Any | None) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _blank_to_none(value: Any | None) -> Any | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text in {"", "<blank>"} else value


def _amount_for_state(value: Any | None) -> Decimal | None:
    state = str(value or "missing").strip().lower()
    if state == "positive":
        return Decimal("1")
    if state == "negative":
        return Decimal("-1")
    if state == "zero":
        return Decimal("0")
    return None


def _bucket_expr(column: str) -> str:
    return (
        f"COALESCE(NULLIF(LTRIM(RTRIM(CONVERT(varchar(255), [{column}]))), ''), "
        "'<blank>')"
    )


def _blank_predicate(column: str) -> str:
    return (
        f"[{column}] IS NULL OR "
        f"LTRIM(RTRIM(CONVERT(varchar(255), [{column}]))) = ''"
    )


def _patient_present_expr(column: str) -> str:
    return f"CASE WHEN {_blank_predicate(column)} THEN 0 ELSE 1 END"


def _amount_state_expr(column: str) -> str:
    return (
        f"CASE WHEN [{column}] IS NULL THEN 'missing' "
        f"WHEN [{column}] > 0 THEN 'positive' "
        f"WHEN [{column}] < 0 THEN 'negative' ELSE 'zero' END"
    )


def _sum_money(column: str, alias: str) -> str:
    return f"SUM(CAST(ISNULL([{column}], 0) AS decimal(19,2))) AS {alias}"


def _same_text_expr(left: str, right: str) -> str:
    return (
        f"COALESCE(NULLIF(LTRIM(RTRIM(CONVERT(varchar(255), {left}))), ''), '<blank>') = "
        f"COALESCE(NULLIF(LTRIM(RTRIM(CONVERT(varchar(255), {right}))), ''), '<blank>')"
    )
