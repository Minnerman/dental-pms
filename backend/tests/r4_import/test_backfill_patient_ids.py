from uuid import uuid4

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_treatment_plan import R4TreatmentPlan
from app.models.user import User
from app.services.r4_import.treatment_plan_importer import (
    backfill_r4_treatment_plan_patients,
)


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(User.id).order_by(User.id.asc()).limit(1))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def test_backfill_r4_treatment_plan_patients():
    session = SessionLocal()
    try:
        actor_id = resolve_actor_id(session)
        seed = int(uuid4().hex[:6], 16)
        legacy_code = 9000000 + seed
        session.execute(
            delete(R4TreatmentPlan).where(
                R4TreatmentPlan.legacy_source == "r4",
                R4TreatmentPlan.legacy_patient_code == legacy_code,
            )
        )
        session.execute(
            delete(R4PatientMapping).where(
                R4PatientMapping.legacy_source == "r4",
                R4PatientMapping.legacy_patient_code == legacy_code,
            )
        )
        session.execute(
            delete(Patient).where(
                Patient.legacy_source == "r4",
                Patient.legacy_id == str(legacy_code),
            )
        )
        session.commit()

        patient = Patient(
            legacy_source="r4",
            legacy_id=str(legacy_code),
            first_name="Backfill",
            last_name="Patient",
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        session.add(patient)
        session.flush()

        plan = R4TreatmentPlan(
            legacy_source="r4",
            legacy_patient_code=legacy_code,
            legacy_tp_number=1,
            plan_index=1,
            is_master=False,
            is_current=True,
            is_accepted=False,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        session.add(plan)
        session.flush()

        mapping = R4PatientMapping(
            legacy_source="r4",
            legacy_patient_code=legacy_code,
            patient_id=patient.id,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        session.add(mapping)
        session.commit()

        stats = backfill_r4_treatment_plan_patients(session, actor_id)
        session.commit()

        refreshed = session.get(R4TreatmentPlan, plan.id)
        assert refreshed is not None
        assert refreshed.patient_id == patient.id
        assert stats.plans_updated >= 1
        assert stats.plans_missing_mapping >= 0
    finally:
        session.close()
