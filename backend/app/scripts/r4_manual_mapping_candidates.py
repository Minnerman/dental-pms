from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.r4_appointment import R4Appointment
from app.models.r4_appointment_patient_link import R4AppointmentPatientLink
from app.models.r4_manual_mapping import R4ManualMapping


def _load_codes(report_path: Path, limit: int) -> list[int]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    items = payload.get("top_unmapped_patient_codes") or []
    codes: list[int] = []
    for item in items:
        code = item.get("patient_code")
        if code is None:
            continue
        codes.append(int(code))
        if len(codes) >= limit:
            break
    return codes


def _parse_codes(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(code.strip()) for code in value.split(",") if code.strip()]


def _format_patient(patient: Patient) -> dict[str, str | int | None]:
    return {
        "patient_id": patient.id,
        "full_name": f"{patient.first_name} {patient.last_name}",
        "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        "phone": patient.phone,
        "email": patient.email,
        "postcode": patient.postcode,
        "legacy_source": patient.legacy_source,
        "legacy_id": patient.legacy_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate candidate packs for R4 manual mappings."
    )
    parser.add_argument(
        "--report",
        default="docs/r4/R4_LINKAGE_REPORT_2025-01-01_2026-01-28.json",
        help="Path to linkage report JSON.",
    )
    parser.add_argument(
        "--codes",
        default=None,
        help="Comma-separated legacy patient codes to use (overrides report).",
    )
    parser.add_argument("--limit", type=int, default=10, help="Top N codes to include.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown path (default: docs/r4/R4_MANUAL_MAPPING_CANDIDATES_<DATE>.md).",
    )
    args = parser.parse_args()

    report_path = Path(args.report)
    codes = _parse_codes(args.codes)
    if not codes:
        if not report_path.exists():
            raise SystemExit(f"Report not found: {report_path}")
        codes = _load_codes(report_path, args.limit)
    if not codes:
        raise SystemExit("No codes found in report.")

    session = SessionLocal()
    try:
        manual_mappings = {
            int(code): int(target)
            for code, target in session.execute(
                select(
                    R4ManualMapping.legacy_patient_code,
                    R4ManualMapping.target_patient_id,
                ).where(R4ManualMapping.legacy_source == "r4")
            ).all()
        }

        sections: list[str] = []
        for code in codes:
            if code in manual_mappings:
                sections.append(
                    f"### legacy_patient_code {code}\n\n"
                    f"- Already mapped to patient_id {manual_mappings[code]}.\n"
                )
                continue

            candidates: dict[int, dict[str, object]] = {}
            signals: dict[int, list[str]] = defaultdict(list)

            # Signal 1: exact legacy_source/legacy_id match
            exact_patients = session.scalars(
                select(Patient).where(
                    Patient.legacy_source == "r4",
                    Patient.legacy_id == str(code),
                )
            ).all()
            for patient in exact_patients:
                candidates[patient.id] = _format_patient(patient)
                signals[patient.id].append("exact legacy_id match")

            # Signal 2: appointment legacy_patient_code linked to patient_id
            appt_patients = session.execute(
                select(Appointment.patient_id)
                .where(
                    Appointment.legacy_patient_code == str(code),
                    Appointment.patient_id.is_not(None),
                )
                .distinct()
            ).scalars()
            for patient_id in appt_patients:
                patient = session.get(Patient, patient_id)
                if patient:
                    candidates[patient.id] = _format_patient(patient)
                    signals[patient.id].append("appointment legacy_patient_code match")

            # Signal 3: R4 appointment patient link by patient_code
            linked_patient_ids = session.execute(
                select(R4AppointmentPatientLink.patient_id)
                .join(
                    R4Appointment,
                    (R4Appointment.legacy_source == R4AppointmentPatientLink.legacy_source)
                    & (
                        R4Appointment.legacy_appointment_id
                        == R4AppointmentPatientLink.legacy_appointment_id
                    ),
                )
                .where(R4Appointment.patient_code == code)
                .distinct()
            ).scalars()
            for patient_id in linked_patient_ids:
                patient = session.get(Patient, patient_id)
                if patient:
                    candidates[patient.id] = _format_patient(patient)
                    signals[patient.id].append("r4_appointment_patient_link match")

            if not candidates:
                sections.append(
                    f"### legacy_patient_code {code}\n\n"
                    "- No internal signal; needs R4 lookup.\n"
                )
                continue

            lines = [f"### legacy_patient_code {code}\n", "Candidates:"]
            for patient_id, payload in candidates.items():
                reason = ", ".join(signals.get(patient_id, [])) or "no signal"
                confidence = (
                    "medium" if "exact legacy_id match" in reason else "low"
                )
                lines.append(
                    f"- patient_id: {payload['patient_id']}\n"
                    f"  - name: {payload['full_name']}\n"
                    f"  - dob: {payload['date_of_birth']}\n"
                    f"  - phone: {payload['phone']}\n"
                    f"  - email: {payload['email']}\n"
                    f"  - postcode: {payload['postcode']}\n"
                    f"  - legacy: {payload['legacy_source']}/{payload['legacy_id']}\n"
                    f"  - signal: {reason}\n"
                    f"  - confidence: {confidence}\n"
                )
            sections.append("\n".join(lines))
    finally:
        session.close()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_path = Path(args.output) if args.output else Path(
        f"docs/r4/R4_MANUAL_MAPPING_CANDIDATES_{stamp}.md"
    )
    header = [
        "# R4 manual mapping candidates",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Top legacy patient codes from linkage report:",
        ", ".join(str(code) for code in codes),
        "",
    ]
    output_path.write_text("\n".join(header + sections).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote candidate pack: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
