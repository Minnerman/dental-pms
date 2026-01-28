from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_appointment import R4Appointment
from app.models.r4_patient_mapping import R4PatientMapping
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.linkage_queue import (
    R4LinkageIssueInput,
    load_linkage_issues,
    normalize_reason_code,
    summarize_queue,
)
from app.services.r4_import.linkage_report import R4LinkageReportBuilder
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _load_patient_mappings(session, legacy_source: str) -> dict[int, int]:
    rows = session.execute(
        select(R4PatientMapping.legacy_patient_code, R4PatientMapping.patient_id).where(
            R4PatientMapping.legacy_source == legacy_source
        )
    ).all()
    return {int(code): int(patient_id) for code, patient_id in rows}


def _load_deleted_patient_ids(session) -> set[int]:
    rows = session.execute(select(Patient.id).where(Patient.deleted_at.is_not(None))).scalars()
    return {int(pid) for pid in rows}


def _load_imported_appointment_ids(session, legacy_source: str) -> set[int]:
    rows = session.execute(
        select(R4Appointment.legacy_appointment_id).where(
            R4Appointment.legacy_source == legacy_source
        )
    ).scalars()
    return {int(appt_id) for appt_id in rows}


def _iter_issues_from_csv(
    path: Path,
    legacy_source: str,
    entity_type: str,
) -> list[R4LinkageIssueInput]:
    issues: list[R4LinkageIssueInput] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            reason = normalize_reason_code(row.get("reason"))
            if reason is None:
                continue
            patient_code_raw = row.get("patient_code") or None
            patient_code = int(patient_code_raw) if patient_code_raw else None
            details = {
                "appointment_id": row.get("appointment_id"),
                "patient_code": patient_code,
                "starts_at": row.get("starts_at"),
                "reason": reason,
            }
            issues.append(
                R4LinkageIssueInput(
                    entity_type=entity_type,
                    legacy_source=legacy_source,
                    legacy_id=str(row.get("appointment_id") or ""),
                    patient_code=patient_code,
                    reason_code=reason,
                    details_json=details,
                )
            )
    return issues


def _iter_issues_from_source(
    source,
    legacy_source: str,
    entity_type: str,
    date_from: date | None,
    date_to: date | None,
    limit: int | None,
) -> tuple[list[R4LinkageIssueInput], dict[str, object]]:
    session = SessionLocal()
    try:
        patient_mappings = _load_patient_mappings(session, legacy_source)
        deleted_patient_ids = _load_deleted_patient_ids(session)
        imported_appointment_ids = _load_imported_appointment_ids(session, legacy_source)
    finally:
        session.close()

    report = R4LinkageReportBuilder(
        patient_mappings=patient_mappings,
        deleted_patient_ids=deleted_patient_ids,
        imported_appointment_ids=imported_appointment_ids,
    )

    issues: list[R4LinkageIssueInput] = []
    for appt in source.stream_appointments(date_from=date_from, date_to=date_to, limit=limit):
        reason = normalize_reason_code(report.ingest(appt))
        if reason is None:
            continue
        details = {
            "appointment_id": appt.appointment_id,
            "patient_code": appt.patient_code,
            "starts_at": appt.starts_at.isoformat(),
            "reason": reason,
        }
        issues.append(
            R4LinkageIssueInput(
                entity_type=entity_type,
                legacy_source=legacy_source,
                legacy_id=str(appt.appointment_id),
                patient_code=appt.patient_code,
                reason_code=reason,
                details_json=details,
            )
        )

    payload = report.finalize()
    payload["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload["source"] = getattr(source, "name", "sqlserver")
    payload["window"] = {
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
        "limit": limit,
    }
    return issues, payload


def _print_counts(summary_rows: list[dict[str, object]], file=sys.stdout) -> None:
    if not summary_rows:
        print("No linkage issues found.", file=file)
        return
    print("Queue summary (reason_code/status):", file=file)
    for row in summary_rows:
        print(
            f"  - {row['reason_code']} / {row['status']}: {row['count']}",
            file=file,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load R4 linkage issues into Postgres (read-only from R4)."
    )
    parser.add_argument(
        "--input-csv",
        help="Path to CSV produced by r4_linkage_report.",
    )
    parser.add_argument(
        "--input-json",
        help="Optional JSON report path (for metadata only).",
    )
    parser.add_argument(
        "--source",
        default="sqlserver",
        choices=("sqlserver", "fixtures"),
        help="Data source for appointments (default: sqlserver).",
    )
    parser.add_argument("--from", dest="date_from", help="Filter from YYYY-MM-DD.")
    parser.add_argument("--to", dest="date_to", help="Filter to YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=None, help="Limit appointments scanned.")
    parser.add_argument(
        "--legacy-source",
        default="r4",
        help="Legacy source tag (default: r4).",
    )
    parser.add_argument(
        "--entity-type",
        default="appointment",
        help="Entity type to store (default: appointment).",
    )
    args = parser.parse_args()

    date_from = _parse_date(args.date_from)
    date_to = _parse_date(args.date_to)

    issues: list[R4LinkageIssueInput]
    metadata: dict[str, object] | None = None

    if args.input_csv:
        issues = _iter_issues_from_csv(
            Path(args.input_csv), legacy_source=args.legacy_source, entity_type=args.entity_type
        )
        if args.input_json:
            metadata = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    else:
        if args.source == "fixtures":
            source = FixtureSource()
        else:
            config = R4SqlServerConfig.from_env()
            config.require_enabled()
            source = R4SqlServerSource(config)
        issues, metadata = _iter_issues_from_source(
            source,
            legacy_source=args.legacy_source,
            entity_type=args.entity_type,
            date_from=date_from,
            date_to=date_to,
            limit=args.limit,
        )

    session = SessionLocal()
    try:
        stats = load_linkage_issues(session, issues)
        session.commit()
        summary = summarize_queue(session, args.legacy_source, args.entity_type)
    finally:
        session.close()

    print(
        f"Loaded linkage issues (created={stats['created']}, updated={stats['updated']})."
    )
    if stats["reason_counts"]:
        print("Batch reason counts:")
        for reason, count in stats["reason_counts"].items():
            print(f"  - {reason}: {count}")

    _print_counts(summary)

    if metadata:
        meta_counts = Counter(metadata.get("unmapped_reasons") or {})
        if meta_counts:
            print("Report unmapped reasons:", file=sys.stdout)
            for reason, count in meta_counts.items():
                print(f"  - {reason}: {count}", file=sys.stdout)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
