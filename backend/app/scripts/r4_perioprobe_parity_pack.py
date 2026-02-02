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
    if start is None and end is None:
        return True
    if value is None:
        return True
    day = value.date()
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True


def _probe_unique_key(row: dict[str, object]) -> str:
    return f"{row.get('trans_id')}:{row.get('tooth')}:{row.get('probing_point')}"


def _latest_sort_tuple(row: dict[str, object]) -> tuple[int, str, int]:
    recorded_at = row.get("recorded_at")
    trans_id = int(row.get("trans_id") or 0)
    if recorded_at:
        return (1, str(recorded_at), trans_id)
    return (0, "", trans_id)


def _latest_key(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    mode = "recorded_at+trans_id" if row.get("recorded_at") else "trans_id"
    return {
        "mode": mode,
        "recorded_at": row.get("recorded_at"),
        "trans_id": row.get("trans_id"),
    }


def _digest_for_trans(rows: list[dict[str, object]], trans_id: int | None) -> list[dict[str, object]]:
    if trans_id is None:
        return []
    # Compare latest-trans digests on distinct probe keys to avoid raw SQL duplicate noise.
    seen: set[str] = set()
    matched: list[dict[str, object]] = []
    for row in rows:
        if row.get("trans_id") != trans_id:
            continue
        key = _probe_unique_key(row)
        if key in seen:
            continue
        seen.add(key)
        matched.append(
            {
                "tooth": row.get("tooth"),
                "probing_point": row.get("probing_point"),
                "depth": row.get("depth"),
                "bleeding": row.get("bleeding"),
                "plaque": row.get("plaque"),
            }
        )
    matched.sort(key=lambda r: (int(r.get("tooth") or 0), int(r.get("probing_point") or 0)))
    return matched


def _canonical_rows(
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
            R4ChartingCanonicalRecord.domain == "perio_probe",
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
        payload = row.payload if isinstance(row.payload, dict) else {}
        trans_id = payload.get("trans_id")
        if trans_id is None and row.r4_source_id:
            part = str(row.r4_source_id).split(":", 1)[0]
            try:
                trans_id = int(part)
            except ValueError:
                trans_id = None
        record = {
            "recorded_at": _iso(row.recorded_at),
            "trans_id": int(trans_id) if trans_id is not None else None,
            "tooth": payload.get("tooth", row.tooth),
            "probing_point": payload.get("probing_point"),
            "depth": payload.get("depth"),
            "bleeding": payload.get("bleeding"),
            "plaque": payload.get("plaque"),
        }
        dt = row.recorded_at
        if not _in_date_window(dt, charting_from, charting_to):
            continue
        out.append(record)
    return out


def _sqlserver_rows(
    source: R4SqlServerSource,
    patient_code: int,
    *,
    charting_from: date | None,
    charting_to: date | None,
    row_limit: int,
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for item in source.list_perio_probes(
        patients_from=patient_code,
        patients_to=patient_code,
        limit=row_limit,
    ):
        if not _in_date_window(item.recorded_at, charting_from, charting_to):
            continue
        out.append(
            {
                "recorded_at": _iso(item.recorded_at),
                "trans_id": item.trans_id,
                "tooth": item.tooth,
                "probing_point": item.probing_point,
                "depth": item.depth,
                "bleeding": item.bleeding,
                "plaque": item.plaque,
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
        canonical = _canonical_rows(
            session,
            code,
            charting_from=charting_from,
            charting_to=charting_to,
            row_limit=row_limit,
        )
        sql_rows = (
            _sqlserver_rows(
                sql_source,
                code,
                charting_from=charting_from,
                charting_to=charting_to,
                row_limit=row_limit,
            )
            if sql_source is not None
            else []
        )

        canonical_latest = _latest_row(canonical)
        sql_latest = _latest_row(sql_rows) if sql_source is not None else None
        canonical_latest_key = _latest_key(canonical_latest)
        sql_latest_key = _latest_key(sql_latest)

        canonical_digest = _digest_for_trans(canonical, canonical_latest_key.get("trans_id") if canonical_latest_key else None)
        sql_digest = _digest_for_trans(sql_rows, sql_latest_key.get("trans_id") if sql_latest_key else None)

        patients.append(
            {
                "patient_code": code,
                "canonical_total_rows": len(canonical),
                "canonical_distinct_unique_keys": len({_probe_unique_key(r) for r in canonical}),
                "sqlserver_total_rows": len(sql_rows) if sql_source is not None else None,
                "sqlserver_distinct_unique_keys": len({_probe_unique_key(r) for r in sql_rows}) if sql_source is not None else None,
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
        "charting_from": charting_from.isoformat() if charting_from else None,
        "charting_to": charting_to.isoformat() if charting_to else None,
        "row_limit": row_limit,
        "include_sqlserver": include_sqlserver,
        "patient_codes": patient_codes,
        "patients": patients,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a PerioProbe parity pack from canonical data and (optionally) SQL Server."
    )
    parser.add_argument("--patient-codes", required=True, help="Comma-separated patient codes.")
    parser.add_argument("--charting-from", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--charting-to", help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument("--row-limit", type=int, default=500, help="Max probe rows per patient per source.")
    parser.add_argument("--skip-sqlserver", action="store_true", help="Skip SQL Server comparison.")
    parser.add_argument("--output-json", help="Optional path to write report JSON.")
    args = parser.parse_args()

    if args.row_limit <= 0:
        raise RuntimeError("--row-limit must be positive.")

    patient_codes = _parse_patient_codes_csv(args.patient_codes)
    charting_from = _parse_day(args.charting_from)
    charting_to = _parse_day(args.charting_to)

    with SessionLocal() as session:
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
