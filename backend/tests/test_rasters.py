import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_lst_tile_inside_bounds():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/900.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers.get("x-effective-year") == "2026"
    assert len(response.content) > 0


def test_lst_tile_outside_bounds():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/918.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 0


@pytest.mark.parametrize(
    "season_param,req_year,expected_effective_year",
    [
        ("summer", 2026, "2026"),
        ("winter", 2026, "2026"),
        ("post_monsoon", 2026, "2025"),
        ("post_monsoon", 2025, "2025"),
        ("monsoon", 2026, "2026"),
    ],
)
def test_lst_tile_all_seasons(season_param: str, req_year: int, expected_effective_year: str):
    response = client.get(
        f"/api/v1/rasters/lst/tiles/11/1438/900.png?season={season_param}&year={req_year}"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers.get("x-effective-year") == expected_effective_year
    assert len(response.content) > 0


def test_lst_tile_invalid_season_422():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/900.png?season=autumn")
    assert response.status_code == 422


def test_lst_tile_missing_raster_404():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/900.png?season=summer&year=2021")
    assert response.status_code == 404
    assert "No seasonal raster found" in response.json()["detail"]
