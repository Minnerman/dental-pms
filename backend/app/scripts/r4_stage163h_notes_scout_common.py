from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from math import ceil
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from app.services.r4_charting.temporary_notes_import import (
    TemporaryNoteDropReport,
    filter_temporary_notes,
    temporary_note_text,
)
from app.services.r4_import.sqlserver_source import R4SqlServerSource
from app.services.r4_import.types import R4TemporaryNote


@dataclass(frozen=True)
class Stage163HRawNoteRow:
    patient_code: int | None
    source_row_id: int | None
    legacy_updated_at: datetime | None
    note: str | None


def _to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _stable_hash_key(patient_code: int, *, seed: int) -> int:
    payload = f"{seed}:{patient_code}".encode("ascii")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def _select_codes_hashed(codes: set[int], *, seed: int, limit: int | None = None) -> list[int]:
    ordered = sorted(codes, key=lambda code: (_stable_hash_key(code, seed=seed), code))
    if limit is None:
        return ordered
    return ordered[:limit]


def _is_in_window(value: datetime | None, *, date_from: date, date_to: date) -> bool:
    if value is None:
        return False
    day = value.date()
    return date_from <= day < date_to


def _note_length(item: R4TemporaryNote) -> int:
    text = temporary_note_text(item)
    if text is None:
        return 0
    return len(text)


def _to_temp_note(row: Stage163HRawNoteRow) -> R4TemporaryNote:
    return R4TemporaryNote(
        patient_code=row.patient_code,
        source_row_id=row.source_row_id,
        note=row.note,
        legacy_updated_at=row.legacy_updated_at,
        user_code=None,
    )


def query_note_rows(
    source: R4SqlServerSource,
    *,
    table: str,
    patient_col_candidates: list[str],
    date_col_candidates: list[str],
    note_col_candidates: list[str],
    row_id_col_candidates: list[str],
) -> tuple[list[Stage163HRawNoteRow], dict[str, Any]]:
    patient_col = source._require_column(table, patient_col_candidates)  # noqa: SLF001
    date_col = source._pick_column(table, date_col_candidates)  # noqa: SLF001
    note_col = source._pick_column(table, note_col_candidates)  # noqa: SLF001
    if note_col is None:
        raise RuntimeError(
            f"{table} missing note text column (tried: {', '.join(note_col_candidates)})."
        )
    row_id_col = source._pick_column(table, row_id_col_candidates)  # noqa: SLF001

    select_cols = [f"{patient_col} AS patient_code"]
    if row_id_col:
        select_cols.append(f"{row_id_col} AS source_row_id")
    else:
        select_cols.append("NULL AS source_row_id")
    if date_col:
        select_cols.append(f"{date_col} AS legacy_updated_at")
    else:
        select_cols.append("NULL AS legacy_updated_at")
    select_cols.append(f"{note_col} AS note")

    order_cols = [patient_col]
    if date_col:
        order_cols.append(date_col)
    if row_id_col:
        order_cols.append(row_id_col)
    order_sql = ", ".join(f"{col} ASC" for col in order_cols)

    rows = source._query(  # noqa: SLF001
        f"SELECT {', '.join(select_cols)} FROM dbo.{table} WITH (NOLOCK) ORDER BY {order_sql}"
    )

    out: list[Stage163HRawNoteRow] = []
    for row in rows:
        out.append(
            Stage163HRawNoteRow(
                patient_code=_to_int_or_none(row.get("patient_code")),
                source_row_id=_to_int_or_none(row.get("source_row_id")),
                legacy_updated_at=row.get("legacy_updated_at"),
                note=(row.get("note") or "").strip() or None,
            )
        )

    return out, {
        "table": f"dbo.{table}",
        "patient_column": patient_col,
        "date_column": date_col,
        "note_column": note_col,
        "row_id_column": row_id_col,
        "query_order": order_cols,
    }


