from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.services.charting_seed import seed_charting_demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo charting data (Postgres only).")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to the database.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.apply:
        print("Pass --apply to seed charting demo data.")
        return 2
    session = SessionLocal()
    try:
        result = seed_charting_demo(session)
        session.commit()
        print(json.dumps(result, indent=2))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
