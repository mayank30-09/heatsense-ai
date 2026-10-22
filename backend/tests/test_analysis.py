from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.raster.catalog import discover_seasonal_cogs

client = TestClient(app)

# Coordinates for a verified urban land area in Udhna, Surat (inside SMC)
VALID_LAND_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [72.82, 21.10],
        [72.84, 21.10],
        [72.84, 21.12],
        [72.82, 21.12],
        [72.82, 21.10],
    ]],
}

# Coordinates for a rural polygon completely outside the SMC boundary (north-west Olpad)
OUTSIDE_SMC_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [72.50, 21.40],
        [72.52, 21.40],
        [72.52, 21.42],
        [72.50, 21.42],
        [72.50, 21.40],
    ]],
}

# Coordinates for a polygon overlapping the eastern boundary of SMC
PARTIALLY_OUTSIDE_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [72.857, 21.128],
        [72.877, 21.128],
        [72.877, 21.148],
        [72.857, 21.148],
        [72.857, 21.128],
    ]],
}

# Coordinates for an open-water segment in the Tapi River reach (Amroli/Katargam loop)
TAPI_WATER_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [72.846, 21.230],
        [72.850, 21.230],
        [72.850, 21.234],
        [72.846, 21.234],
        [72.846, 21.230],
    ]],
}


def test_zonal_statistics_default_summer():
    """Verify default request (omitted season/year) defaults to summer 2026."""
    payload = {"geometry": VALID_LAND_POLYGON}
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "ok"
    assert data["season"] == "summer"
    assert data["effective_year"] == 2026
    assert data["inside_smc_fraction"] == 1.0
    assert data["valid_pixel_count"] > 400
    assert data["statistics"] is not None
    assert 35.0 <= data["statistics"]["mean_c"] <= 55.0
    assert "seasons_table" in data
    assert len(data["seasons_table"]) == 4


@pytest.mark.parametrize("season,expected_year", [
    ("summer", 2026),
    ("winter", 2026),
    ("post_monsoon", 2025),
    ("monsoon", 2026),
])
def test_zonal_statistics_valid_land_polygon_per_season(season: str, expected_year: int):
    """Verify zonal statistics for all 4 supported seasons on valid urban land."""
    cogs = discover_seasonal_cogs()
    if (season, expected_year) not in cogs:
        pytest.skip(f"Seasonal COG for ({season}, {expected_year}) not available in test environment.")

    payload = {
        "geometry": VALID_LAND_POLYGON,
        "season": season,
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "ok"
    assert data["season"] == season
    assert data["effective_year"] == expected_year
    assert data["inside_smc_fraction"] == 1.0
    assert data["valid_pixel_count"] > 0
    assert data["statistics"] is not None


def test_zonal_statistics_outside_study_area():
    """Verify polygon lying entirely outside SMC returns outside_study_area status."""
    payload = {
        "geometry": OUTSIDE_SMC_POLYGON,
        "season": "summer",
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "outside_study_area"
    assert data["inside_smc_fraction"] == 0.0
    assert data["valid_pixel_count"] == 0
    assert data["statistics"] is None


def test_zonal_statistics_partially_outside():
    """Verify polygon crossing SMC boundary returns partially_outside status with inside fraction."""
    payload = {
        "geometry": PARTIALLY_OUTSIDE_POLYGON,
        "season": "summer",
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "partially_outside"
    assert 0.0 < data["inside_smc_fraction"] < 0.99
    assert data["valid_pixel_count"] > 0
    assert data["statistics"] is not None


def test_zonal_statistics_monsoon_polygon_with_gaps():
    """Verify monsoon layer correctly detects cloud gaps and reports is_partial flag."""
    cogs = discover_seasonal_cogs()
    if ("monsoon", 2026) not in cogs:
        pytest.skip("Monsoon 2026 COG missing.")

    payload = {
        "geometry": VALID_LAND_POLYGON,
        "season": "monsoon",
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["season"] == "monsoon"
    assert data["effective_year"] == 2026

    # Locate monsoon row in seasons_table
    monsoon_rows = [s for s in data["seasons_table"] if s["season"] == "monsoon"]
    assert len(monsoon_rows) == 1
    m_row = monsoon_rows[0]
    assert m_row["is_partial"] is True
    assert m_row["data_coverage_percentage"] < 100.0


def test_zonal_statistics_water_warning():
    """Verify open water area triggers water_warning when NDWI water fraction >= 0.25."""
    cogs = discover_seasonal_cogs()
    if ("summer", 2026) not in cogs:
        pytest.skip("Summer 2026 COG missing.")

    payload = {
        "geometry": TAPI_WATER_POLYGON,
        "season": "summer",
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["ndwi_water_fraction"] > 0.25
    assert data["water_warning"] is True
    # Water surface temperature should be cooler than dry urban land (~33°C vs 45°C)
    assert data["statistics"]["mean_c"] < 38.0


def test_zonal_statistics_invalid_season_422():
    """Verify invalid season string fails API boundary validation with HTTP 422."""
    payload = {
        "geometry": VALID_LAND_POLYGON,
        "season": "autumn",
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 422


def test_zonal_statistics_missing_raster_year_404():
    """Verify unavailable season/year returns explicit HTTP 404 (no silent fallback)."""
    payload = {
        "geometry": VALID_LAND_POLYGON,
        "season": "summer",
        "year": 1990,
    }
    response = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert response.status_code == 404
    assert "No seasonal raster found" in response.json()["detail"]


def test_zonal_statistics_invalid_geometry():
    """Verify non-polygon or unclosed geometry returns HTTP 400."""
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
