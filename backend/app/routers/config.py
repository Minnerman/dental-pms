from __future__ import annotations

from fastapi import APIRouter

from app.core.settings import settings

router = APIRouter(tags=["config"])


@router.get("/config")
def get_config() -> dict[str, dict[str, bool]]:
    return {
        "feature_flags": {
            "charting_viewer": settings.feature_charting_viewer,
        }
    }
