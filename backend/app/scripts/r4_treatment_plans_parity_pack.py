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


def _iso(dt: datetime | date | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt
    elif isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day)
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


def _latest_sort_tuple(row: dict[str, object]) -> tuple[str, int, int]:
    return (
        str(row.get("recorded_at") or ""),
        int(row.get("treatment_plan_id") or 0),
        int(row.get("tp_number") or 0),
    )


def _unique_key(row: dict[str, object]) -> str:
    if row.get("treatment_plan_id") is not None:
        return f"id:{row.get('treatment_plan_id')}"
    return f"{row.get('patient_code')}:{row.get('tp_number')}"


def _latest_key(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "recorded_at": row.get("recorded_at"),
        "treatment_plan_id": row.get("treatment_plan_id"),
        "tp_number": row.get("tp_number"),
    }


def _latest_digest(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "accepted_at": row.get("accepted_at"),
        "completed_at": row.get("completed_at"),
        "status_code": row.get("status_code"),
        "is_current": row.get("is_current"),
        "is_accepted": row.get("is_accepted"),
        "is_master": row.get("is_master"),
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
            R4ChartingCanonicalRecord.domain == "treatment_plan",
            R4ChartingCanonicalRecord.legacy_patient_code == patient_code,
        )
        .order_by(
            R4ChartingCanonicalRecord.recorded_at.desc(),
            R4ChartingCanonicalRecord.r4_source_id.desc(),
        )
        .limit(row_limit)
    )
    out: list[dict[str, object]] = []
    for row in session.execute(stmt).scalars().all():
        if not _in_date_window(row.recorded_at, date_from, date_to):
            continue
        payload = row.payload if isinstance(row.payload, dict) else {}
        plan_id = payload.get("treatment_plan_id")
        if plan_id is None and row.r4_source_id:
            try:
                plan_id = int(str(row.r4_source_id))
            except ValueError:
                plan_id = None
        out.append(
            {
                "patient_code": row.legacy_patient_code,
                "tp_number": payload.get("tp_number"),
                "treatment_plan_id": plan_id,
                "recorded_at": _iso(row.recorded_at),
                "accepted_at": _iso(row.entered_at),
                "completed_at": _iso(payload.get("completion_date")),
                "status_code": payload.get("status_code"),
                "is_current": payload.get("is_current"),
                "is_accepted": payload.get("is_accepted"),
                "is_master": payload.get("is_master"),
            }
        )
    return out


def _sqlserver_rows(
    source: R4SqlServerSource,
    patient_code: int,
    *,
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for item in source.list_treatment_plans(
        patients_from=patient_code,
        patients_to=patient_code,
        date_from=date_from,
        date_to=date_to,
        include_undated=False,
        limit=row_limit,
    ):
        if not _in_date_window(item.creation_date, date_from, date_to):
            continue
        out.append(
            {
                "patient_code": item.patient_code,
                "tp_number": item.tp_number,
                "treatment_plan_id": item.treatment_plan_id,
                "recorded_at": _iso(item.creation_date),
                "accepted_at": _iso(item.acceptance_date),
                "completed_at": _iso(item.completion_date),
                "status_code": item.status_code,
                "is_current": item.is_current,
                "is_accepted": item.is_accepted,
                "is_master": item.is_master,
            }
        )
    return out


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
                "sqlserver_distinct_unique_keys": (
                    len({_unique_key(r) for r in sql_rows}) if sql_source is not None else None
                ),
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
        description="Build a TreatmentPlans parity pack from canonical data and SQL Server."
    )
    parser.add_argument("--patient-codes", required=True, help="Comma-separated patient codes.")
    parser.add_argument("--date-from", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument("--row-limit", type=int, default=500, help="Max rows per patient per source.")
    parser.add_argument("--skip-sqlserver", action="store_true", help="Skip SQL Server comparison.")
    parser.add_argument("--output-json", help="Optional path to write report JSON.")
    args = parser.parse_args()

    patient_codes = _parse_patient_codes_csv(args.patient_codes)
    date_from = _parse_day(args.date_from)
    date_to = _parse_day(args.date_to)

    with SessionLocal() as session:
        report = build_parity_report(
            session,
            patient_codes=patient_codes,
            date_from=date_from,
            date_to=date_to,
            row_limit=args.row_limit,
            include_sqlserver=not args.skip_sqlserver,
        )

    if args.output_json:
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
