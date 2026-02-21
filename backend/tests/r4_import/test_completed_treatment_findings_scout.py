from datetime import date

from app.services.r4_charting.completed_treatment_findings_scout import (
    CompletedTreatmentFindingRow,
    apply_drop_reason_skeleton,
)


def test_apply_drop_reason_skeleton_counts_reasons_and_includes_non_restorative_only():
    date_from = date(2017, 1, 1)
    date_to = date(2026, 2, 1)

    rows = [
        CompletedTreatmentFindingRow(
            patient_code=None,
            completed_date=date(2020, 1, 1),
            tooth=11,
            code_id=1,
            treatment_label="Soft Tissue Examination",
        ),
        CompletedTreatmentFindingRow(
            patient_code=1001,
            completed_date=None,
            tooth=11,
            code_id=1,
            treatment_label="Soft Tissue Examination",
        ),
        CompletedTreatmentFindingRow(
            patient_code=1001,
            completed_date=date(2020, 1, 2),
            tooth=None,
            code_id=1,
            treatment_label="Soft Tissue Examination",
        ),
        CompletedTreatmentFindingRow(
            patient_code=1001,
            completed_date=date(2020, 1, 3),
            tooth=11,
            code_id=None,
            treatment_label="Soft Tissue Examination",
        ),
        CompletedTreatmentFindingRow(
            patient_code=1001,
            completed_date=date(2020, 1, 4),
            tooth=11,
            code_id=2,
            treatment_label="Crown",
        ),
        CompletedTreatmentFindingRow(
            patient_code=1001,
            completed_date=date(2020, 1, 5),
            tooth=11,
            code_id=3,
            treatment_label="Soft Tissue Examination",
            ref_id=900,
        ),
        CompletedTreatmentFindingRow(
            patient_code=1001,
            completed_date=date(2020, 1, 6),
            tooth=12,
            code_id=4,
            treatment_label="Soft Tissue Examination",
            ref_id=900,
        ),
        CompletedTreatmentFindingRow(
            patient_code=1002,
            completed_date=date(2020, 1, 7),
            tooth=22,
            code_id=5,
            treatment_label="Exam and cleaning together",
            ref_id=901,
        ),
    ]

    accepted, report = apply_drop_reason_skeleton(rows, date_from=date_from, date_to=date_to)

    assert len(accepted) == 2
    assert {row.patient_code for row in accepted} == {1001, 1002}
    assert report.missing_patient_code == 1
    assert report.out_of_window == 1
    assert report.missing_tooth == 1
    assert report.missing_code_id == 1
    assert report.restorative_classified == 1
    assert report.duplicate_key == 1
    assert report.included == 2


def test_apply_drop_reason_skeleton_uses_fallback_key_when_ref_id_missing():
    date_from = date(2017, 1, 1)
    date_to = date(2026, 2, 1)

    rows = [
        CompletedTreatmentFindingRow(
            patient_code=1010,
            completed_date=date(2020, 2, 1),
            tooth=14,
            code_id=20,
            treatment_label="Soft Tissue Examination",
            ref_id=None,
            tp_number=1,
            tp_item=2,
        ),
        CompletedTreatmentFindingRow(
            patient_code=1010,
            completed_date=date(2020, 2, 1),
            tooth=14,
            code_id=20,
            treatment_label="Soft Tissue Examination",
            ref_id=None,
            tp_number=1,
            tp_item=2,
        ),
    ]

    accepted, report = apply_drop_reason_skeleton(rows, date_from=date_from, date_to=date_to)

    assert len(accepted) == 1
    assert report.duplicate_key == 1
    assert report.included == 1
