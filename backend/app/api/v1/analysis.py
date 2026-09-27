from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...raster.zonal import calculate_lst_zonal_statistics
from ...geocoding.nominatim import reverse_geocode_polygon
from ...geocoding.postgis_locality import resolve_polygon_locality

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
)


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