from datetime import datetime, timezone

from app.services.r4_import.linkage_report import (
    R4LinkageReportBuilder,
    UNMAPPED_MAPPED_TO_DELETED_PATIENT,
    UNMAPPED_MISSING_MAPPING,
    UNMAPPED_UNLINKABLE_MISSING_PATIENT_CODE,
)
from app.services.r4_import.types import R4AppointmentRecord


def _appt(appt_id: int, patient_code: int | None) -> R4AppointmentRecord:
    return R4AppointmentRecord(
        appointment_id=appt_id,
        patient_code=patient_code,
        starts_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc),
        duration_minutes=30,
    )


def test_linkage_report_builder_counts_and_reasons():
    mappings = {1001: 10, 2002: 20}
    deleted_patient_ids = {20}
    imported_appt_ids = {1, 3}
    builder = R4LinkageReportBuilder(
        patient_mappings=mappings,
        deleted_patient_ids=deleted_patient_ids,
        imported_appointment_ids=imported_appt_ids,
        top_limit=5,
    )

    builder.ingest(_appt(1, 1001))
    builder.ingest(_appt(2, None))
    builder.ingest(_appt(3, 3003))
    builder.ingest(_appt(4, 2002))

    report = builder.finalize()
    assert report["appointments_total"] == 4
    assert report["appointments_with_patient_code"] == 3
    assert report["appointments_missing_patient_code"] == 1
    assert report["appointments_mapped"] == 1
    assert report["appointments_unmapped"] == 3
    assert report["appointments_unmapped_actionable"] == 2
    assert report["appointments_unmapped_unlinkable"] == 1
    assert report["appointments_imported"] == 2
    assert report["appointments_not_imported"] == 2

    reasons = report["unmapped_reasons"]
    assert reasons[UNMAPPED_UNLINKABLE_MISSING_PATIENT_CODE] == 1
    assert reasons[UNMAPPED_MISSING_MAPPING] == 1
    assert reasons[UNMAPPED_MAPPED_TO_DELETED_PATIENT] == 1

    top = report["top_unmapped_patient_codes"]
    assert any(item["patient_code"] == 3003 for item in top)
