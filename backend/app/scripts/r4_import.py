from __future__ import annotations

import argparse
import json
from datetime import date

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.importer import import_r4
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource
from app.services.r4_import.treatment_plan_importer import (
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
            "patients_appts",
            "treatments",
            "treatment_plans",
            "treatment_plans_summary",
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
            config.require_enabled()
            source = R4SqlServerSource(config)
            if args.apply:
                session = SessionLocal()
                try:
                    actor_id = resolve_actor_id(session)
                    if args.entity == "patients_appts":
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
                print(json.dumps(stats.as_dict(), indent=2, sort_keys=True))
                return 0
            if args.entity == "patients_appts":
                summary = source.dry_run_summary(
                    limit=args.limit or 10,
                    date_from=args.appts_from,
                    date_to=args.appts_to,
                )
            elif args.entity == "treatments":
                summary = source.dry_run_summary_treatments(limit=args.limit or 10)
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
        if args.entity == "patients_appts":
            stats = import_r4(session, source, actor_id)
        elif args.entity == "treatments":
            stats = import_r4_treatments(session, source, actor_id)
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
        print(json.dumps(stats.as_dict(), indent=2, sort_keys=True))
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
