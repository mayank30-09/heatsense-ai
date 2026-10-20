"""Acceptance Tests for Stage C Spatial Grid and Boundary Area Reconciliation (T-01, T-02, T-03).

Requirements:
- T-01: Boundary Area Reconciliation (461.630791 km² ± 0.001 km² in EPSG:32643).
- T-02: Area Conservation (Sum of clipped boundary intersections of all 50,871 touching cells = authoritative boundary area with < 1e-6% error).
- T-03: Analytical Grid Dimensions (Exactly 49,747 centroid-inside operational cells in database).
"""

from __future__ import annotations

from pathlib import Path
import geopandas as gpd
import numpy as np
import pytest
from shapely.prepared import prep
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models.stage_c import StageCGridCell
from backend.app.db.session import SessionLocal
from gis.spatial.grid import (
    AUTHORITATIVE_SMC_AREA_KM2,
    CANONICAL_SMC_CELL_COUNT,
    CANONICAL_SMC_CLIPPED_AREA_KM2,
    GRID_CRS,
    GRID_HEIGHT,
    GRID_WIDTH,
    INTERSECTING_SMC_CELL_COUNT,
    METRIC_CRS,
    ORIGIN_LAT,
    ORIGIN_LON,
    PERIMETER_SLIVER_CELL_COUNT,
    PERIMETER_SLIVER_CLIPPED_AREA_KM2,
    PIXEL_SIZE,
    get_cell_polygon,
    verify_area_conservation,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOUNDARY_GEOJSON = PROJECT_ROOT / "data" / "raw" / "boundaries" / "surat_smc_boundary.geojson"


def test_t01_boundary_area_reconciliation() -> None:
    """T-01: Verify authoritative SMC boundary projected area is 461.630791 km² in EPSG:32643."""
    assert BOUNDARY_GEOJSON.exists(), f"Boundary file missing: {BOUNDARY_GEOJSON}"

    gdf = gpd.read_file(BOUNDARY_GEOJSON)
    assert len(gdf) == 1, "SMC boundary must contain exactly 1 feature"

    gdf_utm = gdf.to_crs(METRIC_CRS)
    geom_utm = gdf_utm.geometry.iloc[0]
    assert geom_utm.is_valid, "SMC boundary geometry must be topologically valid"

    area_m2 = geom_utm.area
    area_km2 = area_m2 / 1_000_000.0

    assert area_km2 == pytest.approx(AUTHORITATIVE_SMC_AREA_KM2, abs=0.001), (
        f"Calculated boundary area {area_km2:.6f} km² deviates from {AUTHORITATIVE_SMC_AREA_KM2} km²"
    )


def test_t02_area_conservation() -> None:
    """T-02: Verify exact area conservation of clipped grid cells against boundary (< 1e-6% relative error)."""
    gdf = gpd.read_file(BOUNDARY_GEOJSON)
    geom_4326 = gdf.geometry.iloc[0]
    prep_4326 = prep(geom_4326)

    gdf_utm = gdf.to_crs(METRIC_CRS)
    geom_utm = gdf_utm.geometry.iloc[0]
    total_boundary_area_m2 = float(geom_utm.area)

    minx, miny, maxx, maxy = geom_4326.bounds

    c_min = int(np.floor((minx - ORIGIN_LON) / PIXEL_SIZE))
    c_max = int(np.ceil((maxx - ORIGIN_LON) / PIXEL_SIZE))
    r_min = int(np.floor((ORIGIN_LAT - maxy) / PIXEL_SIZE))
    r_max = int(np.ceil((ORIGIN_LAT - miny) / PIXEL_SIZE))

    # Collect all 50,871 boundary-intersecting cells in EPSG:4326
    touching_polys = []
    for r in range(max(0, r_min), min(GRID_HEIGHT, r_max + 1)):
        for c in range(max(0, c_min), min(GRID_WIDTH, c_max + 1)):
            poly = get_cell_polygon(r, c)
            if prep_4326.intersects(poly):
                touching_polys.append(poly)

    assert len(touching_polys) == INTERSECTING_SMC_CELL_COUNT == 50871, (
        f"Expected 50,871 touching cells, got {len(touching_polys)}"
    )

    # Vectorized transformation to metric CRS in a single batch
    series_4326 = gpd.GeoSeries(touching_polys, crs=GRID_CRS)
    series_utm = series_4326.to_crs(METRIC_CRS)

    # Vectorized intersection and area sum
    clipped_areas = series_utm.intersection(geom_utm).area
    sum_clipped_m2 = float(clipped_areas.sum())

    abs_diff_m2 = abs(sum_clipped_m2 - total_boundary_area_m2)
    rel_error = abs_diff_m2 / total_boundary_area_m2

    assert rel_error < 1e-6, (
        f"Relative area conservation error {rel_error:.2e} exceeded tolerance 1e-6"
    )


def test_t03_analytical_grid_dimensions() -> None:
    """T-03: Verify analytical grid centroid-inside cell count equals 49,747 cells (461.77 km² nominal area)."""
    session: Session = SessionLocal()
    try:
        centroid_inside_count = session.scalar(
            select(func.count(StageCGridCell.pixel_id)).where(
                StageCGridCell.is_centroid_inside.is_(True)
            )
        )
        assert centroid_inside_count == CANONICAL_SMC_CELL_COUNT == 49747, (
            f"Expected exactly 49,747 centroid-inside cells, got {centroid_inside_count}"
        )

        nominal_sum_m2 = session.scalar(
            select(func.sum(StageCGridCell.nominal_area_m2))
        )
        nominal_area_km2 = float(nominal_sum_m2) / 1_000_000.0
        assert nominal_area_km2 == pytest.approx(461.77, abs=0.5)
    finally:
        session.close()


def test_operational_grid_coverage_accounting() -> None:
    """Verify operational-grid coverage accounting and perimeter sliver reconciliation."""
    # 1. Total cell count identities
    assert CANONICAL_SMC_CELL_COUNT + PERIMETER_SLIVER_CELL_COUNT == INTERSECTING_SMC_CELL_COUNT == 50871
    assert CANONICAL_SMC_CELL_COUNT == 49747
    assert PERIMETER_SLIVER_CELL_COUNT == 1124

    # 2. Area reconciliation identity
    total_reconstructed_area = CANONICAL_SMC_CLIPPED_AREA_KM2 + PERIMETER_SLIVER_CLIPPED_AREA_KM2
    assert total_reconstructed_area == pytest.approx(AUTHORITATIVE_SMC_AREA_KM2, abs=0.0001)

    # 3. Test verify_area_conservation on canonical subset mock
    mock_canonical_gdf = gpd.GeoDataFrame(
        {
            "pixel_id": [f"R{i:05d}" for i in range(CANONICAL_SMC_CELL_COUNT)],
            "smc_clipped_area_m2": np.full(
                CANONICAL_SMC_CELL_COUNT,
                (CANONICAL_SMC_CLIPPED_AREA_KM2 * 1e6) / CANONICAL_SMC_CELL_COUNT,
            ),
            "nominal_area_m2": np.full(CANONICAL_SMC_CELL_COUNT, 9282.0),
        }
    )
    res_canonical = verify_area_conservation(mock_canonical_gdf)
    assert res_canonical["is_canonical_subset"] is True
    assert res_canonical["conserved"] is True
    assert res_canonical["coverage_pct"] == pytest.approx(99.55, abs=0.1)

    # 4. Test verify_area_conservation on full intersecting grid mock
    mock_full_gdf = gpd.GeoDataFrame(
        {
            "pixel_id": [f"R{i:05d}" for i in range(INTERSECTING_SMC_CELL_COUNT)],
            "smc_clipped_area_m2": np.full(
                INTERSECTING_SMC_CELL_COUNT,
                (AUTHORITATIVE_SMC_AREA_KM2 * 1e6) / INTERSECTING_SMC_CELL_COUNT,
            ),
            "nominal_area_m2": np.full(INTERSECTING_SMC_CELL_COUNT, 9282.0),
        }
    )
    res_full = verify_area_conservation(mock_full_gdf)
    assert res_full["is_canonical_subset"] is False
    assert res_full["conserved"] is True
    assert res_full["coverage_pct"] == pytest.approx(100.0, abs=1e-5)
    assert res_full["delta_km2"] == pytest.approx(0.0, abs=1e-6)
