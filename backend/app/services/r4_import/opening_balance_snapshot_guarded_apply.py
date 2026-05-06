from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - register ORM relationship targets for CLI sessions
from app.models.invoice import Invoice, Payment
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.patient import Patient
from app.services.r4_import.opening_balance_snapshot_apply_plan import (
    OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
    OPENING_BALANCE_APPLY_REPRESENTATION,
    OPENING_BALANCE_REFERENCE_PREFIX,
    build_opening_balance_snapshot_apply_plan,
)

__all__ = [
    "OpeningBalanceScratchApplyError",
    "build_opening_balance_scratch_apply_payload",
    "compute_sha256",
    "run_opening_balance_scratch_apply",
]


class OpeningBalanceScratchApplyError(RuntimeError):
    pass


@dataclass(frozen=True)
class _PlannedLedgerAdjustment:
    source_patient_code: str
    patient_id: int
    amount_pence: int
    direction: str
    reference: str

    def ledger_kwargs(self, *, actor_id: int, report_sha256: str) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "entry_type": LedgerEntryType.adjustment,
            "amount_pence": self.amount_pence,
            "method": None,
            "reference": self.reference,
            "note": (
                "R4 PatientStats opening-balance scratch apply; "
                f"report_sha256={report_sha256}"
            ),
            "related_invoice_id": None,
            "created_by_user_id": actor_id,
            "updated_by_user_id": actor_id,
        }


def compute_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_opening_balance_scratch_apply_payload(
    *,
    dry_run_report_path: str | Path,
    database_url: str,
    manifest_id: str,
    apply: bool = False,
    confirmation_token: str | None = None,
    actor_id: int | None = None,
    output_json: str | Path | None = None,
    expected_report_sha256: str | None = None,
    expected_total_balance: str | None = None,
    expected_eligible_count: int | None = None,
    expected_repo_sha: str | None = None,
    acknowledge_source_drift: bool = False,
    sample_limit: int = 5,
) -> dict[str, Any]:
    if sample_limit < 1:
        raise OpeningBalanceScratchApplyError("sample_limit must be at least 1.")
    if apply and actor_id is None:
        raise OpeningBalanceScratchApplyError("--actor-id is required with --apply.")

    source_database = ensure_opening_balance_scratch_database_url(database_url)
    report = _load_dry_run_report(dry_run_report_path)
    report_sha256 = compute_sha256(dry_run_report_path)
    _validate_report_identity(
        report,
        report_sha256=report_sha256,
        expected_report_sha256=expected_report_sha256,
        expected_total_balance=expected_total_balance,
        expected_eligible_count=expected_eligible_count,
    )

    candidate_rows = _candidate_rows_from_report(report)
    expected_eligible = _eligible_count(report)
    if expected_eligible is None:
        raise OpeningBalanceScratchApplyError(
            "Dry-run report is missing eligibility_summary.eligible_opening_balance."
        )

    if not apply:
        plan = build_opening_balance_snapshot_apply_plan(
            dry_run_report=report,
            database_target=database_url,
            confirmation_token=confirmation_token,
            manifest_id=manifest_id,
            before_finance_counts=_before_counts_from_report(report),
            source_drift_acknowledged=acknowledge_source_drift,
            candidate_rows=candidate_rows,
            expected_dry_run_repo_sha=expected_repo_sha,
            sample_limit=sample_limit,
        )
        return _payload(
            dry_run_report_path=dry_run_report_path,
            output_json=output_json,
            database_url=database_url,
            source_database=source_database,
            manifest_id=manifest_id,
            report_sha256=report_sha256,
            apply_requested=False,
            plan=plan,
            before_counts=None,
            after_counts=None,
            result_counts={"created": 0, "updated": 0, "skipped": 0, "refused": 0},
            row_source_complete=len(candidate_rows) == expected_eligible,
        )

    if confirmation_token != OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN:
        raise OpeningBalanceScratchApplyError(
            "Scratch opening-balance apply requires "
            "--confirm SCRATCH_OPENING_BALANCE_APPLY."
        )
    if len(candidate_rows) != expected_eligible:
        raise OpeningBalanceScratchApplyError(
            "Dry-run report does not contain every eligible opening-balance row; "
            "rerun the dry-run with a full eligible-row artefact before scratch apply."
        )

    adjustments = _planned_adjustments(candidate_rows, manifest_id=manifest_id)
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        before_counts = _finance_counts(session)
        existing_rows = _existing_manifest_rows(session, manifest_id)
        existing_markers = _existing_other_opening_balance_markers(session, manifest_id)
        plan = build_opening_balance_snapshot_apply_plan(
            dry_run_report=report,
            database_target=database_url,
            confirmation_token=confirmation_token,
            manifest_id=manifest_id,
            before_finance_counts=before_counts,
            source_drift_acknowledged=acknowledge_source_drift,
            candidate_rows=candidate_rows,
            existing_manifest_rows=existing_rows,
            existing_opening_balance_markers=existing_markers,
            expected_dry_run_repo_sha=expected_repo_sha,
            sample_limit=sample_limit,
        )
        if not plan["is_safe_to_apply_in_scratch"]:
            raise OpeningBalanceScratchApplyError(
                "Opening-balance scratch apply preflight refused: "
                + ", ".join(plan["reason_codes"])
            )

        _ensure_patients_exist(session, adjustments)
        created, skipped = _apply_adjustments(
            session,
            adjustments,
            actor_id=int(actor_id),
            report_sha256=report_sha256,
        )
        after_counts = _finance_counts(session)
        expected_ledger_after = before_counts["patient_ledger_entries"] + created
        if after_counts["patient_ledger_entries"] != expected_ledger_after:
            raise OpeningBalanceScratchApplyError(
                "Scratch ledger count mismatch after guarded apply: "
                f"expected {expected_ledger_after}, got "
                f"{after_counts['patient_ledger_entries']}."
            )
        if after_counts["invoices"] != before_counts["invoices"]:
            raise OpeningBalanceScratchApplyError(
                "Scratch apply unexpectedly changed invoice count."
            )
        if after_counts["payments"] != before_counts["payments"]:
            raise OpeningBalanceScratchApplyError(
                "Scratch apply unexpectedly changed payment count."
            )

        payload = _payload(
            dry_run_report_path=dry_run_report_path,
            output_json=output_json,
            database_url=database_url,
            source_database=source_database,
            manifest_id=manifest_id,
            report_sha256=report_sha256,
            apply_requested=True,
            plan=plan,
            before_counts=before_counts,
            after_counts=after_counts,
            result_counts={
                "created": created,
                "updated": 0,
                "skipped": skipped,
                "refused": plan["write_plan_summary"]["would_refuse"],
            },
            row_source_complete=True,
        )
        if output_json:
            _write_json(output_json, payload)
        session.commit()
        return payload
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_opening_balance_scratch_apply(**kwargs: Any) -> dict[str, Any]:
    payload = build_opening_balance_scratch_apply_payload(**kwargs)
    output_json = kwargs.get("output_json")
    if output_json and not payload["summary"]["apply_requested"]:
        _write_json(output_json, payload)
    return payload


