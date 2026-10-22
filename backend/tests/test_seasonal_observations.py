"""Acceptance and unit tests for seasonal LST observations.

Verifies:
1. Winter mean LST differs from summer mean LST (both in DB and via API).
2. All four seasons (summer, winter, monsoon, post_monsoon) exist and are queryable.
3. Summer thermal extremes exceed winter extremes.
4. Raster tiles generated for summer and winter yield distinct thermal images.
"""

from __future__ import annotations

import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.db.models.stage_c import StageCGridObservation
from backend.app.db.session import SessionLocal
from backend.app.main import app
from backend.app.raster.tiles import get_lst_tile

client = TestClient(app)


def test_db_winter_mean_lst_differs_from_summer() -> None:
    """Verify in DB that winter mean LST is significantly lower than summer mean LST."""
    db = SessionLocal()
    try:
        stats_query = (
            select(
                StageCGridObservation.season,
                func.count(StageCGridObservation.pixel_id).label("count"),
                func.avg(StageCGridObservation.observed_lst_c).label("mean_lst"),
                func.min(StageCGridObservation.observed_lst_c).label("min_lst"),
                func.max(StageCGridObservation.observed_lst_c).label("max_lst"),
            )
            .where(StageCGridObservation.year == 2026)
            .group_by(StageCGridObservation.season)
        )
        rows = {r.season: r for r in db.execute(stats_query).all()}

        assert "summer" in rows, "Summer 2026 observations missing from DB"
        assert "winter" in rows, "Winter 2026 observations missing from DB"

        summer_stats = rows["summer"]
        winter_stats = rows["winter"]

        assert summer_stats.count > 40000
        assert winter_stats.count > 40000

        # Mean LST assertion: winter must be distinctly cooler than summer (>= 8°C delta)
        mean_diff = float(summer_stats.mean_lst) - float(winter_stats.mean_lst)
        assert mean_diff >= 8.0, (
            f"Expected summer mean ({summer_stats.mean_lst:.2f}°C) to exceed "
            f"winter mean ({winter_stats.mean_lst:.2f}°C) by at least 8°C, got {mean_diff:.2f}°C"
        )

        # Max LST assertion: summer maximum must exceed winter maximum
        assert float(summer_stats.max_lst) > float(winter_stats.max_lst)
        assert float(summer_stats.max_lst) >= 55.0  # Summer heat extremes ~58°C
        assert float(winter_stats.max_lst) <= 48.0  # Winter peaks <= 45°C
    finally:
        db.close()


def test_api_winter_lst_differs_from_summer() -> None:
    """Verify that calling /api/v1/heat-priority/cells with season=winter vs summer returns distinct LSTs."""
    res_summer = client.get("/api/v1/heat-priority/cells?season=summer&year=2026&limit=25")
    assert res_summer.status_code == 200, res_summer.text
    items_summer = {it["pixel_id"]: it["observed_lst_c"] for it in res_summer.json()["items"]}

    res_winter = client.get("/api/v1/heat-priority/cells?season=winter&year=2026&limit=25")
    assert res_winter.status_code == 200, res_winter.text
    items_winter = {it["pixel_id"]: it["observed_lst_c"] for it in res_winter.json()["items"]}

    # Match pixels and assert seasonal delta
    common_pids = set(items_summer.keys()) & set(items_winter.keys())
    assert len(common_pids) >= 10

    diffs = []
    for pid in common_pids:
        s_lst = items_summer[pid]
        w_lst = items_winter[pid]
        if s_lst is not None and w_lst is not None:
            diffs.append(s_lst - w_lst)

    assert len(diffs) > 0
    avg_delta = sum(diffs) / len(diffs)
    # Individual cell difference should be >= 8°C on average
    assert avg_delta >= 8.0, f"Average summer-winter cell delta was only {avg_delta:.2f}°C"


def test_all_four_seasons_available_in_dataset() -> None:
    """Confirm all four seasons (summer, winter, monsoon, post_monsoon) exist in the observations database."""
    db = SessionLocal()
    try:
        seasons_q = select(StageCGridObservation.season).distinct()
        seasons = set(db.scalars(seasons_q).all())
        expected = {"summer", "winter", "monsoon", "post_monsoon"}
        missing = expected - seasons
        assert not missing, f"Missing seasons in stage_c_grid_observations: {missing}"
    finally:
        db.close()


def test_raster_tiles_differ_between_summer_and_winter() -> None:
    """Verify that get_lst_tile produces distinct raster images for winter vs summer."""
    # Surat central tile at zoom 11
    tile_summer = get_lst_tile(1438, 900, 11, season="summer", year=2026)
    tile_winter = get_lst_tile(1438, 900, 11, season="winter", year=2026)

    hash_s = hashlib.sha256(tile_summer).hexdigest()
    hash_w = hashlib.sha256(tile_winter).hexdigest()

    assert hash_s != hash_w, "Summer and winter raster tiles produced identical byte output"
    assert len(tile_summer) > 1000
    assert len(tile_winter) > 1000
