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

SEXTANT_KEYS = (
    "sextant_1",
    "sextant_2",
    "sextant_3",
    "sextant_4",
    "sextant_5",
    "sextant_6",
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
        except ValueError as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Invalid patient code: {part}") from exc
        if code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def _in_date_window(value: datetime | None, start: date | None, end: date | None) -> bool:
    if value is None:
        return start is None and end is None
    day = value.date()
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True


def _snapshot_from_payload(payload: dict | None) -> dict[str, int | None]:
    if not isinstance(payload, dict):
        return {key: None for key in SEXTANT_KEYS}
    return {key: payload.get(key) for key in SEXTANT_KEYS}


def _canonical_timeline(
    session: Session,
    patient_code: int,
    *,
    charting_from: date | None,
    charting_to: date | None,
    row_limit: int,
) -> list[dict[str, object]]:
    stmt = (
        select(R4ChartingCanonicalRecord)
        .where(
            R4ChartingCanonicalRecord.domain == "bpe_entry",
            R4ChartingCanonicalRecord.legacy_patient_code == patient_code,
        )
        .order_by(
            R4ChartingCanonicalRecord.recorded_at.desc(),
            R4ChartingCanonicalRecord.r4_source_id.desc(),
        )
        .limit(row_limit)
    )
    rows = session.execute(stmt).scalars().all()
    timeline: list[dict[str, object]] = []
    for row in rows:
        if not _in_date_window(row.recorded_at, charting_from, charting_to):
            continue
        timeline.append(
            {
                "recorded_at": _iso(row.recorded_at),
                "r4_source_id": row.r4_source_id,
                "sextants": _snapshot_from_payload(row.payload),
                "notes": row.payload.get("notes") if isinstance(row.payload, dict) else None,
            }
        )
    return timeline


def _sqlserver_timeline(
    source: R4SqlServerSource,
    patient_code: int,
    *,
    charting_from: date | None,
    charting_to: date | None,
    row_limit: int,
) -> list[dict[str, object]]:
    timeline: list[dict[str, object]] = []
    for item in source.list_bpe_entries(
        patients_from=patient_code,
        patients_to=patient_code,
        limit=row_limit,
    ):
        if not _in_date_window(item.recorded_at, charting_from, charting_to):
            continue
        timeline.append(
            {
                "recorded_at": _iso(item.recorded_at),
                "r4_source_id": str(item.bpe_id) if item.bpe_id is not None else None,
                "sextants": {
                    "sextant_1": item.sextant_1,
                    "sextant_2": item.sextant_2,
                    "sextant_3": item.sextant_3,
                    "sextant_4": item.sextant_4,
                    "sextant_5": item.sextant_5,
                    "sextant_6": item.sextant_6,
                },
                "notes": item.notes,
            }
        )
    timeline.sort(key=lambda row: (row.get("recorded_at") or "", str(row.get("r4_source_id") or "")), reverse=True)
    return timeline


def _latest_entry(rows: list[dict[str, object]]) -> dict[str, object] | None:
    if not rows:
        return None
    return rows[0]


def _latest_match(
    canonical_latest: dict[str, object] | None,
    sql_latest: dict[str, object] | None,
) -> dict[str, bool]:
    if canonical_latest is None or sql_latest is None:
        return {"recorded_at": False, "sextants": False, "all": False}
    recorded_at_match = canonical_latest.get("recorded_at") == sql_latest.get("recorded_at")
    sextants_match = canonical_latest.get("sextants") == sql_latest.get("sextants")
    return {
        "recorded_at": recorded_at_match,
        "sextants": sextants_match,
        "all": recorded_at_match and sextants_match,
    }


def _sample_patient_codes(session: Session, *, limit: int) -> list[int]:
    stmt = (
        select(R4ChartingCanonicalRecord.legacy_patient_code)
        .where(
            R4ChartingCanonicalRecord.domain == "bpe_entry",
            R4ChartingCanonicalRecord.legacy_patient_code.is_not(None),
        )
        .order_by(R4ChartingCanonicalRecord.recorded_at.desc())
        .limit(limit * 5)
    )
    seen: set[int] = set()
    picked: list[int] = []
    for value in session.execute(stmt).scalars():
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        picked.append(code)
        if len(picked) >= limit:
            break
    return picked


def build_parity_report(
    session: Session,
    *,
    patient_codes: list[int],
    charting_from: date | None,
    charting_to: date | None,
    row_limit: int,
    include_sqlserver: bool,
) -> dict[str, object]:
    sql_source: R4SqlServerSource | None = None
    if include_sqlserver:
        config = R4SqlServerConfig.from_env()
        config.require_enabled()
        config.require_readonly()
        sql_source = R4SqlServerSource(config)
        sql_source.ensure_select_only()

    patients: list[dict[str, object]] = []
    for code in patient_codes:
        canonical = _canonical_timeline(
            session,
            code,
            charting_from=charting_from,
            charting_to=charting_to,
            row_limit=row_limit,
        )
        sql_rows = (
            _sqlserver_timeline(
                sql_source,
                code,
                charting_from=charting_from,
                charting_to=charting_to,
                row_limit=row_limit,
            )
            if sql_source is not None
            else []
        )
        canonical_latest = _latest_entry(canonical)
        sql_latest = _latest_entry(sql_rows) if sql_source is not None else None
        patients.append(
            {
                "patient_code": code,
                "canonical_count": len(canonical),
                "sqlserver_count": len(sql_rows) if sql_source is not None else None,
                "canonical_latest": canonical_latest,
                "sqlserver_latest": sql_latest,
                "latest_match": _latest_match(canonical_latest, sql_latest)
                if sql_source is not None
                else None,
                "canonical_timeline": canonical,
                "sqlserver_timeline": sql_rows if sql_source is not None else None,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "charting_from": charting_from.isoformat() if charting_from else None,
        "charting_to": charting_to.isoformat() if charting_to else None,
        "row_limit": row_limit,
        "include_sqlserver": include_sqlserver,
        "patient_codes": patient_codes,
        "patients": patients,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a BPE parity pack for selected patients from canonical data "
            "and (optionally) SQL Server."
        )
    )
    parser.add_argument(
        "--patient-codes",
        help="Comma-separated patient codes (e.g. 1000035,1000036).",
    )
    parser.add_argument(
        "--limit-patients",
        type=int,
        default=5,
        help="When --patient-codes is not set, sample this many patient codes from canonical BPE entries.",
    )
    parser.add_argument("--charting-from", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--charting-to", help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument("--row-limit", type=int, default=100, help="Max BPE rows per patient per source.")
    parser.add_argument(
        "--skip-sqlserver",
        action="store_true",
        help="Skip SQL Server comparison and report canonical timeline only.",
    )
    parser.add_argument("--output-json", help="Optional path to write report JSON.")
    args = parser.parse_args()

    if args.row_limit <= 0:
        raise RuntimeError("--row-limit must be positive.")

    charting_from = _parse_day(args.charting_from)
    charting_to = _parse_day(args.charting_to)

    with SessionLocal() as session:
        if args.patient_codes:
            patient_codes = _parse_patient_codes_csv(args.patient_codes)
        else:
            patient_codes = _sample_patient_codes(session, limit=args.limit_patients)
        if not patient_codes:
            raise RuntimeError("No patient codes available for parity pack.")

        report = build_parity_report(
            session,
            patient_codes=patient_codes,
            charting_from=charting_from,
            charting_to=charting_to,
            row_limit=args.row_limit,
            include_sqlserver=not args.skip_sqlserver,
        )

    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
