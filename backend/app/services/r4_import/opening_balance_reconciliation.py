from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.r4_import.finance_classification_policy import (
    R4FinanceClassificationResult,
    classify_finance_row,
)
from app.services.r4_import.sqlserver_source import R4SqlServerSource

__all__ = [
    "run_opening_balance_reconciliation",
]


MONEY_ZERO = "CAST(0 AS decimal(19,2))"
TOLERANCE = Decimal("0.01")


def run_opening_balance_reconciliation(
    source: R4SqlServerSource,
    *,
    sample_limit: int = 10,
) -> dict[str, Any]:
    source.ensure_select_only()
    if sample_limit < 1:
        raise RuntimeError("sample_limit must be at least 1.")

    patient_stats = _patient_stats_consistency(source, sample_limit=sample_limit)
    aged_debt = _aged_debt_report(
        source,
        patient_stats=patient_stats,
        sample_limit=sample_limit,
    )
    linkage = _patient_linkage_report(patient_stats)
    samples = patient_stats.pop("samples")
    classification_summary = _classification_summary(patient_stats, samples)
    cross_source_indicators = _cross_source_indicators(source)
    risks = _risks(
        patient_stats=patient_stats,
        aged_debt=aged_debt,
        classification_summary=classification_summary,
        cross_source_indicators=cross_source_indicators,
    )

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "select_only": True,
        "query_shape": {
            "query_types": [
                "aggregate PatientStats balance/component/aged-debt checks",
                "bounded PatientStats risk samples",
                "aggregate cross-source finance indicators",
            ],
            "sources": [
                "dbo.PatientStats",
                "dbo.vwPayments",
                "dbo.Adjustments",
                "dbo.Transactions",
                "dbo.PaymentAllocations",
                "dbo.vwAllocatedPayments",
            ],
        },
        "patient_stats_consistency": patient_stats,
        "aged_debt": aged_debt,
        "patient_linkage": linkage,
        "classification_summary": classification_summary,
        "cross_source_indicators": cross_source_indicators,
        "risks": risks,
        "samples": samples,
    }


