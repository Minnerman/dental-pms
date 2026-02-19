from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_linkage_issue import R4LinkageIssue
from app.models.r4_manual_mapping import R4ManualMapping
from app.models.user import User
from app.services.r4_import.linkage_queue import (
    REASON_MISSING_MAPPING,
    REASON_UNLINKABLE_MISSING_PATIENT_CODE,
    STATUS_RESOLVED,
    R4LinkageIssueInput,
    is_actionable_reason,
    load_linkage_issues,
    normalize_reason_code,
    summarize_queue,
)
from app.services.r4_import.linkage_report import (
    R4LinkageReportBuilder,
    UNMAPPED_MISSING_MAPPING,
)
from app.services.r4_import.types import R4AppointmentRecord


def _clear_issues(session, legacy_source: str) -> None:
    session.execute(
        delete(R4LinkageIssue).where(R4LinkageIssue.legacy_source == legacy_source)
    )


def _resolve_user_id(session) -> int:
    user_id = session.scalar(select(func.min(User.id)))
    if not user_id:
        raise RuntimeError("No users found; cannot create patient.")
    return int(user_id)


def test_linkage_queue_idempotent_load():
    session = SessionLocal()
    try:
        _clear_issues(session, "r4-test")
        session.commit()

        issue = R4LinkageIssueInput(
            entity_type="appointment",
            legacy_source="r4-test",
            legacy_id="1001",
            patient_code=123,
            reason_code="missing_patient_code",
            details_json={"appointment_id": "1001"},
        )

        stats_first = load_linkage_issues(session, [issue])
        session.commit()

        count_first = session.scalar(
            select(func.count()).select_from(R4LinkageIssue).where(
                R4LinkageIssue.legacy_source == "r4-test"
            )
        )

        stats_second = load_linkage_issues(session, [issue])
        session.commit()

        count_second = session.scalar(
            select(func.count()).select_from(R4LinkageIssue).where(
                R4LinkageIssue.legacy_source == "r4-test"
            )
        )

        assert stats_first["created"] == 1
        assert stats_second["created"] == 0
        assert count_first == 1
        assert count_second == 1
    finally:
        session.close()


def test_linkage_queue_reason_normalization():
    session = SessionLocal()
    try:
        _clear_issues(session, "r4-test")
        session.commit()

        normalized = normalize_reason_code("patient_code_not_found")
        issue = R4LinkageIssueInput(
            entity_type="appointment",
            legacy_source="r4-test",
            legacy_id="2001",
            patient_code=999,
            reason_code=normalized,
            details_json={"appointment_id": "2001"},
        )

        load_linkage_issues(session, [issue])
        session.commit()

        stored = session.scalar(
            select(R4LinkageIssue.reason_code).where(
                R4LinkageIssue.legacy_source == "r4-test",
                R4LinkageIssue.legacy_id == "2001",
            )
        )
        assert stored == REASON_MISSING_MAPPING
        assert normalize_reason_code("missing_patient_code") == REASON_UNLINKABLE_MISSING_PATIENT_CODE
        assert is_actionable_reason("missing_patient_code") is False
        assert is_actionable_reason("missing_patient_mapping") is True
    finally:
        session.close()


def test_linkage_queue_actionable_only_excludes_unlinkable():
    session = SessionLocal()
    try:
        _clear_issues(session, "r4-test")
        session.commit()

        issues = [
            R4LinkageIssueInput(
                entity_type="appointment",
                legacy_source="r4-test",
                legacy_id="4001",
                patient_code=None,
                reason_code="missing_patient_code",
                details_json={"appointment_id": "4001"},
            ),
            R4LinkageIssueInput(
                entity_type="appointment",
                legacy_source="r4-test",
                legacy_id="4002",
                patient_code=555,
                reason_code="missing_patient_mapping",
                details_json={"appointment_id": "4002"},
            ),
        ]

        stats = load_linkage_issues(session, issues, actionable_only=True)
        session.commit()

        rows = session.execute(
            select(R4LinkageIssue.legacy_id, R4LinkageIssue.reason_code).where(
                R4LinkageIssue.legacy_source == "r4-test"
            )
        ).all()

        assert stats["created"] == 1
        assert stats["updated"] == 0
        assert stats["reason_counts"] == {"missing_patient_mapping": 1}
        assert stats["excluded_reason_counts"] == {REASON_UNLINKABLE_MISSING_PATIENT_CODE: 1}
        assert rows == [("4002", "missing_patient_mapping")]
    finally:
        session.close()


