import json
import math
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ...core.rate_limit import InMemoryRateLimiter, get_client_ip
from ...db.models.stage_c import (
    StageCGridCell,
    StageCGridObservation,
    StageCHeatPriorityScore,
)
from ...db.session import get_db
from ...raster.catalog import Season
from ...raster.zonal import calculate_lst_zonal_statistics
from ...geocoding.nominatim import reverse_geocode_polygon
from ...geocoding.postgis_locality import resolve_polygon_locality
from gis.interventions.recommendations import (
    PolygonSummary,
    RecommendationsResponse,
    generate_polygon_recommendations,
)

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
    season: Season = Field(
        default=Season.summer,
        description="Analysis season (summer, winter, monsoon, post_monsoon)",
    )
    year: int | None = Field(
        default=None,
        description="Observation year (defaults to authoritative effective year)",
    )


@router.post("/zonal-stats")
def zonal_statistics(
    request: ZonalStatisticsRequest,
) -> dict:

    try:
        validate_analysis_geometry(request.geometry)
        return calculate_lst_zonal_statistics(
            request.geometry,
            season=request.season,
            year=request.year,
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

@router.post(
    "/resolve-area-name",
    deprecated=True,
    summary="Resolve locality name via Nominatim (Deprecated)",
    description="Legacy Nominatim-based resolver. Deprecated in favor of /resolve-area-name-postgis.",
)
def resolve_area_name(
    request: ZonalStatisticsRequest,
    response: Response,
) -> dict:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/v1/analysis/resolve-area-name-postgis>; rel="successor-version"'
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


# Rate limiter for public recommendations endpoint (30 requests/minute per IP)
recommendations_rate_limiter = InMemoryRateLimiter(max_attempts=30, window_seconds=60)


class RecommendationsRequest(BaseModel):
    geometry: dict = Field(
        ...,
        description="GeoJSON Polygon geometry in EPSG:4326",
    )
    season: Season = Field(
        default=Season.summer,
        description="Analysis season (summer, winter, monsoon, post_monsoon)",
    )
    year: int | None = Field(
        default=None,
        description="Observation year (defaults to authoritative effective year)",
    )


@router.post(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="Generate evidence-backed intervention recommendations for a custom polygon",
    description="Public rate-limited endpoint synthesizing spatial recommendations strictly from observed metrics and Stage D models.",
)
def get_polygon_recommendations(
    request_data: RecommendationsRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> RecommendationsResponse:
    """Synthesize evidence-based intervention recommendations for a spatial polygon."""
    # 1. Rate Limiting Check
    client_ip = get_client_ip(http_request)
    is_allowed, retry_after = recommendations_rate_limiter.check_and_record(f"recs_{client_ip}")
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Geometry Validation
    try:
        validate_analysis_geometry(request_data.geometry)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 3. Calculate Zonal LST Statistics and SMC Containment
    try:
        zonal_stats = calculate_lst_zonal_statistics(
            request_data.geometry,
            season=request_data.season,
            year=request_data.year,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to calculate zonal statistics for polygon: {exc}",
        ) from exc

    # 4. Extract Zonal Fields
    status_str = zonal_stats.get("status", "ok")
    area_km2 = float(zonal_stats.get("area_km2", 0.0))
    inside_smc = float(zonal_stats.get("inside_smc_fraction", 1.0))
    effective_year = int(zonal_stats.get("effective_year", request_data.year or 2026))
    coverage_pct = float(zonal_stats.get("data_coverage_percentage", 0.0))
    water_fraction = float(zonal_stats.get("ndwi_water_fraction", 0.0))
    water_warning = bool(zonal_stats.get("water_warning", False))

    stats_dict = zonal_stats.get("statistics") or {}
    mean_lst = stats_dict.get("mean_c") if "mean_c" in stats_dict else stats_dict.get("mean")
    max_lst = stats_dict.get("max_c") if "max_c" in stats_dict else stats_dict.get("max")
    min_lst = stats_dict.get("min_c") if "min_c" in stats_dict else stats_dict.get("min")
    p90_lst = stats_dict.get("p90_c") if "p90_c" in stats_dict else stats_dict.get("p90")

    # 5. Query Intersecting Stage C Grid Cells from PostGIS
    poly_json = json.dumps(request_data.geometry)
    geom_expr = func.ST_SetSRID(func.ST_GeomFromGeoJSON(poly_json), 4326)

    cell_query = (
        select(
            StageCGridCell.pixel_id,
            StageCGridCell.row_idx,
            StageCGridCell.col_idx,
            StageCHeatPriorityScore.heat_priority_score,
            StageCHeatPriorityScore.vegetation_deficit_component,
            StageCHeatPriorityScore.built_density_component,
            StageCHeatPriorityScore.persistence_component,
            StageCHeatPriorityScore.confidence_index,
            StageCHeatPriorityScore.confidence_tier,
            StageCHeatPriorityScore.is_chronic_hotspot,
            StageCHeatPriorityScore.hotspot_frequency,
            StageCGridObservation.ndvi,
            StageCGridObservation.ndbi,
            StageCGridObservation.ndwi,
        )
        .join(StageCHeatPriorityScore, StageCGridCell.pixel_id == StageCHeatPriorityScore.pixel_id)
        .outerjoin(
            StageCGridObservation,
            and_(
                StageCGridCell.pixel_id == StageCGridObservation.pixel_id,
                StageCGridObservation.season == request_data.season.value,
                StageCGridObservation.year == effective_year,
            ),
        )
        .where(func.ST_Intersects(StageCGridCell.geometry, geom_expr))
    )

    cell_rows = db.execute(cell_query).all()
    cell_count = len(cell_rows)

    if cell_count > 0:
        hpi_vals = [r.heat_priority_score for r in cell_rows if r.heat_priority_score is not None]
        mean_hpi = float(sum(hpi_vals) / len(hpi_vals)) if hpi_vals else None
        max_hpi = float(max(hpi_vals)) if hpi_vals else None

        veg_vals = [r.vegetation_deficit_component for r in cell_rows if r.vegetation_deficit_component is not None]
        mean_veg_def = float(sum(veg_vals) / len(veg_vals)) if veg_vals else None

        built_vals = [r.built_density_component for r in cell_rows if r.built_density_component is not None]
        mean_built = float(sum(built_vals) / len(built_vals)) if built_vals else None

        conf_vals = [r.confidence_index for r in cell_rows if r.confidence_index is not None]
        mean_conf = float(sum(conf_vals) / len(conf_vals)) if conf_vals else 0.0

        chronic_count = sum(1 for r in cell_rows if r.is_chronic_hotspot)
        chronic_share = float(chronic_count / cell_count)

        frequent_count = sum(1 for r in cell_rows if r.hotspot_frequency is not None and r.hotspot_frequency >= 0.50)
        frequent_share = float(frequent_count / cell_count)

        ndvi_vals = [r.ndvi for r in cell_rows if r.ndvi is not None]
        mean_ndvi = float(sum(ndvi_vals) / len(ndvi_vals)) if ndvi_vals else None

        ndbi_vals = [r.ndbi for r in cell_rows if r.ndbi is not None]
        mean_ndbi = float(sum(ndbi_vals) / len(ndbi_vals)) if ndbi_vals else None

        ndwi_vals = [r.ndwi for r in cell_rows if r.ndwi is not None]
        mean_ndwi = float(sum(ndwi_vals) / len(ndwi_vals)) if ndwi_vals else None

        conf_tier = "HIGH" if mean_conf >= 0.70 else ("MEDIUM" if mean_conf >= 0.40 else "LOW")
    else:
        mean_hpi = None
        max_hpi = None
        mean_veg_def = None
        mean_built = None
        mean_conf = 0.0
        chronic_count = 0
        chronic_share = 0.0
        frequent_share = 0.0
        mean_ndvi = None
        mean_ndbi = None
        mean_ndwi = None
        conf_tier = "LOW"

    # 6. Assemble PolygonSummary
    summary = PolygonSummary(
        status=status_str,
        area_km2=round(area_km2, 4),
        inside_smc_fraction=round(inside_smc, 4),
        season=request_data.season.value,
        effective_year=effective_year,
        mean_lst_c=round(mean_lst, 2) if mean_lst is not None else None,
        max_lst_c=round(max_lst, 2) if max_lst is not None else None,
        min_lst_c=round(min_lst, 2) if min_lst is not None else None,
        p90_lst_c=round(p90_lst, 2) if p90_lst is not None else None,
        mean_hpi=round(mean_hpi, 2) if mean_hpi is not None else None,
        max_hpi=round(max_hpi, 2) if max_hpi is not None else None,
        vegetation_deficit_component=round(mean_veg_def, 4) if mean_veg_def is not None else None,
        built_density_component=round(mean_built, 4) if mean_built is not None else None,
        mean_ndvi=round(mean_ndvi, 4) if mean_ndvi is not None else None,
        mean_ndbi=round(mean_ndbi, 4) if mean_ndbi is not None else None,
        mean_ndwi=round(mean_ndwi, 4) if mean_ndwi is not None else None,
        water_fraction=round(water_fraction, 4),
        water_warning=water_warning,
        cell_count=cell_count,
        chronic_cell_count=chronic_count,
        chronic_cell_share=round(chronic_share, 4),
        frequent_cell_share=round(frequent_share, 4),
        data_coverage_percentage=round(coverage_pct, 2),
        confidence_score=round(mean_conf, 4),
        confidence_tier=conf_tier,
    )

    # 7. Generate Recommendations via pure rule engine
    return generate_polygon_recommendations(summary)