def ensure_opening_balance_scratch_database_url(database_url: str) -> str:
    try:
        url = make_url(database_url)
    except Exception as exc:  # pragma: no cover - defensive parser wrapper
        raise OpeningBalanceScratchApplyError("Invalid database URL.") from exc

    database = (url.database or "").strip()
    database_name = Path(database).name if database else ""
    database_key = database_name.lower()
    target_text = " ".join(
        value.lower()
        for value in (
            url.host or "",
            database,
            database_name,
            str(url.query.get("application_name", "")) if url.query else "",
        )
        if value
    )
    forbidden = ("production", "prod", "live")
    if any(marker in target_text for marker in forbidden):
        raise OpeningBalanceScratchApplyError(
            "Opening-balance scratch apply refuses production/live-looking targets."
        )
    if database_key == "dental_pms" or not any(
        marker in database_key for marker in ("scratch", "test")
    ):
        raise OpeningBalanceScratchApplyError(
            "Opening-balance scratch apply requires an explicit scratch/test "
            f"database; refusing database {database_name!r}."
        )
    return database_name


def _load_dry_run_report(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OpeningBalanceScratchApplyError(
            "Dry-run report JSON is invalid."
        ) from exc
    if not isinstance(payload, dict):
        raise OpeningBalanceScratchApplyError(
            "Dry-run report JSON must contain an object."
        )
    return payload


def _validate_report_identity(
    report: Mapping[str, Any],
    *,
    report_sha256: str,
    expected_report_sha256: str | None,
    expected_total_balance: str | None,
    expected_eligible_count: int | None,
) -> None:
    if expected_report_sha256 and report_sha256 != expected_report_sha256:
        raise OpeningBalanceScratchApplyError(
            "Dry-run report SHA256 mismatch: "
            f"expected {expected_report_sha256}, got {report_sha256}."
        )
    if expected_total_balance is not None:
        expected = _decimal(expected_total_balance, "--expected-total-balance")
        observed = _decimal(
            _mapping_value(_mapping_value(report, "source_summary"), "known_totals").get(
                "total_balance"
            ),
            "source_summary.known_totals.total_balance",
        )
        if observed != expected:
            raise OpeningBalanceScratchApplyError(
                "Dry-run report total balance mismatch: "
                f"expected {expected:.2f}, got {observed:.2f}."
            )
    if expected_eligible_count is not None:
        observed = _eligible_count(report)
        if observed != expected_eligible_count:
            raise OpeningBalanceScratchApplyError(
                "Dry-run report eligible count mismatch: "
                f"expected {expected_eligible_count}, got {observed}."
            )


def _candidate_rows_from_report(report: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    samples = _mapping_value(report, "samples").get("eligible_opening_balance")
    if samples is None:
        return ()
    if not isinstance(samples, list) or not all(isinstance(row, Mapping) for row in samples):
        raise OpeningBalanceScratchApplyError(
            "Dry-run report samples.eligible_opening_balance must be a list of objects."
        )
    return tuple(samples)


def _planned_adjustments(
    candidate_rows: tuple[Mapping[str, Any], ...],
    *,
    manifest_id: str,
) -> tuple[_PlannedLedgerAdjustment, ...]:
    rows: list[_PlannedLedgerAdjustment] = []
    seen_references: set[str] = set()
    for row in candidate_rows:
        patient_code = _clean_text(row.get("source_patient_code"))
        patient_id = _positive_int(row.get("mapped_patient_id"), "mapped_patient_id")
        amount_pence = _int_value(row.get("amount_pence"), "amount_pence")
        direction = _clean_text(row.get("proposed_pms_direction"))
        decision = _clean_text(row.get("decision"))
        if decision != "eligible_opening_balance":
            raise OpeningBalanceScratchApplyError(
                "Scratch apply only accepts eligible_opening_balance rows."
            )
        if not patient_code:
            raise OpeningBalanceScratchApplyError(
                "Scratch apply row is missing source_patient_code."
            )
        if amount_pence == 0:
            raise OpeningBalanceScratchApplyError(
                "Scratch apply row unexpectedly has zero amount_pence."
            )
        if amount_pence > 0 and direction != "increase_debt":
            raise OpeningBalanceScratchApplyError(
                "Positive opening-balance amount must increase debt."
            )
        if amount_pence < 0 and direction != "decrease_debt_or_credit":
            raise OpeningBalanceScratchApplyError(
                "Negative opening-balance amount must decrease debt or create credit."
            )
        reference = f"{OPENING_BALANCE_REFERENCE_PREFIX}:{manifest_id}:{patient_code}"
        if reference in seen_references:
            raise OpeningBalanceScratchApplyError(
                "Duplicate opening-balance reference in dry-run artefact."
            )
        seen_references.add(reference)
        rows.append(
            _PlannedLedgerAdjustment(
                source_patient_code=patient_code,
                patient_id=patient_id,
                amount_pence=amount_pence,
                direction=direction,
                reference=reference,
            )
        )
    return tuple(rows)


def _finance_counts(session) -> dict[str, int]:
    return {
        "patient_ledger_entries": _count_table(session, PatientLedgerEntry),
        "invoices": _count_table(session, Invoice),
        "payments": _count_table(session, Payment),
    }


def _count_table(session, model: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _existing_manifest_rows(session, manifest_id: str) -> tuple[dict[str, Any], ...]:
    prefix = f"{OPENING_BALANCE_REFERENCE_PREFIX}:{manifest_id}:"
    rows = session.execute(
        select(PatientLedgerEntry).where(PatientLedgerEntry.reference.like(f"{prefix}%"))
    ).scalars()
    return tuple(_existing_row_dict(row, manifest_id=manifest_id) for row in rows)


def _existing_other_opening_balance_markers(
    session,
    manifest_id: str,
) -> tuple[dict[str, Any], ...]:
    prefix = f"{OPENING_BALANCE_REFERENCE_PREFIX}:{manifest_id}:"
    rows = session.execute(
        select(PatientLedgerEntry).where(
            PatientLedgerEntry.reference.like(f"{OPENING_BALANCE_REFERENCE_PREFIX}:%"),
            PatientLedgerEntry.reference.not_like(f"{prefix}%"),
        )
    ).scalars()
    return tuple(_existing_row_dict(row, manifest_id=None) for row in rows)


def _existing_row_dict(
    row: PatientLedgerEntry,
    *,
    manifest_id: str | None,
) -> dict[str, Any]:
    entry_type = row.entry_type.value if hasattr(row.entry_type, "value") else row.entry_type
    return {
        "manifest_id": manifest_id,
        "entry_type": entry_type,
        "representation": OPENING_BALANCE_APPLY_REPRESENTATION,
        "reference": row.reference,
        "patient_id": row.patient_id,
        "amount_pence": row.amount_pence,
    }


def _ensure_patients_exist(
    session,
    adjustments: tuple[_PlannedLedgerAdjustment, ...],
) -> None:
    patient_ids = {row.patient_id for row in adjustments}
    if not patient_ids:
        return
    existing = set(
        session.execute(select(Patient.id).where(Patient.id.in_(patient_ids))).scalars()
    )
    missing = sorted(patient_ids - existing)
    if missing:
        raise OpeningBalanceScratchApplyError(
            "Scratch apply target is missing mapped patient IDs: "
            + ", ".join(str(value) for value in missing[:10])
        )


def _apply_adjustments(
    session,
    adjustments: tuple[_PlannedLedgerAdjustment, ...],
    *,
    actor_id: int,
    report_sha256: str,
) -> tuple[int, int]:
    existing = {
        row.reference: row
        for row in session.execute(
            select(PatientLedgerEntry).where(
                PatientLedgerEntry.reference.in_([row.reference for row in adjustments])
            )
        ).scalars()
    }
    created = 0
    skipped = 0
    for adjustment in adjustments:
        existing_row = existing.get(adjustment.reference)
        if existing_row is not None:
            _ensure_existing_row_matches(existing_row, adjustment)
            skipped += 1
            continue
        session.add(
            PatientLedgerEntry(
                **adjustment.ledger_kwargs(
                    actor_id=actor_id,
                    report_sha256=report_sha256,
                )
            )
        )
        created += 1
    if created:
        session.flush()
    return created, skipped


def _ensure_existing_row_matches(
    existing: PatientLedgerEntry,
    adjustment: _PlannedLedgerAdjustment,
) -> None:
    entry_type = (
        existing.entry_type.value
        if hasattr(existing.entry_type, "value")
        else existing.entry_type
    )
    if (
        entry_type != LedgerEntryType.adjustment.value
        or existing.patient_id != adjustment.patient_id
        or existing.amount_pence != adjustment.amount_pence
    ):
        raise OpeningBalanceScratchApplyError(
            "Existing opening-balance ledger marker does not match the dry-run plan."
        )


def _payload(
    *,
    dry_run_report_path: str | Path,
    output_json: str | Path | None,
    database_url: str,
    source_database: str,
    manifest_id: str,
    report_sha256: str,
    apply_requested: bool,
    plan: Mapping[str, Any],
    before_counts: Mapping[str, int] | None,
    after_counts: Mapping[str, int] | None,
    result_counts: Mapping[str, int],
    row_source_complete: bool,
) -> dict[str, Any]:
    return {
        "summary": {
            "dry_run_report_json": str(dry_run_report_path),
            "output_json": str(output_json) if output_json else None,
            "database_target": _redact_database_url(database_url),
            "source_database": source_database,
            "manifest_id": manifest_id,
            "report_sha256": report_sha256,
            "scratch_only": True,
            "apply_requested": apply_requested,
            "row_source_complete": row_source_complete,
            "finance_import_ready": False,
            "representation": OPENING_BALANCE_APPLY_REPRESENTATION,
            "result_counts": dict(result_counts),
            "finance_counts": {
                "before": dict(before_counts) if before_counts is not None else None,
                "after": dict(after_counts) if after_counts is not None else None,
            },
            "write_intent": {
                "invoices": 0,
                "payments": 0,
                "staging_models": 0,
                "balance_mutation_outside_ledger_adjustment": False,
            },
        },
        "preflight_plan": _jsonable(plan),
    }


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _before_counts_from_report(report: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = report.get("before_finance_counts")
    if isinstance(value, Mapping):
        return value
    value = report.get("finance_counts_before")
    if isinstance(value, Mapping):
        return value
    finance_counts = report.get("finance_counts")
    if isinstance(finance_counts, Mapping):
        before = finance_counts.get("before")
        if isinstance(before, Mapping):
            return before
    return None


def _eligible_count(report: Mapping[str, Any]) -> int | None:
    value = _mapping_value(report, "eligibility_summary").get("eligible_opening_balance")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _mapping_value(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    return value if isinstance(value, Mapping) else {}


def _decimal(value: Any, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise OpeningBalanceScratchApplyError(f"Invalid decimal for {label}.") from exc
    if not parsed.is_finite():
        raise OpeningBalanceScratchApplyError(f"Invalid decimal for {label}.")
    return parsed


def _positive_int(value: Any, label: str) -> int:
    parsed = _int_value(value, label)
    if parsed <= 0:
        raise OpeningBalanceScratchApplyError(f"{label} must be a positive integer.")
    return parsed


def _int_value(value: Any, label: str) -> int:
    if isinstance(value, bool) or value is None:
        raise OpeningBalanceScratchApplyError(f"{label} must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise OpeningBalanceScratchApplyError(f"{label} must be an integer.") from exc


def _clean_text(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _redact_database_url(database_url: str) -> str:
    try:
        return make_url(database_url).render_as_string(hide_password=True)
    except Exception:  # pragma: no cover - summary best effort
        return "<invalid database url>"


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value