def test_summarize_queue_actionable_only_filters_unlinkable():
    session = SessionLocal()
    try:
        _clear_issues(session, "r4-test")
        session.commit()

        load_linkage_issues(
            session,
            [
                R4LinkageIssueInput(
                    entity_type="appointment",
                    legacy_source="r4-test",
                    legacy_id="4101",
                    patient_code=None,
                    reason_code="missing_patient_code",
                    details_json={"appointment_id": "4101"},
                ),
                R4LinkageIssueInput(
                    entity_type="appointment",
                    legacy_source="r4-test",
                    legacy_id="4102",
                    patient_code=777,
                    reason_code="missing_patient_mapping",
                    details_json={"appointment_id": "4102"},
                ),
            ],
        )
        session.commit()

        actionable_summary = summarize_queue(
            session,
            "r4-test",
            "appointment",
            actionable_only=True,
        )
        full_summary = summarize_queue(session, "r4-test", "appointment")

        assert actionable_summary == [
            {
                "reason_code": "missing_patient_mapping",
                "status": "open",
                "count": 1,
            }
        ]
        assert len(full_summary) == 2
    finally:
        session.close()


def test_linkage_queue_preserves_resolved_status():
    session = SessionLocal()
    try:
        _clear_issues(session, "r4-test")
        session.commit()

        issue = R4LinkageIssueInput(
            entity_type="appointment",
            legacy_source="r4-test",
            legacy_id="3001",
            patient_code=555,
            reason_code="missing_patient_code",
            details_json={"appointment_id": "3001"},
        )

        load_linkage_issues(session, [issue])
        session.commit()

        row = session.scalar(
            select(R4LinkageIssue).where(
                R4LinkageIssue.legacy_source == "r4-test",
                R4LinkageIssue.legacy_id == "3001",
            )
        )
        row.status = STATUS_RESOLVED
        session.commit()

        issue_update = R4LinkageIssueInput(
            entity_type="appointment",
            legacy_source="r4-test",
            legacy_id="3001",
            patient_code=556,
            reason_code="missing_patient_code",
            details_json={"appointment_id": "3001", "patient_code": 556},
        )

        load_linkage_issues(session, [issue_update])
        session.commit()

        refreshed = session.scalar(
            select(R4LinkageIssue).where(
                R4LinkageIssue.legacy_source == "r4-test",
                R4LinkageIssue.legacy_id == "3001",
            )
        )
        assert refreshed.status == STATUS_RESOLVED
        assert refreshed.patient_code == 556
    finally:
        session.close()


def _appt(appt_id: int, patient_code: int | None) -> R4AppointmentRecord:
    return R4AppointmentRecord(
        appointment_id=appt_id,
        patient_code=patient_code,
        starts_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc),
        duration_minutes=30,
    )


def test_linkage_report_bucket_without_override():
    builder = R4LinkageReportBuilder(
        patient_mappings={},
        manual_mappings={},
        deleted_patient_ids=set(),
    )
    builder.ingest(_appt(1, 7001))
    report = builder.finalize()
    assert report["appointments_mapped"] == 0
    assert report["unmapped_reasons"][UNMAPPED_MISSING_MAPPING] == 1


def test_linkage_report_bucket_with_override():
    session = SessionLocal()
    try:
        session.execute(
            delete(R4ManualMapping).where(
                R4ManualMapping.legacy_source == "r4",
                R4ManualMapping.legacy_patient_code == 7002,
            )
        )
        session.commit()
        actor_id = _resolve_user_id(session)
        patient = Patient(
            legacy_source="r4",
            legacy_id="override-7002",
            first_name="Override",
            last_name="Patient",
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        session.add(patient)
        session.flush()

        session.add(
            R4ManualMapping(
                legacy_source="r4",
                legacy_patient_code=7002,
                target_patient_id=patient.id,
                note="test override",
            )
        )
        session.commit()

        manual_mappings = {
            int(code): int(pid)
            for code, pid in session.execute(
                select(R4ManualMapping.legacy_patient_code, R4ManualMapping.target_patient_id)
            ).all()
        }

        builder = R4LinkageReportBuilder(
            patient_mappings={},
            manual_mappings=manual_mappings,
            deleted_patient_ids=set(),
        )
        builder.ingest(_appt(1, 7002))
        report = builder.finalize()
        assert report["appointments_mapped"] == 1
        assert report["appointments_unmapped"] == 0
    finally:
        session.close()
