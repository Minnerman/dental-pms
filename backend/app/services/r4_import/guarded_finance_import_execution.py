from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = [
    "GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN",
    "GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN",
    "LIVE_DENTAL_PMS_TARGET_CLASSIFICATION",
    "GuardedFinanceImportExecutionError",
    "build_guarded_finance_import_execution_result",
    "build_guarded_finance_import_execution_packet",
    "compute_sha256",
    "load_execution_manifest",
    "load_opening_balance_report",
    "write_classification_packet",
]


GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN = (
    "GUARDED_FINANCE_IMPORT_APPLY"
)
GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN = (
    "OWNER_AUTHORISED_PRODUCTION_FINANCE_IMPORT"
)
LIVE_DENTAL_PMS_TARGET_CLASSIFICATION = "dental-pms-live-main"
_OPENING_BALANCE_REFERENCE_PREFIX = "R4OB"

_SUPPORTED_CATEGORY = "opening-balance"
_UNSUPPORTED_CATEGORY_REASONS = {
    "invoice": "invoice_import_not_supported_by_guarded_path",
    "payment": "payment_import_not_supported_by_guarded_path",
    "staging": "staging_import_not_supported_by_guarded_path",
}
_LIVE_TARGETS = {
    LIVE_DENTAL_PMS_TARGET_CLASSIFICATION,
}
_UNCLEAR_OR_REFUSED_TARGETS = {
    "production",
    "live",
    "default",
    "live-default",
    "live/default",
    "actual-production-postgres",
    "r4",
    "r4-live",
    "r4-main",
}
_SAFE_NON_LIVE_TARGETS = {"scratch", "test", "non-live", "nonlive"}


class GuardedFinanceImportExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class _OpeningBalanceAdjustment:
    patient_id: int
    amount_pence: int
    reference: str

    def ledger_kwargs(self, *, actor_id: int, report_sha256: str) -> dict[str, Any]:
        from app.models.ledger import LedgerEntryType

        return {
            "patient_id": self.patient_id,
            "entry_type": LedgerEntryType.adjustment,
            "amount_pence": self.amount_pence,
            "method": None,
            "reference": self.reference,
            "note": (
                "Guarded live opening-balance import; "
                f"report_sha256={report_sha256}"
            ),
            "related_invoice_id": None,
            "created_by_user_id": actor_id,
            "updated_by_user_id": actor_id,
        }


