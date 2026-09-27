import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_lst_tile_inside_bounds():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/900.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 0


def test_lst_tile_outside_bounds():
    response = client.get("/api/v1/rasters/lst/tiles/11/1438/918.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 0
