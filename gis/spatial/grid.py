"""Spatial Grid Definition and Area Reconciliation for HEATSENSE AI.

Authoritative analytical grid parameters for Surat Municipal Corporation (SMC).
Ensures stable row/col pixel identities, exact polygon area conservation,
and deterministic fractional spatial allocation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
from shapely.geometry import Polygon, box
from shapely.prepared import prep

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BOUNDARY_PATH = PROJECT_ROOT / "data" / "raw" / "boundaries" / "surat_smc_boundary.geojson"

# Invariant raster grid constants
GRID_CRS: str = "EPSG:4326"
METRIC_CRS: str = "EPSG:32643"
GRID_WIDTH: int = 318
GRID_HEIGHT: int = 324
GRID_TOTAL_CELLS: int = GRID_WIDTH * GRID_HEIGHT  # 103,032
ORIGIN_LON: float = 72.68358795339460
ORIGIN_LAT: float = 21.32420821442920
PIXEL_SIZE: float = 0.0008983152841195215  # ~100m in lat, ~93m in lon

CANONICAL_SMC_CELL_COUNT: int = 49747
INTERSECTING_SMC_CELL_COUNT: int = 50871
PERIMETER_SLIVER_CELL_COUNT: int = 1124
AUTHORITATIVE_SMC_AREA_KM2: float = 461.630791
CANONICAL_SMC_CLIPPED_AREA_KM2: float = 459.550165
PERIMETER_SLIVER_CLIPPED_AREA_KM2: float = 2.080626


def get_cell_polygon(row: int, col: int) -> Polygon:
    """Construct bounding box polygon in EPSG:4326 for given grid cell."""
    x0 = ORIGIN_LON + col * PIXEL_SIZE
    y1 = ORIGIN_LAT - row * PIXEL_SIZE
    x1 = x0 + PIXEL_SIZE
    y0 = y1 - PIXEL_SIZE
    return box(x0, y0, x1, y1)


def get_cell_centroid(row: int, col: int) -> tuple[float, float]:
    """Return (longitude, latitude) center coordinate of grid cell."""
    lon = ORIGIN_LON + (col + 0.5) * PIXEL_SIZE
    lat = ORIGIN_LAT - (row + 0.5) * PIXEL_SIZE
    return float(np.round(lon, 6)), float(np.round(lat, 6))


def build_affine_transform() -> rasterio.Affine:
    """Return 6-parameter affine transform for the analytical raster grid."""
    return rasterio.Affine(PIXEL_SIZE, 0.0, ORIGIN_LON, 0.0, -PIXEL_SIZE, ORIGIN_LAT)


def generate_smc_grid_dataframe(
    boundary_path: Path | str | None = None,
    canonical_only: bool = True,
) -> gpd.GeoDataFrame:
    """
    Generate authoritative analytical grid cells for Surat Municipal Corporation.

    Parameters
    ----------
    boundary_path : Path or str, optional
        Path to authoritative SMC boundary GeoJSON.
    canonical_only : bool, default True
        If True, returns exactly the 49,747 centroid-inside cells.
        If False, returns all 50,871 boundary-intersecting cells.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with cell geometries, UTM coordinates, and exact fractional weights.
    """
    path = Path(boundary_path) if boundary_path else DEFAULT_BOUNDARY_PATH
    if not path.exists():
        raise FileNotFoundError(f"Authoritative boundary not found at {path}")

    gdf_boundary = gpd.read_file(path)
    poly_4326 = gdf_boundary.geometry.iloc[0]
    gdf_utm = gdf_boundary.to_crs(METRIC_CRS)
    poly_utm = gdf_utm.geometry.iloc[0]

    transform = build_affine_transform()

    # Rasterize with all_touched=True and all_touched=False
    mask_touched = rasterio.features.rasterize(
        [(poly_4326, 1)],
        out_shape=(GRID_HEIGHT, GRID_WIDTH),
        transform=transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )
    mask_centroid = rasterio.features.rasterize(
        [(poly_4326, 1)],
        out_shape=(GRID_HEIGHT, GRID_WIDTH),
        transform=transform,
        fill=0,
        all_touched=False,
        dtype=np.uint8,
    )

    rows, cols = np.where(mask_touched == 1)

    boxes_4326: list[Polygon] = []
    cell_ids: list[str] = []
    is_centroid_in: list[bool] = []
    lats: list[float] = []
    lons: list[float] = []

    for r, c in zip(rows, cols):
        boxes_4326.append(get_cell_polygon(r, c))
        cell_ids.append(f"R{r:03d}_C{c:03d}")
        is_centroid_in.append(bool(mask_centroid[r, c] == 1))
        lon_c, lat_c = get_cell_centroid(r, c)
        lons.append(lon_c)
        lats.append(lat_c)

    gdf_cells = gpd.GeoDataFrame(
        {
            "pixel_id": cell_ids,
            "row_idx": rows,
            "col_idx": cols,
            "latitude": lats,
            "longitude": lons,
            "centroid_inside": is_centroid_in,
            "geometry": boxes_4326,
        },
        crs=GRID_CRS,
    )

    # Project to metric CRS for exact area calculations
    gdf_cells_utm = gdf_cells.to_crs(METRIC_CRS)
    nominal_areas = gdf_cells_utm.geometry.area.to_numpy()
    centroids_utm = gdf_cells_utm.geometry.centroid

    poly_boundary_utm = poly_utm.boundary
    boundary_cells_mask = gdf_cells_utm.geometry.intersects(poly_boundary_utm).to_numpy()

    intersection_areas = np.zeros(len(gdf_cells_utm), dtype=np.float64)

    # Interior cells: 100% inside
    interior_mask = (~boundary_cells_mask) & np.array(is_centroid_in)
    intersection_areas[interior_mask] = nominal_areas[interior_mask]

    # Boundary intersecting cells: compute geometric intersection
    boundary_indices = np.where(boundary_cells_mask)[0]
    for idx in boundary_indices:
        cell_poly = gdf_cells_utm.geometry.iloc[idx]
        intersection_areas[idx] = cell_poly.intersection(poly_utm).area

    fractional_weights = np.clip(intersection_areas / nominal_areas, 0.0, 1.0)

    gdf_cells["x_utm"] = np.round(centroids_utm.x.to_numpy(), 2)
    gdf_cells["y_utm"] = np.round(centroids_utm.y.to_numpy(), 2)
    gdf_cells["nominal_area_m2"] = np.round(nominal_areas, 2)
    gdf_cells["smc_clipped_area_m2"] = np.round(intersection_areas, 2)
    gdf_cells["smc_fractional_weight"] = np.round(fractional_weights, 6)
    gdf_cells["is_centroid_inside"] = is_centroid_in
    gdf_cells["is_boundary_cell"] = boundary_cells_mask

    if canonical_only:
        gdf_cells = gdf_cells[gdf_cells["is_centroid_inside"]].copy().reset_index(drop=True)

    return gdf_cells


def verify_area_conservation(
    gdf_cells: gpd.GeoDataFrame,
    authoritative_area_km2: float = AUTHORITATIVE_SMC_AREA_KM2,
    tolerance_pct: float = 0.0001,
) -> dict[str, Any]:
    """
    Verify conservation of area between grid cell intersections and municipal vector boundary.

    Supports both:
    1. Full intersecting grid (50,871 cells): Area conservation is exact (error < 1e-6%).
    2. Canonical operational grid (49,747 cells): Covers 99.55% of the municipal area,
       with the remaining 0.45% (2.08 km²) residing in 1,124 perimeter slivers.
    """
    n_cells = len(gdf_cells)
    clipped_sum_km2 = float(gdf_cells["smc_clipped_area_m2"].sum() / 1e6)
    nominal_sum_km2 = (
        float(gdf_cells["nominal_area_m2"].sum() / 1e6)
        if "nominal_area_m2" in gdf_cells.columns
        else None
    )

    is_canonical_subset = n_cells == CANONICAL_SMC_CELL_COUNT
    expected_area_km2 = (
        CANONICAL_SMC_CLIPPED_AREA_KM2 if is_canonical_subset else authoritative_area_km2
    )

    delta_km2 = clipped_sum_km2 - authoritative_area_km2
    delta_pct = abs(delta_km2 / authoritative_area_km2) * 100.0
    coverage_pct = (clipped_sum_km2 / authoritative_area_km2) * 100.0

    if is_canonical_subset:
        conserved = (abs(clipped_sum_km2 - expected_area_km2) / expected_area_km2) * 100.0 <= 0.05
    else:
        conserved = delta_pct <= tolerance_pct

    result: dict[str, Any] = {
        "cell_count": n_cells,
        "is_canonical_subset": is_canonical_subset,
        "authoritative_area_km2": authoritative_area_km2,
        "clipped_sum_km2": round(clipped_sum_km2, 6),
        "delta_km2": round(delta_km2, 8),
        "delta_pct": round(delta_pct, 8),
        "coverage_pct": round(coverage_pct, 4),
        "conserved": conserved,
    }
    if nominal_sum_km2 is not None:
        result["nominal_sum_km2"] = round(nominal_sum_km2, 6)
    return result
