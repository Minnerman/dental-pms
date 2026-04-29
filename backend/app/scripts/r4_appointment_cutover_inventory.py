from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


SOURCE_TABLE = "vwAppointmentDetails"
SOURCE_SQL = f"dbo.{SOURCE_TABLE} WITH (NOLOCK)"
EXPECTED_STATUS_VALUES = {
    "arrived",
    "booked",
    "cancelled",
    "checked in",
    "checked-in",
    "complete",
    "completed",
    "did not attend",
    "dna",
    "in progress",
    "in_progress",
    "no show",
    "no-show",
    "pending",
}


def _to_int(value: Any | None) -> int:
    if value is None:
        return 0
    return int(value)


def _format_dt(value: Any | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_value(value: Any | None) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _text_expr(column: str) -> str:
    return f"LTRIM(RTRIM(CONVERT(varchar(255), {column})))"


def _bucket_expr(column: str) -> str:
    return f"COALESCE(NULLIF({_text_expr(column)}, ''), '<blank>')"


def _blank_predicate(column: str) -> str:
    return f"{column} IS NULL OR {_text_expr(column)} = ''"


def _read_only_query(source: R4SqlServerSource, sql: str, params: list[Any] | None = None):
    stripped = sql.lstrip().upper()
    if not stripped.startswith("SELECT "):
        raise RuntimeError("Appointment cutover inventory only permits SELECT queries.")
    blocked = (" INSERT ", " UPDATE ", " DELETE ", " MERGE ", " DROP ", " ALTER ", " EXEC ")
    padded = f" {stripped} "
    if any(token in padded for token in blocked):
        raise RuntimeError("Appointment cutover inventory refused a non-read-only query.")
    return source._query(sql, params or [])  # noqa: SLF001


def _distribution(
    source: R4SqlServerSource,
    *,
    column: str | None,
    top_limit: int,
) -> dict[str, Any]:
    if not column:
        return {"column": None, "distinct_count": 0, "blank_count": None, "top": []}

    bucket = _bucket_expr(column)
    rows = _read_only_query(
        source,
        (
            f"SELECT TOP (?) {bucket} AS value, COUNT(1) AS count "
            f"FROM {SOURCE_SQL} "
            f"GROUP BY {bucket} "
            f"ORDER BY COUNT(1) DESC, {bucket} ASC"
        ),
        [top_limit],
    )
    summary_rows = _read_only_query(
        source,
        (
            f"SELECT COUNT(DISTINCT {bucket}) AS distinct_count, "
            f"SUM(CASE WHEN {_blank_predicate(column)} THEN 1 ELSE 0 END) AS blank_count "
            f"FROM {SOURCE_SQL}"
        ),
    )
    summary = summary_rows[0] if summary_rows else {}
    return {
        "column": column,
        "distinct_count": _to_int(summary.get("distinct_count")),
        "blank_count": _to_int(summary.get("blank_count")),
        "top": [
            {"value": row.get("value"), "count": _to_int(row.get("count"))}
            for row in rows
        ],
    }


def _select_columns(
    *,
    appt_id_col: str,
    starts_col: str,
    patient_col: str | None,
    duration_col: str | None,
    provider_col: str | None,
    status_col: str | None,
    cancelled_col: str | None,
    clinic_col: str | None,
    type_col: str | None,
    flag_col: str | None,
) -> list[str]:
    columns = [
        f"{appt_id_col} AS appointment_id",
        f"{starts_col} AS starts_at",
    ]
    optional = [
        (patient_col, "patient_code"),
        (duration_col, "duration_minutes"),
        (provider_col, "clinician_code"),
        (status_col, "status"),
        (cancelled_col, "cancelled"),
        (clinic_col, "clinic_code"),
        (type_col, "appointment_type"),
        (flag_col, "appt_flag"),
    ]
    for column, alias in optional:
        if column:
            columns.append(f"{column} AS {alias}")
    return columns


def _sample_rows(
    source: R4SqlServerSource,
    *,
    where_sql: str,
    params: list[Any],
    order_sql: str,
    limit: int,
    select_cols: list[str],
) -> list[dict[str, Any]]:
    rows = _read_only_query(
        source,
        (
            f"SELECT TOP (?) {', '.join(select_cols)} "
            f"FROM {SOURCE_SQL} "
            f"WHERE {where_sql} "
            f"ORDER BY {order_sql}"
        ),
        [limit, *params],
    )
    return [{key: _json_value(value) for key, value in row.items()} for row in rows]


def run_inventory(
    source: R4SqlServerSource,
    *,
    cutover_date: date,
    sample_limit: int = 10,
    top_limit: int = 20,
) -> dict[str, Any]:
    source.ensure_select_only()

    appt_id_col = source._require_column(SOURCE_TABLE, ["apptid"])  # noqa: SLF001
    starts_col = source._require_column(  # noqa: SLF001
        SOURCE_TABLE,
        ["appointmentDateTimevalue"],
    )
    duration_col = source._pick_column(SOURCE_TABLE, ["duration"])  # noqa: SLF001
    patient_col = source._pick_column(SOURCE_TABLE, ["patientcode"])  # noqa: SLF001
    provider_col = source._pick_column(SOURCE_TABLE, ["providerCode"])  # noqa: SLF001
    status_col = source._pick_column(SOURCE_TABLE, ["status"])  # noqa: SLF001
    cancelled_col = source._pick_column(SOURCE_TABLE, ["cancelled"])  # noqa: SLF001
    clinic_col = source._pick_column(SOURCE_TABLE, ["cliniccode"])  # noqa: SLF001
    type_col = source._pick_column(SOURCE_TABLE, ["appointmentType"])  # noqa: SLF001
    flag_col = source._pick_column(SOURCE_TABLE, ["apptflag"])  # noqa: SLF001

    cutover_dt = datetime.combine(cutover_date, time.min)
    before_7d = cutover_dt - timedelta(days=7)
    after_7d = cutover_dt + timedelta(days=7)
    after_1d = cutover_dt + timedelta(days=1)

    patient_blank_sql = (
        f"SUM(CASE WHEN {_blank_predicate(patient_col)} THEN 1 ELSE 0 END) "
        if patient_col
        else "CAST(NULL AS int)"
    )
    base_rows = _read_only_query(
        source,
        (
            "SELECT "
            "COUNT(1) AS total_count, "
            f"SUM(CASE WHEN {starts_col} < ? THEN 1 ELSE 0 END) AS past_count, "
            f"SUM(CASE WHEN {starts_col} >= ? THEN 1 ELSE 0 END) AS future_count, "
            f"MIN({starts_col}) AS min_start, "
            f"MAX({starts_col}) AS max_start, "
            f"SUM(CASE WHEN {starts_col} IS NULL THEN 1 ELSE 0 END) AS null_start_count, "
            f"{patient_blank_sql} AS null_blank_patient_code_count, "
            f"SUM(CASE WHEN {starts_col} >= ? AND {starts_col} < ? THEN 1 ELSE 0 END) AS cutover_day_count, "
            f"SUM(CASE WHEN {starts_col} >= ? AND {starts_col} < ? THEN 1 ELSE 0 END) AS seven_days_before_count, "
            f"SUM(CASE WHEN {starts_col} >= ? AND {starts_col} < ? THEN 1 ELSE 0 END) AS seven_days_after_count "
            f"FROM {SOURCE_SQL}"
        ),
        [
            cutover_dt,
            cutover_dt,
            cutover_dt,
            after_1d,
            before_7d,
            cutover_dt,
            cutover_dt,
            after_7d,
        ],
    )
    base = base_rows[0] if base_rows else {}

    by_year_rows = _read_only_query(
        source,
        (
            f"SELECT DATEPART(year, {starts_col}) AS year, COUNT(1) AS count "
            f"FROM {SOURCE_SQL} "
            f"GROUP BY DATEPART(year, {starts_col}) "
            "ORDER BY DATEPART(year, {0}) ASC".format(starts_col)
        ),
    )
    future_by_month_rows = _read_only_query(
        source,
        (
            f"SELECT CONVERT(char(7), {starts_col}, 120) AS month, COUNT(1) AS count "
            f"FROM {SOURCE_SQL} "
            f"WHERE {starts_col} >= ? "
            f"GROUP BY CONVERT(char(7), {starts_col}, 120) "
            f"ORDER BY CONVERT(char(7), {starts_col}, 120) ASC"
        ),
        [cutover_dt],
    )

    select_cols = _select_columns(
        appt_id_col=appt_id_col,
        starts_col=starts_col,
        patient_col=patient_col,
        duration_col=duration_col,
        provider_col=provider_col,
        status_col=status_col,
        cancelled_col=cancelled_col,
        clinic_col=clinic_col,
        type_col=type_col,
        flag_col=flag_col,
    )

    samples: dict[str, list[dict[str, Any]]] = {
        "future_rows": _sample_rows(
            source,
            where_sql=f"{starts_col} >= ?",
            params=[cutover_dt],
            order_sql=f"{starts_col} ASC, {appt_id_col} ASC",
            limit=sample_limit,
            select_cols=select_cols,
        ),
    }
    if patient_col:
        samples["null_or_blank_patient_code_rows"] = _sample_rows(
            source,
            where_sql=_blank_predicate(patient_col),
            params=[],
            order_sql=f"{starts_col} ASC, {appt_id_col} ASC",
            limit=sample_limit,
            select_cols=select_cols,
        )
    else:
        samples["null_or_blank_patient_code_rows"] = []

    if cancelled_col or status_col:
        cancelled_predicates: list[str] = []
        if cancelled_col:
            cancelled_predicates.append(
                f"LOWER({_text_expr(cancelled_col)}) IN ('1', 'true', 'yes', 'y')"
            )
        if status_col:
            cancelled_predicates.append(f"LOWER({_text_expr(status_col)}) LIKE '%cancel%'")
        samples["cancelled_rows"] = _sample_rows(
            source,
            where_sql=" OR ".join(cancelled_predicates),
            params=[],
            order_sql=f"{starts_col} DESC, {appt_id_col} ASC",
            limit=sample_limit,
            select_cols=select_cols,
        )
    else:
        samples["cancelled_rows"] = []

    if status_col:
        status_expr = f"LOWER({_text_expr(status_col)})"
        placeholders = ", ".join("?" for _ in EXPECTED_STATUS_VALUES)
        samples["unusual_status_rows"] = _sample_rows(
            source,
            where_sql=(
                f"{status_col} IS NOT NULL AND {_text_expr(status_col)} <> '' "
                f"AND {status_expr} NOT IN ({placeholders})"
            ),
            params=sorted(EXPECTED_STATUS_VALUES),
            order_sql=f"{starts_col} DESC, {appt_id_col} ASC",
            limit=sample_limit,
            select_cols=select_cols,
        )
    else:
        samples["unusual_status_rows"] = []

    distributions = {
        "status": _distribution(source, column=status_col, top_limit=top_limit),
        "cancelled": _distribution(source, column=cancelled_col, top_limit=top_limit),
        "appt_flag": _distribution(source, column=flag_col, top_limit=top_limit),
        "clinician_code": _distribution(source, column=provider_col, top_limit=top_limit),
        "clinic_code": _distribution(source, column=clinic_col, top_limit=top_limit),
    }

    risk_flags = []
    if _to_int(base.get("future_count")):
        risk_flags.append("future appointments exist on or after the cutover date")
    if _to_int(base.get("null_blank_patient_code_count")):
        risk_flags.append("appointments with null/blank patient codes need an unlinkable policy")
    if distributions["status"]["distinct_count"] > 0:
        risk_flags.append("status values need deterministic PMS status mapping before promotion")
    if distributions["clinician_code"]["distinct_count"] > 0:
        risk_flags.append("clinician/provider codes need mapping before core diary promotion")
    if distributions["clinic_code"]["distinct_count"] > 0:
        risk_flags.append("clinic/room codes need mapping before core diary promotion")

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "sqlserver",
        "source_table": f"dbo.{SOURCE_TABLE}",
        "select_only": True,
        "cutover_date": cutover_date.isoformat(),
        "columns": {
            "appointment_id": appt_id_col,
            "starts_at": starts_col,
            "patient_code": patient_col,
            "duration_minutes": duration_col,
            "clinician_code": provider_col,
            "status": status_col,
            "cancelled": cancelled_col,
            "clinic_code": clinic_col,
            "appointment_type": type_col,
            "appt_flag": flag_col,
        },
        "counts": {
            "total_appointments": _to_int(base.get("total_count")),
            "past_appointments": _to_int(base.get("past_count")),
            "future_appointments": _to_int(base.get("future_count")),
            "null_start_count": _to_int(base.get("null_start_count")),
            "null_blank_patient_code_count": _to_int(
                base.get("null_blank_patient_code_count")
            ),
        },
        "date_range": {
            "min_start": _format_dt(base.get("min_start")),
            "max_start": _format_dt(base.get("max_start")),
        },
        "cutover_boundary": {
            "cutover_day_count": _to_int(base.get("cutover_day_count")),
            "seven_days_before_count": _to_int(base.get("seven_days_before_count")),
            "seven_days_after_count": _to_int(base.get("seven_days_after_count")),
        },
        "date_distribution": {
            "by_year": [
                {"year": row.get("year"), "count": _to_int(row.get("count"))}
                for row in by_year_rows
            ],
            "future_by_month": [
                {"month": row.get("month"), "count": _to_int(row.get("count"))}
                for row in future_by_month_rows
            ],
        },
        "distributions": distributions,
        "samples": samples,
        "risk_flags": risk_flags,
        "query_shape": {
            "table": f"FROM {SOURCE_SQL}",
            "query_types": [
                "aggregate counts/min/max",
                "date distribution by year",
                "future distribution by month",
                "top distributions by status/cancelled/appt_flag/clinician_code/clinic_code",
                "edge samples for future/null-patient/cancelled/unusual-status rows",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SELECT-only R4 appointment cutover inventory proof."
    )
    parser.add_argument(
        "--cutover-date",
        required=True,
        help="Cutover split date, YYYY-MM-DD. Rows before this date are past; rows on/after are future.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="Sample rows to include per edge-case bucket.",
    )
    parser.add_argument(
        "--top-limit",
        type=int,
        default=20,
        help="Top distribution buckets to include.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write inventory JSON.",
    )
    args = parser.parse_args()

    cutover_date = date.fromisoformat(args.cutover_date)
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
        cutover_date=cutover_date,
        sample_limit=args.sample_limit,
        top_limit=args.top_limit,
    )

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "output_json": str(output_path),
        "cutover_date": report["cutover_date"],
        "total_appointments": report["counts"]["total_appointments"],
        "past_appointments": report["counts"]["past_appointments"],
        "future_appointments": report["counts"]["future_appointments"],
        "null_blank_patient_code_count": report["counts"][
            "null_blank_patient_code_count"
        ],
        "date_range": report["date_range"],
        "status_top": report["distributions"]["status"]["top"][:5],
        "cancelled_top": report["distributions"]["cancelled"]["top"][:5],
        "risk_flags": report["risk_flags"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
