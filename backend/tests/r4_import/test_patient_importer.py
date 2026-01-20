from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy import delete, func, select, update

from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_treatment_plan import R4TreatmentPlan
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.patient_importer import import_r4_patients


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
        delete(R4PatientMapping).where(R4PatientMapping.patient_id.in_(r4_patient_ids))
    )
    session.execute(delete(Appointment).where(Appointment.legacy_source == "r4"))
    session.execute(delete(Patient).where(Patient.legacy_source == "r4"))


def test_r4_patient_import_idempotent():
    session = SessionLocal()
    try:
        clear_r4(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        stats_first = import_r4_patients(session, source, actor_id)
        session.commit()

        assert stats_first.patients_created == 2
        assert stats_first.patients_updated == 0
        assert stats_first.patients_skipped == 0

        stats_second = import_r4_patients(session, source, actor_id)
        session.commit()

        assert stats_second.patients_created == 0
        assert stats_second.patients_updated == 0
        assert stats_second.patients_skipped == 2
    finally:
        session.close()


def test_r4_patient_import_updates_existing():
    session = SessionLocal()
    try:
        clear_r4(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        import_r4_patients(session, source, actor_id)
        session.commit()

        patient = session.scalar(
            select(Patient).where(
                Patient.legacy_source == "r4",
                Patient.legacy_id == "1001",
            )
        )
        assert patient is not None
        patient.last_name = "Old"
        patient.updated_by_user_id = actor_id
        session.commit()

        stats = import_r4_patients(session, source, actor_id)
        session.commit()

        refreshed = session.get(Patient, patient.id)
        assert refreshed is not None
        assert refreshed.last_name == "Patient A"
        assert stats.patients_updated == 1
        assert stats.patients_skipped == 1
    finally:
        session.close()


def test_r4_patient_import_normalizes_fields():
    class DummySource:
        def stream_patients(
            self,
            patients_from: int | None = None,
            patients_to: int | None = None,
            limit: int | None = None,
        ):
            return [
                SimpleNamespace(
                    patient_code=2001,
                    first_name="Jane   ",
                    last_name="Doe   ",
                    date_of_birth=datetime(1985, 5, 1, 3, 4, 5),
                ),
            ]

    session = SessionLocal()
    try:
        clear_r4(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = DummySource()

        stats = import_r4_patients(session, source, actor_id)
        session.commit()

        assert stats.patients_created == 1

        patient = session.scalar(
            select(Patient).where(
                Patient.legacy_source == "r4",
                Patient.legacy_id == "2001",
            )
        )
        assert patient is not None
        assert patient.first_name == "Jane"
        assert patient.last_name == "Doe"
        assert patient.date_of_birth == date(1985, 5, 1)
    finally:
        session.close()
