from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_appointment import R4Appointment
from app.models.r4_manual_mapping import R4ManualMapping
from app.models.r4_patient_mapping import R4PatientMapping
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.linkage_report import (
    R4LinkageReportBuilder,
    UNMAPPED_MAPPED_TO_DELETED_PATIENT,
    UNMAPPED_MISSING_MAPPING,
    UNMAPPED_MISSING_PATIENT_CODE,
)
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


def _load_manual_mappings(session, legacy_source: str) -> dict[int, int]:
    rows = session.execute(
        select(R4ManualMapping.legacy_patient_code, R4ManualMapping.target_patient_id).where(
            R4ManualMapping.legacy_source == legacy_source,
            R4ManualMapping.legacy_patient_code.is_not(None),
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


def _print_summary(payload: dict[str, object], *, file=sys.stderr) -> None:
    reasons = payload.get("unmapped_reasons") or {}
    top_codes = payload.get("top_unmapped_patient_codes") or []
    print("R4 linkage quality report", file=file)
    print(f"  appointments_total: {payload.get('appointments_total')}", file=file)
    print(
        "  appointments_with_patient_code: "
        f"{payload.get('appointments_with_patient_code')}",
        file=file,
    )
    print(
        "  appointments_missing_patient_code: "
        f"{payload.get('appointments_missing_patient_code')}",
        file=file,
    )
    print(f"  appointments_mapped: {payload.get('appointments_mapped')}", file=file)
    print(f"  appointments_unmapped: {payload.get('appointments_unmapped')}", file=file)
    if "appointments_imported" in payload:
        print(
            f"  appointments_imported: {payload.get('appointments_imported')}",
            file=file,
        )
        print(
            f"  appointments_not_imported: {payload.get('appointments_not_imported')}",
            file=file,
        )
    print("  unmapped_reasons:", file=file)
    for key, value in reasons.items():
        print(f"    - {key}: {value}", file=file)
    if top_codes:
        print("  top_unmapped_patient_codes:", file=file)
        for item in top_codes:
            print(
                f"    - {item.get('patient_code')}: {item.get('count')}", file=file
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report R4 appointment linkage quality (read-only)."
    )
    parser.add_argument(
        "--source",
        default="sqlserver",
        choices=("sqlserver", "fixtures"),
        help="Data source for appointments (default: sqlserver).",
    )
    parser.add_argument("--from", dest="date_from", help="Filter from YYYY-MM-DD.")
    parser.add_argument("--to", dest="date_to", help="Filter to YYYY-MM-DD.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit appointments scanned."
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Top N unmapped patient codes to report.",
    )
    parser.add_argument(
        "--output-json",
        default="-",
        help="Write JSON to PATH (default: stdout).",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Optional CSV path for unmapped appointment rows.",
    )
    parser.add_argument(
        "--legacy-source",
        default="r4",
        help="Legacy source tag (default: r4).",
    )
    args = parser.parse_args()

    date_from = _parse_date(args.date_from)
    date_to = _parse_date(args.date_to)

    if args.source == "fixtures":
        source = FixtureSource()
    else:
        config = R4SqlServerConfig.from_env()
        config.require_enabled()
        source = R4SqlServerSource(config)

    session = SessionLocal()
    try:
        patient_mappings = _load_patient_mappings(session, args.legacy_source)
        manual_mappings = _load_manual_mappings(session, args.legacy_source)
        deleted_patient_ids = _load_deleted_patient_ids(session)
        imported_appointment_ids = _load_imported_appointment_ids(
            session, args.legacy_source
        )
    finally:
        session.close()

    report = R4LinkageReportBuilder(
        patient_mappings=patient_mappings,
        manual_mappings=manual_mappings,
        deleted_patient_ids=deleted_patient_ids,
        imported_appointment_ids=imported_appointment_ids,
        top_limit=args.top,
    )

    csv_writer = None
    csv_fp = None
    if args.output_csv:
        output_path = Path(args.output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        csv_fp = output_path.open("w", newline="", encoding="utf-8")
        csv_writer = csv.DictWriter(
            csv_fp,
            fieldnames=["appointment_id", "patient_code", "starts_at", "reason"],
        )
        csv_writer.writeheader()

    try:
        for appt in source.stream_appointments(
            date_from=date_from,
            date_to=date_to,
            limit=args.limit,
        ):
            reason = report.ingest(appt)
            if csv_writer and reason is not None:
                csv_writer.writerow(
                    {
                        "appointment_id": appt.appointment_id,
                        "patient_code": appt.patient_code,
                        "starts_at": appt.starts_at.isoformat(),
                        "reason": reason,
                    }
                )
    finally:
        if csv_fp:
            csv_fp.close()

    payload = report.finalize()
    payload["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload["source"] = args.source
    payload["window"] = {
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
        "limit": args.limit,
    }
    payload["unmapped_reason_definitions"] = {
        UNMAPPED_MISSING_PATIENT_CODE: "R4 appointment row has no patient code.",
        UNMAPPED_MISSING_MAPPING: "No r4_patient_mappings entry for patient_code.",
        UNMAPPED_MAPPED_TO_DELETED_PATIENT: "Mapping points to a soft-deleted patient.",
    }

    _print_summary(payload)

    output_json = args.output_json or "-"
    if output_json == "-":
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        output_path = Path(output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
