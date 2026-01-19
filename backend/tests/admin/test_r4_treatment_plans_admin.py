from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.r4_treatment_plan import (
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
)
from app.models.user import Role, User
from app.services.users import create_user


def seed_r4_plan(session, actor_id: int, patient_code: int, tp_number: int, created_at: datetime):
    plan = R4TreatmentPlan(
        legacy_source="r4",
        legacy_patient_code=patient_code,
        legacy_tp_number=tp_number,
        plan_index=1,
        is_master=False,
        is_current=True,
        is_accepted=False,
        creation_date=created_at,
        status_code=1,
        tp_group=1,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(plan)
    session.flush()
    return plan


def test_r4_treatment_plan_list_requires_admin(api_client):
    session = SessionLocal()
    try:
        email = f"external-{uuid4().hex[:8]}@example.com"
        password = "ChangeMe123!000"
        create_user(session, email=email, password=password, role=Role.external)
    finally:
        session.close()

    res = api_client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = api_client.get(
        "/admin/r4/treatment-plans",
        headers=headers,
        params={"legacy_patient_code": 1000002, "limit": 10},
    )
    assert res.status_code == 403, res.text


def test_r4_treatment_plan_list_filters_and_limits(api_client, auth_headers):
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        seed = int(uuid4().hex[:6], 16)
        patient_code = 8000000 + seed
        other_code = patient_code + 1
        plan_old = seed_r4_plan(
            session,
            actor.id,
            patient_code,
            tp_number=1,
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        plan_new = seed_r4_plan(
            session,
            actor.id,
            patient_code,
            tp_number=2,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        seed_r4_plan(
            session,
            actor.id,
            other_code,
            tp_number=1,
            created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        item_key = 9000000 + seed
        item = R4TreatmentPlanItem(
            treatment_plan_id=plan_new.id,
            legacy_source="r4",
            legacy_tp_item=1,
            legacy_tp_item_key=item_key,
            code_id=1,
            completed=False,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        session.add(item)
        session.commit()
        plan_new_id = plan_new.id
    finally:
        session.close()

    res = api_client.get(
        "/admin/r4/treatment-plans",
        headers=auth_headers,
        params={"legacy_patient_code": patient_code, "limit": 1},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert len(payload) == 1
    assert payload[0]["id"] == plan_new_id
    assert payload[0]["item_count"] == 1

    res = api_client.get(
        "/admin/r4/treatment-plans",
        headers=auth_headers,
        params={"legacy_patient_code": other_code, "limit": 10},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert all(item["legacy_patient_code"] == other_code for item in payload)


def test_r4_treatment_plan_detail(api_client, auth_headers):
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        seed = int(uuid4().hex[:6], 16)
        plan = seed_r4_plan(
            session,
            actor.id,
            9000000 + seed,
            tp_number=1,
            created_at=datetime(2022, 5, 1, tzinfo=timezone.utc),
        )
        item_a = R4TreatmentPlanItem(
            treatment_plan_id=plan.id,
            legacy_source="r4",
            legacy_tp_item=1,
            legacy_tp_item_key=9000000 + seed,
            code_id=2,
            completed=False,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        item_b = R4TreatmentPlanItem(
            treatment_plan_id=plan.id,
            legacy_source="r4",
            legacy_tp_item=2,
            legacy_tp_item_key=9000001 + seed,
            code_id=3,
            completed=True,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        review = R4TreatmentPlanReview(
            treatment_plan_id=plan.id,
            temporary_note="Review note",
            reviewed=False,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        session.add_all([item_a, item_b, review])
        session.commit()
        session.refresh(plan)
    finally:
        session.close()

    res = api_client.get(f"/admin/r4/treatment-plans/{plan.id}", headers=auth_headers)
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["plan"]["id"] == plan.id
    assert len(payload["items"]) == 2
    assert payload["reviews"][0]["temporary_note"] == "Review note"


def test_r4_treatment_plan_detail_404(api_client, auth_headers):
    res = api_client.get("/admin/r4/treatment-plans/999999", headers=auth_headers)
    assert res.status_code == 404, res.text
