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
                    stats = import_r4(
                        session,
                        source,
                        actor_id,
                        legacy_source="r4",
                        appts_from=args.appts_from,
                        appts_to=args.appts_to,
                        limit=None,
                    )
                    session.commit()
                finally:
                    session.close()
                print(json.dumps(stats.as_dict(), indent=2, sort_keys=True))
                return 0
            summary = source.dry_run_summary(
                limit=args.limit or 10,
                date_from=args.appts_from,
                date_to=args.appts_to,
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
        stats = import_r4(session, source, actor_id)
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
