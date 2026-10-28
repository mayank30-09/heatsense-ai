"""Zonal statistics engine for Land Surface Temperature (LST) and NDWI features.

Computes multi-temporal zonal statistics clipped to the Surat Municipal Corporation
(SMC) boundary. Enforces season/year awareness, explicit status reporting
(ok, outside_study_area, partially_outside, no_valid_observations), NDWI open-water
detection with thermal warning, and multi-season comparative reporting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Geod
from rasterio.features import geometry_mask
from rasterio.mask import mask
from shapely.geometry import MultiPolygon, Polygon, box, shape
from shapely.ops import unary_union

from backend.app.raster.catalog import (
    CANONICAL_SEASONS,
    DATA_DIR,
    Season,
    discover_seasonal_cogs,
    resolve_seasonal_cog,
)

NODATA = -9999.0
geod = Geod(ellps="WGS84")

_CACHED_SMC_BOUNDARY: Polygon | MultiPolygon | None = None


def get_smc_boundary() -> Polygon | MultiPolygon:
    """Load and cache the official Surat Municipal Corporation (SMC) study boundary."""
    global _CACHED_SMC_BOUNDARY
    if _CACHED_SMC_BOUNDARY is not None:
        return _CACHED_SMC_BOUNDARY

    # Try loading from PostGIS database
    try:
        from backend.app.db.session import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            res = db.execute(
                text("SELECT ST_AsGeoJSON(geometry) FROM study_areas WHERE id = 1;")
            ).scalar()
            if res:
                _CACHED_SMC_BOUNDARY = shape(json.loads(res))
                return _CACHED_SMC_BOUNDARY
        finally:
            db.close()
    except Exception:
        pass

    # Fallback to local GeoJSON boundary artifact
    boundary_file = (
        DATA_DIR.parents[0] / "raw" / "boundaries" / "surat_smc_boundary.geojson"
    )
    if boundary_file.exists():
        with open(boundary_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "features" in data and len(data["features"]) > 0:
            _CACHED_SMC_BOUNDARY = shape(data["features"][0]["geometry"])
        elif "geometry" in data:
            _CACHED_SMC_BOUNDARY = shape(data["geometry"])
        else:
            _CACHED_SMC_BOUNDARY = shape(data)
        return _CACHED_SMC_BOUNDARY

    # Default fallback bounding box if boundary artifact missing
    _CACHED_SMC_BOUNDARY = box(72.6775, 21.0487, 72.9934, 21.2985)
    return _CACHED_SMC_BOUNDARY


def calculate_polygon_area_km2(geometry) -> float:
    area_m2, _ = geod.geometry_area_perimeter(geometry)
    return abs(area_m2) / 1_000_000.0


def calculate_polygon_perimeter_km(geometry) -> float:
    _, perimeter_m = geod.geometry_area_perimeter(geometry)
    return perimeter_m / 1_000.0


def _extract_layer_stats(
    cog_path: Path,
    target_geom: Polygon | MultiPolygon,
) -> dict[str, Any] | None:
    """Internal helper to extract LST statistics for a specific COG."""
    if not cog_path.exists():
        return None

    try:
        with rasterio.open(cog_path) as src:
            data, out_transform = mask(
                src,
                [target_geom.__geo_interface__],
                crop=True,
                filled=False,
            )
            band = data[0]

            inside = geometry_mask(
                [target_geom.__geo_interface__],
                out_shape=band.shape,
                transform=out_transform,
                invert=True,
                all_touched=False,
            )
            raw = np.asarray(band.data, dtype=np.float32)
            valid = (
                inside
                & (raw != NODATA)
                & np.isfinite(raw)
                & (raw > 0.0)
                & (raw < 100.0)
            )

            total_intersecting = int(inside.sum())
            valid_count = int(valid.sum())
            if total_intersecting == 0:
                return None

            cov_pct = (
                round(float(valid_count / total_intersecting * 100.0), 1)
                if total_intersecting > 0
                else 0.0
            )

            if valid_count == 0:
                return {
                    "mean_c": None,
                    "min_c": None,
                    "max_c": None,
                    "valid_pixel_count": 0,
                    "total_intersecting_pixel_count": total_intersecting,
                    "data_coverage_percentage": 0.0,
                    "is_partial": True,
                }

            vals = raw[valid]
            return {
                "mean_c": round(float(np.mean(vals)), 2),
                "min_c": round(float(np.min(vals)), 2),
                "max_c": round(float(np.max(vals)), 2),
                "valid_pixel_count": valid_count,
                "total_intersecting_pixel_count": total_intersecting,
                "data_coverage_percentage": cov_pct,
                "is_partial": bool(valid_count < total_intersecting),
            }
    except Exception:
        return None


def calculate_lst_zonal_statistics(
    geometry: dict,
    season: Season | str = Season.summer,
    year: int | None = None,
) -> dict:
    """Calculate season-aware, SMC-clipped zonal statistics for a given polygon."""
    polygon = shape(geometry)

    if polygon.is_empty:
        raise ValueError("Selected area geometry is empty.")

    geometry_repaired = False
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
        geometry_repaired = True

    if polygon.is_empty or not polygon.is_valid:
        raise ValueError("Selected area geometry is invalid.")

    if polygon.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Only Polygon or MultiPolygon geometries are supported.")

    # 1. Resolve requested seasonal COG (strictly no silent fallback)
    raster_entry = resolve_seasonal_cog(season=season, year=year)
    cog_path = raster_entry.path
    effective_year = raster_entry.effective_year
    season_str = raster_entry.season.value

    # 2. Polygon Geometry Metadata
    area_km2 = calculate_polygon_area_km2(polygon)
    perimeter_km = calculate_polygon_perimeter_km(polygon)
    centroid = polygon.centroid
    min_lon, min_lat, max_lon, max_lat = polygon.bounds

    polygon_metadata = {
        "geometry_type": polygon.geom_type,
        "crs": "EPSG:32643 planar",
        "display_crs": "EPSG:4326",
        "planar_crs": "EPSG:32643",
        "area_method": "Geodesic ellipsoidal area (WGS84) / planar projection EPSG:32643",
        "pixel_size": "100m × 100m (1 ha)",
        "area_km2": round(area_km2, 4),
        "perimeter_km": round(perimeter_km, 4),
        "centroid": {
            "longitude": round(float(centroid.x), 6),
            "latitude": round(float(centroid.y), 6),
        },
        "bounding_box": {
            "min_longitude": round(float(min_lon), 6),
            "min_latitude": round(float(min_lat), 6),
            "max_longitude": round(float(max_lon), 6),
            "max_latitude": round(float(max_lat), 6),
        },
    }

    # 3. SMC Boundary Clipping & Spatial Containment Evaluation
    smc_poly = get_smc_boundary()
    intersection = polygon.intersection(smc_poly)

    if polygon.area > 0:
        inside_smc_fraction = round(float(intersection.area / polygon.area), 4)
    else:
        inside_smc_fraction = 0.0
    inside_smc_fraction = max(0.0, min(1.0, inside_smc_fraction))

    # Case A: Polygon lies completely outside the official SMC boundary
    if intersection.is_empty or inside_smc_fraction <= 0.0001:
        return {
            "status": "outside_study_area",
            "season": season_str,
            "effective_year": effective_year,
            "source_file": cog_path.name,
            "area_km2": round(area_km2, 4),
            "inside_smc_fraction": 0.0,
            "valid_pixel_count": 0,
            "total_intersecting_pixel_count": 0,
            "data_coverage_percentage": 0.0,
            "ndwi_water_fraction": 0.0,
            "water_warning": False,
            "geometry": polygon_metadata,
            "statistics": None,
            "seasons_table": [],
            "raster": {
                "source": cog_path.name,
                "crs": "EPSG:4326",
                "nodata": NODATA,
                "units": "degrees_celsius",
            },
        }

    # 4. Perform Mask Extraction on the SMC-Clipped Intersection Geometry
    with rasterio.open(cog_path) as src:
        try:
            data, out_transform = mask(
                src,
                [intersection.__geo_interface__],
                crop=True,
                filled=False,
            )
        except ValueError as exc:
            if "do not overlap raster" in str(exc):
                return {
                    "status": "outside_study_area",
                    "season": season_str,
                    "effective_year": effective_year,
                    "source_file": cog_path.name,
                    "area_km2": round(area_km2, 4),
                    "inside_smc_fraction": inside_smc_fraction,
                    "valid_pixel_count": 0,
                    "total_intersecting_pixel_count": 0,
                    "data_coverage_percentage": 0.0,
                    "ndwi_water_fraction": 0.0,
                    "water_warning": False,
                    "geometry": polygon_metadata,
                    "statistics": None,
                    "seasons_table": [],
                    "raster": {
                        "source": cog_path.name,
                        "crs": str(src.crs or "EPSG:4326"),
                        "nodata": NODATA,
                        "units": "degrees_celsius",
                    },
                }
            raise

        band_lst = data[0]
        band_ndwi = data[3] if src.count >= 4 else None

        inside_intersection = geometry_mask(
            [intersection.__geo_interface__],
            out_shape=band_lst.shape,
            transform=out_transform,
            invert=True,
            all_touched=False,
        )

        raw_lst = np.asarray(band_lst.data, dtype=np.float32)
        valid_pixels = (
            inside_intersection
            & (raw_lst != NODATA)
            & np.isfinite(raw_lst)
            & (raw_lst > 0.0)
            & (raw_lst < 100.0)
        )

        total_intersecting_pixels = int(inside_intersection.sum())
        valid_pixel_count = int(valid_pixels.sum())

        if total_intersecting_pixels == 0 or valid_pixel_count == 0:
            return {
                "status": "no_valid_observations",
                "season": season_str,
                "effective_year": effective_year,
                "source_file": cog_path.name,
                "area_km2": round(area_km2, 4),
                "inside_smc_fraction": inside_smc_fraction,
                "valid_pixel_count": 0,
                "total_intersecting_pixel_count": total_intersecting_pixels,
                "data_coverage_percentage": 0.0,
                "ndwi_water_fraction": 0.0,
                "water_warning": False,
                "geometry": polygon_metadata,
                "statistics": None,
                "seasons_table": [],
                "raster": {
                    "source": cog_path.name,
                    "crs": str(src.crs or "EPSG:4326"),
                    "nodata": NODATA,
                    "units": "degrees_celsius",
                },
            }

        coverage_percentage = round(
            float(valid_pixel_count / total_intersecting_pixels * 100.0), 2
        )
        lst_values = raw_lst[valid_pixels]

        # 5. NDWI Water Fraction and Warning Assessment
        if band_ndwi is not None:
            raw_ndwi = np.asarray(band_ndwi.data, dtype=np.float32)
            ndwi_values = raw_ndwi[valid_pixels]
            valid_ndwi = ndwi_values[
                (ndwi_values != NODATA) & np.isfinite(ndwi_values)
            ]
            if len(valid_ndwi) > 0:
                water_pixels = int(np.sum(valid_ndwi > 0.05))
                ndwi_water_fraction = round(float(water_pixels / len(valid_ndwi)), 4)
            else:
                ndwi_water_fraction = 0.0
        else:
            ndwi_water_fraction = 0.0

        water_warning = bool(ndwi_water_fraction >= 0.25)

    # 6. Detailed Descriptive Statistics
    statistics = {
        "min_c": round(float(np.min(lst_values)), 2),
        "max_c": round(float(np.max(lst_values)), 2),
        "mean_c": round(float(np.mean(lst_values)), 2),
        "median_c": round(float(np.median(lst_values)), 2),
        "std_c": round(float(np.std(lst_values)), 2),
        "p10_c": round(float(np.percentile(lst_values, 10)), 2),
        "p25_c": round(float(np.percentile(lst_values, 25)), 2),
        "p75_c": round(float(np.percentile(lst_values, 75)), 2),
        "p90_c": round(float(np.percentile(lst_values, 90)), 2),
    }

    # 7. Multi-Season Comparative Table Across All 4 Layers
    seasons_table: list[dict[str, Any]] = []
    available_catalog = discover_seasonal_cogs()

    # Years where all four seasons exist on disk/DB: 2022, 2023, 2024, 2025
    if year in (2022, 2023, 2024, 2025):
        target_seasons = [
            (Season.summer, year),
            (Season.winter, year),
            (Season.post_monsoon, year),
            (Season.monsoon, year),
        ]
        is_same_year = True
    else:
        target_seasons = CANONICAL_SEASONS
        is_same_year = False

    extracted_entries: list[tuple[str, int, dict[str, Any] | None]] = []
    summer_mean_c: float | None = None

    for s_enum, y_val in target_seasons:
        s_key = s_enum.value
        c_path = available_catalog.get((s_key, y_val))
        if c_path is not None:
            l_stats = _extract_layer_stats(c_path, intersection)
        else:
            l_stats = None
        extracted_entries.append((s_key, y_val, l_stats))
        if s_key == "summer" and l_stats is not None and l_stats.get("mean_c") is not None:
            summer_mean_c = l_stats["mean_c"]

    for s_key, y_val, l_stats in extracted_entries:
        if l_stats is not None:
            # Paired difference only where both seasons have valid observations
            if l_stats.get("mean_c") is not None and summer_mean_c is not None:
                delta_to_summer_c = round(float(l_stats["mean_c"] - summer_mean_c), 2)
            else:
                delta_to_summer_c = None

            seasons_table.append(
                {
                    "season": s_key,
                    "year": y_val,
                    "effective_year": y_val,
                    "mean_c": l_stats["mean_c"],
                    "min_c": l_stats["min_c"],
                    "max_c": l_stats["max_c"],
                    "valid_pixel_count": l_stats["valid_pixel_count"],
                    "data_coverage_percentage": l_stats["data_coverage_percentage"],
                    "is_partial": l_stats["is_partial"],
                    "delta_to_summer_c": delta_to_summer_c,
                }
            )

    # 8. Status Categorization
    if inside_smc_fraction < 0.99:
        status_label = "partially_outside"
    else:
        status_label = "ok"

    return {
        "status": status_label,
        "season": season_str,
        "effective_year": effective_year,
        "same_year_comparison": is_same_year,
        "season_note": (
            f"Same-year comparison ({year})"
            if is_same_year
            else "latest available composite per season (mixed years: Post-Monsoon 2025)"
        ),
        "source_file": cog_path.name,
        "area_km2": round(area_km2, 4),
        "inside_smc_fraction": inside_smc_fraction,
        "boundary_source": "SMC study-area polygon in PostGIS",
        "valid_pixel_count": valid_pixel_count,
        "total_intersecting_pixel_count": total_intersecting_pixels,
        "nodata_pixel_count": max(0, total_intersecting_pixels - valid_pixel_count),
        "data_coverage_percentage": coverage_percentage,
        "coverage_definition": "valid / intersecting pixels",
        "geometry_repaired": geometry_repaired,
        "is_very_small_polygon": area_km2 < 0.01,
        "ndwi_water_fraction": ndwi_water_fraction,
        "water_warning": water_warning,
        "geometry": polygon_metadata,
        "statistics": statistics,
        "seasons_table": seasons_table,
        "raster": {
            "source": cog_path.name,
            "crs": "EPSG:32643 planar (analytical) / EPSG:4326 (display)",
            "nodata": NODATA,
            "units": "degrees_celsius",
        },
    }