def _patient_stats_consistency(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> dict[str, Any]:
    table = "PatientStats"
    columns = _columns(source, table)
    if not columns:
        return {
            "source": "dbo.PatientStats",
            "present": False,
            "summary": {"row_count": 0},
            "component_checks": {},
            "samples": {},
        }

    balance_components = _balance_components_expr()
    treatment_components = _treatment_components_expr()
    aged_total = _aged_debt_total_expr()
    summary = _one(
        _read_only_query(
            source,
            (
                "SELECT COUNT(1) AS row_count, "
                "COUNT(DISTINCT NULLIF(LTRIM(RTRIM(CONVERT(varchar(255), [PatientCode]))), '')) "
                "AS distinct_patient_codes, "
                f"{_count_null_blank_expr(columns, 'PatientCode', 'null_blank_patient_code_count')}, "
                "SUM(CASE WHEN [Balance] IS NULL THEN 1 ELSE 0 END) AS null_balance_count, "
                "SUM(CASE WHEN [Balance] IS NOT NULL AND [Balance] = 0 THEN 1 ELSE 0 END) "
                "AS zero_balance_count, "
                "SUM(CASE WHEN ISNULL([Balance], 0) <> 0 THEN 1 ELSE 0 END) "
                "AS nonzero_balance_count, "
                "SUM(CASE WHEN ISNULL([Balance], 0) > 0 THEN 1 ELSE 0 END) AS debit_count, "
                "SUM(CASE WHEN ISNULL([Balance], 0) < 0 THEN 1 ELSE 0 END) AS credit_count, "
                f"{_sum_optional_money_expr(columns, 'Balance', 'total_balance')}, "
                "SUM(CASE WHEN ISNULL([Balance], 0) > 0 THEN "
                f"{_money_expr('Balance')} ELSE {MONEY_ZERO} END) AS total_debit_balance, "
                "SUM(CASE WHEN ISNULL([Balance], 0) < 0 THEN "
                f"{_money_expr('Balance')} ELSE {MONEY_ZERO} END) AS total_credit_balance_rows, "
                f"{_sum_optional_money_expr(columns, 'TreatmentBalance', 'total_treatment_balance')}, "
                f"{_sum_optional_money_expr(columns, 'SundriesBalance', 'total_sundries_balance')}, "
                f"{_sum_optional_money_expr(columns, 'NHSBalance', 'total_nhs_balance')}, "
                f"{_sum_optional_money_expr(columns, 'PrivateBalance', 'total_private_balance')}, "
                f"{_sum_optional_money_expr(columns, 'DPBBalance', 'total_dpb_balance')}, "
                f"{_sum_optional_money_expr(columns, 'CreditBalance', 'total_credit_balance')}, "
                f"{_sum_optional_money_expr(columns, 'AgeDebtor30To60', 'aged_debt_30_to_60')}, "
                f"{_sum_optional_money_expr(columns, 'AgeDebtor60To90', 'aged_debt_60_to_90')}, "
                f"{_sum_optional_money_expr(columns, 'AgeDebtor90Plus', 'aged_debt_90_plus')}, "
                f"SUM({aged_total}) AS total_aged_debt, "
                "SUM(CASE WHEN ABS("
                f"{_money_expr('Balance')} - ({balance_components})"
                ") > 0.01 THEN 1 ELSE 0 END) AS balance_component_mismatch_count, "
                "MAX(ABS("
                f"{_money_expr('Balance')} - ({balance_components})"
                ")) AS max_balance_component_difference, "
                "SUM(CASE WHEN ABS("
                f"{_money_expr('TreatmentBalance')} - ({treatment_components})"
                ") > 0.01 THEN 1 ELSE 0 END) AS treatment_split_mismatch_count, "
                "MAX(ABS("
                f"{_money_expr('TreatmentBalance')} - ({treatment_components})"
                ")) AS max_treatment_split_difference "
                "FROM dbo.PatientStats WITH (NOLOCK)"
            ),
        )
    )
    summary = _json_row(summary)
    component_checks = {
        "tolerance": str(TOLERANCE),
        "balance_equals_treatment_plus_sundries": {
            "mismatch_count": _to_int(summary.get("balance_component_mismatch_count")),
            "max_difference": summary.get("max_balance_component_difference"),
            "passes": _to_int(summary.get("balance_component_mismatch_count")) == 0,
        },
        "treatment_equals_nhs_private_dpb": {
            "mismatch_count": _to_int(summary.get("treatment_split_mismatch_count")),
            "max_difference": summary.get("max_treatment_split_difference"),
            "passes": _to_int(summary.get("treatment_split_mismatch_count")) == 0,
        },
    }
    return {
        "source": "dbo.PatientStats",
        "present": True,
        "summary": summary,
        "component_checks": component_checks,
        "samples": {
            "top_debit_rows": _patient_stats_sample(
                source,
                where_sql="ISNULL([Balance], 0) > 0",
                order_sql=f"{_money_expr('Balance')} DESC, [PatientCode] ASC",
                sample_limit=sample_limit,
            ),
            "top_credit_rows": _patient_stats_sample(
                source,
                where_sql="ISNULL([Balance], 0) < 0",
                order_sql=f"ABS({_money_expr('Balance')}) DESC, [PatientCode] ASC",
                sample_limit=sample_limit,
            ),
            "balance_component_mismatch_rows": _patient_stats_sample(
                source,
                where_sql=(
                    "ABS("
                    f"{_money_expr('Balance')} - ({balance_components})"
                    ") > 0.01"
                ),
                order_sql=(
                    "ABS("
                    f"{_money_expr('Balance')} - ({balance_components})"
                    ") DESC, [PatientCode] ASC"
                ),
                sample_limit=sample_limit,
            ),
            "treatment_split_mismatch_rows": _patient_stats_sample(
                source,
                where_sql=(
                    "ABS("
                    f"{_money_expr('TreatmentBalance')} - ({treatment_components})"
                    ") > 0.01"
                ),
                order_sql=(
                    "ABS("
                    f"{_money_expr('TreatmentBalance')} - ({treatment_components})"
                    ") DESC, [PatientCode] ASC"
                ),
                sample_limit=sample_limit,
            ),
            "zero_balance_rows": _patient_stats_sample(
                source,
                where_sql="[Balance] IS NOT NULL AND [Balance] = 0",
                order_sql="[PatientCode] ASC",
                sample_limit=sample_limit,
            ),
        },
    }


def _aged_debt_report(
    source: R4SqlServerSource,
    *,
    patient_stats: dict[str, Any],
    sample_limit: int,
) -> dict[str, Any]:
    if not patient_stats.get("present"):
        return {"source": "dbo.PatientStats", "present": False}
    aged_total = _aged_debt_total_expr()
    summary = _one(
        _read_only_query(
            source,
            (
                "SELECT "
                f"{_sum_money('AgeDebtor30To60', 'aged_debt_30_to_60')}, "
                f"{_sum_money('AgeDebtor60To90', 'aged_debt_60_to_90')}, "
                f"{_sum_money('AgeDebtor90Plus', 'aged_debt_90_plus')}, "
                f"SUM({aged_total}) AS total_aged_debt, "
                f"SUM(CASE WHEN {aged_total} <> 0 THEN 1 ELSE 0 END) AS rows_with_aged_debt, "
                f"SUM(CASE WHEN {aged_total} <> 0 AND ISNULL([Balance], 0) = 0 "
                "THEN 1 ELSE 0 END) AS aged_debt_with_zero_balance_count, "
                f"SUM(CASE WHEN ISNULL([Balance], 0) <> 0 AND {aged_total} = 0 "
                "THEN 1 ELSE 0 END) AS balance_without_aged_debt_count "
                "FROM dbo.PatientStats WITH (NOLOCK)"
            ),
        )
    )
    summary = _json_row(summary)
    patient_summary = patient_stats["summary"]
    total_aged_debt = _decimal(summary.get("total_aged_debt"))
    total_balance = _decimal(patient_summary.get("total_balance"))
    total_debit_balance = _decimal(patient_summary.get("total_debit_balance"))
    reconciliation = {
        "against_total_balance": {
            "difference": _decimal_str(_decimal_diff(total_aged_debt, total_balance)),
            "matches_within_tolerance": _decimal_close(total_aged_debt, total_balance),
        },
        "against_positive_debt_total": {
            "difference": _decimal_str(
                _decimal_diff(total_aged_debt, total_debit_balance)
            ),
            "matches_within_tolerance": _decimal_close(
                total_aged_debt,
                total_debit_balance,
            ),
        },
        "interpretation": (
            "Aged debt is treated as ageing evidence only; it does not create "
            "ledger rows by itself and may omit current/not-yet-aged balances."
        ),
    }
    return {
        "source": "dbo.PatientStats",
        "present": True,
        "summary": summary,
        "obvious_reconciliation": reconciliation,
        "samples": {
            "aged_debt_with_zero_balance_rows": _patient_stats_sample(
                source,
                where_sql=f"{aged_total} <> 0 AND ISNULL([Balance], 0) = 0",
                order_sql=f"ABS({aged_total}) DESC, [PatientCode] ASC",
                sample_limit=sample_limit,
            ),
            "balance_without_aged_debt_rows": _patient_stats_sample(
                source,
                where_sql=f"ISNULL([Balance], 0) <> 0 AND {aged_total} = 0",
                order_sql=f"ABS({_money_expr('Balance')}) DESC, [PatientCode] ASC",
                sample_limit=sample_limit,
            ),
        },
    }


def _patient_linkage_report(patient_stats: dict[str, Any]) -> dict[str, Any]:
    summary = patient_stats.get("summary", {})
    row_count = _to_int(summary.get("row_count"))
    blank = _to_int(summary.get("null_blank_patient_code_count"))
    return {
        "source": "dbo.PatientStats",
        "patient_code_present_count": max(row_count - blank, 0),
        "patient_code_blank_null_count": blank,
        "distinct_patient_codes": _to_int(summary.get("distinct_patient_codes")),
        "mapping_policy": (
            "PatientCode linkage is reported only; this proof does not query or "
            "write PMS patient mappings."
        ),
    }


def _classification_summary(
    patient_stats: dict[str, Any],
    samples: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    summary = patient_stats.get("summary", {})
    debit_count = _to_int(summary.get("debit_count"))
    credit_count = _to_int(summary.get("credit_count"))
    zero_count = _to_int(summary.get("zero_balance_count"))
    null_count = _to_int(summary.get("null_balance_count"))
    blank_patient_count = _to_int(summary.get("null_blank_patient_code_count"))
    nonzero_count = debit_count + credit_count
    classification_counts = {
        "balance_snapshot_candidate": nonzero_count,
        "excluded": zero_count + blank_patient_count,
        "manual_review": null_count,
    }
    safety_decision_counts = {
        "reconciliation_only": nonzero_count,
        "excluded": zero_count + blank_patient_count,
        "manual_review": null_count,
    }
    raw_sign_counts = {
        "positive": debit_count,
        "negative": credit_count,
        "zero": zero_count,
        "unknown": null_count,
    }
    pms_direction_counts = {
        "increase_debt": debit_count,
        "decrease_debt": credit_count,
        "no_change": zero_count,
    }
    sample_rows = (
        samples.get("top_debit_rows", [])[:2]
        + samples.get("top_credit_rows", [])[:2]
        + samples.get("zero_balance_rows", [])[:1]
    )
    return {
        "source": "dbo.PatientStats",
        "policy": (
            "Raw R4 signs are preserved. Positive balances are probable PMS debt "
            "increase, negative balances are probable PMS debt decrease, and all "
            "directions remain proof-only until reconciliation passes."
        ),
        "classification_counts": classification_counts,
        "safety_decision_counts": safety_decision_counts,
        "raw_sign_counts": raw_sign_counts,
        "proposed_pms_direction_counts": pms_direction_counts,
        "sample_classifications": [
            _classification_to_json(classify_finance_row("PatientStats", row))
            for row in sample_rows
        ],
    }


def _cross_source_indicators(source: R4SqlServerSource) -> dict[str, Any]:
    patient_stats = _patient_stats_cross_summary(source)
    payments = _one(
        _read_only_query(
            source,
            (
                "SELECT COUNT(1) AS row_count, "
                f"{_sum_money('Amount', 'total_amount')}, "
                "SUM(CASE WHEN [IsPayment] = 1 THEN 1 ELSE 0 END) AS payment_count, "
                "SUM(CASE WHEN [IsRefund] = 1 THEN 1 ELSE 0 END) AS refund_count, "
                "SUM(CASE WHEN [IsCredit] = 1 THEN 1 ELSE 0 END) AS credit_count, "
                "SUM(CASE WHEN [IsCancelled] = 1 THEN 1 ELSE 0 END) AS cancellation_count "
                "FROM dbo.vwPayments WITH (NOLOCK)"
            ),
        )
    )
    adjustments = _one(
        _read_only_query(
            source,
            (
                "SELECT COUNT(1) AS row_count, "
                f"{_sum_money('Amount', 'total_amount')}, "
                "SUM(CASE WHEN [CancellationOf] IS NOT NULL THEN 1 ELSE 0 END) "
                "AS cancellation_of_count "
                "FROM dbo.Adjustments WITH (NOLOCK)"
            ),
        )
    )
    transactions = _one(
        _read_only_query(
            source,
            (
                "SELECT COUNT(1) AS row_count, "
                f"{_sum_money('PatientCost', 'total_patient_cost')}, "
                f"{_sum_money('DPBCost', 'total_dpb_cost')}, "
                "SUM(CASE WHEN [PaymentAdjustmentID] IS NOT NULL THEN 1 ELSE 0 END) "
                "AS payment_adjustment_id_count "
                "FROM dbo.Transactions WITH (NOLOCK)"
            ),
        )
    )
    allocations = {
        "payment_allocations": _allocation_summary(source, "PaymentAllocations"),
        "allocated_payments_view": _allocation_summary(source, "vwAllocatedPayments"),
    }
    comparisons = {
        "patient_stats_balance_minus_vw_payments_amount": _decimal_str(
            _decimal_diff(
                _decimal(patient_stats.get("total_balance")),
                _decimal(payments.get("total_amount")),
            )
        ),
        "patient_stats_balance_minus_adjustments_amount": _decimal_str(
            _decimal_diff(
                _decimal(patient_stats.get("total_balance")),
                _decimal(adjustments.get("total_amount")),
            )
        ),
        "patient_stats_balance_minus_transaction_patient_cost": _decimal_str(
            _decimal_diff(
                _decimal(patient_stats.get("total_balance")),
                _decimal(transactions.get("total_patient_cost")),
            )
        ),
    }
    return {
        "interpretation": (
            "These are aggregate indicators only. They do not prove payments, "
            "adjustments, transactions, or allocations are R4 ledger truth."
        ),
        "patient_stats": _json_row(patient_stats),
        "payments": _json_row(payments),
        "adjustments": _json_row(adjustments),
        "transactions": _json_row(transactions),
        "allocations": allocations,
        "comparisons": comparisons,
    }


def _patient_stats_cross_summary(source: R4SqlServerSource) -> dict[str, Any]:
    return _one(
        _read_only_query(
            source,
            (
                "SELECT COUNT(1) AS row_count, "
                f"{_sum_money('Balance', 'total_balance')}, "
                "SUM(CASE WHEN ISNULL([Balance], 0) <> 0 THEN 1 ELSE 0 END) "
                "AS nonzero_balance_count "
                "FROM dbo.PatientStats WITH (NOLOCK)"
            ),
        )
    )


def _allocation_summary(source: R4SqlServerSource, table: str) -> dict[str, Any]:
    return _json_row(
        _one(
            _read_only_query(
                source,
                (
                    "SELECT COUNT(1) AS row_count, "
                    f"{_sum_money('Cost', 'total_cost')}, "
                    "SUM(CASE WHEN [IsRefund] = 1 THEN 1 ELSE 0 END) AS refund_count, "
                    "SUM(CASE WHEN [IsAdvancedPayment] = 1 THEN 1 ELSE 0 END) "
                    "AS advanced_payment_count, "
                    "SUM(CASE WHEN [ChargeTransactionRefID] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS charge_transaction_ref_count, "
                    "SUM(CASE WHEN [ChargeAdjustmentRefID] IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS charge_adjustment_ref_count "
                    f"FROM dbo.{table} WITH (NOLOCK)"
                ),
            )
        )
    )


def _risks(
    *,
    patient_stats: dict[str, Any],
    aged_debt: dict[str, Any],
    classification_summary: dict[str, Any],
    cross_source_indicators: dict[str, Any],
) -> list[str]:
    risks = [
        "opening balance proof is report-only and must not create PMS ledger rows",
        "PatientStats is a snapshot source, not row-level invoice/payment truth",
        "cross-source totals are high-level indicators only, not forced reconciliation",
    ]
    checks = patient_stats.get("component_checks", {})
    if not checks.get("balance_equals_treatment_plus_sundries", {}).get("passes"):
        risks.append("Balance does not fully reconcile to TreatmentBalance + SundriesBalance")
    if not checks.get("treatment_equals_nhs_private_dpb", {}).get("passes"):
        risks.append("TreatmentBalance does not fully reconcile to NHS + Private + DPB")
    if _to_int(aged_debt.get("summary", {}).get("aged_debt_with_zero_balance_count")):
        risks.append("some rows have aged debt values with zero Balance")
    if _to_int(aged_debt.get("summary", {}).get("balance_without_aged_debt_count")):
        risks.append("some non-zero Balance rows have no aged debt values")
    if _to_int(
        classification_summary.get("classification_counts", {}).get("manual_review")
    ):
        risks.append("some PatientStats rows require manual review for balance sign")
    payments_refunds = _to_int(
        cross_source_indicators.get("payments", {}).get("refund_count")
    )
    allocation_refunds = _to_int(
        cross_source_indicators.get("allocations", {})
        .get("payment_allocations", {})
        .get("refund_count")
    )
    if payments_refunds != allocation_refunds:
        risks.append(
            "refund counts differ between vwPayments and PaymentAllocations; "
            "refund/allocation proof remains required"
        )
    return risks


def _patient_stats_sample(
    source: R4SqlServerSource,
    *,
    where_sql: str,
    order_sql: str,
    sample_limit: int,
) -> list[dict[str, Any]]:
    rows = _read_only_query(
        source,
        (
            "SELECT TOP (?) [PatientCode] AS PatientCode, [Balance] AS Balance, "
            "[TreatmentBalance] AS TreatmentBalance, [SundriesBalance] AS SundriesBalance, "
            "[NHSBalance] AS NHSBalance, [PrivateBalance] AS PrivateBalance, "
            "[DPBBalance] AS DPBBalance, [AgeDebtor30To60] AS AgeDebtor30To60, "
            "[AgeDebtor60To90] AS AgeDebtor60To90, [AgeDebtor90Plus] AS AgeDebtor90Plus, "
            "[OutstandingSince] AS OutstandingSince "
            "FROM dbo.PatientStats WITH (NOLOCK) "
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


def _read_only_query(
    source: R4SqlServerSource,
    sql: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    source.ensure_select_only()
    stripped = sql.lstrip().upper()
    if not stripped.startswith("SELECT "):
        raise RuntimeError("R4 opening balance proof only permits SELECT queries.")
    padded = f" {stripped} "
    blocked = (" INSERT ", " UPDATE ", " DELETE ", " MERGE ", " DROP ", " ALTER ", " EXEC ")
    if any(token in padded for token in blocked):
        raise RuntimeError("R4 opening balance proof refused a non-read-only query.")
    return source._query(sql, params or [])  # noqa: SLF001


def _columns(source: R4SqlServerSource, table: str) -> set[str]:
    return set(source._get_columns(table))  # noqa: SLF001


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


def _q(column: str) -> str:
    return f"[{column}]"


def _text_expr(column: str) -> str:
    return f"LTRIM(RTRIM(CONVERT(varchar(255), {_q(column)})))"


def _blank_predicate(column: str) -> str:
    return f"{_q(column)} IS NULL OR {_text_expr(column)} = ''"


def _money_expr(column: str) -> str:
    return f"CAST(ISNULL({_q(column)}, 0) AS decimal(19,2))"


def _sum_money(column: str, alias: str) -> str:
    return f"SUM({_money_expr(column)}) AS {alias}"


def _sum_optional_money_expr(columns: set[str], column: str, alias: str) -> str:
    if column not in columns:
        return f"{MONEY_ZERO} AS {alias}"
    return _sum_money(column, alias)


def _count_null_blank_expr(columns: set[str], column: str, alias: str) -> str:
    if column not in columns:
        return f"CAST(NULL AS int) AS {alias}"
    return f"SUM(CASE WHEN {_blank_predicate(column)} THEN 1 ELSE 0 END) AS {alias}"


def _balance_components_expr() -> str:
    return f"{_money_expr('TreatmentBalance')} + {_money_expr('SundriesBalance')}"


def _treatment_components_expr() -> str:
    return (
        f"{_money_expr('NHSBalance')} + {_money_expr('PrivateBalance')} + "
        f"{_money_expr('DPBBalance')}"
    )


def _aged_debt_total_expr() -> str:
    return (
        f"{_money_expr('AgeDebtor30To60')} + {_money_expr('AgeDebtor60To90')} + "
        f"{_money_expr('AgeDebtor90Plus')}"
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


def _decimal_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
