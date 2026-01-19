from decimal import Decimal
import json

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_treatment_plan import (
    R4Treatment,
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
)
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.treatment_plan_importer import (
    import_r4_treatment_plans,
    import_r4_treatments,
)


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def clear_r4_clinical(session) -> None:
    session.execute(delete(R4TreatmentPlanReview))
    session.execute(delete(R4TreatmentPlanItem))
    session.execute(delete(R4TreatmentPlan))
    session.execute(delete(R4Treatment))


def ensure_patient(session, actor_id: int, patient_code: int) -> Patient:
    patient = session.scalar(
        select(Patient).where(
            Patient.legacy_source == "r4",
            Patient.legacy_id == str(patient_code),
        )
    )
    if patient:
        return patient
    patient = Patient(
        legacy_source="r4",
        legacy_id=str(patient_code),
        first_name="Fixture",
        last_name=f"Patient {patient_code}",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(patient)
    session.flush()
    return patient


def test_r4_treatments_idempotent_and_updates():
    session = SessionLocal()
    try:
        clear_r4_clinical(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        stats_first = import_r4_treatments(session, source, actor_id)
        session.commit()

        assert stats_first.treatments_created == 2

        treatment = session.scalar(
            select(R4Treatment).where(R4Treatment.legacy_treatment_code == 2001)
        )
        assert treatment is not None
        treatment.description = "Old description"
        treatment.updated_by_user_id = actor_id
        session.commit()

        stats_second = import_r4_treatments(session, source, actor_id)
        session.commit()

        assert stats_second.treatments_updated == 1
        assert stats_second.treatments_created == 0
    finally:
        session.close()


def test_r4_treatment_plans_idempotent_and_missing_patient():
    session = SessionLocal()
    try:
        clear_r4_clinical(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        ensure_patient(session, actor_id, patient_code=1001)
        session.commit()

        source = FixtureSource()
        stats_first = import_r4_treatment_plans(session, source, actor_id)
        session.commit()

        assert stats_first.plans_created == 2
        assert stats_first.items_created == 2
        assert stats_first.reviews_created == 1
        assert stats_first.plans_unmapped_patient_refs == 1

        missing_plan = session.scalar(
            select(R4TreatmentPlan).where(R4TreatmentPlan.legacy_patient_code == 9999)
        )
        assert missing_plan is not None
        assert missing_plan.patient_id is None

        stats_second = import_r4_treatment_plans(session, source, actor_id)
        session.commit()

        assert stats_second.plans_created == 0
        assert stats_second.items_created == 0
        assert stats_second.reviews_created == 0
        assert stats_second.plans_updated == 0
        assert stats_second.items_updated == 0
    finally:
        session.close()


def test_r4_treatment_plans_apply_updates():
    session = SessionLocal()
    try:
        clear_r4_clinical(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        ensure_patient(session, actor_id, patient_code=1001)
        session.commit()

        source = FixtureSource()
        import_r4_treatment_plans(session, source, actor_id)
        session.commit()

        item = session.scalar(
            select(R4TreatmentPlanItem).where(R4TreatmentPlanItem.legacy_tp_item_key == 5001)
        )
        assert item is not None
        item.patient_cost = Decimal("10.00")
        item.updated_by_user_id = actor_id
        session.commit()

        stats_second = import_r4_treatment_plans(session, source, actor_id)
        session.commit()

        assert stats_second.items_updated == 1
    finally:
        session.close()


def test_r4_treatment_plans_progress_output(capsys):
    session = SessionLocal()
    try:
        clear_r4_clinical(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        ensure_patient(session, actor_id, patient_code=1001)
        session.commit()

        source = FixtureSource()
        import_r4_treatment_plans(
            session,
            source,
            actor_id,
            batch_size=1,
            progress_every=1,
            progress_enabled=True,
        )
        session.commit()

        output_lines = [
            line
            for line in capsys.readouterr().out.strip().splitlines()
            if line
        ]
        progress_lines = [
            line for line in output_lines if '"event": "r4_import_progress"' in line
        ]
        assert progress_lines
        payloads = [json.loads(line) for line in progress_lines]
        assert {payload["event"] for payload in payloads} == {"r4_import_progress"}
        assert "plans" in {payload["phase"] for payload in payloads}
        assert "items" in {payload["phase"] for payload in payloads}
    finally:
        session.close()
