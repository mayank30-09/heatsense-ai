from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from pyproj import Geod
from rasterio.features import geometry_mask
from rasterio.mask import mask
from shapely.geometry import shape


COG_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "rasters"
    / "surat_landsat_lst_first_scene_cog.tif"
)

NODATA = -9999.0

geod = Geod(ellps="WGS84")


def calculate_polygon_area_km2(geometry) -> float:
    area_m2, _ = geod.geometry_area_perimeter(geometry)
    return abs(area_m2) / 1_000_000.0


def calculate_polygon_perimeter_km(geometry) -> float:
    _, perimeter_m = geod.geometry_area_perimeter(geometry)
    return perimeter_m / 1_000.0


def calculate_lst_zonal_statistics(
    geometry: dict,
) -> dict:

    if not COG_PATH.exists():
        raise FileNotFoundError(
            f"LST COG not found: {COG_PATH}"
        )

    polygon = shape(geometry)

    if polygon.is_empty:
        raise ValueError(
            "Selected area geometry is empty."
        )

    if not polygon.is_valid:
        polygon = polygon.buffer(0)

    if polygon.is_empty or not polygon.is_valid:
        raise ValueError(
            "Selected area geometry is invalid."
        )

    if polygon.geom_type != "Polygon":
        raise ValueError(
            "Only Polygon geometries are currently supported."
        )

    # ---------------------------------------------------------
    # Selected polygon metadata
    # ---------------------------------------------------------

    area_km2 = calculate_polygon_area_km2(
        polygon
    )

    perimeter_km = calculate_polygon_perimeter_km(
        polygon
    )

    centroid = polygon.centroid

    min_lon, min_lat, max_lon, max_lat = (
        polygon.bounds
    )

    polygon_metadata = {
        "geometry_type": polygon.geom_type,
        "crs": "EPSG:4326",
        "area_km2": round(area_km2, 4),
        "perimeter_km": round(perimeter_km, 4),
        "centroid": {
            "longitude": round(
                float(centroid.x),
                6,
            ),
            "latitude": round(
                float(centroid.y),
                6,
            ),
        },
        "bounding_box": {
            "min_longitude": round(
                float(min_lon),
                6,
            ),
            "min_latitude": round(
                float(min_lat),
                6,
            ),
            "max_longitude": round(
                float(max_lon),
                6,
            ),
            "max_latitude": round(
                float(max_lat),
                6,
            ),
        },
    }

    with rasterio.open(COG_PATH) as src:

        if src.crs is None:
            raise ValueError(
                "LST raster has no CRS."
            )

        raster_geometry = polygon

        if str(src.crs) != "EPSG:4326":
            from rasterio.warp import transform_geom

            raster_geometry = shape(
                transform_geom(
                    "EPSG:4326",
                    src.crs,
                    polygon.__geo_interface__,
                )
            )

        try:
            data, out_transform = mask(
                src,
                [
                    raster_geometry.__geo_interface__
                ],
                crop=True,
                filled=False,
            )

        except ValueError as exc:

            if "do not overlap raster" in str(exc):
                return {
                    "status": "no_data",
                    "area_km2": round(
                        area_km2,
                        4,
                    ),
                    "valid_pixel_count": 0,
                    "total_intersecting_pixel_count": 0,
                    "data_coverage_percentage": 0.0,
                    "geometry": polygon_metadata,
                    "statistics": None,
                    "raster": {
                        "source": COG_PATH.name,
                        "crs": str(src.crs),
                        "nodata": NODATA,
                        "units": "degrees_celsius",
                    },
                }

            raise

        band = data[0]

        # Pixels whose centers/intersection footprint are
        # considered part of the selected polygon.
        inside_polygon = geometry_mask(
            [
                raster_geometry.__geo_interface__
            ],
            out_shape=band.shape,
            transform=out_transform,
            invert=True,
            all_touched=False,
        )

        masked_values = np.ma.getmaskarray(
            band
        )

        valid_pixels = (
            inside_polygon
            & ~masked_values
        )

        raw_values = np.asarray(
            band.data,
            dtype=np.float32,
        )

        valid_pixels &= np.isfinite(
            raw_values
        )

        valid_pixels &= (
            raw_values != NODATA
        )

        total_intersecting_pixels = int(
            inside_polygon.sum()
        )

        valid_pixel_count = int(
            valid_pixels.sum()
        )

        if total_intersecting_pixels == 0:
            return {
                "status": "no_data",
                "area_km2": round(
                    area_km2,
                    4,
                ),
                "valid_pixel_count": 0,
                "total_intersecting_pixel_count": 0,
                "data_coverage_percentage": 0.0,
                "geometry": polygon_metadata,
                "statistics": None,
                "raster": {
                    "source": COG_PATH.name,
                    "crs": str(src.crs),
                    "nodata": NODATA,
                    "units": "degrees_celsius",
                },
            }

        coverage_percentage = (
            valid_pixel_count
            / total_intersecting_pixels
            * 100.0
        )

        values = raw_values[
            valid_pixels
        ]

    if values.size == 0:
        return {
            "status": "no_data",
            "area_km2": round(
                area_km2,
                4,
            ),
            "valid_pixel_count": 0,
            "total_intersecting_pixel_count": (
                total_intersecting_pixels
            ),
            "data_coverage_percentage": 0.0,
            "geometry": polygon_metadata,
            "statistics": None,
            "raster": {
                "source": COG_PATH.name,
                "crs": str(src.crs),
                "nodata": NODATA,
                "units": "degrees_celsius",
            },
        }

    statistics = {
        "min_c": round(
            float(np.min(values)),
            3,
        ),
        "max_c": round(
            float(np.max(values)),
            3,
        ),
        "mean_c": round(
            float(np.mean(values)),
            3,
        ),
        "median_c": round(
            float(np.median(values)),
            3,
        ),
        "std_c": round(
            float(np.std(values)),
            3,
        ),
        "p10_c": round(
            float(np.percentile(values, 10)),
            3,
        ),
        "p25_c": round(
            float(np.percentile(values, 25)),
            3,
        ),
        "p75_c": round(
            float(np.percentile(values, 75)),
            3,
        ),
        "p90_c": round(
            float(np.percentile(values, 90)),
            3,
        ),
    }

    return {
        "status": "ok",

        "area_km2": round(
            area_km2,
            4,
        ),

        "valid_pixel_count": valid_pixel_count,

        "total_intersecting_pixel_count": (
            total_intersecting_pixels
        ),

        "data_coverage_percentage": round(
            coverage_percentage,
            2,
        ),

        "geometry": polygon_metadata,

        "statistics": statistics,

        "raster": {
            "source": COG_PATH.name,
            "crs": str(src.crs),
            "nodata": NODATA,
            "units": "degrees_celsius",
        },
    }