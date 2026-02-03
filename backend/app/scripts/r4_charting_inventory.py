from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


DATE_CANDIDATES = [
    "Date",
    "NoteDate",
    "DateAdded",
    "DateCreated",
    "DateCompleted",
    "DateAccepted",
    "EntryDate",
    "RecordedDate",
    "CreatedDate",
    "CreatedOn",
]


@dataclass
class TableSpec:
    name: str
    patient_cols: list[str]
    date_cols: list[str]


DIRECT_TABLE_SPECS = [
    TableSpec("ChartHealingActions", ["PatientCode"], DATE_CANDIDATES),
    TableSpec("TreatmentPlans", ["PatientCode"], DATE_CANDIDATES),
    TableSpec("TreatmentPlanItems", ["PatientCode"], DATE_CANDIDATES),
    TableSpec("TreatmentPlanReviews", ["PatientCode"], DATE_CANDIDATES),
    TableSpec("BPE", ["PatientCode"], DATE_CANDIDATES),
    TableSpec("PatientNotes", ["PatientCode"], DATE_CANDIDATES),
    TableSpec("TreatmentNotes", ["PatientCode"], DATE_CANDIDATES),
    TableSpec("OldPatientNotes", ["PatientCode"], DATE_CANDIDATES),
    TableSpec("TemporaryNotes", ["PatientCode"], DATE_CANDIDATES),
]


def _to_int(value: Any | None) -> int:
    if value is None:
        return 0
    return int(value)


