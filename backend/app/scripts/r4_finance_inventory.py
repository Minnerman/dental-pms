from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


MONEY_ZERO = "CAST(0 AS decimal(19,2))"
CORE_SOURCES = {
    "patient_stats": "PatientStats",
    "payments": "vwPayments",
    "adjustments": "Adjustments",
    "transactions": "Transactions",
    "payment_allocations": "PaymentAllocations",
    "allocated_payments_view": "vwAllocatedPayments",
}
LOOKUP_TABLES = {
    "payment_types": "PaymentTypes",
    "other_payment_types": "OtherPaymentTypes",
    "payment_card_types": "PaymentCardTypes",
    "adjustment_types": "AdjustmentTypes",
}
SCHEME_SOURCES = {
    "denplan_view": "vwDenplan",
    "denplan_patients": "DenplanPatients",
    "nhs_patient_details": "NHSPatientDetails",
}


def _to_int(value: Any | None) -> int:
    if value is None:
        return 0
    return int(value)


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


def _q(column: str) -> str:
    return f"[{column}]"


def _text_expr(column: str) -> str:
    return f"LTRIM(RTRIM(CONVERT(varchar(255), {_q(column)})))"


def _bucket_expr(column: str) -> str:
    return f"COALESCE(NULLIF({_text_expr(column)}, ''), '<blank>')"


def _blank_predicate(column: str) -> str:
    return f"{_q(column)} IS NULL OR {_text_expr(column)} = ''"


def _money_expr(column: str) -> str:
    return f"CAST(ISNULL({_q(column)}, 0) AS decimal(19,2))"


def _sum_money(column: str, alias: str) -> str:
    return f"SUM({_money_expr(column)}) AS {alias}"


