from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.models.r4_treatment_plan import R4Treatment
from app.services.r4_charting.canonical_importer import import_r4_charting_canonical_report
from app.services.r4_charting.sqlserver_extract import SqlServerChartingExtractor
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource
from app.services.tooth_state_classification import classify_tooth_state_type

_RESTORATIVE_DOMAINS = ("restorative_treatment", "restorative_treatments")


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def _recorded_at(item) -> datetime | None:
    return item.recorded_at or item.completion_date or item.transaction_date or item.creation_date


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


def _int_counts(values: Counter[str]) -> dict[str, int]:
    return {key: int(values[key]) for key in sorted(values)}


def _int_only(payload: dict[str, object] | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(payload, dict):
        return out
    for key, value in payload.items():
        if isinstance(value, int):
            out[key] = value
    return out


def _sqlserver_restorative_count(
    source: R4SqlServerSource,
    *,
    patient_code: int,
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
) -> int:
    count = 0
    for item in source.list_restorative_treatments(
        patients_from=patient_code,
        patients_to=patient_code,
        date_from=None,
        date_to=None,
        limit=row_limit,
        include_not_completed=True,
        require_tooth=False,
        status_descriptions=None,
        require_code_id=False,
    ):
        if _in_date_window(_recorded_at(item), date_from, date_to):
            count += 1
    return count


def _postgres_rows_breakdown(
    session: Session,
    *,
    patient_code: int,
    date_from: date | None,
    date_to: date | None,
) -> tuple[int, dict[str, int], dict[str, int]]:
    stmt = (
        select(R4ChartingCanonicalRecord, R4Treatment.description.label("code_label"))
        .outerjoin(
            R4Treatment,
            and_(
                R4Treatment.legacy_source == "r4",
                R4Treatment.legacy_treatment_code == R4ChartingCanonicalRecord.code_id,
            ),
        )
        .where(
            R4ChartingCanonicalRecord.legacy_patient_code == patient_code,
            R4ChartingCanonicalRecord.domain.in_(_RESTORATIVE_DOMAINS),
        )
        .order_by(R4ChartingCanonicalRecord.recorded_at.desc(), R4ChartingCanonicalRecord.r4_source_id.desc())
    )
    rows = session.execute(stmt).all()
    by_status: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    count = 0
    for record, code_label in rows:
        if not _in_date_window(record.recorded_at, date_from, date_to):
            continue
        payload = record.payload if isinstance(record.payload, dict) else {}
        status_raw = payload.get("status_description", record.status)
        status = str(status_raw or "unknown").strip().lower() or "unknown"
        by_status[status] += 1

        resolved_label = None
        if isinstance(code_label, str):
            resolved_label = code_label.strip() or None
        if not resolved_label:
            payload_label = payload.get("code_label")
            if isinstance(payload_label, str):
                resolved_label = payload_label.strip() or None
        if not resolved_label:
            fallback_label = payload.get("description") or payload.get("status_description")
            if isinstance(fallback_label, str):
                resolved_label = fallback_label.strip() or None
        code_id = payload.get("code_id", record.code_id)
        if not resolved_label and code_id is not None:
            resolved_label = "Unknown code"
        by_type[classify_tooth_state_type(resolved_label)] += 1
        count += 1

    return count, _int_counts(by_status), _int_counts(by_type)


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

    sql_count = _sqlserver_restorative_count(
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
        domains=["restorative_treatments"],
        limit=row_limit,
        dry_run=True,
    )
    dropped = _int_only(canonical_report.get("dropped") if isinstance(canonical_report, dict) else None)

    pg_count, pg_rows_by_status, pg_rows_by_type = _postgres_rows_breakdown(
        session,
        patient_code=patient_code,
        date_from=date_from,
        date_to=date_to,
    )

    importer_candidates = int(canonical_report.get("total_records") or 0)
    return {
        "patient_code": patient_code,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "sql_count": sql_count,
        "pg_count": pg_count,
        "delta_sql_minus_pg": sql_count - pg_count,
        "canonical_dry_run_candidates": importer_candidates,
        "delta_candidates_minus_pg": importer_candidates - pg_count,
        "pg_rows_by_status": pg_rows_by_status,
        "pg_rows_by_type": pg_rows_by_type,
        "dropped_reasons": dropped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain restorative_treatments SQL vs Postgres gaps for one patient.")
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
