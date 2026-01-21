from app.db.session import SessionLocal
from app.models.patient import Patient
from app.services.r4_import.postgres_verify import verify_patients_window

from .test_patient_importer import clear_r4, resolve_actor_id


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
