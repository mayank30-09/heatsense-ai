from __future__ import annotations

import math
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...raster.zonal import calculate_lst_zonal_statistics
from ...geocoding.nominatim import reverse_geocode_polygon
from ...geocoding.postgis_locality import resolve_polygon_locality

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
)


MAX_GEOMETRY_VERTICES = 2500


def validate_analysis_geometry(geometry: dict) -> None:
    """Validate GeoJSON polygon geometry complexity, closure, and coordinate bounds.

    Shields downstream rasterio and PostGIS spatial engines against non-finite values (NaN/Inf),
    unclosed linear rings, boolean type coercion, degenerate polygons, and unbounded coordinate complexity.
    """
    if not isinstance(geometry, dict):
        raise ValueError("Geometry must be a GeoJSON dictionary object.")

    geom_type = geometry.get("type")
    if geom_type != "Polygon":
        raise ValueError(f"Unsupported geometry type '{geom_type}'. Only 'Polygon' is accepted.")

    coords = geometry.get("coordinates")
    if not isinstance(coords, list) or len(coords) == 0:
        raise ValueError("Polygon coordinates must be a non-empty list of linear rings.")

    total_vertices = 0
    for ring_idx, ring in enumerate(coords):
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError(f"Linear ring {ring_idx} must contain at least 4 coordinate positions.")

        # RFC 7946 GeoJSON §3.1.6: The first and last points of a linear ring MUST be equivalent
        if ring[0] != ring[-1]:
            raise ValueError(f"Linear ring {ring_idx} is not closed: first and last coordinates must match.")

        total_vertices += len(ring)
        if total_vertices > MAX_GEOMETRY_VERTICES:
            raise ValueError(
                f"Polygon exceeds maximum allowed complexity ({MAX_GEOMETRY_VERTICES} vertices). "
                "Please simplify the polygon before requesting analysis."
            )

        distinct_positions: set[tuple[float, float]] = set()
        for pt_idx, pt in enumerate(ring):
            if not isinstance(pt, (list, tuple)) or len(pt) not in (2, 3):
                raise ValueError(
                    f"Invalid coordinate format at ring {ring_idx}, index {pt_idx}; expected [lon, lat]."
                )

            lon, lat = pt[0], pt[1]
            if isinstance(lon, bool) or isinstance(lat, bool):
                raise ValueError(f"Coordinate ({lon}, {lat}) must be numeric, not boolean.")
            if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
                raise ValueError(f"Coordinate ({lon}, {lat}) must be numeric.")
            if not math.isfinite(lon) or not math.isfinite(lat):
                raise ValueError(f"Coordinate ({lon}, {lat}) must be finite numbers.")
            if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                raise ValueError(f"Coordinate ({lon}, {lat}) out of valid range [-180, 180] lon, [-90, 90] lat.")

            distinct_positions.add((round(float(lon), 8), round(float(lat), 8)))

        if len(distinct_positions) < 3:
            raise ValueError(f"Linear ring {ring_idx} must contain at least 3 distinct coordinate positions.")


class ZonalStatisticsRequest(BaseModel):
    geometry: dict = Field(
        ...,
        description="GeoJSON Polygon geometry in EPSG:4326",
    )


@router.post("/zonal-stats")
def zonal_statistics(
    request: ZonalStatisticsRequest,
) -> dict:

    try:
        validate_analysis_geometry(request.geometry)
        return calculate_lst_zonal_statistics(
            request.geometry
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to calculate zonal statistics: {exc}",
        ) from exc

@router.post("/resolve-area-name")
def resolve_area_name(
    request: ZonalStatisticsRequest,
) -> dict:
    try:
        validate_analysis_geometry(request.geometry)
        return reverse_geocode_polygon(
            request.geometry
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to resolve area name: {exc}",
        ) from exc

@router.post("/resolve-area-name-postgis")
def resolve_area_name_postgis(
    request: ZonalStatisticsRequest,
) -> dict:
    try:
        validate_analysis_geometry(request.geometry)
        postgis_result = resolve_polygon_locality(
            request.geometry
        )

        # Primary resolver succeeded.
        if postgis_result.get("resolved"):
            return postgis_result

        # PostGIS did not have a sufficiently confident
        # locality match. Use Nominatim as fallback.
        nominatim_result = reverse_geocode_polygon(
            request.geometry
        )

        if nominatim_result.get("resolved"):
            return {
                **nominatim_result,
                "method": "nominatim_fallback",
                "postgis_result": {
                    "resolved": False,
                    "nearest_name": postgis_result.get(
                        "nearest_name"
                    ),
                    "nearest_distance_m": postgis_result.get(
                        "nearest_distance_m"
                    ),
                },
            }

        # Neither provider could confidently resolve
        # a human-readable locality.
        return {
            "resolved": False,
            "method": "unresolved",
            "name": None,
            "reason": (
                "No sufficiently confident locality "
                "could be resolved."
            ),
            "postgis_result": postgis_result,
            "nominatim_result": nominatim_result,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to resolve locality: "
                f"{exc}"
            ),
        ) from exc