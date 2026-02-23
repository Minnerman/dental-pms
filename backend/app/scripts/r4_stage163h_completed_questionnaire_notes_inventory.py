from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.scripts.r4_stage163h_notes_scout_common import (
    build_inventory_bundle,
    query_note_rows,
    write_standard_outputs,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Stage 163H scout inventory for CompletedQuestionnaire notes "
            "(questionnaire note candidate domain)."
        )
    )
    parser.add_argument("--date-from", required=True, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", required=True, help="Exclusive end date (YYYY-MM-DD).")
    parser.add_argument("--seed", type=int, default=17, help="Deterministic hashed ordering seed.")
    parser.add_argument(
        "--cohort-limit",
        type=int,
        default=200,
        help="Max number of selected patient codes to emit in the scout cohort.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write the standard artifact set.",
    )
    args = parser.parse_args()

    date_from = date.fromisoformat(args.date_from)
    date_to = date.fromisoformat(args.date_to)
    if date_to <= date_from:
        raise RuntimeError("--date-to must be after --date-from.")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    rows, column_metadata = query_note_rows(
        source,
        table="CompletedQuestionnaire",
        patient_col_candidates=["PatientCode", "patientcode"],
        date_col_candidates=["DateTime", "Date", "CompletedDate", "CreatedDate", "LastEditDate"],
        note_col_candidates=["Notes", "Note", "NoteBody", "FreeText"],
        row_id_col_candidates=[
            "CompletedQuestionnaireID",
            "CompletedQuestionnaireId",
            "QuestionnaireID",
            "QuestionnaireId",
            "ID",
            "Id",
            "RecordID",
            "RowID",
        ],
    )

    bundle = build_inventory_bundle(
        domain="completed_questionnaire_notes",
        source_table=column_metadata["table"],
        rows=rows,
        column_metadata=column_metadata,
        date_from=date_from,
        date_to=date_to,
        seed=args.seed,
        cohort_limit=args.cohort_limit,
        recommended_seen_ledger=".run/seen_stage163h_completed_questionnaire_notes.txt",
    )
    paths = write_standard_outputs(
        output_dir=Path(args.output_dir),
        filename_prefix="stage163h_completed_questionnaire_notes",
        bundle=bundle,
    )

    summary = bundle["inventory_json"]["summary"]
    print(
        json.dumps(
            {
                "domain": bundle["inventory_json"]["domain"],
                "source_table": bundle["inventory_json"]["source_table"],
                "rows_total": summary["rows_total"],
                "rows_in_window": summary["rows_in_window"],
                "nonblank_rows_in_window": summary["nonblank_rows_in_window"],
                "nonblank_pct_in_window": summary["nonblank_pct_in_window"],
                "accepted_patients": summary["accepted_patients"],
                "selected_count": bundle["inventory_json"]["selection"]["selected_count"],
                "output_dir": str(Path(args.output_dir)),
                "paths": paths,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

