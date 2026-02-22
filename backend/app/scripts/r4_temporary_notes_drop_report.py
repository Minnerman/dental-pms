from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.services.r4_charting.canonical_importer import import_r4_charting_canonical_report
from app.services.r4_charting.sqlserver_extract import SqlServerChartingExtractor
from app.services.r4_charting.temporary_notes_import import (
    filter_temporary_notes,
    temporary_note_source_id,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource

_DOMAIN_NAMES = ("temporary_note", "temporary_notes")


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def _in_date_window(value: datetime | None, start: date | None, end: date | None) -> bool:
    if start is None and end is None:
        return True
    if value is None:
        return False
    day = value.date()
    if start and day < start:
        return False
    if end and day >= end:
        return False
    return True


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _normalize_note(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _latest_sort_key(row: dict[str, object]) -> tuple[str, int, str]:
    return (
        str(row.get("recorded_at") or ""),
        int(row.get("source_row_id") or 0),
        str(row.get("source_id") or ""),
    )


def _latest_row(rows: list[dict[str, object]]) -> dict[str, object] | None:
    if not rows:
        return None
    return max(rows, key=_latest_sort_key)


def _latest_key(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "recorded_at": row.get("recorded_at"),
        "source_id": row.get("source_id"),
        "source_row_id": row.get("source_row_id"),
    }


def _latest_digest(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "note_body": row.get("note_body"),
        "user_code": row.get("user_code"),
    }


def _int_only(payload: dict[str, object] | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(payload, dict):
        return out
    for key, value in payload.items():
        if isinstance(value, int):
            out[key] = value
    return out


def _sqlserver_filtered_rows(
    source: R4SqlServerSource,
    *,
    patient_code: int,
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
) -> tuple[list[dict[str, object]], dict[str, int], int]:
    candidates = list(
        source.list_temporary_notes(
            patients_from=patient_code,
            patients_to=patient_code,
            limit=row_limit,
        )
    )
    accepted, drop_report = filter_temporary_notes(
        candidates,
        date_from=date_from,
        date_to=date_to,
    )
    rows: list[dict[str, object]] = []
    for item in accepted:
        rows.append(
            {
                "recorded_at": _iso(item.legacy_updated_at),
                "source_id": temporary_note_source_id(item),
                "source_row_id": item.source_row_id,
                "note_body": _normalize_note(item.note),
                "user_code": item.user_code,
            }
        )
    return rows, drop_report.as_dict(), len(candidates)


def _postgres_rows(
    session: Session,
    *,
    patient_code: int,
    date_from: date | None,
    date_to: date | None,
) -> list[dict[str, object]]:
    stmt = (
        select(R4ChartingCanonicalRecord)
        .where(
            R4ChartingCanonicalRecord.legacy_patient_code == patient_code,
            R4ChartingCanonicalRecord.domain.in_(_DOMAIN_NAMES),
        )
        .order_by(
            R4ChartingCanonicalRecord.recorded_at.desc(),
            R4ChartingCanonicalRecord.r4_source_id.desc(),
        )
    )
    rows: list[dict[str, object]] = []
    for record in session.execute(stmt).scalars().all():
        if not _in_date_window(record.recorded_at, date_from, date_to):
            continue
        payload = record.payload if isinstance(record.payload, dict) else {}
        rows.append(
            {
                "recorded_at": _iso(record.recorded_at),
                "source_id": record.r4_source_id,
                "source_row_id": payload.get("source_row_id"),
                "note_body": _normalize_note(payload.get("note")),
                "user_code": payload.get("user_code"),
            }
        )
    return rows


def build_drop_report(
    session: Session,
    *,
    patient_code: int,
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
) -> dict[str, object]:
    cfg = R4SqlServerConfig.from_env()
    cfg.require_enabled()
    cfg.require_readonly()
    source = R4SqlServerSource(cfg)
    source.ensure_select_only()

    sql_rows, sql_dropped_reasons, sql_candidates_total = _sqlserver_filtered_rows(
        source,
        patient_code=patient_code,
        date_from=date_from,
        date_to=date_to,
        row_limit=row_limit,
    )

    extractor = SqlServerChartingExtractor(cfg)
    _, canonical_report = import_r4_charting_canonical_report(
        session,
        extractor,
        patient_codes=[patient_code],
        date_from=date_from,
        date_to=date_to,
        domains=["temporary_notes"],
        limit=row_limit,
        dry_run=True,
    )
    dropped = _int_only(canonical_report.get("dropped") if isinstance(canonical_report, dict) else None)

    pg_rows = _postgres_rows(
        session,
        patient_code=patient_code,
        date_from=date_from,
        date_to=date_to,
    )

    sql_latest = _latest_row(sql_rows)
    pg_latest = _latest_row(pg_rows)
    importer_candidates = int(canonical_report.get("total_records") or 0)
    return {
        "patient_code": patient_code,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "sql_count": len(sql_rows),
        "pg_count": len(pg_rows),
        "delta_sql_minus_pg": len(sql_rows) - len(pg_rows),
        "sql_candidates_total": sql_candidates_total,
        "canonical_dry_run_candidates": importer_candidates,
        "delta_candidates_minus_pg": importer_candidates - len(pg_rows),
        "sql_dropped_reasons": sql_dropped_reasons,
        "dropped_reasons": dropped,
        "sql_latest_key": _latest_key(sql_latest),
        "pg_latest_key": _latest_key(pg_latest),
        "latest_match": _latest_key(sql_latest) == _latest_key(pg_latest),
        "sql_latest_digest": _latest_digest(sql_latest),
        "pg_latest_digest": _latest_digest(pg_latest),
        "latest_digest_match": _latest_digest(sql_latest) == _latest_digest(pg_latest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explain temporary_notes SQL vs Postgres gaps for one patient."
    )
    parser.add_argument("--patient-code", type=int, required=True)
    parser.add_argument("--date-from", type=str, default=None)
    parser.add_argument("--date-to", type=str, default=None)
    parser.add_argument("--row-limit", type=int, default=50000)
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args()

    date_from = _parse_day(args.date_from)
    date_to = _parse_day(args.date_to)
    with SessionLocal() as session:
        payload = build_drop_report(
            session,
            patient_code=int(args.patient_code),
            date_from=date_from,
            date_to=date_to,
            row_limit=max(1, int(args.row_limit)),
        )

    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
