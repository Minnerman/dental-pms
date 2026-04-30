from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Iterable

from sqlalchemy import func, select

from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.r4_appointment import R4Appointment
from app.models.r4_appointment_patient_link import R4AppointmentPatientLink
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_user import R4User
from app.services.r4_import.appointment_promotion_dryrun import (
    R4AppointmentPromotionRow,
    build_appointment_promotion_dryrun_report,
    ensure_scratch_database_url,
)


def _load_patient_mapping_codes(session, legacy_source: str) -> set[int]:
    return {
        int(value)
        for value in session.execute(
            select(R4PatientMapping.legacy_patient_code).where(
                R4PatientMapping.legacy_source == legacy_source
            )
        ).scalars()
    }


def _load_appointment_link_ids(session, legacy_source: str) -> set[int]:
    return {
        int(value)
        for value in session.execute(
            select(R4AppointmentPatientLink.legacy_appointment_id).where(
                R4AppointmentPatientLink.legacy_source == legacy_source
            )
        ).scalars()
    }


def _load_r4_user_codes(session, legacy_source: str) -> set[int]:
    return {
        int(value)
        for value in session.execute(
            select(R4User.legacy_user_code).where(
                R4User.legacy_source == legacy_source
            )
        ).scalars()
    }


def _stream_r4_appointments(
    session,
    *,
    legacy_source: str,
    limit: int | None,
) -> Iterable[R4AppointmentPromotionRow]:
    stmt = (
        select(
            R4Appointment.legacy_appointment_id,
            R4Appointment.patient_code,
            R4Appointment.starts_at,
            R4Appointment.ends_at,
            R4Appointment.clinician_code,
            R4Appointment.status,
            R4Appointment.cancelled,
            R4Appointment.clinic_code,
            R4Appointment.appointment_type,
            R4Appointment.appt_flag,
        )
        .where(R4Appointment.legacy_source == legacy_source)
        .order_by(R4Appointment.starts_at.asc(), R4Appointment.legacy_appointment_id.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    for row in session.execute(stmt):
        yield R4AppointmentPromotionRow(
            legacy_appointment_id=int(row.legacy_appointment_id),
            patient_code=row.patient_code,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            clinician_code=row.clinician_code,
            status=row.status,
            cancelled=row.cancelled,
            clinic_code=row.clinic_code,
            appointment_type=row.appointment_type,
            appt_flag=row.appt_flag,
        )


def _count_core_appointments(session) -> int:
    return int(session.scalar(select(func.count()).select_from(Appointment)) or 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report-only R4 appointment promotion dry-run from imported staging rows. "
            "The command selects from scratch/test PMS DB tables only and never writes "
            "core appointments."
        )
    )
    parser.add_argument(
        "--cutover-date",
        required=True,
        help="Cutover split date, YYYY-MM-DD. Rows before this date are past; rows on/after are future.",
    )
    parser.add_argument(
        "--legacy-source",
        default="r4",
        help="Legacy source tag to read from r4_* tables (default: r4).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum staging rows to consider.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="Maximum sample rows per risk bucket.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write promotion dry-run report JSON.",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        raise RuntimeError("--limit must be at least 1 when provided.")
    if args.sample_limit < 1:
        raise RuntimeError("--sample-limit must be at least 1.")

    cutover_date = date.fromisoformat(args.cutover_date)
    source_database = ensure_scratch_database_url(settings.database_url)

    session = SessionLocal()
    try:
        core_before = _count_core_appointments(session)
        report = build_appointment_promotion_dryrun_report(
            _stream_r4_appointments(
                session,
                legacy_source=args.legacy_source,
                limit=args.limit,
            ),
            cutover_date=cutover_date,
            patient_mapping_codes=_load_patient_mapping_codes(
                session,
                args.legacy_source,
            ),
            appointment_link_ids=_load_appointment_link_ids(
                session,
                args.legacy_source,
            ),
            r4_user_codes=_load_r4_user_codes(session, args.legacy_source),
            legacy_source=args.legacy_source,
            source_database=source_database,
            core_appointments_before=core_before,
            core_appointments_after=_count_core_appointments(session),
            sample_limit=args.sample_limit,
        )
        session.rollback()
    finally:
        session.close()

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "output_json": str(output_path),
        "source_database": report["source_database"],
        "cutover_date": report["cutover_date"],
        "total_considered": report["total_considered"],
        "time_window_counts": report["time_window_counts"],
        "promotion_candidate_counts": report["promotion_candidate_counts"],
        "linkage_counts": report["linkage_counts"],
        "clinician_counts": report["clinician_counts"],
        "core_appointments": report["core_appointments"],
        "risk_flags": report["risk_flags"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
