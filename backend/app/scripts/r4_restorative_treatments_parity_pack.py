from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


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


def _in_date_window(value: datetime | None, start: date | None, end: date | None) -> bool:
    if start is None and end is None:
        return True
    if value is None:
        return False
    day = value.date()
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True


def _latest_sort_tuple(row: dict[str, object]) -> tuple[str, int, int, int, int, int]:
    return (
        str(row.get("recorded_at") or ""),
        int(row.get("ref_id") or 0),
        int(row.get("tp_item_key") or 0),
        int(row.get("trans_code") or 0),
        int(row.get("tooth") or 0),
        int(row.get("surface") or 0),
    )


def _unique_key(row: dict[str, object]) -> str:
    ref_id = row.get("ref_id")
    if ref_id is not None:
        return f"ref:{ref_id}"
    tp_item_key = row.get("tp_item_key")
    if tp_item_key is not None:
        return f"tpitem:{tp_item_key}"
    return ":".join(
        [
            str(row.get("patient_code") or ""),
            str(row.get("recorded_at") or ""),
            str(row.get("code_id") or ""),
            str(row.get("tooth") or ""),
            str(row.get("surface") or ""),
            str(row.get("status_description") or ""),
        ]
    )


def _latest_key(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "recorded_at": row.get("recorded_at"),
        "ref_id": row.get("ref_id"),
        "tp_item_key": row.get("tp_item_key"),
        "trans_code": row.get("trans_code"),
        "tooth": row.get("tooth"),
        "surface": row.get("surface"),
    }


def _latest_digest(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "code_id": row.get("code_id"),
        "status_description": row.get("status_description"),
        "description": row.get("description"),
        "complete": row.get("complete"),
        "completed": row.get("completed"),
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
            R4ChartingCanonicalRecord.domain.in_(("restorative_treatment", "restorative_treatments")),
        )
        .order_by(R4ChartingCanonicalRecord.recorded_at.desc(), R4ChartingCanonicalRecord.r4_source_id.desc())
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
                "creation_date": payload.get("creation_date"),
                "acceptance_date": payload.get("acceptance_date"),
                "completion_date": payload.get("completion_date"),
                "transaction_date": payload.get("transaction_date"),
                "ref_id": payload.get("ref_id"),
                "tp_number": payload.get("tp_number"),
                "tp_item": payload.get("tp_item"),
                "tp_item_key": payload.get("tp_item_key"),
                "trans_code": payload.get("trans_code"),
                "code_id": payload.get("code_id", record.code_id),
                "tooth": payload.get("tooth", record.tooth),
                "surface": payload.get("surface", record.surface),
                "status_code": payload.get("status_code"),
                "status_description": payload.get("status_description", record.status),
                "description": payload.get("description"),
                "complete": payload.get("complete"),
                "completed": payload.get("completed"),
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
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in source.list_restorative_treatments(
        patients_from=patient_code,
        patients_to=patient_code,
        date_from=date_from,
        date_to=date_to,
        limit=row_limit,
    ):
        recorded_at = (
            item.recorded_at
            or item.completion_date
            or item.transaction_date
            or item.creation_date
        )
        if not _in_date_window(recorded_at, date_from, date_to):
            continue
        rows.append(
            {
                "patient_code": item.patient_code,
                "recorded_at": _iso(recorded_at),
                "creation_date": _iso(item.creation_date),
                "acceptance_date": _iso(item.acceptance_date),
                "completion_date": _iso(item.completion_date),
                "transaction_date": _iso(item.transaction_date),
                "ref_id": item.ref_id,
                "tp_number": item.tp_number,
                "tp_item": item.tp_item,
                "tp_item_key": item.tp_item_key,
                "trans_code": item.trans_code,
                "code_id": item.code_id,
                "tooth": item.tooth,
                "surface": item.surface,
                "status_code": item.status_code,
                "status_description": item.status_description,
                "description": item.description,
                "complete": item.complete,
                "completed": item.completed,
            }
        )
    return rows


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
        sql_rows = (
            _sqlserver_rows(
                sql_source,
                code,
                date_from=date_from,
                date_to=date_to,
                row_limit=row_limit,
            )
            if sql_source is not None
            else []
        )
        canonical_latest = _latest_row(canonical_rows)
        sql_latest = _latest_row(sql_rows) if sql_source is not None else None
        canonical_latest_key = _latest_key(canonical_latest)
        sql_latest_key = _latest_key(sql_latest)
        canonical_digest = _latest_digest(canonical_latest)
        sql_digest = _latest_digest(sql_latest)
        patients.append(
            {
                "patient_code": code,
                "canonical_total_rows": len(canonical_rows),
                "canonical_distinct_unique_keys": len({_unique_key(r) for r in canonical_rows}),
                "sqlserver_total_rows": len(sql_rows) if sql_source is not None else None,
                "sqlserver_distinct_unique_keys": len({_unique_key(r) for r in sql_rows}) if sql_source is not None else None,
                "canonical_latest_key": canonical_latest_key,
                "sqlserver_latest_key": sql_latest_key,
                "latest_match": canonical_latest_key == sql_latest_key if sql_source is not None else None,
                "canonical_latest_digest": canonical_digest,
                "sqlserver_latest_digest": sql_digest if sql_source is not None else None,
                "latest_digest_match": canonical_digest == sql_digest if sql_source is not None else None,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "row_limit": row_limit,
        "include_sqlserver": include_sqlserver,
        "patient_codes": patient_codes,
        "patients": patients,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a restorative_treatments parity pack from canonical data and SQL Server."
    )
    parser.add_argument("--patient-codes", required=True, help="Comma-separated patient codes.")
    parser.add_argument("--date-from", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument("--row-limit", type=int, default=500, help="Max rows per patient per source.")
    parser.add_argument("--skip-sqlserver", action="store_true", help="Skip SQL Server comparison.")
    parser.add_argument("--output-json", help="Optional path to write report JSON.")
    args = parser.parse_args()

    if args.row_limit <= 0:
        raise RuntimeError("--row-limit must be positive.")

    patient_codes = _parse_patient_codes_csv(args.patient_codes)
    with SessionLocal() as session:
        report = build_parity_report(
            session,
            patient_codes=patient_codes,
            date_from=_parse_day(args.date_from),
            date_to=_parse_day(args.date_to),
            row_limit=args.row_limit,
            include_sqlserver=not args.skip_sqlserver,
        )

    if args.output_json:
        p = Path(args.output_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
