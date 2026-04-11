from datetime import datetime, timezone

from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.services.r4_charting.tooth_state_engine import (
    build_tooth_state_engine_row,
    project_tooth_state_rows,
)


def _record(
    *,
    unique_key: str,
    tooth: int,
    domain: str = "restorative_treatment",
    r4_source: str = "dbo.vwTreatments",
    r4_source_id: str = "row",
    surface: int = 0,
    code_id: int | None = None,
    status: str | None = "1",
    recorded_at: datetime | None = None,
    payload: dict | None = None,
) -> R4ChartingCanonicalRecord:
    return R4ChartingCanonicalRecord(
        unique_key=unique_key,
        domain=domain,
        r4_source=r4_source,
        r4_source_id=r4_source_id,
        legacy_patient_code=999999999,
        tooth=tooth,
        surface=surface,
        code_id=code_id,
        status=status,
        recorded_at=recorded_at,
        payload=payload or {},
    )


def test_build_tooth_state_engine_row_normalizes_real_domain_surfaces_and_label():
    row = build_tooth_state_engine_row(
        _record(
            unique_key="root",
            tooth=26,
            r4_source_id="root-row",
            surface=224,
            code_id=2001,
            status="4",
            recorded_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            payload={
                "tooth": 26,
                "surface": 224,
                "code_id": 2001,
                "status_description": "Root Filling",
                "description": "Root Filling",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )

    assert row is not None
    assert row.tooth_key == "26"
    assert row.restoration_type == "root_canal"
    assert row.surfaces == ("I",)
    assert row.is_real_domain is True
    assert row.is_proxy_domain is False
    assert row.code_label == "Root Filling"


def test_project_tooth_state_rows_prefers_latest_surviving_row_within_family():
    older = build_tooth_state_engine_row(
        _record(
            unique_key="older",
            tooth=14,
            r4_source_id="older-fill",
            surface=3,
            code_id=1001,
            status="1",
            recorded_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            payload={
                "tooth": 14,
                "surface": 3,
                "code_id": 1001,
                "status_description": "Fillings",
                "description": "Composite filling old",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )
    newer = build_tooth_state_engine_row(
        _record(
            unique_key="newer",
            tooth=14,
            r4_source_id="newer-fill",
            surface=3,
            code_id=1002,
            status="4",
            recorded_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            payload={
                "tooth": 14,
                "surface": 3,
                "code_id": 1002,
                "status_description": "Fillings",
                "description": "Composite filling new",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )

    assert older is not None
    assert newer is not None

    teeth = project_tooth_state_rows([older, newer])
    tooth_14 = teeth["14"]

    assert len(tooth_14.restorations) == 1
    assert tooth_14.restorations[0].type == "filling"
    assert tooth_14.restorations[0].surfaces == ("M", "O")
    assert tooth_14.restorations[0].meta["code_id"] == 1002
    assert tooth_14.restorations[0].meta["code_label"] == "Composite filling new"


def test_project_tooth_state_rows_respects_reset_boundary_and_skips_tooth_present():
    pre_reset = build_tooth_state_engine_row(
        _record(
            unique_key="pre",
            tooth=35,
            r4_source_id="pre-reset",
            surface=20,
            code_id=1101,
            status="1",
            recorded_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            payload={
                "tooth": 35,
                "surface": 20,
                "code_id": 1101,
                "status_description": "Fillings",
                "description": "Composite filling before reset",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )
    reset = build_tooth_state_engine_row(
        _record(
            unique_key="reset",
            tooth=35,
            domain="restorative_treatment",
            r4_source="dbo.Transactions",
            r4_source_id="reset",
            surface=0,
            status="4",
            recorded_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            payload={
                "tooth": 35,
                "surface": 0,
                "status_description": "Reset Tooth",
                "description": "Reset Tooth",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )
    present = build_tooth_state_engine_row(
        _record(
            unique_key="present",
            tooth=35,
            domain="restorative_treatment",
            r4_source="dbo.Transactions",
            r4_source_id="present",
            surface=0,
            status="3",
            recorded_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
            payload={
                "tooth": 35,
                "surface": 0,
                "status_description": "Tooth Present",
                "description": "Tooth Present",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )
    post_reset = build_tooth_state_engine_row(
        _record(
            unique_key="post",
            tooth=35,
            r4_source_id="post-reset",
            surface=20,
            code_id=1102,
            status="1",
            recorded_at=datetime(2025, 1, 4, tzinfo=timezone.utc),
            payload={
                "tooth": 35,
                "surface": 20,
                "code_id": 1102,
                "status_description": "Fillings",
                "description": "Composite filling after reset",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )

    assert pre_reset is not None
    assert reset is not None
    assert present is not None
    assert post_reset is not None

    teeth = project_tooth_state_rows([pre_reset, reset, present, post_reset])
    tooth_35 = teeth["35"]

    assert len(tooth_35.restorations) == 1
    assert tooth_35.restorations[0].type == "filling"
    assert tooth_35.restorations[0].surfaces == ("D", "L")
    assert tooth_35.restorations[0].meta["code_id"] == 1102


def test_project_tooth_state_rows_preserves_crown_root_canal_and_post_coexistence():
    crown = build_tooth_state_engine_row(
        _record(
            unique_key="crown",
            tooth=11,
            r4_source_id="crown",
            surface=1,
            code_id=1201,
            status="1",
            recorded_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
            payload={
                "tooth": 11,
                "surface": 1,
                "code_id": 1201,
                "status_description": "White Crown",
                "description": "White Crown",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )
    root = build_tooth_state_engine_row(
        _record(
            unique_key="root",
            tooth=11,
            r4_source_id="root",
            surface=32,
            code_id=1202,
            status="1",
            recorded_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            payload={
                "tooth": 11,
                "surface": 32,
                "code_id": 1202,
                "status_description": "Root Filling",
                "description": "Root Filling",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )
    post = build_tooth_state_engine_row(
        _record(
            unique_key="post",
            tooth=11,
            r4_source_id="post",
            surface=0,
            code_id=1203,
            status="1",
            recorded_at=datetime(2025, 1, 12, tzinfo=timezone.utc),
            payload={
                "tooth": 11,
                "surface": 0,
                "code_id": 1203,
                "status_description": "Post and core build-up",
                "description": "Post and core build-up",
                "completed": True,
                "complete": True,
            },
        ),
        None,
    )

    assert crown is not None
    assert root is not None
    assert post is not None

    teeth = project_tooth_state_rows([crown, root, post])
    types = {item.type for item in teeth["11"].restorations}

    assert types == {"crown", "root_canal", "post"}
