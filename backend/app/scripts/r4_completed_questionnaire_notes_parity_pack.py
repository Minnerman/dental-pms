from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.services.r4_charting.completed_questionnaire_notes_import import (
    completed_questionnaire_note_source_id,
    filter_completed_questionnaire_notes,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource

_DOMAIN_NAMES = ("completed_questionnaire_note", "completed_questionnaire_notes")


def _parse_patient_codes_csv(raw: str) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for token in raw.split(","):
        part = token.strip()
        if not part:
            raise RuntimeError("Invalid --patient-codes value: empty token.")
        try:
            code = int(part)
        except ValueError as exc:
            raise RuntimeError(f"Invalid patient code: {part}") from exc
        if code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


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


def _latest_sort_tuple(row: dict[str, object]) -> tuple[str, int, str]:
    return (
        str(row.get("recorded_at") or ""),
        int(row.get("source_row_id") or 0),
        str(row.get("source_id") or ""),
    )


def _unique_key(row: dict[str, object]) -> str:
    return str(row.get("source_id") or "")


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
    }


def _canonical_rows(
    session: Session,
    patient_code: int,
    *,
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
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
        .limit(row_limit)
    )
    rows: list[dict[str, object]] = []
    for record in session.execute(stmt).scalars().all():
        if not _in_date_window(record.recorded_at, date_from, date_to):
            continue
        payload = record.payload if isinstance(record.payload, dict) else {}
        rows.append(
            {
                "patient_code": payload.get("patient_code", record.legacy_patient_code),
                "recorded_at": _iso(record.recorded_at),
                "source_id": record.r4_source_id,
                "source_row_id": payload.get("source_row_id"),
                "note_body": _normalize_note(payload.get("note")),
            }
        )
    return rows


def _sqlserver_rows(
    source: R4SqlServerSource,
    patient_code: int,
    *,
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
) -> tuple[list[dict[str, object]], dict[str, int], int]:
    candidates = list(
        source.list_completed_questionnaire_notes(
            patients_from=patient_code,
            patients_to=patient_code,
            limit=row_limit,
        )
    )
    accepted, dropped = filter_completed_questionnaire_notes(
        candidates,
        date_from=date_from,
        date_to=date_to,
    )
    rows: list[dict[str, object]] = []
    for item in accepted:
        rows.append(
            {
                "patient_code": item.patient_code,
                "recorded_at": _iso(item.completed_at),
                "source_id": completed_questionnaire_note_source_id(item),
                "source_row_id": item.source_row_id,
                "note_body": _normalize_note(item.note),
            }
        )
    return rows, dropped.as_dict(), len(candidates)


def _latest_row(rows: list[dict[str, object]]) -> dict[str, object] | None:
    if not rows:
        return None
    return max(rows, key=_latest_sort_tuple)


def build_parity_report(
    session: Session,
    *,
    patient_codes: list[int],
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
    include_sqlserver: bool,
) -> dict[str, object]:
    sql_source: R4SqlServerSource | None = None
    if include_sqlserver:
        cfg = R4SqlServerConfig.from_env()
        cfg.require_enabled()
        cfg.require_readonly()
        sql_source = R4SqlServerSource(cfg)
        sql_source.ensure_select_only()

    patients: list[dict[str, object]] = []
    for code in patient_codes:
        canonical_rows = _canonical_rows(
            session,
            code,
            date_from=date_from,
            date_to=date_to,
            row_limit=row_limit,
        )
        sql_rows: list[dict[str, object]] = []
        sql_dropped: dict[str, int] = {}
        sql_candidates_total: int | None = None
        if sql_source is not None:
            sql_rows, sql_dropped, sql_candidates_total = _sqlserver_rows(
                sql_source,
                code,
                date_from=date_from,
                date_to=date_to,
                row_limit=row_limit,
            )

        canonical_latest = _latest_row(canonical_rows)
        sql_latest = _latest_row(sql_rows) if sql_source is not None else None
        canonical_latest_key = _latest_key(canonical_latest)
        sql_latest_key = _latest_key(sql_latest)
        canonical_digest = _latest_digest(canonical_latest)
        sql_digest = _latest_digest(sql_latest)
        if sql_source is None or not sql_rows:
            latest_match: bool | None = None
            digest_match: bool | None = None
        else:
            latest_match = canonical_latest_key == sql_latest_key
            digest_match = canonical_digest == sql_digest

        patients.append(
            {
                "patient_code": code,
                "canonical_total_rows": len(canonical_rows),
                "canonical_distinct_unique_keys": len({_unique_key(r) for r in canonical_rows}),
                "sqlserver_total_rows": len(sql_rows) if sql_source is not None else None,
                "sqlserver_candidates_total": sql_candidates_total if sql_source is not None else None,
                "sqlserver_dropped_reasons": sql_dropped if sql_source is not None else None,
                "sqlserver_distinct_unique_keys": len({_unique_key(r) for r in sql_rows})
                if sql_source is not None
                else None,
                "canonical_latest_key": canonical_latest_key,
                "sqlserver_latest_key": sql_latest_key,
                "latest_match": latest_match,
                "canonical_latest_digest": canonical_digest,
                "sqlserver_latest_digest": sql_digest if sql_source is not None else None,
                "latest_digest_match": digest_match,
            }
        )

    patients_with_data = sum(
        1
        for patient in patients
        if isinstance(patient.get("sqlserver_total_rows"), int)
        and int(patient.get("sqlserver_total_rows") or 0) > 0
    )
    patients_no_data = len(patients) - patients_with_data

    latest_compared = [
        bool(patient["latest_match"])
        for patient in patients
        if isinstance(patient.get("latest_match"), bool)
    ]
    digest_compared = [
        bool(patient["latest_digest_match"])
        for patient in patients
        if isinstance(patient.get("latest_digest_match"), bool)
    ]
    latest_matched = sum(1 for value in latest_compared if value)
    digest_matched = sum(1 for value in digest_compared if value)

    overall_status = "pass"
    if latest_compared and latest_matched != len(latest_compared):
        overall_status = "fail"
    if digest_compared and digest_matched != len(digest_compared):
        overall_status = "fail"

    return {
        "patients": patients,
        "patients_with_data": patients_with_data,
        "patients_no_data": patients_no_data,
        "overall": {
            "status": overall_status,
            "latest_match": {
                "matched": latest_matched,
                "compared": len(latest_compared),
            },
            "latest_digest_match": {
                "matched": digest_matched,
                "compared": len(digest_compared),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a completed_questionnaire_notes parity pack from canonical data and SQL Server."
        )
    )
    parser.add_argument("--patient-codes", required=True, help="Comma-separated patient codes.")
    parser.add_argument("--date-from", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", help="Exclusive end date (YYYY-MM-DD).")
    parser.add_argument("--row-limit", type=int, default=1000)
    parser.add_argument("--output", required=True, help="Path to write JSON report.")
    args = parser.parse_args()

    patient_codes = _parse_patient_codes_csv(args.patient_codes)
    date_from = _parse_day(args.date_from)
    date_to = _parse_day(args.date_to)

    with SessionLocal() as session:
        payload = build_parity_report(
            session,
            patient_codes=patient_codes,
            date_from=date_from,
            date_to=date_to,
            row_limit=args.row_limit,
            include_sqlserver=True,
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
