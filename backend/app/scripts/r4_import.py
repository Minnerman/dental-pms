from __future__ import annotations

import argparse
import json

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.importer import import_r4


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import R4 fixtures into the PMS.")
    parser.add_argument(
        "--source",
        default="fixtures",
        help="Import source (only 'fixtures' is supported).",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        actor_id = resolve_actor_id(session)
        if args.source != "fixtures":
            raise ValueError(f"Unsupported source '{args.source}'.")
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
