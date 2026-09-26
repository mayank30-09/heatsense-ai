import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.mark.integration
def test_health_endpoint_requires_postgis():
    """Requires a running PostGIS database; skipped when unavailable locally."""
    client = TestClient(app)
    try:
        response = client.get("/api/v1/health")
    except Exception as exc:
        pytest.skip(f"PostGIS is not available in the test environment: {exc}")

    if response.status_code == 503:
        pytest.skip("PostGIS database is not running")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "heatsense-api",
        "database": "connected",
    }
