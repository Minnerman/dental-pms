from sqlalchemy import delete, func, select, update

from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.r4_charting import R4ChartingImportState
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_treatment_plan import R4TreatmentPlan
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.importer import import_r4


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
    session.execute(
        delete(R4ChartingCanonicalRecord).where(
            R4ChartingCanonicalRecord.patient_id.in_(r4_patient_ids)
        )
    )
    session.execute(delete(Appointment).where(Appointment.legacy_source == "r4"))
    session.execute(delete(Patient).where(Patient.legacy_source == "r4"))


def test_r4_import_idempotent():
    session = SessionLocal()
    try:
        clear_r4(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        stats_first = import_r4(session, source, actor_id)
        session.commit()

        assert stats_first.patients_created == 2
        assert stats_first.appts_created == 2
        assert stats_first.appts_unmapped_patient_refs == 1

        stats_second = import_r4(session, source, actor_id)
        session.commit()

        assert stats_second.patients_created == 0
        assert stats_second.patients_updated == 0
        assert stats_second.appts_created == 0
        assert stats_second.appts_updated == 0
        assert stats_second.appts_unmapped_patient_refs == 1

        unmapped = session.scalar(
            select(Appointment).where(Appointment.legacy_id == "A9999-1")
        )
        assert unmapped is not None
        assert unmapped.patient_id is None
    finally:
        session.close()


def test_r4_import_preserves_manual_resolve():
    session = SessionLocal()
    try:
        clear_r4(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        import_r4(session, source, actor_id)
        session.commit()

        unmapped = session.scalar(
            select(Appointment).where(Appointment.legacy_id == "A9999-1")
        )
        assert unmapped is not None

        target_patient = session.scalar(
            select(Patient).where(
                Patient.legacy_source == "r4",
                Patient.legacy_id == "1001",
            )
        )
        assert target_patient is not None

        unmapped.patient_id = target_patient.id
        unmapped.updated_by_user_id = actor_id
        session.commit()

        stats_second = import_r4(session, source, actor_id)
        session.commit()

        refreshed = session.get(Appointment, unmapped.id)
        assert refreshed is not None
        assert refreshed.patient_id == target_patient.id
        assert stats_second.appts_unmapped_patient_refs == 0
        assert stats_second.appts_patient_conflicts == 0
    finally:
        session.close()


def test_r4_import_reports_patient_conflicts():
    session = SessionLocal()
    try:
        clear_r4(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        import_r4(session, source, actor_id)
        session.commit()

        mapped = session.scalar(
            select(Appointment).where(Appointment.legacy_id == "A1001-1")
        )
        assert mapped is not None

        other_patient = session.scalar(
            select(Patient).where(
                Patient.legacy_source == "r4",
                Patient.legacy_id == "1002",
            )
        )
        assert other_patient is not None

        mapped.patient_id = other_patient.id
        mapped.updated_by_user_id = actor_id
        session.commit()

        stats_second = import_r4(session, source, actor_id)
        session.commit()

        refreshed = session.get(Appointment, mapped.id)
        assert refreshed is not None
        assert refreshed.patient_id == other_patient.id
        assert stats_second.appts_patient_conflicts == 1
    finally:
        session.close()