def _percent(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def _drop_report_dict(report: TemporaryNoteDropReport) -> dict[str, int]:
    return report.as_dict()


def _compact_drop_reasons(report: TemporaryNoteDropReport) -> dict[str, int]:
    data = report.as_dict()
    out: dict[str, int] = {}
    for key in ("missing_patient_code", "missing_date", "out_of_window", "blank_note", "duplicate_key"):
        value = int(data.get(key, 0))
        if value:
            out[key] = value
    included = int(data.get("included", 0))
    if included:
        out["included"] = included
    return out


def _quality_counters(report: TemporaryNoteDropReport) -> dict[str, int]:
    data = report.as_dict()
    out: dict[str, int] = {}
    for key in ("accepted_nonblank_note", "accepted_blank_note"):
        value = int(data.get(key, 0))
        if value:
            out[key] = value
    return out


def _note_length_summary(items: Iterable[R4TemporaryNote]) -> dict[str, int | float] | None:
    lengths = sorted(_note_length(item) for item in items if _note_length(item) > 0)
    if not lengths:
        return None
    p90_index = min(len(lengths) - 1, max(0, ceil(len(lengths) * 0.90) - 1))
    return {
        "min": lengths[0],
        "median": float(median(lengths)),
        "p90": lengths[p90_index],
        "max": lengths[-1],
    }


def _build_proof_patients(
    accepted_rows: list[R4TemporaryNote],
    *,
    seed: int,
    domain: str,
    source_table: str,
    proof_limit: int = 5,
) -> dict[str, Any]:
    grouped: dict[int, dict[str, Any]] = {}
    for item in accepted_rows:
        if item.patient_code is None:
            continue
        patient_code = int(item.patient_code)
        note_len = _note_length(item)
        group = grouped.setdefault(
            patient_code,
            {
                "row_count": 0,
                "max_note_length": 0,
                "latest_legacy_updated_at": None,
            },
        )
        group["row_count"] += 1
        if note_len > int(group["max_note_length"]):
            group["max_note_length"] = note_len
        ts = item.legacy_updated_at
        if ts is not None:
            current = group["latest_legacy_updated_at"]
            if current is None or ts > current:
                group["latest_legacy_updated_at"] = ts

    ranked = sorted(
        grouped.items(),
        key=lambda item: (
            -int(item[1]["max_note_length"]),
            -int(item[1]["row_count"]),
            _stable_hash_key(item[0], seed=seed),
            item[0],
        ),
    )[:proof_limit]

    return {
        "domain": domain,
        "source_table": source_table,
        "selection": (
            "stage163h scout proof set from accepted in-window nonblank rows "
            f"(top note_length, hashed tie-break seed {seed})"
        ),
        "patients": [
            {
                "patient_id": None,
                "legacy_patient_code": patient_code,
                "row_count": int(meta["row_count"]),
                "max_note_length": int(meta["max_note_length"]),
                "note_blank": False,
                "legacy_updated_at": (
                    meta["latest_legacy_updated_at"].isoformat()
                    if meta["latest_legacy_updated_at"] is not None
                    else None
                ),
            }
            for patient_code, meta in ranked
        ],
    }


def build_inventory_bundle(
    *,
    domain: str,
    source_table: str,
    rows: list[Stage163HRawNoteRow],
    column_metadata: dict[str, Any],
    date_from: date,
    date_to: date,
    seed: int,
    cohort_limit: int,
    recommended_seen_ledger: str,
) -> dict[str, Any]:
    raw_notes = [_to_temp_note(row) for row in rows]
    accepted_rows, drop_report = filter_temporary_notes(raw_notes, date_from=date_from, date_to=date_to)

    raw_patients = {int(item.patient_code) for item in raw_notes if item.patient_code is not None}
    rows_with_date = [item for item in raw_notes if item.legacy_updated_at is not None]
    in_window_rows = [item for item in raw_notes if _is_in_window(item.legacy_updated_at, date_from=date_from, date_to=date_to)]
    in_window_patients = {
        int(item.patient_code)
        for item in in_window_rows
        if item.patient_code is not None
    }
    in_window_nonblank_rows = [item for item in in_window_rows if temporary_note_text(item) is not None]
    in_window_blank_rows = [item for item in in_window_rows if temporary_note_text(item) is None]
    accepted_patients = {int(item.patient_code) for item in accepted_rows if item.patient_code is not None}

    ordered_full_pool_codes = _select_codes_hashed(accepted_patients, seed=seed, limit=None)
    selected_codes = ordered_full_pool_codes[:cohort_limit]

    drop_dict = _drop_report_dict(drop_report)
    quality_dict = _quality_counters(drop_report)
    dropped_total = sum(
        int(drop_dict.get(key, 0))
        for key in ("missing_patient_code", "missing_date", "out_of_window", "blank_note", "duplicate_key")
    )

    inventory_json = {
        "domain": domain,
        "source_table": source_table,
        "source_columns": column_metadata,
        "window": {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
        "selection": {
            "order": "hashed",
            "seed": seed,
            "cohort_limit": cohort_limit,
            "selected_count": len(selected_codes),
            "selected_patient_codes": selected_codes,
        },
        "summary": {
            "rows_total": len(raw_notes),
            "patients_total": len(raw_patients),
            "rows_with_date": len(rows_with_date),
            "rows_in_window": len(in_window_rows),
            "patients_in_window": len(in_window_patients),
            "nonblank_rows_in_window": len(in_window_nonblank_rows),
            "blank_rows_in_window": len(in_window_blank_rows),
            "nonblank_pct_in_window": _percent(len(in_window_nonblank_rows), len(in_window_rows)),
            "accepted_rows": len(accepted_rows),
            "accepted_patients": len(accepted_patients),
            "recommended_chunk_size": 200,
            "estimated_chunks": ceil(len(accepted_patients) / 200) if accepted_patients else 0,
            "recommended_seen_ledger": recommended_seen_ledger,
        },
        "drop_reasons_skeleton": _compact_drop_reasons(drop_report),
        "quality_counters": quality_dict,
        "proof_patients": [p["legacy_patient_code"] for p in _build_proof_patients(
            accepted_rows,
            seed=seed,
            domain=domain,
            source_table=source_table,
        )["patients"]],
        "accepted_note_length": _note_length_summary(accepted_rows),
    }

    drop_skeleton_json = {
        "domain": domain,
        "source_table": source_table,
        "window": {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
        "rows_total": len(raw_notes),
        "patients_total": len(raw_patients),
        "rows_in_window": len(in_window_rows),
        "patients_in_window": len(in_window_patients),
        "accepted_rows": len(accepted_rows),
        "accepted_patients": len(accepted_patients),
        "drop_reasons_skeleton": _compact_drop_reasons(drop_report),
        "quality_counters": quality_dict,
        "dropped_total_excluding_non_drop_counters": dropped_total,
        "top_drops": Counter(
            {
                k: v
                for k, v in _compact_drop_reasons(drop_report).items()
                if k != "included"
            }
        ).most_common(),
    }

    proof_json = _build_proof_patients(
        accepted_rows,
        seed=seed,
        domain=domain,
        source_table=source_table,
    )

    return {
        "inventory_json": inventory_json,
        "drop_skeleton_json": drop_skeleton_json,
        "proof_patients_json": proof_json,
        "full_pool_codes": ordered_full_pool_codes,
        "cohort_codes": selected_codes,
    }


def write_standard_outputs(
    *,
    output_dir: Path,
    filename_prefix: str,
    bundle: dict[str, Any],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory_path = output_dir / f"{filename_prefix}_inventory.json"
    full_pool_csv_path = output_dir / f"{filename_prefix}_full_pool.csv"
    cohort_csv_path = output_dir / f"{filename_prefix}_cohort.csv"
    drop_path = output_dir / f"{filename_prefix}_drop_skeleton.json"
    proof_path = output_dir / f"{filename_prefix}_proof_patients.json"

    inventory_path.write_text(json.dumps(bundle["inventory_json"], indent=2), encoding="utf-8")
    drop_path.write_text(json.dumps(bundle["drop_skeleton_json"], indent=2), encoding="utf-8")
    proof_path.write_text(json.dumps(bundle["proof_patients_json"], indent=2), encoding="utf-8")

    for path, codes in (
        (full_pool_csv_path, bundle["full_pool_codes"]),
        (cohort_csv_path, bundle["cohort_codes"]),
    ):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["patient_code"])
            for code in codes:
                writer.writerow([code])

    return {
        "inventory_json": str(inventory_path),
        "full_pool_csv": str(full_pool_csv_path),
        "cohort_csv": str(cohort_csv_path),
        "drop_skeleton_json": str(drop_path),
        "proof_patients_json": str(proof_path),
    }

