import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_lst_tile_inside_bounds():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/900.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers.get("x-effective-year") == "2026"
    assert response.headers.get("x-data-source") == "surat_2026_summer_features_cog.tif"
    assert response.headers.get("x-effective-season") == "summer"
    assert len(response.content) > 0


def test_lst_tile_outside_bounds():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/918.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 0


@pytest.mark.parametrize(
    "season_param,req_year,expected_effective_year,expected_source_file",
    [
        ("summer", 2026, "2026", "surat_2026_summer_features_cog.tif"),
        ("winter", 2026, "2026", "surat_2026_winter_features_cog.tif"),
        ("post_monsoon", 2026, "2025", "surat_2025_post_monsoon_features_cog.tif"),
        ("post_monsoon", 2025, "2025", "surat_2025_post_monsoon_features_cog.tif"),
        ("monsoon", 2026, "2026", "surat_2026_monsoon_features_cog.tif"),
    ],
)
def test_lst_tile_all_seasons(season_param: str, req_year: int, expected_effective_year: str, expected_source_file: str):
    response = client.get(
        f"/api/v1/rasters/lst/tiles/11/1438/900.png?season={season_param}&year={req_year}"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers.get("x-effective-year") == expected_effective_year
    assert response.headers.get("x-data-source") == expected_source_file
    assert response.headers.get("x-effective-season") == season_param
    assert len(response.content) > 0


def test_lst_tile_invalid_season_422():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/900.png?season=autumn")
    assert response.status_code == 422


def test_lst_tile_missing_raster_404():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/900.png?season=summer&year=2021")
    assert response.status_code == 404
    assert "No seasonal raster found" in response.json()["detail"]
