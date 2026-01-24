import pytest

from app.core.settings import settings


def test_seed_route_disabled_by_default(api_client):
    if settings.app_env.strip().lower() == "test" or settings.enable_test_routes:
        pytest.skip("Test routes enabled in this environment")
    res = api_client.post("/test/seed/charting")
    assert res.status_code == 404
