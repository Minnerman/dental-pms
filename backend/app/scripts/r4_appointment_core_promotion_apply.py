from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from sqlalchemy import func, select

from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.r4_appointment import R4Appointment
from app.models.r4_appointment_patient_link import R4AppointmentPatientLink
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.user import User
from app.services.appointment_conflicts import ExistingAppointmentConflict
from app.services.r4_import.appointment_core_promotion_apply import (
    GUARDED_CORE_PROMOTION_CONFIRMATION,
    GuardedCoreAppointmentPromotionApplyPlan,
    build_guarded_core_appointment_promotion_apply_plan,
    build_scratch_core_appointment_models_for_guarded_apply,
)
from app.services.r4_import.appointment_promotion_dryrun import (
    ensure_scratch_database_url,
)


def _count_core_appointments(session) -> int:
    return int(session.scalar(select(func.count()).select_from(Appointment)) or 0)


def _resolve_actor_id(session, actor_id: int | None) -> int:
    if actor_id is not None:
        return actor_id
    resolved = session.scalar(select(func.min(User.id)))
    if not resolved:
        raise RuntimeError(
            "No users found; cannot attribute scratch appointment promotion."
        )
    return int(resolved)


def _load_patient_mapping(session, legacy_source: str) -> dict[int, int]:
    rows = session.execute(
        select(R4PatientMapping.legacy_patient_code, R4PatientMapping.patient_id).where(
            R4PatientMapping.legacy_source == legacy_source
        )
    ).all()
    return {int(code): int(patient_id) for code, patient_id in rows}


def _load_appointment_patient_links(session, legacy_source: str) -> dict[int, int]:
    rows = session.execute(
        select(
            R4AppointmentPatientLink.legacy_appointment_id,
            R4AppointmentPatientLink.patient_id,
        ).where(R4AppointmentPatientLink.legacy_source == legacy_source)
    ).all()
    return {
        int(appointment_id): int(patient_id)
        for appointment_id, patient_id in rows
    }


