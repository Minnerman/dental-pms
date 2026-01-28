from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.r4_linkage_issue import R4LinkageIssue
from app.services.r4_import.linkage_queue import (
    REASON_MISSING_MAPPING,
    STATUS_RESOLVED,
    R4LinkageIssueInput,
    load_linkage_issues,
    normalize_reason_code,
)


def _clear_issues(session, legacy_source: str) -> None:
    session.execute(
        delete(R4LinkageIssue).where(R4LinkageIssue.legacy_source == legacy_source)
    )


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