def _direct_table_inventory(
    source: R4SqlServerSource,
    *,
    spec: TableSpec,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    columns = source._get_columns(spec.name)  # noqa: SLF001
    if not columns:
        return {"table": spec.name, "status": "missing"}

    patient_col = source._pick_column(spec.name, spec.patient_cols)  # noqa: SLF001
    date_col = source._pick_column(spec.name, spec.date_cols)  # noqa: SLF001
    out: dict[str, Any] = {
        "table": spec.name,
        "status": "ok",
        "patient_col": patient_col,
        "date_col": date_col,
        "columns": columns,
    }

    if patient_col and date_col:
        rows = source._query(  # noqa: SLF001
            (
                "SELECT "
                "COUNT(1) AS total_rows, "
                f"SUM(CASE WHEN {date_col} >= ? AND {date_col} < ? THEN 1 ELSE 0 END) AS rows_in_window, "
                f"SUM(CASE WHEN {date_col} IS NULL THEN 1 ELSE 0 END) AS null_date_rows, "
                f"COUNT(DISTINCT CASE WHEN {patient_col} IS NOT NULL THEN {patient_col} END) AS patients_total, "
                f"COUNT(DISTINCT CASE WHEN {patient_col} IS NOT NULL AND {date_col} >= ? AND {date_col} < ? THEN {patient_col} END) AS patients_in_window "
                f"FROM dbo.{spec.name} WITH (NOLOCK)"
            ),
            [date_from, date_to, date_from, date_to],
        )
        row = rows[0] if rows else {}
        out.update(
            {
                "total_rows": _to_int(row.get("total_rows")),
                "rows_in_window": _to_int(row.get("rows_in_window")),
                "null_date_rows": _to_int(row.get("null_date_rows")),
                "patients_total": _to_int(row.get("patients_total")),
                "patients_in_window": _to_int(row.get("patients_in_window")),
            }
        )
        return out

    if patient_col:
        rows = source._query(  # noqa: SLF001
            (
                "SELECT "
                "COUNT(1) AS total_rows, "
                f"COUNT(DISTINCT CASE WHEN {patient_col} IS NOT NULL THEN {patient_col} END) AS patients_total "
                f"FROM dbo.{spec.name} WITH (NOLOCK)"
            )
        )
        row = rows[0] if rows else {}
        out.update(
            {
                "total_rows": _to_int(row.get("total_rows")),
                "patients_total": _to_int(row.get("patients_total")),
            }
        )
        return out

    rows = source._query(  # noqa: SLF001
        f"SELECT COUNT(1) AS total_rows FROM dbo.{spec.name} WITH (NOLOCK)"
    )
    row = rows[0] if rows else {}
    out.update({"total_rows": _to_int(row.get("total_rows"))})
    return out


def _perio_probe_linked_inventory(
    source: R4SqlServerSource,
    *,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    pp_trans_col = source._pick_column("PerioProbe", ["TransId", "TransID"])  # noqa: SLF001
    tx_ref_col = source._pick_column("Transactions", ["RefId", "RefID"])  # noqa: SLF001
    tx_patient_col = source._pick_column("Transactions", ["PatientCode"])  # noqa: SLF001
    tx_date_col = source._pick_column("Transactions", DATE_CANDIDATES)  # noqa: SLF001
    if not (pp_trans_col and tx_ref_col and tx_patient_col):
        return {"table": "PerioProbe(linked)", "status": "unsupported"}

    if tx_date_col:
        rows = source._query(  # noqa: SLF001
            (
                "SELECT "
                "COUNT(1) AS total_rows, "
                f"SUM(CASE WHEN t.{tx_ref_col} IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_transaction, "
                f"SUM(CASE WHEN t.{tx_patient_col} IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_patient, "
                f"SUM(CASE WHEN t.{tx_date_col} >= ? AND t.{tx_date_col} < ? THEN 1 ELSE 0 END) AS rows_in_window, "
                f"COUNT(DISTINCT CASE WHEN t.{tx_patient_col} IS NOT NULL THEN t.{tx_patient_col} END) AS patients_total, "
                f"COUNT(DISTINCT CASE WHEN t.{tx_patient_col} IS NOT NULL AND t.{tx_date_col} >= ? AND t.{tx_date_col} < ? THEN t.{tx_patient_col} END) AS patients_in_window "
                "FROM dbo.PerioProbe pp WITH (NOLOCK) "
                f"LEFT JOIN dbo.Transactions t WITH (NOLOCK) ON t.{tx_ref_col} = pp.{pp_trans_col}"
            ),
            [date_from, date_to, date_from, date_to],
        )
    else:
        rows = source._query(  # noqa: SLF001
            (
                "SELECT "
                "COUNT(1) AS total_rows, "
                f"SUM(CASE WHEN t.{tx_ref_col} IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_transaction, "
                f"SUM(CASE WHEN t.{tx_patient_col} IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_patient, "
                f"COUNT(DISTINCT CASE WHEN t.{tx_patient_col} IS NOT NULL THEN t.{tx_patient_col} END) AS patients_total "
                "FROM dbo.PerioProbe pp WITH (NOLOCK) "
                f"LEFT JOIN dbo.Transactions t WITH (NOLOCK) ON t.{tx_ref_col} = pp.{pp_trans_col}"
            )
        )
    row = rows[0] if rows else {}
    out = {
        "table": "PerioProbe(linked)",
        "status": "ok",
        "patient_col": f"Transactions.{tx_patient_col}",
        "date_col": f"Transactions.{tx_date_col}" if tx_date_col else None,
        "total_rows": _to_int(row.get("total_rows")),
        "rows_with_transaction": _to_int(row.get("rows_with_transaction")),
        "rows_with_patient": _to_int(row.get("rows_with_patient")),
        "patients_total": _to_int(row.get("patients_total")),
    }
    if tx_date_col:
        out["rows_in_window"] = _to_int(row.get("rows_in_window"))
        out["patients_in_window"] = _to_int(row.get("patients_in_window"))
    return out


def _bpe_furcation_linked_inventory(
    source: R4SqlServerSource,
    *,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    bpe_id_col = source._pick_column("BPE", ["BPEID", "BPEId", "ID", "RefId", "RefID"])  # noqa: SLF001
    bpe_patient_col = source._pick_column("BPE", ["PatientCode"])  # noqa: SLF001
    bpe_date_col = source._pick_column("BPE", DATE_CANDIDATES)  # noqa: SLF001
    fur_bpe_id_col = source._pick_column("BPEFurcation", ["BPEID", "BPEId"])  # noqa: SLF001
    if not (bpe_id_col and bpe_patient_col and bpe_date_col and fur_bpe_id_col):
        return {"table": "BPEFurcation(linked)", "status": "unsupported"}

    rows = source._query(  # noqa: SLF001
        (
            "SELECT "
            "COUNT(1) AS total_rows, "
            f"SUM(CASE WHEN b.{bpe_patient_col} IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_patient, "
            f"SUM(CASE WHEN b.{bpe_date_col} >= ? AND b.{bpe_date_col} < ? THEN 1 ELSE 0 END) AS rows_in_window, "
            f"COUNT(DISTINCT CASE WHEN b.{bpe_patient_col} IS NOT NULL THEN b.{bpe_patient_col} END) AS patients_total, "
            f"COUNT(DISTINCT CASE WHEN b.{bpe_patient_col} IS NOT NULL AND b.{bpe_date_col} >= ? AND b.{bpe_date_col} < ? THEN b.{bpe_patient_col} END) AS patients_in_window "
            "FROM dbo.BPEFurcation bf WITH (NOLOCK) "
            "LEFT JOIN dbo.BPE b WITH (NOLOCK) "
            f"ON bf.{fur_bpe_id_col} = b.{bpe_id_col}"
        ),
        [date_from, date_to, date_from, date_to],
    )
    row = rows[0] if rows else {}
    return {
        "table": "BPEFurcation(linked)",
        "status": "ok",
        "patient_col": f"BPE.{bpe_patient_col}",
        "date_col": f"BPE.{bpe_date_col}",
        "total_rows": _to_int(row.get("total_rows")),
        "rows_with_patient": _to_int(row.get("rows_with_patient")),
        "rows_in_window": _to_int(row.get("rows_in_window")),
        "patients_total": _to_int(row.get("patients_total")),
        "patients_in_window": _to_int(row.get("patients_in_window")),
    }


def run_inventory(*, date_from: date, date_to: date) -> dict[str, Any]:
    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    direct = [
        _direct_table_inventory(source, spec=spec, date_from=date_from, date_to=date_to)
        for spec in DIRECT_TABLE_SPECS
    ]
    linked = [
        _perio_probe_linked_inventory(source, date_from=date_from, date_to=date_to),
        _bpe_furcation_linked_inventory(source, date_from=date_from, date_to=date_to),
    ]

    ranked_candidates: list[dict[str, Any]] = []
    for row in [*direct, *linked]:
        patients_in_window = row.get("patients_in_window")
        if isinstance(patients_in_window, int) and patients_in_window > 0:
            ranked_candidates.append(
                {
                    "table": row["table"],
                    "patients_in_window": patients_in_window,
                    "rows_in_window": row.get("rows_in_window", 0),
                    "date_col": row.get("date_col"),
                    "patient_col": row.get("patient_col"),
                }
            )
    ranked_candidates.sort(
        key=lambda item: (item["patients_in_window"], item["rows_in_window"]),
        reverse=True,
    )

    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "direct_tables": direct,
        "linked_tables": linked,
        "ranked_candidates": ranked_candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Stage 132 inventory for charting-related R4 tables."
    )
    parser.add_argument("--date-from", required=True, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", required=True, help="Exclusive end date (YYYY-MM-DD).")
    parser.add_argument("--output-json", required=True, help="Path to write inventory JSON.")
    args = parser.parse_args()

    date_from = date.fromisoformat(args.date_from)
    date_to = date.fromisoformat(args.date_to)
    if date_to <= date_from:
        raise RuntimeError("--date-to must be after --date-from.")

    report = run_inventory(date_from=date_from, date_to=date_to)
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
