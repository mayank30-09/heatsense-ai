import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_zonal_statistics_valid_polygon():
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.82, 21.10],
                [72.84, 21.10],
                [72.84, 21.12],
                [72.82, 21.12],
                [72.82, 21.10],
            ]],
        }
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "no_data")
    assert "area_km2" in data
    assert "geometry" in data


def test_zonal_statistics_invalid_geometry():
    payload = {
        "geometry": {
            "type": "Point",
            "coordinates": [72.83, 21.17],
        }
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 400


@pytest.mark.integration
def test_resolve_area_name_postgis_contains():
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.835, 21.160],
                [72.845, 21.160],
                [72.845, 21.170],
                [72.835, 21.170],
                [72.835, 21.160],
            ]],
        }
    }
    response = client.post("/api/v1/analysis/resolve-area-name-postgis", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("resolved") is True
    assert data.get("name") == "Udhana"
    assert data.get("method") == "contains"


def test_resolve_area_name_openapi_deprecated():
    schema = app.openapi()
    endpoint = schema["paths"]["/api/v1/analysis/resolve-area-name"]["post"]
    assert endpoint.get("deprecated") is True


def test_resolve_area_name_deprecation_headers(monkeypatch):
    from backend.app.api.v1 import analysis

    monkeypatch.setattr(
        analysis,
        "reverse_geocode_polygon",
        lambda geom: {"resolved": True, "name": "Surat Old City", "method": "nominatim_mock"},
    )

    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.82, 21.10],
                [72.84, 21.10],
                [72.84, 21.12],
                [72.82, 21.12],
                [72.82, 21.10],
            ]],
        }
    }
    response = client.post("/api/v1/analysis/resolve-area-name", json=payload)
    assert response.status_code == 200
    assert response.headers.get("Deprecation") == "true"
    assert "resolve-area-name-postgis" in response.headers.get("Link", "")