def load_execution_manifest(path: str | Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise GuardedFinanceImportExecutionError(
            "Execution manifest is missing or unreadable."
        ) from exc
    except json.JSONDecodeError as exc:
        raise GuardedFinanceImportExecutionError(
            "Execution manifest JSON is invalid."
        ) from exc
    if not isinstance(payload, Mapping):
        raise GuardedFinanceImportExecutionError(
            "Execution manifest JSON must contain an object."
        )
    return payload


def load_opening_balance_report(path: str | Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise GuardedFinanceImportExecutionError(
            "Opening-balance report is missing or unreadable."
        ) from exc
    except json.JSONDecodeError as exc:
        raise GuardedFinanceImportExecutionError(
            "Opening-balance report JSON is invalid."
        ) from exc
    if not isinstance(payload, Mapping):
        raise GuardedFinanceImportExecutionError(
            "Opening-balance report JSON must contain an object."
        )
    return payload


def compute_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_guarded_finance_import_execution_packet(
    *,
    manifest: Mapping[str, Any] | None,
    import_category: str | None,
    target_classification: str | None,
    apply_requested: bool = False,
    apply_confirmation: str | None = None,
    production_execution_gate: str | None = None,
    no_secrets_exposed: bool = False,
    no_patient_data_exposed: bool = False,
    no_private_paths_exposed: bool = False,
    no_backup_contents_exposed: bool = False,
) -> dict[str, Any]:
    """Build a classification-only finance/import execution readiness packet.

    This helper is intentionally pure: it does not open databases, read R4,
    inspect production, or execute import work. It validates the operator's
    future execution inputs and fails closed before any later writer can run.
    """

    reasons: list[str] = []
    blockers: list[str] = []
    manifest_obj = manifest if isinstance(manifest, Mapping) else {}
    if not manifest_obj:
        blockers.append("manifest_missing_or_unclear")

    category = _normalize(import_category) or _manifest_category(manifest_obj)
    if category is None:
        blockers.append("import_category_missing_or_unclear")
    elif category != _SUPPORTED_CATEGORY:
        blockers.append(
            _UNSUPPORTED_CATEGORY_REASONS.get(
                category,
                "unsupported_import_category",
            )
        )
    else:
        reasons.append("opening_balance_category_supported")

    manifest_id = _manifest_id(manifest_obj)
    if manifest_obj and manifest_id is None:
        blockers.append("manifest_id_missing_or_unclear")

    if _manifest_declares_sensitive_committed_data(manifest_obj):
        blockers.append("manifest_declares_sensitive_committed_data")

    target = _normalize(target_classification) or _manifest_target(manifest_obj)
    if target is None:
        blockers.append("target_classification_missing_or_unclear")
    elif target in _LIVE_TARGETS:
        if production_execution_gate == GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN:
            reasons.append("production_execution_gate_accepted")
        else:
            blockers.append("production_execution_gate_required")
    elif target in _UNCLEAR_OR_REFUSED_TARGETS:
        blockers.append("target_classification_refused")
    elif target in _SAFE_NON_LIVE_TARGETS:
        reasons.append("non_live_target_classification_accepted")
    else:
        blockers.append("target_classification_unclear")

    if apply_requested:
        if apply_confirmation == GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN:
            reasons.append("apply_confirmation_accepted")
        else:
            blockers.append("apply_confirmation_required")
    else:
        reasons.append("default_dry_run_no_write")

    safety_confirmations = {
        "No secrets exposed": _yes_no(no_secrets_exposed),
        "No patient data exposed": _yes_no(no_patient_data_exposed),
        "No private paths exposed": _yes_no(no_private_paths_exposed),
        "No backup contents exposed": _yes_no(no_backup_contents_exposed),
    }
    for label, value in safety_confirmations.items():
        if value != "yes":
            blockers.append(_safety_blocker(label))

    opening_balance_ready = (
        "ready"
        if category == _SUPPORTED_CATEGORY and not blockers
        else "blocked"
    )
    invoice_payment_staging_ready = "blocked"

    if blockers:
        blocker_classification = "; ".join(dict.fromkeys(blockers))
    else:
        blocker_classification = (
            "invoice/payment/staging import remains blocked by this guarded "
            "path; import execution has not run"
        )

    if reasons:
        reason_classification = "; ".join(dict.fromkeys(reasons))
    else:
        reason_classification = "guarded finance/import execution gate failed closed"

    return {
        "Guarded finance/import process available": "yes",
        "Opening-balance/live finance import execution readiness": (
            opening_balance_ready
        ),
        "Invoice/payment/staging import execution readiness": (
            invoice_payment_staging_ready
        ),
        "finance_import_ready": False,
        "Apply/write mode requested": _yes_no(apply_requested),
        "Execution performed": "no",
        "Reason classification": reason_classification,
        "Blocker classification": blocker_classification,
        **safety_confirmations,
    }


def build_guarded_finance_import_execution_result(
    *,
    manifest: Mapping[str, Any] | None,
    opening_balance_report: Mapping[str, Any] | None,
    target_classification: str | None,
    database_url: str | None = None,
    apply_requested: bool = False,
    apply_confirmation: str | None = None,
    production_execution_gate: str | None = None,
    actor_id: int | None = None,
    expected_report_sha256: str | None = None,
    observed_report_sha256: str | None = None,
    expected_total_balance: str | None = None,
    expected_eligible_count: int | None = None,
    expected_repo_sha: str | None = None,
    no_secrets_exposed: bool = False,
    no_patient_data_exposed: bool = False,
    no_private_paths_exposed: bool = False,
    no_backup_contents_exposed: bool = False,
) -> dict[str, Any]:
    manifest_obj = manifest if isinstance(manifest, Mapping) else {}
    report_obj = opening_balance_report if isinstance(opening_balance_report, Mapping) else {}
    readiness = build_guarded_finance_import_execution_packet(
        manifest=manifest_obj,
        import_category="opening-balance",
        target_classification=target_classification,
        apply_requested=apply_requested,
        apply_confirmation=apply_confirmation,
        production_execution_gate=production_execution_gate,
        no_secrets_exposed=no_secrets_exposed,
        no_patient_data_exposed=no_patient_data_exposed,
        no_private_paths_exposed=no_private_paths_exposed,
        no_backup_contents_exposed=no_backup_contents_exposed,
    )
    blockers = _split_classification(readiness["Blocker classification"])
    reasons = _split_classification(readiness["Reason classification"])

    manifest_id = _manifest_id(manifest_obj)
    if not report_obj:
        blockers.append("opening_balance_report_missing_or_unclear")
    else:
        _validate_report_contract(
            report_obj,
            blockers=blockers,
            reasons=reasons,
            expected_report_sha256=expected_report_sha256,
            observed_report_sha256=observed_report_sha256,
            expected_total_balance=expected_total_balance,
            expected_eligible_count=expected_eligible_count,
            expected_repo_sha=expected_repo_sha,
        )

    adjustments: tuple[_OpeningBalanceAdjustment, ...] = ()
    if report_obj and manifest_id:
        adjustments = _opening_balance_adjustments(report_obj, manifest_id, blockers)

    result_counts = {"created": 0, "updated": 0, "skipped": 0, "refused": 0}
    execution_result = "not checked"
    rollback_required = "no"
    rollback_executed = "not required"
    import_write_state_after_failed_run = "unknown"
    mapped_patient_target_remediation_status = "pending"

    if apply_requested:
        if actor_id is None:
            blockers.append("actor_id_required")
        if not database_url:
            blockers.append("database_url_env_missing")
        if blockers:
            execution_result = "blocked"
        else:
            try:
                _check_opening_balance_target_patient_coverage(
                    database_url=str(database_url),
                    adjustments=adjustments,
                )
                mapped_patient_target_remediation_status = "remediated"
                reasons.append("mapped_patient_target_coverage_confirmed")
                created, skipped = _apply_opening_balance_adjustments(
                    database_url=str(database_url),
                    adjustments=adjustments,
                    manifest_id=str(manifest_id),
                    actor_id=int(actor_id),
                    report_sha256=observed_report_sha256 or "not-recorded",
                )
                result_counts = {
                    "created": created,
                    "updated": 0,
                    "skipped": skipped,
                    "refused": 0,
                }
                execution_result = "pass"
                reasons.append("opening_balance_live_import_apply_completed")
            except GuardedFinanceImportExecutionError as exc:
                error_classification = str(exc)
                if error_classification == "mapped_patient_missing_in_target":
                    execution_result = "blocked"
                    rollback_required = "no"
                    rollback_executed = "not required"
                    import_write_state_after_failed_run = "no writes"
                    mapped_patient_target_remediation_status = "blocked"
                else:
                    execution_result = "fail"
                    rollback_required = "yes"
                    rollback_executed = "no"
                blockers.append(error_classification)
    elif blockers:
        execution_result = "blocked"

    opening_balance_readiness = (
        "ready" if readiness["Opening-balance/live finance import execution readiness"] == "ready"
        and not _blocking_without_apply_only(blockers)
        else "blocked"
    )
    if apply_requested and execution_result == "pass":
        opening_balance_readiness = "ready"

    return {
        "Guarded finance/import process available": "yes",
        "Opening-balance/live finance import execution readiness": (
            opening_balance_readiness
        ),
        "Opening-balance/live finance import execution result": execution_result,
        "Invoice/payment/staging import execution readiness": "blocked",
        "Invoice/payment/staging import execution result": "blocked",
        "finance_import_ready": (
            apply_requested and execution_result == "pass" and not blockers
        ),
        "Rollback required": rollback_required,
        "Rollback executed": rollback_executed,
        "Import write-state after failed run": import_write_state_after_failed_run,
        "Mapped patient target remediation status": (
            mapped_patient_target_remediation_status
        ),
        "Result counts classification": dict(result_counts),
        "Reason classification": (
            "; ".join(dict.fromkeys(reasons))
            if reasons
            else "guarded opening-balance execution failed closed"
        ),
        "Blocker classification": (
            "; ".join(dict.fromkeys(blockers))
            if blockers
            else "invoice/payment/staging import remains blocked by this guarded path"
        ),
        "No secrets exposed": readiness["No secrets exposed"],
        "No patient data exposed": readiness["No patient data exposed"],
        "No private paths exposed": readiness["No private paths exposed"],
        "No backup contents exposed": readiness["No backup contents exposed"],
    }


def write_classification_packet(path: str | Path, packet: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dict(packet), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _manifest_category(manifest: Mapping[str, Any]) -> str | None:
    for value in (
        manifest.get("import_category"),
        manifest.get("category"),
        _nested(manifest, "execution", "import_category"),
        _nested(manifest, "evidence_requirements", "import_category"),
    ):
        normalized = _normalize(value)
        if normalized:
            return normalized
    return None


def _manifest_id(manifest: Mapping[str, Any]) -> str | None:
    for value in (
        manifest.get("manifest_id"),
        _nested(manifest, "fixture", "manifest_id"),
        _nested(manifest, "evidence_requirements", "manifest_id"),
        _nested(manifest, "manifest", "manifest_id"),
    ):
        text = _clean_text(value)
        if text:
            return text
    return None


def _manifest_target(manifest: Mapping[str, Any]) -> str | None:
    for value in (
        manifest.get("target_classification"),
        _nested(manifest, "target", "classification"),
        _nested(manifest, "evidence_requirements", "target_classification"),
    ):
        normalized = _normalize(value)
        if normalized:
            return normalized.replace("_", "-")
    return None


def _manifest_declares_sensitive_committed_data(manifest: Mapping[str, Any]) -> bool:
    sensitive_policy = _mapping(manifest.get("sensitive_data_policy"))
    safety = _mapping(manifest.get("safety"))
    return any(
        value is True
        for value in (
            sensitive_policy.get("committed_fixture_contains_real_r4_data"),
            sensitive_policy.get("committed_fixture_contains_real_patient_data"),
            safety.get("real_patient_data"),
            safety.get("real_r4_artifact"),
        )
    )


def _validate_report_contract(
    report: Mapping[str, Any],
    *,
    blockers: list[str],
    reasons: list[str],
    expected_report_sha256: str | None,
    observed_report_sha256: str | None,
    expected_total_balance: str | None,
    expected_eligible_count: int | None,
    expected_repo_sha: str | None,
) -> None:
    if report.get("dry_run") is True:
        reasons.append("dry_run_report_confirmed")
    else:
        blockers.append("dry_run_report_required")
    if report.get("import_ready") is False:
        reasons.append("import_ready_false_confirmed")
    else:
        blockers.append("import_ready_false_required")
    if report.get("finance_import_ready") is False:
        reasons.append("finance_import_ready_false_confirmed")
    elif report.get("finance_import_ready") is True:
        blockers.append("finance_import_ready_true_refused")

    manifest = _mapping(report.get("manifest"))
    if manifest.get("no_write") is not True:
        blockers.append("report_manifest_no_write_required")
    if manifest.get("apply_mode") is not False:
        blockers.append("report_manifest_apply_mode_false_required")
    repo_sha = _clean_text(manifest.get("repo_sha"))
    if expected_repo_sha and repo_sha != expected_repo_sha:
        blockers.append("report_repo_sha_mismatch")
    elif repo_sha:
        reasons.append("report_repo_sha_present")
    else:
        blockers.append("report_repo_sha_missing")

    if expected_report_sha256 and observed_report_sha256 != expected_report_sha256:
        blockers.append("report_sha256_mismatch")
    elif expected_report_sha256:
        reasons.append("report_sha256_confirmed")

    eligible_count = _eligible_count(report)
    if expected_eligible_count is not None and eligible_count != expected_eligible_count:
        blockers.append("eligible_count_mismatch")
    elif eligible_count is not None:
        reasons.append("eligible_count_confirmed")
    else:
        blockers.append("eligible_count_missing")

    total_balance = _clean_text(
        _mapping(_mapping(report.get("source_summary")).get("known_totals")).get(
            "total_balance"
        )
    )
    if expected_total_balance is not None and total_balance != expected_total_balance:
        blockers.append("expected_total_balance_mismatch")
    elif total_balance is not None:
        reasons.append("expected_total_balance_present")

    mapping_summary = _mapping(report.get("mapping_summary"))
    unmapped = _int_value(mapping_summary.get("unmapped_nonzero_candidates"))
    coverage = _clean_text(mapping_summary.get("nonzero_mapping_coverage"))
    if unmapped == 0 and coverage == "1.0000":
        reasons.append("nonzero_mapping_coverage_complete")
    else:
        blockers.append("nonzero_mapping_coverage_incomplete")

    eligibility = _mapping(report.get("eligibility_summary"))
    if _int_value(eligibility.get("component_mismatch_would_write_count")):
        blockers.append("component_mismatch_would_write_refused")
    if _int_value(eligibility.get("ambiguous_sign_would_write_count")):
        blockers.append("ambiguous_sign_would_write_refused")

    samples = _candidate_rows(report)
    if eligible_count is None or len(samples) != eligible_count:
        blockers.append("full_eligible_row_source_required")
    else:
        reasons.append("full_eligible_row_source_confirmed")


def _opening_balance_adjustments(
    report: Mapping[str, Any],
    manifest_id: str,
    blockers: list[str],
) -> tuple[_OpeningBalanceAdjustment, ...]:
    adjustments: list[_OpeningBalanceAdjustment] = []
    references: set[str] = set()
    for row in _candidate_rows(report):
        if _clean_text(row.get("decision")) != "eligible_opening_balance":
            blockers.append("non_eligible_opening_balance_row_refused")
            continue
        patient_id = _positive_int(row.get("mapped_patient_id"))
        amount = _int_value(row.get("amount_pence"))
        direction = _clean_text(row.get("proposed_pms_direction"))
        patient_code = _clean_text(row.get("source_patient_code"))
        if patient_id is None or amount is None or not direction or not patient_code:
            blockers.append("eligible_row_missing_required_fields")
            continue
        if amount == 0:
            blockers.append("zero_amount_row_refused")
            continue
        if amount > 0 and direction != "increase_debt":
            blockers.append("positive_amount_direction_refused")
            continue
        if amount < 0 and direction != "decrease_debt_or_credit":
            blockers.append("negative_amount_direction_refused")
            continue
        reference = f"{_OPENING_BALANCE_REFERENCE_PREFIX}:{manifest_id}:{patient_code}"
        if reference in references:
            blockers.append("duplicate_opening_balance_reference_refused")
            continue
        references.add(reference)
        adjustments.append(
            _OpeningBalanceAdjustment(
                patient_id=patient_id,
                amount_pence=amount,
                reference=reference,
            )
        )
    return tuple(adjustments)


def _check_opening_balance_target_patient_coverage(
    *,
    database_url: str,
    adjustments: tuple[_OpeningBalanceAdjustment, ...],
) -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    import app.models  # noqa: F401 - register ORM relationship targets
    from app.models.patient import Patient

    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        patient_ids = {row.patient_id for row in adjustments}
        existing_patients = set(
            session.execute(
                select(Patient.id).where(Patient.id.in_(patient_ids))
            ).scalars()
        )
        if patient_ids - existing_patients:
            raise GuardedFinanceImportExecutionError("mapped_patient_missing_in_target")
    finally:
        session.close()
        engine.dispose()


def _apply_opening_balance_adjustments(
    *,
    database_url: str,
    adjustments: tuple[_OpeningBalanceAdjustment, ...],
    manifest_id: str,
    actor_id: int,
    report_sha256: str,
) -> tuple[int, int]:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    import app.models  # noqa: F401 - register ORM relationship targets
    from app.models.ledger import PatientLedgerEntry

    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        existing_other = tuple(
            session.execute(
                select(PatientLedgerEntry.reference).where(
                    PatientLedgerEntry.reference.like(
                        f"{_OPENING_BALANCE_REFERENCE_PREFIX}:%"
                    ),
                    PatientLedgerEntry.reference.not_like(
                        f"{_OPENING_BALANCE_REFERENCE_PREFIX}:{manifest_id}:%"
                    ),
                )
            ).scalars()
        )
        if existing_other:
            raise GuardedFinanceImportExecutionError(
                "existing_opening_balance_marker_refused"
            )

        existing_rows = {
            row.reference: row
            for row in session.execute(
                select(PatientLedgerEntry).where(
                    PatientLedgerEntry.reference.in_(
                        [row.reference for row in adjustments]
                    )
                )
            ).scalars()
        }
        created = 0
        skipped = 0
        for adjustment in adjustments:
            existing = existing_rows.get(adjustment.reference)
            if existing is not None:
                _ensure_existing_matches(existing, adjustment)
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
        session.commit()
        return created, skipped
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def _ensure_existing_matches(
    existing: Any,
    adjustment: _OpeningBalanceAdjustment,
) -> None:
    from app.models.ledger import LedgerEntryType

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
        raise GuardedFinanceImportExecutionError(
            "existing_opening_balance_marker_mismatch_refused"
        )


def _candidate_rows(report: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows = _mapping(report.get("samples")).get("eligible_opening_balance")
    if not isinstance(rows, list):
        return ()
    return tuple(row for row in rows if isinstance(row, Mapping))


def _eligible_count(report: Mapping[str, Any]) -> int | None:
    return _int_value(
        _mapping(report.get("eligibility_summary")).get("eligible_opening_balance")
    )


def _split_classification(value: Any) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    if text == "invoice/payment/staging import remains blocked by this guarded path; import execution has not run":
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def _blocking_without_apply_only(blockers: list[str]) -> list[str]:
    return [blocker for blocker in blockers if blocker != "apply_confirmation_required"]


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalize(value: Any) -> str | None:
    text = _clean_text(value)
    return text.lower().replace("_", "-") if text else None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _positive_int(value: Any) -> int | None:
    parsed = _int_value(value)
    return parsed if parsed is not None and parsed > 0 else None


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _safety_blocker(label: str) -> str:
    return label.lower().replace(" ", "_") + "_not_confirmed"
