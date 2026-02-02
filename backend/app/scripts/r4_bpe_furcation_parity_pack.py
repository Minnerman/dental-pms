from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.services.r4_charting.sqlserver_extract import SqlServerChartingExtractor
from app.services.r4_import.sqlserver_source import R4SqlServerConfig


_FURCATION_KEYS = (
    "furcation_1",
    "furcation_2",
    "furcation_3",
    "furcation_4",
    "furcation_5",
    "furcation_6",
)


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


def _furcation_payload(payload: dict | None) -> dict[str, object | None]:
    if not isinstance(payload, dict):
        return {key: None for key in _FURCATION_KEYS}
    return {key: payload.get(key) for key in _FURCATION_KEYS}


def _latest_sort_tuple(row: dict[str, object]) -> tuple[str, int]:
    return (str(row.get("recorded_at") or ""), int(row.get("bpe_id") or 0))


def _unique_key(row: dict[str, object]) -> str:
    patient = row.get("patient_code")
    bpe_id = row.get("bpe_id")
    pkey = row.get("pkey")
    return f"{patient}:{bpe_id if bpe_id is not None else f'pkey:{pkey}'}"


def _latest_key(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "recorded_at": row.get("recorded_at"),
        "bpe_id": row.get("bpe_id"),
    }


def _latest_digest(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    out: dict[str, object] = {
        "recorded_at": row.get("recorded_at"),
    }
    for key in _FURCATION_KEYS:
        out[key] = row.get(key)
    return out


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
            R4ChartingCanonicalRecord.domain == "bpe_furcation",
            R4ChartingCanonicalRecord.legacy_patient_code == patient_code,
        )
        .order_by(
            R4ChartingCanonicalRecord.recorded_at.desc(),
            R4ChartingCanonicalRecord.r4_source_id.desc(),
        )
        .limit(row_limit)
    )
    rows = session.execute(stmt).scalars().all()
    out: list[dict[str, object]] = []
    for row in rows:
        if not _in_date_window(row.recorded_at, date_from, date_to):
            continue
        payload = row.payload if isinstance(row.payload, dict) else {}
        bpe_id = payload.get("bpe_id")
        if bpe_id is None and row.r4_source_id:
            try:
                bpe_id = int(str(row.r4_source_id))
            except ValueError:
                bpe_id = None
        furcations = _furcation_payload(payload)
        out.append(
            {
                "patient_code": row.legacy_patient_code,
                "recorded_at": _iso(row.recorded_at),
                "bpe_id": bpe_id,
                "pkey": payload.get("pkey"),
                **furcations,
            }
        )
    return out


def _sqlserver_rows(
    patient_code: int,
    *,
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
) -> list[dict[str, object]]:
    cfg = R4SqlServerConfig.from_env()
    cfg.require_enabled()
    cfg.require_readonly()
    extractor = SqlServerChartingExtractor(cfg)
    records, _ = extractor.collect_canonical_records(
        patient_codes=[patient_code],
        date_from=date_from,
        date_to=date_to,
        limit=row_limit,
    )
    out: list[dict[str, object]] = []
    for record in records:
        if record.r4_source != "dbo.BPEFurcation":
            continue
        payload = record.payload if isinstance(record.payload, dict) else {}
        out.append(
            {
                "patient_code": record.legacy_patient_code,
                "recorded_at": _iso(record.recorded_at),
                "bpe_id": payload.get("bpe_id"),
                "pkey": payload.get("pkey"),
                **_furcation_payload(payload),
            }
        )
    return out


def _latest_row(rows: list[dict[str, object]]) -> dict[str, object] | None:
    if not rows:
        return None
    return max(rows, key=_latest_sort_tuple)


def _write_csv_summary(path: str, patients: list[dict[str, object]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "patient_code",
        "canonical_total_rows",
        "sqlserver_total_rows",
        "canonical_distinct_unique_keys",
        "sqlserver_distinct_unique_keys",
        "latest_match",
        "latest_digest_match",
        "canonical_latest_recorded_at",
        "sqlserver_latest_recorded_at",
        "canonical_latest_bpe_id",
        "sqlserver_latest_bpe_id",
    ]
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in patients:
            c_key = row.get("canonical_latest_key") or {}
            s_key = row.get("sqlserver_latest_key") or {}
            writer.writerow(
                {
                    "patient_code": row.get("patient_code"),
                    "canonical_total_rows": row.get("canonical_total_rows"),
                    "sqlserver_total_rows": row.get("sqlserver_total_rows"),
                    "canonical_distinct_unique_keys": row.get("canonical_distinct_unique_keys"),
                    "sqlserver_distinct_unique_keys": row.get("sqlserver_distinct_unique_keys"),
                    "latest_match": row.get("latest_match"),
                    "latest_digest_match": row.get("latest_digest_match"),
                    "canonical_latest_recorded_at": c_key.get("recorded_at"),
                    "sqlserver_latest_recorded_at": s_key.get("recorded_at"),
                    "canonical_latest_bpe_id": c_key.get("bpe_id"),
                    "sqlserver_latest_bpe_id": s_key.get("bpe_id"),
                }
            )


def build_parity_report(
    session: Session,
    *,
    patient_codes: list[int],
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
    include_sqlserver: bool,
) -> dict[str, object]:
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
                code,
                date_from=date_from,
                date_to=date_to,
                row_limit=row_limit,
            )
            if include_sqlserver
            else []
        )

        canonical_latest = _latest_row(canonical_rows)
        sql_latest = _latest_row(sql_rows) if include_sqlserver else None
        canonical_latest_key = _latest_key(canonical_latest)
        sql_latest_key = _latest_key(sql_latest)
        canonical_digest = _latest_digest(canonical_latest)
        sql_digest = _latest_digest(sql_latest)

        patients.append(
            {
                "patient_code": code,
                "canonical_total_rows": len(canonical_rows),
                "canonical_distinct_unique_keys": len({_unique_key(r) for r in canonical_rows}),
                "sqlserver_total_rows": len(sql_rows) if include_sqlserver else None,
                "sqlserver_distinct_unique_keys": len({_unique_key(r) for r in sql_rows}) if include_sqlserver else None,
                "canonical_latest_key": canonical_latest_key,
                "sqlserver_latest_key": sql_latest_key,
                "latest_match": canonical_latest_key == sql_latest_key if include_sqlserver else None,
                "canonical_latest_digest": canonical_digest,
                "sqlserver_latest_digest": sql_digest if include_sqlserver else None,
                "latest_digest_match": canonical_digest == sql_digest if include_sqlserver else None,
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
        description="Build a BPEFurcation parity pack from canonical data and SQL Server."
    )
    parser.add_argument("--patient-codes", required=True, help="Comma-separated patient codes.")
    parser.add_argument("--date-from", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument("--row-limit", type=int, default=500, help="Max rows per patient per source.")
    parser.add_argument("--skip-sqlserver", action="store_true", help="Skip SQL Server comparison.")
    parser.add_argument("--output-json", help="Optional path to write report JSON.")
    parser.add_argument("--output-csv", help="Optional path to write compact summary CSV.")
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

    if args.output_csv:
        _write_csv_summary(args.output_csv, report["patients"])

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