def _load_r4_appointments(
    session,
    *,
    legacy_source: str,
    limit: int | None,
) -> tuple[R4Appointment, ...]:
    stmt = (
        select(R4Appointment)
        .where(R4Appointment.legacy_source == legacy_source)
        .order_by(
            R4Appointment.starts_at.asc(),
            R4Appointment.legacy_appointment_id.asc(),
        )
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return tuple(session.execute(stmt).scalars())


def _load_existing_core_legacy_ids(session, legacy_source: str) -> tuple[str, ...]:
    rows = session.execute(
        select(Appointment.legacy_id).where(
            Appointment.legacy_source == legacy_source,
            Appointment.legacy_id.is_not(None),
        )
    ).scalars()
    return tuple(str(value) for value in rows if value is not None)


def _load_existing_core_conflicts(session) -> tuple[ExistingAppointmentConflict, ...]:
    rows = session.execute(
        select(
            Appointment.starts_at,
            Appointment.ends_at,
            Appointment.status,
            Appointment.clinician_user_id,
            Appointment.patient_id,
            Appointment.deleted_at,
        )
    ).all()
    return tuple(
        ExistingAppointmentConflict(
            starts_at=starts_at,
            ends_at=ends_at,
            status=status,
            clinician_user_id=clinician_user_id,
            patient_id=patient_id,
            deleted=deleted_at is not None,
        )
        for starts_at, ends_at, status, clinician_user_id, patient_id, deleted_at in rows
    )


def _load_json_mapping(path: str | None) -> dict[str, int]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("--clinician-user-mapping-json must contain a JSON object.")
    mapping: dict[str, int] = {}
    for key, value in payload.items():
        cleaned_key = str(key).strip()
        if not cleaned_key:
            raise RuntimeError("--clinician-user-mapping-json contains a blank key.")
        try:
            mapping[cleaned_key] = int(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "--clinician-user-mapping-json values must be integer PMS user IDs."
            ) from exc
    return mapping


def _load_dryrun_report(path: str, *, source_database: str) -> dict[str, Any]:
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise RuntimeError("--dryrun-report-json must contain a JSON object.")
    report_database = report.get("source_database")
    if report_database is not None and str(report_database) != source_database:
        raise RuntimeError(
            "Promotion dry-run report source_database does not match target scratch DB: "
            f"{report_database!r} != {source_database!r}."
        )
    return report


def _apply_plan_to_session(
    session,
    plan: GuardedCoreAppointmentPromotionApplyPlan,
    *,
    actor_id: int,
) -> dict[str, int]:
    models = build_scratch_core_appointment_models_for_guarded_apply(
        plan,
        actor_id=actor_id,
    )
    if models:
        session.add_all(models)
        session.flush()
    return {
        "created": len(models),
        "updated": 0,
        "skipped": plan.skipped_count,
        "refused": plan.refused_count,
    }


def _write_json(path: str, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _summary_payload(
    *,
    output_json: str,
    source_database: str,
    legacy_source: str,
    core_before: int,
    core_after: int,
    result_counts: Mapping[str, int],
    plan: GuardedCoreAppointmentPromotionApplyPlan,
) -> dict[str, Any]:
    return {
        "output_json": output_json,
        "source_database": source_database,
        "legacy_source": legacy_source,
        "scratch_only": True,
        "core_appointments": {
            "before": core_before,
            "after": core_after,
            "delta": core_after - core_before,
            "expected_after": plan.expected_core_appointments_after,
        },
        "result_counts": dict(result_counts),
        "action_counts": plan.action_counts,
        "reason_counts": plan.reason_counts,
        "promotion_plan_action_counts": plan.promotion_plan_action_counts,
        "promotion_plan_reason_counts": plan.promotion_plan_reason_counts,
    }


def run_apply(
    *,
    dryrun_report_json: str,
    output_json: str,
    confirm: str,
    actor_id: int | None = None,
    legacy_source: str = "r4",
    limit: int | None = None,
    sample_limit: int = 10,
    clinician_user_mapping_json: str | None = None,
    require_clinician_user_mapping: bool = False,
) -> dict[str, Any]:
    source_database = ensure_scratch_database_url(settings.database_url)
    dryrun_report = _load_dryrun_report(
        dryrun_report_json,
        source_database=source_database,
    )
    clinician_mapping = _load_json_mapping(clinician_user_mapping_json)

    session = SessionLocal()
    try:
        resolved_actor_id = _resolve_actor_id(session, actor_id)
        core_before = _count_core_appointments(session)
        rows = _load_r4_appointments(
            session,
            legacy_source=legacy_source,
            limit=limit,
        )
        plan = build_guarded_core_appointment_promotion_apply_plan(
            rows,
            database_url=settings.database_url,
            confirm=confirm,
            dryrun_report=dryrun_report,
            patient_mapping=_load_patient_mapping(session, legacy_source),
            appointment_patient_links=_load_appointment_patient_links(
                session,
                legacy_source,
            ),
            clinician_user_mapping=clinician_mapping,
            require_clinician_user_mapping=require_clinician_user_mapping,
            existing_core_appointments=_load_existing_core_conflicts(session),
            existing_core_legacy_ids=_load_existing_core_legacy_ids(
                session,
                legacy_source,
            ),
            legacy_source=legacy_source,
            core_appointments_before=core_before,
            sample_limit=sample_limit,
        )
        result_counts = _apply_plan_to_session(session, plan, actor_id=resolved_actor_id)
        core_after = _count_core_appointments(session)
        expected_after = core_before + result_counts["created"]
        if core_after != expected_after:
            raise RuntimeError(
                "Scratch core appointment count mismatch after guarded apply: "
                f"expected {expected_after}, got {core_after}."
            )

        payload = {
            "summary": _summary_payload(
                output_json=output_json,
                source_database=source_database,
                legacy_source=legacy_source,
                core_before=core_before,
                core_after=core_after,
                result_counts=result_counts,
                plan=plan,
            ),
            "plan": plan.as_dict(),
        }
        _write_json(output_json, payload)
        session.commit()
        return payload
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scratch-only guarded R4 appointment core promotion apply. The command "
            "reads imported r4_appointments staging rows, validates the prior "
            "no-core-write promotion dry-run report, refuses default/live DBs, "
            "and writes core appointments only to a scratch/test PMS DB."
        )
    )
    parser.add_argument(
        "--dryrun-report-json",
        required=True,
        help="Path to the prior no-core-write promotion dry-run JSON report.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write guarded scratch apply JSON output.",
    )
    parser.add_argument(
        "--confirm",
        required=True,
        help="Required confirmation token; must be SCRATCH_APPLY.",
    )
    parser.add_argument(
        "--legacy-source",
        default="r4",
        help="Legacy source tag to read/write (default: r4).",
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
        help="Maximum sample legacy IDs per reason.",
    )
    parser.add_argument(
        "--actor-id",
        type=int,
        default=None,
        help="Optional PMS user ID for audit fields; defaults to the minimum user ID.",
    )
    parser.add_argument(
        "--clinician-user-mapping-json",
        default=None,
        help="Optional JSON object mapping R4 clinician codes to PMS user IDs.",
    )
    parser.add_argument(
        "--require-clinician-user-mapping",
        action="store_true",
        help="Refuse apply unless every clinician-coded promote candidate maps to a PMS user.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1 when provided.")
    if args.sample_limit < 1:
        parser.error("--sample-limit must be at least 1.")
    if args.confirm != GUARDED_CORE_PROMOTION_CONFIRMATION:
        parser.error("Refusing to apply without --confirm SCRATCH_APPLY.")

    payload = run_apply(
        dryrun_report_json=args.dryrun_report_json,
        output_json=args.output_json,
        confirm=args.confirm,
        actor_id=args.actor_id,
        legacy_source=args.legacy_source,
        limit=args.limit,
        sample_limit=args.sample_limit,
        clinician_user_mapping_json=args.clinician_user_mapping_json,
        require_clinician_user_mapping=args.require_clinician_user_mapping,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
