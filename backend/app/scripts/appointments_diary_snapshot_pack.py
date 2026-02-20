from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from app.db.session import SessionLocal
from app.services.appointments_snapshot import (
    build_appointments_snapshot,
    collect_diary_day_metrics,
    select_representative_diary_dates,
)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: _serialize_value(value) for key, value in row.items()} for row in rows]


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Stage 157 appointments diary parity snapshot pack."
    )
    parser.add_argument(
        "--output-dir",
        default=".run/stage157",
        help="Output directory for snapshot and metadata artifacts.",
    )
    parser.add_argument(
        "--week-snapshots",
        choices=["none", "first", "all"],
        default="all",
        help="Whether to include week snapshots in addition to day snapshots.",
    )
    parser.add_argument(
        "--unmask-names",
        action="store_true",
        help="Disable patient-name masking in snapshot output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        metrics = collect_diary_day_metrics(db)
        selected = select_representative_diary_dates(metrics)
        if not selected:
            raise RuntimeError("No appointment rows found. Cannot build diary parity pack.")

        selected = selected[:5]
        serialized_metrics = _serialize_rows(metrics)
        serialized_selected = _serialize_rows(selected)

        _write_json(output_dir / "diary_day_metrics.json", serialized_metrics)
        _write_json(
            output_dir / "diary_representative_dates.json",
            {
                "selected_dates": serialized_selected,
                "selection_count": len(serialized_selected),
                "total_days_seen": len(serialized_metrics),
            },
        )

        views: list[str]
        if args.week_snapshots == "none":
            views = ["day"]
        elif args.week_snapshots == "first":
            views = ["day"]
        else:
            views = ["day", "week"]

        for index, row in enumerate(selected):
            anchor_day = row["day"]
            if not isinstance(anchor_day, date):
                raise RuntimeError(f"Invalid day value in representative set: {anchor_day!r}")
            day_key = anchor_day.isoformat()
            day_snapshot = build_appointments_snapshot(
                db,
                anchor_date=anchor_day,
                view="day",
                mask_names=not args.unmask_names,
            )
            _write_json(
                output_dir / f"diary_snapshot_{day_key}_day.json",
                day_snapshot.model_dump(mode="json"),
            )

            include_week = "week" in views or (args.week_snapshots == "first" and index == 0)
            if include_week:
                week_snapshot = build_appointments_snapshot(
                    db,
                    anchor_date=anchor_day,
                    view="week",
                    mask_names=not args.unmask_names,
                )
                _write_json(
                    output_dir / f"diary_snapshot_{day_key}_week.json",
                    week_snapshot.model_dump(mode="json"),
                )

        print(
            "Diary snapshot pack complete:",
            f"dates={len(selected)}",
            f"output_dir={output_dir}",
            sep=" ",
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
