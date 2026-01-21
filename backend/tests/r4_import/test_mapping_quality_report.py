from datetime import date

from app.services.r4_import.mapping_quality import PatientMappingQualityReportBuilder
from app.services.r4_import.types import R4Patient


def test_patient_mapping_quality_report_counts_and_samples():
    patients = [
        R4Patient(
            patient_code=1,
            first_name="A",
            last_name="",
            date_of_birth=None,
            email="bad@",
            postcode="BAD",
        ),
        R4Patient(
            patient_code=2,
            first_name="B",
            last_name="Smith",
            date_of_birth=date(1990, 5, 4),
            email="A@Example.com",
            mobile_no="07700 900111",
            postcode="SW1A 1AA",
            nhs_number="9434765919",
        ),
        R4Patient(
            patient_code=3,
            first_name="C",
            last_name="Jones",
            date_of_birth=date(1989, 7, 2),
            email="a@example.com",
            phone="07700900111",
            postcode="SW1A1AA",
            nhs_number="9434765919",
        ),
        R4Patient(
            patient_code=4,
            first_name="D",
            last_name="Taylor",
            date_of_birth=date(1980, 1, 1),
            mobile_no="123",
        ),
    ]

    builder = PatientMappingQualityReportBuilder(sample_limit=10)
    for patient in patients:
        builder.ingest(patient)
    report = builder.finalize()

    assert report["patients_total"] == 4
    assert report["missing_fields"] == {
        "surname": 1,
        "dob": 1,
        "postcode": 1,
        "phone": 1,
        "email": 1,
    }
    assert report["invalid_fields"] == {
        "email": 1,
        "phone": 1,
        "postcode": 1,
    }
    assert report["duplicates"]["email"]["count"] == 1
    assert report["duplicates"]["email"]["sample"] == ["a@example.com"]
    assert report["duplicates"]["phone"]["count"] == 1
    assert report["duplicates"]["phone"]["sample"] == ["07700900111"]
    assert report["duplicates"]["nhs_number"]["count"] == 1
    assert report["duplicates"]["nhs_number"]["sample"] == ["9434765919"]
