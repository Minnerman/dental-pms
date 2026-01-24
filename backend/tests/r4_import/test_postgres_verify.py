from sqlalchemy import delete, func, select, update

from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.r4_charting import R4ChartingImportState
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_treatment_plan import R4TreatmentPlan
from app.models.user import User
from app.services.r4_import.postgres_verify import verify_patients_window


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def clear_r4(session) -> None:
    r4_patient_ids = select(Patient.id).where(Patient.legacy_source == "r4")
    session.execute(
        update(R4TreatmentPlan)
        .where(R4TreatmentPlan.patient_id.in_(r4_patient_ids))
        .values(patient_id=None)
    )
    session.execute(
        delete(R4ChartingImportState).where(
            R4ChartingImportState.patient_id.in_(r4_patient_ids)
        )
    )
    session.execute(
        delete(R4PatientMapping).where(R4PatientMapping.patient_id.in_(r4_patient_ids))
    )
    session.execute(delete(Appointment).where(Appointment.legacy_source == "r4"))
    session.execute(delete(Patient).where(Patient.legacy_source == "r4"))


def test_verify_patients_window_counts_and_range():
    session = SessionLocal()
    try:
        clear_r4(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        session.add_all(
            [
                Patient(
                    legacy_source="r4",
                    legacy_id="100",
                    first_name="A",
                    last_name="Patient",
                    created_by_user_id=actor_id,
                    updated_by_user_id=actor_id,
                ),
                Patient(
                    legacy_source="r4",
                    legacy_id="200",
                    first_name="B",
                    last_name="Patient",
                    created_by_user_id=actor_id,
                    updated_by_user_id=actor_id,
                ),
                Patient(
                    legacy_source="r4",
                    legacy_id="abc",
                    first_name="C",
                    last_name="Patient",
                    created_by_user_id=actor_id,
                    updated_by_user_id=actor_id,
                ),
            ]
        )
        session.commit()

        summary_all = verify_patients_window(session)
        assert summary_all["postgres_count_in_window"] == 2
        assert summary_all["min_patient_code"] == 100
        assert summary_all["max_patient_code"] == 200

        summary_window = verify_patients_window(session, patients_from=150, patients_to=250)
        assert summary_window["postgres_count_in_window"] == 1
        assert summary_window["min_patient_code"] == 200
        assert summary_window["max_patient_code"] == 200
    finally:
        session.close()