def _read_only_query(
    source: R4SqlServerSource,
    sql: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    source.ensure_select_only()
    stripped = sql.lstrip().upper()
    if not stripped.startswith("SELECT "):
        raise RuntimeError("R4 finance inventory only permits SELECT queries.")
    padded = f" {stripped} "
    blocked = (" INSERT ", " UPDATE ", " DELETE ", " MERGE ", " DROP ", " ALTER ", " EXEC ")
    if any(token in padded for token in blocked):
        raise RuntimeError("R4 finance inventory refused a non-read-only query.")
    return source._query(sql, params or [])  # noqa: SLF001


def _columns(source: R4SqlServerSource, table: str) -> set[str]:
    return set(source._get_columns(table))  # noqa: SLF001


def _source_present(source: R4SqlServerSource, table: str) -> bool:
    return bool(_columns(source, table))


def _count_null_blank_expr(columns: set[str], column: str, alias: str) -> str:
    if column not in columns:
        return f"CAST(NULL AS int) AS {alias}"
    return f"SUM(CASE WHEN {_blank_predicate(column)} THEN 1 ELSE 0 END) AS {alias}"


def _sum_optional_money_expr(columns: set[str], column: str, alias: str) -> str:
    if column not in columns:
        return f"{MONEY_ZERO} AS {alias}"
    return _sum_money(column, alias)


def _non_null_count_expr(columns: set[str], column: str, alias: str) -> str:
    if column not in columns:
        return f"CAST(NULL AS int) AS {alias}"
    return f"SUM(CASE WHEN {_q(column)} IS NOT NULL THEN 1 ELSE 0 END) AS {alias}"


def _top_distribution(
    source: R4SqlServerSource,
    *,
    table: str,
    column: str,
    top_limit: int,
    amount_column: str | None = None,
) -> list[dict[str, Any]]:
    columns = _columns(source, table)
    if column not in columns:
        return []
    bucket = _bucket_expr(column)
    amount_sql = (
        f", {_sum_money(amount_column, 'total_amount')}"
        if amount_column and amount_column in columns
        else ""
    )
    rows = _read_only_query(
        source,
        (
            f"SELECT TOP (?) {bucket} AS value, COUNT(1) AS row_count{amount_sql} "
            f"FROM dbo.{table} WITH (NOLOCK) "
            f"GROUP BY {bucket} "
            f"ORDER BY COUNT(1) DESC, {bucket} ASC"
        ),
        [top_limit],
    )
    return [_json_row(row) for row in rows]


def _run_summary_query(
    source: R4SqlServerSource,
    *,
    table: str,
    sql: str,
) -> dict[str, Any]:
    if not _source_present(source, table):
        return {"present": False, "row_count": 0}
    summary = _one(_read_only_query(source, sql))
    summary["present"] = True
    return summary


def _sample_query(
    source: R4SqlServerSource,
    *,
    table: str,
    select_sql: str,
    where_sql: str,
    order_sql: str,
    sample_limit: int,
) -> list[dict[str, Any]]:
    if not _source_present(source, table):
        return []
    rows = _read_only_query(
        source,
        (
            f"SELECT TOP (?) {select_sql} "
            f"FROM dbo.{table} WITH (NOLOCK) "
            f"WHERE {where_sql} "
            f"ORDER BY {order_sql}"
        ),
        [sample_limit],
    )
    return [_json_row(row) for row in rows]


def _patient_stats_report(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
) -> dict[str, Any]:
    table = CORE_SOURCES["patient_stats"]
    columns = _columns(source, table)
    if not columns:
        return {"source": f"dbo.{table}", "present": False, "row_count": 0}
    summary = _run_summary_query(
        source,
        table=table,
        sql=(
            "SELECT COUNT(1) AS row_count, "
            f"{_count_null_blank_expr(columns, 'PatientCode', 'null_blank_patient_code_count')}, "
            "SUM(CASE WHEN ISNULL([Balance], 0) <> 0 THEN 1 ELSE 0 END) AS nonzero_balance_count, "
            f"{_sum_optional_money_expr(columns, 'Balance', 'total_balance')}, "
            f"{_sum_optional_money_expr(columns, 'TreatmentBalance', 'total_treatment_balance')}, "
            f"{_sum_optional_money_expr(columns, 'SundriesBalance', 'total_sundries_balance')}, "
            f"{_sum_optional_money_expr(columns, 'NHSBalance', 'total_nhs_balance')}, "
            f"{_sum_optional_money_expr(columns, 'PrivateBalance', 'total_private_balance')}, "
            f"{_sum_optional_money_expr(columns, 'DPBBalance', 'total_dpb_balance')}, "
            f"{_sum_optional_money_expr(columns, 'CreditBalance', 'total_credit_balance')}, "
            f"{_sum_optional_money_expr(columns, 'AgeDebtor30To60', 'aged_debt_30_to_60')}, "
            f"{_sum_optional_money_expr(columns, 'AgeDebtor60To90', 'aged_debt_60_to_90')}, "
            f"{_sum_optional_money_expr(columns, 'AgeDebtor90Plus', 'aged_debt_90_plus')}, "
            "MIN([OutstandingSince]) AS min_outstanding_since, "
            "MAX([OutstandingSince]) AS max_outstanding_since "
            "FROM dbo.PatientStats WITH (NOLOCK)"
        ),
    )
    distribution = _read_only_query(
        source,
        (
            "SELECT "
            "CASE WHEN ISNULL([Balance], 0) < 0 THEN 'credit' "
            "WHEN ISNULL([Balance], 0) > 0 THEN 'debt' ELSE 'zero' END AS balance_bucket, "
            "COUNT(1) AS row_count, "
            f"{_sum_money('Balance', 'total_balance')} "
            "FROM dbo.PatientStats WITH (NOLOCK) "
            "GROUP BY CASE WHEN ISNULL([Balance], 0) < 0 THEN 'credit' "
            "WHEN ISNULL([Balance], 0) > 0 THEN 'debt' ELSE 'zero' END "
            "ORDER BY COUNT(1) DESC"
        ),
    )
    samples = _sample_query(
        source,
        table=table,
        select_sql=(
            "[PatientCode] AS patient_code, [Balance] AS balance, "
            "[TreatmentBalance] AS treatment_balance, [SundriesBalance] AS sundries_balance, "
            "[NHSBalance] AS nhs_balance, [PrivateBalance] AS private_balance, "
            "[OutstandingSince] AS outstanding_since"
        ),
        where_sql="ISNULL([Balance], 0) <> 0",
        order_sql="ABS(CAST(ISNULL([Balance], 0) AS decimal(19,2))) DESC, [PatientCode] ASC",
        sample_limit=sample_limit,
    )
    return {
        "source": f"dbo.{table}",
        "summary": summary,
        "balance_distribution": [_json_row(row) for row in distribution],
        "top_balance_rows": samples,
    }


def _payments_report(
    source: R4SqlServerSource,
    *,
    sample_limit: int,
    top_limit: int,
) -> dict[str, Any]:
    table = CORE_SOURCES["payments"]
    columns = _columns(source, table)
    if not columns:
        return {"source": f"dbo.{table}", "present": False, "row_count": 0}
    summary = _run_summary_query(
        source,
        table=table,
        sql=(
            "SELECT COUNT(1) AS row_count, "
            f"{_count_null_blank_expr(columns, 'PatientCode', 'null_blank_patient_code_count')}, "
            "MIN([At]) AS min_at, MAX([At]) AS max_at, "
            f"{_sum_optional_money_expr(columns, 'Amount', 'total_amount')}, "
            "SUM(CASE WHEN [IsCancelled] = 1 THEN 1 ELSE 0 END) AS cancellation_count, "
            "SUM(CASE WHEN [IsPayment] = 1 THEN 1 ELSE 0 END) AS payment_count, "
            "SUM(CASE WHEN [IsRefund] = 1 THEN 1 ELSE 0 END) AS refund_count, "
            "SUM(CASE WHEN [IsCredit] = 1 THEN 1 ELSE 0 END) AS credit_count "
            "FROM dbo.vwPayments WITH (NOLOCK)"
        ),
    )
    flag_groups = _read_only_query(
        source,
        (
            "SELECT TOP (?) [IsPayment] AS is_payment, [IsRefund] AS is_refund, "
            "[IsCredit] AS is_credit, [IsCancelled] AS is_cancelled, "
            "COUNT(1) AS row_count, "
            f"{_sum_money('Amount', 'total_amount')} "
            "FROM dbo.vwPayments WITH (NOLOCK) "
            "GROUP BY [IsPayment], [IsRefund], [IsCredit], [IsCancelled] "
            "ORDER BY COUNT(1) DESC"
        ),
        [top_limit],
    )
    sample_select = (
        "[RefId] AS ref_id, [PatientCode] AS patient_code, [At] AS at, "
        "[Amount] AS amount, [Type] AS type, [IsPayment] AS is_payment, "
        "[IsRefund] AS is_refund, [IsCredit] AS is_credit, [IsCancelled] AS is_cancelled, "
        "[PaymentTypeDescription] AS payment_type_description, "
        "[AdjustmentTypeDescription] AS adjustment_type_description"
    )
    return {
        "source": f"dbo.{table}",
        "summary": summary,
        "by_type": _top_distribution(
            source,
            table=table,
            column="Type",
            amount_column="Amount",
            top_limit=top_limit,
        ),
        "by_flags": [_json_row(row) for row in flag_groups],
        "by_payment_type": _top_distribution(
            source,
            table=table,
            column="PaymentTypeDescription",
            amount_column="Amount",
            top_limit=top_limit,
        ),
        "samples": {
            "cancelled_rows": _sample_query(
                source,
                table=table,
                select_sql=sample_select,
                where_sql="[IsCancelled] = 1",
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=sample_limit,
            ),
            "refund_rows": _sample_query(
                source,
                table=table,
                select_sql=sample_select,
                where_sql="[IsRefund] = 1",
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=sample_limit,
            ),
            "credit_rows": _sample_query(
                source,
                table=table,
                select_sql=sample_select,
                where_sql="[IsCredit] = 1",
                order_sql="[At] DESC, [RefId] DESC",
                sample_limit=sample_limit,
            ),
        },
    }


def _adjustments_report(
    source: R4SqlServerSource,
    *,
    top_limit: int,
) -> dict[str, Any]:
    table = CORE_SOURCES["adjustments"]
    columns = _columns(source, table)
    if not columns:
        return {"source": f"dbo.{table}", "present": False, "row_count": 0}
    summary = _run_summary_query(
        source,
        table=table,
        sql=(
            "SELECT COUNT(1) AS row_count, "
            f"{_count_null_blank_expr(columns, 'PatientCode', 'null_blank_patient_code_count')}, "
            "MIN([At]) AS min_at, MAX([At]) AS max_at, "
            f"{_sum_optional_money_expr(columns, 'Amount', 'total_amount')}, "
            f"{_non_null_count_expr(columns, 'CancellationOf', 'cancellation_of_count')} "
            "FROM dbo.Adjustments WITH (NOLOCK)"
        ),
    )
    grouped = _read_only_query(
        source,
        (
            "SELECT TOP (?) [AdjustmentType] AS adjustment_type, "
            "[PaymentType] AS payment_type, [Status] AS status, "
            "COUNT(1) AS row_count, "
            f"{_sum_money('Amount', 'total_amount')} "
            "FROM dbo.Adjustments WITH (NOLOCK) "
            "GROUP BY [AdjustmentType], [PaymentType], [Status] "
            "ORDER BY COUNT(1) DESC"
        ),
        [top_limit],
    )
    return {
        "source": f"dbo.{table}",
        "summary": summary,
        "by_adjustment_payment_status": [_json_row(row) for row in grouped],
    }


def _transactions_report(
    source: R4SqlServerSource,
    *,
    top_limit: int,
) -> dict[str, Any]:
    table = CORE_SOURCES["transactions"]
    columns = _columns(source, table)
    if not columns:
        return {"source": f"dbo.{table}", "present": False, "row_count": 0}
    summary = _run_summary_query(
        source,
        table=table,
        sql=(
            "SELECT COUNT(1) AS row_count, "
            f"{_count_null_blank_expr(columns, 'PatientCode', 'null_blank_patient_code_count')}, "
            "MIN([Date]) AS min_date, MAX([Date]) AS max_date, "
            f"{_sum_optional_money_expr(columns, 'PatientCost', 'total_patient_cost')}, "
            f"{_sum_optional_money_expr(columns, 'DPBCost', 'total_dpb_cost')}, "
            f"{_non_null_count_expr(columns, 'PaymentAdjustmentID', 'payment_adjustment_id_count')}, "
            f"{_non_null_count_expr(columns, 'TPNumber', 'tp_number_count')}, "
            f"{_non_null_count_expr(columns, 'TPItem', 'tp_item_count')} "
            "FROM dbo.Transactions WITH (NOLOCK)"
        ),
    )
    user_groups = _read_only_query(
        source,
        (
            "SELECT TOP (?) [UserCode] AS user_code, COUNT(1) AS row_count, "
            f"{_sum_money('PatientCost', 'total_patient_cost')}, "
            f"{_sum_money('DPBCost', 'total_dpb_cost')} "
            "FROM dbo.Transactions WITH (NOLOCK) "
            "GROUP BY [UserCode] "
            "ORDER BY COUNT(1) DESC"
        ),
        [top_limit],
    )
    return {
        "source": f"dbo.{table}",
        "summary": summary,
        "by_user_code": [_json_row(row) for row in user_groups],
    }


def _allocation_report(
    source: R4SqlServerSource,
    *,
    table: str,
) -> dict[str, Any]:
    columns = _columns(source, table)
    if not columns:
        return {"source": f"dbo.{table}", "present": False, "row_count": 0}
    return {
        "source": f"dbo.{table}",
        "summary": _run_summary_query(
            source,
            table=table,
            sql=(
                "SELECT COUNT(1) AS row_count, "
                f"{_count_null_blank_expr(columns, 'PatientCode', 'null_blank_patient_code_count')}, "
                "MIN([AllocationDate]) AS min_allocation_date, "
                "MAX([AllocationDate]) AS max_allocation_date, "
                "MIN([PaymentDate]) AS min_payment_date, "
                "MAX([PaymentDate]) AS max_payment_date, "
                f"{_sum_optional_money_expr(columns, 'Cost', 'total_cost')}, "
                "SUM(CASE WHEN [IsRefund] = 1 THEN 1 ELSE 0 END) AS refund_count, "
                "SUM(CASE WHEN [IsAdvancedPayment] = 1 THEN 1 ELSE 0 END) AS advanced_payment_count, "
                "SUM(CASE WHEN [IsAllocationAdjustment] = 1 THEN 1 ELSE 0 END) AS allocation_adjustment_count, "
                "SUM(CASE WHEN [IsBalancingEntry] = 1 THEN 1 ELSE 0 END) AS balancing_entry_count, "
                f"{_non_null_count_expr(columns, 'PaymentID', 'linked_payment_count')}, "
                f"{_non_null_count_expr(columns, 'ChargeTransactionRefID', 'charge_transaction_ref_count')}, "
                f"{_non_null_count_expr(columns, 'ChargeAdjustmentRefID', 'charge_adjustment_ref_count')} "
                f"FROM dbo.{table} WITH (NOLOCK)"
            ),
        ),
        "by_payment_type": _top_distribution(
            source,
            table=table,
            column="PaymentTypeDesc",
            amount_column="Cost",
            top_limit=20,
        ),
    }


def _lookup_table_report(
    source: R4SqlServerSource,
    *,
    table: str,
    key_candidates: list[str],
    value_candidates: list[str],
    sample_limit: int,
) -> dict[str, Any]:
    columns = _columns(source, table)
    if not columns:
        return {"source": f"dbo.{table}", "present": False, "row_count": 0, "samples": []}
    key_col = next((col for col in key_candidates if col in columns), None)
    value_col = next((col for col in value_candidates if col in columns), None)
    extra_cols = [col for col in ("Current", "CardType") if col in columns and col != value_col]
    select_cols = ["COUNT(1) AS row_count"]
    summary = _one(
        _read_only_query(
            source,
            f"SELECT {', '.join(select_cols)} FROM dbo.{table} WITH (NOLOCK)",
        )
    )
    sample_select: list[str] = []
    if key_col:
        sample_select.append(f"{_q(key_col)} AS lookup_key")
    if value_col:
        sample_select.append(f"{_q(value_col)} AS lookup_value")
    for extra_col in extra_cols:
        sample_select.append(f"{_q(extra_col)} AS lookup_{extra_col.lower()}")
    if not sample_select:
        sample_select = [f"{_q(columns.pop())} AS lookup_value"]
    order_col = key_col or value_col or sample_select[0].split(" AS ", 1)[0]
    samples = _read_only_query(
        source,
        (
            f"SELECT TOP (?) {', '.join(sample_select)} "
            f"FROM dbo.{table} WITH (NOLOCK) "
            f"ORDER BY {order_col} ASC"
        ),
        [sample_limit],
    )
    return {
        "source": f"dbo.{table}",
        "present": True,
        "summary": summary,
        "samples": [_json_row(row) for row in samples],
    }


def _scheme_report(
    source: R4SqlServerSource,
    *,
    top_limit: int,
) -> dict[str, Any]:
    denplan_view = SCHEME_SOURCES["denplan_view"]
    denplan_patients = SCHEME_SOURCES["denplan_patients"]
    nhs_details = SCHEME_SOURCES["nhs_patient_details"]
    return {
        "vw_denplan": {
            "source": f"dbo.{denplan_view}",
            "summary": _run_summary_query(
                source,
                table=denplan_view,
                sql=(
                    "SELECT COUNT(1) AS row_count, "
                    f"{_count_null_blank_expr(_columns(source, denplan_view), 'PatientCode', 'null_blank_patient_code_count')}, "
                    "COUNT(DISTINCT [PatientCode]) AS distinct_patient_codes "
                    "FROM dbo.vwDenplan WITH (NOLOCK)"
                ),
            ),
            "by_patient_status": _top_distribution(
                source,
                table=denplan_view,
                column="PatientStatus",
                top_limit=top_limit,
            ),
            "by_payment_status": _top_distribution(
                source,
                table=denplan_view,
                column="PaymentStatus",
                top_limit=top_limit,
            ),
            "by_fee_code": _top_distribution(
                source,
                table=denplan_view,
                column="FeeCode",
                top_limit=top_limit,
            ),
        },
        "denplan_patients": {
            "source": f"dbo.{denplan_patients}",
            "summary": _run_summary_query(
                source,
                table=denplan_patients,
                sql=(
                    "SELECT COUNT(1) AS row_count, "
                    "COUNT(DISTINCT [ID]) AS distinct_ids "
                    "FROM dbo.DenplanPatients WITH (NOLOCK)"
                ),
            ),
            "by_patient_status": _top_distribution(
                source,
                table=denplan_patients,
                column="PatientStatus",
                top_limit=top_limit,
            ),
            "by_payment_status": _top_distribution(
                source,
                table=denplan_patients,
                column="PaymentStatus",
                top_limit=top_limit,
            ),
        },
        "nhs_patient_details": {
            "source": f"dbo.{nhs_details}",
            "summary": _run_summary_query(
                source,
                table=nhs_details,
                sql=(
                    "SELECT COUNT(1) AS row_count, "
                    f"{_count_null_blank_expr(_columns(source, nhs_details), 'PatientCode', 'null_blank_patient_code_count')}, "
                    "COUNT(DISTINCT [PatientCode]) AS distinct_patient_codes "
                    "FROM dbo.NHSPatientDetails WITH (NOLOCK)"
                ),
            ),
            "by_ethnicity_category": _top_distribution(
                source,
                table=nhs_details,
                column="EthnicityCatID",
                top_limit=top_limit,
            ),
        },
    }


def _risks(report: dict[str, Any]) -> list[str]:
    risks = [
        "sign conventions for balances/payments/refunds/credits require proof",
        "cancellation/reversal handling must be mapped before any finance import",
        "allocation semantics require reconciliation before ledger writes",
        "no explicit invoice/statement source has been confirmed",
        "NHS/private/Denplan classifications must not be inferred as ledger truth",
    ]
    payments_summary = report["payments"].get("summary", {})
    payment_allocations_summary = report["allocations"]["payment_allocations"].get(
        "summary",
        {},
    )
    patient_stats_summary = report["patient_stats"].get("summary", {})
    payments_refunds = _to_int(payments_summary.get("refund_count"))
    allocation_refunds = _to_int(payment_allocations_summary.get("refund_count"))
    if payments_refunds != allocation_refunds:
        risks.append(
            "refund counts differ between vwPayments and PaymentAllocations; reconcile before import"
        )
    if _to_int(patient_stats_summary.get("nonzero_balance_count")):
        risks.append("opening balances exist and need PatientStats reconciliation proof")
    return risks


def run_inventory(
    source: R4SqlServerSource,
    *,
    sample_limit: int = 10,
    top_limit: int = 20,
) -> dict[str, Any]:
    source.ensure_select_only()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "select_only": True,
        "query_shape": {
            "query_types": [
                "metadata-backed aggregate counts/min/max/sums",
                "grouped status/type/method/flag distributions",
                "small bounded samples for balance/cancelled/refund/credit edge rows",
                "lookup table key/value snapshots",
            ],
            "sources": {
                **CORE_SOURCES,
                **LOOKUP_TABLES,
                **SCHEME_SOURCES,
            },
        },
        "patient_stats": _patient_stats_report(source, sample_limit=sample_limit),
        "payments": _payments_report(
            source,
            sample_limit=sample_limit,
            top_limit=top_limit,
        ),
        "adjustments": _adjustments_report(source, top_limit=top_limit),
        "transactions": _transactions_report(source, top_limit=top_limit),
        "allocations": {
            "payment_allocations": _allocation_report(
                source,
                table=CORE_SOURCES["payment_allocations"],
            ),
            "allocated_payments_view": _allocation_report(
                source,
                table=CORE_SOURCES["allocated_payments_view"],
            ),
        },
        "lookup_tables": {
            "payment_types": _lookup_table_report(
                source,
                table=LOOKUP_TABLES["payment_types"],
                key_candidates=["PaymentType", "ID", "Id"],
                value_candidates=["Description", "Name"],
                sample_limit=sample_limit,
            ),
            "other_payment_types": _lookup_table_report(
                source,
                table=LOOKUP_TABLES["other_payment_types"],
                key_candidates=["OtherPaymentTypeID", "ID", "Id"],
                value_candidates=["Description", "Name"],
                sample_limit=sample_limit,
            ),
            "payment_card_types": _lookup_table_report(
                source,
                table=LOOKUP_TABLES["payment_card_types"],
                key_candidates=["Id", "ID", "PaymentCardTypeId"],
                value_candidates=["Description", "CardType", "Name"],
                sample_limit=sample_limit,
            ),
            "adjustment_types": _lookup_table_report(
                source,
                table=LOOKUP_TABLES["adjustment_types"],
                key_candidates=["AdjustmentType", "ID", "Id"],
                value_candidates=["Description", "Abbrev", "Name"],
                sample_limit=sample_limit,
            ),
        },
        "scheme_classification": _scheme_report(source, top_limit=top_limit),
    }
    report["risks"] = _risks(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SELECT-only R4 finance/payment/balance inventory report."
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="Bounded sample rows to include for edge-case categories.",
    )
    parser.add_argument(
        "--top-limit",
        type=int,
        default=20,
        help="Top grouped distribution buckets to include.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write inventory JSON.",
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
    report = run_inventory(
        source,
        sample_limit=args.sample_limit,
        top_limit=args.top_limit,
    )

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "output_json": str(output_path),
        "select_only": report["select_only"],
        "patient_stats": {
            "row_count": report["patient_stats"]["summary"].get("row_count"),
            "nonzero_balance_count": report["patient_stats"]["summary"].get(
                "nonzero_balance_count"
            ),
            "total_balance": report["patient_stats"]["summary"].get("total_balance"),
        },
        "payments": {
            "row_count": report["payments"]["summary"].get("row_count"),
            "total_amount": report["payments"]["summary"].get("total_amount"),
            "payment_count": report["payments"]["summary"].get("payment_count"),
            "refund_count": report["payments"]["summary"].get("refund_count"),
            "credit_count": report["payments"]["summary"].get("credit_count"),
            "cancellation_count": report["payments"]["summary"].get(
                "cancellation_count"
            ),
        },
        "adjustments": {
            "row_count": report["adjustments"]["summary"].get("row_count"),
            "total_amount": report["adjustments"]["summary"].get("total_amount"),
        },
        "transactions": {
            "row_count": report["transactions"]["summary"].get("row_count"),
            "total_patient_cost": report["transactions"]["summary"].get(
                "total_patient_cost"
            ),
            "total_dpb_cost": report["transactions"]["summary"].get("total_dpb_cost"),
        },
        "risks": report["risks"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
