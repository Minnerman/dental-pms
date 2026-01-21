from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.importer import import_r4
from app.services.r4_import.mapping_quality import PatientMappingQualityReportBuilder
from app.services.r4_import.patient_importer import import_r4_patients
from app.services.r4_import.postgres_verify import verify_patients_window
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource
from app.services.r4_import.treatment_transactions_importer import (
    import_r4_treatment_transactions,
)
from app.services.r4_import.treatment_plan_importer import (
    backfill_r4_treatment_plan_patients,
    import_r4_treatment_plans,
    import_r4_treatments,
    summarize_r4_treatment_plans,
)


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def _parse_date_arg(value: str) -> date:
    return date.fromisoformat(value)


def _build_patients_mapping_quality(
    source,
    patients_from: int | None,
    patients_to: int | None,
    limit: int | None,
) -> dict[str, object]:
    report = PatientMappingQualityReportBuilder()
    for patient in source.stream_patients(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        report.ingest(patient)
    return report.finalize()


def _write_mapping_quality_file(path: str, payload: dict[str, object]) -> None:
    target = Path(path)
    parent = target.parent
    if parent and not parent.exists():
        raise RuntimeError(f"Mapping quality output directory does not exist: {parent}")
    data = json.dumps(payload, indent=2, sort_keys=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(parent) if parent else None,
    ) as handle:
        handle.write(data)
        handle.write("\n")
        tmp_path = handle.name
    os.replace(tmp_path, target)


def _maybe_write_mapping_quality(
    path: str | None,
    mapping_quality: dict[str, object] | None,
    patients_from: int | None,
    patients_to: int | None,
) -> None:
    if not path:
        return
    if mapping_quality is None:
        raise RuntimeError("Mapping quality output requested, but no report was generated.")
    payload = {
        "entity": "patients",
        "window": {
            "patients_from": patients_from,
            "patients_to": patients_to,
        },
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mapping_quality": mapping_quality,
    }
    _write_mapping_quality_file(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import R4 data into the PMS.")
    parser.add_argument(
        "--source",
        default="fixtures",
        choices=("fixtures", "sqlserver"),
        help="Import source (fixtures or sqlserver).",
    )
    parser.add_argument(
        "--entity",
        default="patients_appts",
        choices=(
            "patients",
            "patients_appts",
            "treatments",
            "treatment_transactions",
            "treatment_plans",
            "treatment_plans_summary",
            "treatment_plans_backfill_patient_ids",
        ),
        help="Entity to import (default: patients_appts).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="For SQL Server source, run a read-only connectivity check and stats summary.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply SQL Server data to Postgres via the importer (explicitly gated).",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help="Safety latch for apply mode (must be 'APPLY').",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit rows for dry-run samples (or apply if specified).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for treatment plan imports (default: 1000).",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=0,
        help="Optional sleep per batch in milliseconds (default: 0).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=5000,
        help="Progress update frequency in items/plans (default: 5000).",
    )
    parser.add_argument(
        "--mapping-quality-out",
        dest="mapping_quality_out",
        default=None,
        help="Write patients mapping quality JSON to PATH (patients entity only).",
    )
    parser.add_argument(
        "--verify-postgres",
        action="store_true",
        help="Verify patients in Postgres for a window (no SQL Server connection).",
    )
    parser.add_argument(
        "--connect-timeout-seconds",
        type=int,
        default=None,
        help="Override SQL Server connection timeout in seconds (sqlserver source only).",
    )
    parser.add_argument(
        "--patients-from",
        dest="patients_from",
        type=int,
        default=None,
        help="Filter treatment plans/items from patient code (inclusive).",
    )
    parser.add_argument(
        "--patients-to",
        dest="patients_to",
        type=int,
        default=None,
        help="Filter treatment plans/items to patient code (inclusive).",
    )
    parser.add_argument(
        "--tp-from",
        dest="tp_from",
        type=int,
        default=None,
        help="Filter treatment plans/items from TP number (inclusive).",
    )
    parser.add_argument(
        "--tp-to",
        dest="tp_to",
        type=int,
        default=None,
        help="Filter treatment plans/items to TP number (inclusive).",
    )
    parser.add_argument(
        "--appts-from",
        dest="appts_from",
        type=_parse_date_arg,
        default=None,
        help="Filter appointments from YYYY-MM-DD (inclusive).",
    )
    parser.add_argument(
        "--appts-to",
        dest="appts_to",
        type=_parse_date_arg,
        default=None,
        help="Filter appointments to YYYY-MM-DD (inclusive).",
    )
    args = parser.parse_args()

    if args.mapping_quality_out and args.entity != "patients":
        print("--mapping-quality-out is only supported for --entity patients.")
        return 2
    if args.verify_postgres and args.entity != "patients":
        print("--verify-postgres is only supported for --entity patients.")
        return 2
    if args.connect_timeout_seconds is not None and args.connect_timeout_seconds <= 0:
        print("--connect-timeout-seconds must be a positive integer.")
        return 2

    if args.verify_postgres:
        session = SessionLocal()
        try:
            summary = verify_patients_window(
                session,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        finally:
            session.close()

    if args.entity == "treatment_plans_backfill_patient_ids":
        if not args.apply or args.confirm != "APPLY":
            print("Refusing to backfill without --apply --confirm APPLY.")
            return 2
        session = SessionLocal()
        try:
            actor_id = resolve_actor_id(session)
            stats = backfill_r4_treatment_plan_patients(session, actor_id)
            session.commit()
            print(json.dumps(stats.as_dict(), indent=2, sort_keys=True))
            return 0
        finally:
            session.close()

    if args.entity == "treatment_plans_summary":
        session = SessionLocal()
        try:
            summary = summarize_r4_treatment_plans(session)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        finally:
            session.close()

    if args.source == "sqlserver":
        if args.apply and args.dry_run:
            print("Choose either --apply or --dry-run (default is dry-run).")
            return 2
        if args.apply and args.confirm != "APPLY":
            print("Refusing to apply without --confirm APPLY.")
            return 2
        try:
            config = R4SqlServerConfig.from_env()
            if args.connect_timeout_seconds is not None:
                config.timeout_seconds = args.connect_timeout_seconds
            config.require_enabled()
            source = R4SqlServerSource(config)
            if args.apply:
                session = SessionLocal()
                try:
                    actor_id = resolve_actor_id(session)
                    if args.entity == "patients":
                        stats = import_r4_patients(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            patients_from=args.patients_from,
                            patients_to=args.patients_to,
                            limit=args.limit,
                            progress_every=args.progress_every,
                        )
                    elif args.entity == "patients_appts":
                        stats = import_r4(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            appts_from=args.appts_from,
                            appts_to=args.appts_to,
                            limit=None,
                        )
                    elif args.entity == "treatments":
                        stats = import_r4_treatments(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            limit=args.limit,
                        )
                    elif args.entity == "treatment_transactions":
                        stats = import_r4_treatment_transactions(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            patients_from=args.patients_from,
                            patients_to=args.patients_to,
                            limit=args.limit,
                        )
                    else:
                        stats = import_r4_treatment_plans(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            patients_from=args.patients_from,
                            patients_to=args.patients_to,
                            tp_from=args.tp_from,
                            tp_to=args.tp_to,
                            limit=args.limit,
                            batch_size=args.batch_size,
                            sleep_ms=args.sleep_ms,
                            progress_every=args.progress_every,
                            progress_enabled=True,
                        )
                    session.commit()
                finally:
                    session.close()
                if args.entity == "patients":
                    _maybe_write_mapping_quality(
                        args.mapping_quality_out,
                        stats.mapping_quality,
                        args.patients_from,
                        args.patients_to,
                    )
                print(json.dumps(stats.as_dict(), indent=2, sort_keys=True))
                return 0
            if args.entity == "patients":
                summary = source.dry_run_summary_patients(
                    limit=args.limit or 10,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                )
                if args.mapping_quality_out:
                    mapping_quality = _build_patients_mapping_quality(
                        source,
                        patients_from=args.patients_from,
                        patients_to=args.patients_to,
                        limit=None,
                    )
                    _maybe_write_mapping_quality(
                        args.mapping_quality_out,
                        mapping_quality,
                        args.patients_from,
                        args.patients_to,
                    )
            elif args.entity == "patients_appts":
                summary = source.dry_run_summary(
                    limit=args.limit or 10,
                    date_from=args.appts_from,
                    date_to=args.appts_to,
                )
            elif args.entity == "treatments":
                summary = source.dry_run_summary_treatments(limit=args.limit or 10)
            elif args.entity == "treatment_transactions":
                summary = source.dry_run_summary_treatment_transactions(
                    limit=args.limit or 10,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                )
            else:
                summary = source.dry_run_summary_treatment_plans(
                    limit=args.limit or 10,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                    tp_from=args.tp_from,
                    tp_to=args.tp_to,
                )
        except RuntimeError as exc:
            print(str(exc))
            return 2
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.dry_run or args.apply:
        print("--dry-run/--apply are only supported with --source sqlserver.")
        return 2

    session = SessionLocal()
    try:
        actor_id = resolve_actor_id(session)
        source = FixtureSource()
        if args.entity == "patients":
            stats = import_r4_patients(
                session,
                source,
                actor_id,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
                limit=args.limit,
                progress_every=args.progress_every,
            )
        elif args.entity == "patients_appts":
            stats = import_r4(session, source, actor_id)
        elif args.entity == "treatments":
            stats = import_r4_treatments(session, source, actor_id)
        elif args.entity == "treatment_transactions":
            stats = import_r4_treatment_transactions(
                session,
                source,
                actor_id,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
                limit=args.limit,
            )
        else:
            stats = import_r4_treatment_plans(
                session,
                source,
                actor_id,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
                tp_from=args.tp_from,
                tp_to=args.tp_to,
                limit=args.limit,
                batch_size=args.batch_size,
                sleep_ms=args.sleep_ms,
                progress_every=args.progress_every,
                progress_enabled=False,
            )
        session.commit()
        if args.entity == "patients":
            _maybe_write_mapping_quality(
                args.mapping_quality_out,
                stats.mapping_quality,
                args.patients_from,
                args.patients_to,
            )
        print(json.dumps(stats.as_dict(), indent=2, sort_keys=True))
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
