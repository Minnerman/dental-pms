from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import func, select

from app.models.r4_linkage_issue import R4LinkageIssue


STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"
STATUS_IGNORED = "ignored"

REASON_MISSING_PATIENT_CODE = "missing_patient_code"
REASON_MISSING_MAPPING = "missing_patient_mapping"
REASON_MAPPED_TO_DELETED_PATIENT = "mapped_to_deleted_patient"
REASON_PMS_RECORD_ID_PARSE = "pmsrecordid_parse_failure"
REASON_DUPLICATE_MAPPING = "duplicate_mapping"
REASON_PATIENT_CODE_NOT_FOUND = "patient_code_not_found"

REASON_ALIASES = {
    REASON_PATIENT_CODE_NOT_FOUND: REASON_MISSING_MAPPING,
}


@dataclass(frozen=True)
class R4LinkageIssueInput:
    entity_type: str
    legacy_source: str
    legacy_id: str
    patient_code: int | None
    reason_code: str
    details_json: dict | None = None


def normalize_reason_code(reason_code: str | None) -> str | None:
    if not reason_code:
        return None
    return REASON_ALIASES.get(reason_code, reason_code)


def upsert_linkage_issue(session, issue: R4LinkageIssueInput) -> tuple[R4LinkageIssue, bool]:
    existing = session.scalar(
        select(R4LinkageIssue).where(
            R4LinkageIssue.legacy_source == issue.legacy_source,
            R4LinkageIssue.entity_type == issue.entity_type,
            R4LinkageIssue.legacy_id == issue.legacy_id,
        )
    )
    if existing:
        existing.patient_code = issue.patient_code
        existing.reason_code = issue.reason_code
        existing.details_json = issue.details_json
        return existing, False

    row = R4LinkageIssue(
        entity_type=issue.entity_type,
        legacy_source=issue.legacy_source,
        legacy_id=issue.legacy_id,
        patient_code=issue.patient_code,
        reason_code=issue.reason_code,
        details_json=issue.details_json,
        status=STATUS_OPEN,
    )
    session.add(row)
    return row, True


def load_linkage_issues(
    session,
    issues: Iterable[R4LinkageIssueInput],
) -> dict[str, object]:
    created = 0
    updated = 0
    reason_counts: Counter[str] = Counter()

    for issue in issues:
        reason_counts[issue.reason_code] += 1
        _, is_created = upsert_linkage_issue(session, issue)
        if is_created:
            created += 1
        else:
            updated += 1

    return {
        "created": created,
        "updated": updated,
        "reason_counts": dict(reason_counts),
    }


def summarize_queue(session, legacy_source: str, entity_type: str) -> list[dict[str, object]]:
    rows = session.execute(
        select(
            R4LinkageIssue.reason_code,
            R4LinkageIssue.status,
            func.count().label("count"),
        )
        .where(
            R4LinkageIssue.legacy_source == legacy_source,
            R4LinkageIssue.entity_type == entity_type,
        )
        .group_by(R4LinkageIssue.reason_code, R4LinkageIssue.status)
        .order_by(R4LinkageIssue.reason_code, R4LinkageIssue.status)
    ).all()

    return [
        {"reason_code": reason, "status": status, "count": count}
        for reason, status, count in rows
    ]
