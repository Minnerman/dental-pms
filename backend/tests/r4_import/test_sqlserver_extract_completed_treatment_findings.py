from datetime import date, datetime

from app.services.r4_charting import sqlserver_extract as extract
from app.services.r4_import.types import R4CompletedTreatmentFinding


def test_collect_canonical_records_completed_treatment_findings_filters_and_maps():
    class DummySource:
        def __init__(self, _config=None):
            self._config = _config

        def list_completed_treatment_findings(
            self,
            patients_from=None,
            patients_to=None,
            date_from=None,
            date_to=None,
            limit=None,
        ):
            rows = [
                R4CompletedTreatmentFinding(
                    patient_code=None,
                    completed_date=datetime(2020, 1, 5, 9, 0, 0),
                    tooth=11,
                    code_id=200,
                    treatment_label="Soft Tissue Examination",
                    ref_id=10,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2020, 2, 1, 0, 0, 0),  # end-exclusive out of window
                    tooth=11,
                    code_id=200,
                    treatment_label="Soft Tissue Examination",
                    ref_id=11,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2020, 1, 6, 9, 0, 0),
                    tooth=None,
                    code_id=200,
                    treatment_label="Soft Tissue Examination",
                    ref_id=12,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2020, 1, 7, 9, 0, 0),
                    tooth=11,
                    code_id=None,
                    treatment_label="Soft Tissue Examination",
                    ref_id=13,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2020, 1, 8, 9, 0, 0),
                    tooth=11,
                    code_id=201,
                    treatment_label="Crown",
                    ref_id=14,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2020, 1, 9, 9, 0, 0),
                    tooth=11,
                    code_id=202,
                    treatment_label="Soft Tissue Examination",
                    ref_id=15,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1001,
                    completed_date=datetime(2020, 1, 9, 10, 0, 0),
                    tooth=12,
                    code_id=203,
                    treatment_label="Soft Tissue Examination",
                    ref_id=15,
                ),
                R4CompletedTreatmentFinding(
                    patient_code=1002,
                    completed_date=datetime(2020, 1, 10, 9, 0, 0),
                    tooth=21,
                    code_id=300,
                    treatment_label="Soft Tissue Examination",
                    ref_id=16,
                    tp_number=1,
                    tp_item=2,
                ),
            ]
            if patients_from is not None and patients_to is not None:
                rows = [
                    row
                    for row in rows
                    if row.patient_code is not None
                    and (patients_from <= row.patient_code <= patients_to)
                ]
            if limit is not None:
                rows = rows[:limit]
            return rows

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = DummySource()

    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1001, 1002],
        date_from=date(2020, 1, 1),
        date_to=date(2020, 2, 1),
        domains=["completed_treatment_findings"],
        limit=100,
    )

    assert len(records) == 2
    assert {record.legacy_patient_code for record in records} == {1001, 1002}
    for record in records:
        assert record.domain == "completed_treatment_finding"
        assert record.r4_source == "dbo.vwCompletedTreatmentTransactions"
        assert record.surface is None
        assert record.status == "completed"
        assert isinstance(record.payload, dict)

    first = next(record for record in records if record.legacy_patient_code == 1001)
    assert first.r4_source_id == "ref:15"
    assert first.code_id == 202
    assert first.tooth == 11

    assert dropped["missing_patient_code"] == 0
    assert dropped["out_of_window"] == 1
    assert dropped["missing_tooth"] == 1
    assert dropped["missing_code_id"] == 1
    assert dropped["restorative_classified"] == 1
    assert dropped["duplicate_key"] == 1
    assert dropped["included"] == 2


def test_collect_canonical_records_completed_treatment_findings_domain_alias():
    class DummySource:
        def __init__(self, _config=None):
            self._config = _config

        def list_completed_treatment_findings(
            self,
            patients_from=None,
            patients_to=None,
            date_from=None,
            date_to=None,
            limit=None,
        ):
            return [
                R4CompletedTreatmentFinding(
                    patient_code=1003,
                    completed_date=datetime(2020, 1, 15, 10, 0, 0),
                    tooth=31,
                    code_id=400,
                    treatment_label="Soft Tissue Examination",
                    ref_id=99,
                )
            ]

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = DummySource()

    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1003],
        date_from=date(2020, 1, 1),
        date_to=date(2020, 2, 1),
        domains=["completed_treatment_finding"],
        limit=10,
    )

    assert len(records) == 1
    assert records[0].domain == "completed_treatment_finding"
    assert dropped["included"] == 1
