"""API endpoints for Stage C Heat Priority Index (HPI) data.

Provides read-only access to authoritative analytical grid cells, HPI scores,
component layers (thermal severity, persistence, vegetation deficit, built density),
confidence ratings, and chronic hotspot status.
"""

from __future__ import annotations

import json
import math
from pathlib import Path as FilePath
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models.stage_c import (
    StageCGridCell,
    StageCGridObservation,
    StageCHeatPriorityScore,
)
from backend.app.db.session import get_db
from backend.app.raster.catalog import Season

PROJECT_ROOT = FilePath(__file__).resolve().parents[4]

router = APIRouter(
    prefix="/heat-priority",
    tags=["heat-priority"],
)



def safe_float(val: Any, decimals: int | None = None) -> float | None:
    """Safely convert and round floating point values, converting NaN/Inf/None to None (JSON null)."""
    if val is None:
        return None
    try:
        f = float(val)
        if not math.isfinite(f):
            return None
        return round(f, decimals) if decimals is not None else f
    except (ValueError, TypeError):
        return None


class NormalizationConstants(BaseModel):
    t_min_c: float = 30.0
    t_max_c: float = 50.0
    ndvi_min: float = 0.05
    ndvi_target: float = 0.45
    ndbi_min: float = -0.25
    ndbi_max: float = 0.15
    w_thermal: float = 0.40
    w_persistence: float = 0.30
    w_vegetation: float = 0.15
    w_builtup: float = 0.15
    formula: str = "HPI = 100 * (0.40 * T_norm + 0.30 * P_persist + 0.15 * V_deficit + 0.15 * B_density)"
    data_observation_years: str = "2021-2026 (Summer, Winter, Monsoon); 2021-2025 (Post-Monsoon)"
    overpass_solar_time: str = "~10:30 local solar time (about 11:00 IST)"


class HeatPrioritySummaryResponse(BaseModel):
    scoring_period: str
    spec_version: str
    total_grid_cells: int
    scored_cells: int
    mean_hpi: float | None = None
    min_hpi: float | None = None
    max_hpi: float | None = None
    chronic_hotspots_count: int
    confidence_tier_counts: dict[str, int]
    persistence_tier_counts: dict[str, int]
    normalization_constants: NormalizationConstants = Field(default_factory=NormalizationConstants)


class LSTStatsResponse(BaseModel):
    season: Season
    year: int
    effective_year: int
    n_cells: int
    n_valid: int
    valid_fraction: float | None = None
    mean_c: float | None = None
    min_c: float | None = None
    max_c: float | None = None
    p90_c: float | None = None
    source: str = "stage_c_grid_observations"
    is_partial: bool = False
    n_scenes: int | None = None
    first_acquisition_date: str | None = None
    last_acquisition_date: str | None = None
    date_window: str | None = None


SEASON_PROVENANCE: dict[tuple[str, int], dict[str, Any]] = {
    ("summer", 2026): {
        "n_scenes": 22,
        "first_acquisition_date": "2026-03-04",
        "last_acquisition_date": "2026-05-31",
        "date_window": "2026-03-04 to 2026-05-31",
    },
    ("winter", 2026): {
        "n_scenes": 20,
        "first_acquisition_date": "2025-12-06",
        "last_acquisition_date": "2026-02-24",
        "date_window": "2025-12-06 to 2026-02-24",
    },
    ("monsoon", 2026): {
        "n_scenes": 6,
        "first_acquisition_date": "2026-06-08",
        "last_acquisition_date": "2026-09-28",
        "date_window": "2026-06-08 to 2026-09-28",
    },
    ("post_monsoon", 2025): {
        "n_scenes": 14,
        "first_acquisition_date": "2025-10-03",
        "last_acquisition_date": "2025-11-28",
        "date_window": "2025-10-03 to 2025-11-28",
    },
}


class GridCellScoreItem(BaseModel):
    pixel_id: str
    row_idx: int
    col_idx: int
    latitude: float
    longitude: float
    nearest_osm_place_name: str | None = None
    nearest_osm_distance_m: float | None = None
    heat_priority_score: float | None = None
    thermal_severity_component: float | None = None
    persistence_component: float | None = None
    vegetation_deficit_component: float | None = None
    built_density_component: float | None = None
    confidence_index: float | None = None
    confidence_tier: str | None = None
    persistence_tier: str | None = None
    is_chronic_hotspot: bool = False
    hotspot_frequency: float | None = None
    eligibility_status: str | None = None
    observed_lst_c: float | None = None
    optical_imputation_flag: str | None = None


class GridCellsPaginatedResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[GridCellScoreItem]


@router.get("/summary", response_model=HeatPrioritySummaryResponse)
def get_heat_priority_summary(
    response: Response,
    scoring_period: str = Query("2026_summer_operational", description="Scoring period identifier"),
    spec_version: str = Query("v2.0", description="Specification version"),
    db: Session = Depends(get_db),
) -> HeatPrioritySummaryResponse:
    """Retrieve aggregate summary statistics for the operational HPI dataset."""
    total_cells = db.scalar(select(func.count()).select_from(StageCGridCell)) or 0

    scores_q = (
        select(
            func.count(StageCHeatPriorityScore.pixel_id).label("scored_count"),
            func.avg(StageCHeatPriorityScore.heat_priority_score).label("mean_score"),
            func.min(StageCHeatPriorityScore.heat_priority_score).label("min_score"),
            func.max(StageCHeatPriorityScore.heat_priority_score).label("max_score"),
            func.count()
            .filter(StageCHeatPriorityScore.is_chronic_hotspot.is_(True))
            .label("chronic_count"),
        )
        .where(StageCHeatPriorityScore.scoring_period == scoring_period)
        .where(StageCHeatPriorityScore.spec_version == spec_version)
    )
    score_stats = db.execute(scores_q).one()

    # Confidence tiers distribution
    conf_q = (
        select(
            StageCHeatPriorityScore.confidence_tier,
            func.count(StageCHeatPriorityScore.pixel_id),
        )
        .where(StageCHeatPriorityScore.scoring_period == scoring_period)
        .where(StageCHeatPriorityScore.spec_version == spec_version)
        .group_by(StageCHeatPriorityScore.confidence_tier)
    )
    conf_counts = {tier: count for tier, count in db.execute(conf_q).all()}

    # Persistence tiers distribution
    pers_q = (
        select(
            StageCHeatPriorityScore.persistence_tier,
            func.count(StageCHeatPriorityScore.pixel_id),
        )
        .where(StageCHeatPriorityScore.scoring_period == scoring_period)
        .where(StageCHeatPriorityScore.spec_version == spec_version)
        .group_by(StageCHeatPriorityScore.persistence_tier)
    )
    pers_counts = {tier: count for tier, count in db.execute(pers_q).all()}

    response.headers["Cache-Control"] = "public, max-age=1800, must-revalidate"
    response.headers["ETag"] = f'"hpi-summary-{scoring_period}-{spec_version}"'

    return HeatPrioritySummaryResponse(
        scoring_period=scoring_period,
        spec_version=spec_version,
        total_grid_cells=total_cells,
        scored_cells=score_stats.scored_count or 0,
        mean_hpi=safe_float(score_stats.mean_score, 2),
        min_hpi=safe_float(score_stats.min_score, 2),
        max_hpi=safe_float(score_stats.max_score, 2),
        chronic_hotspots_count=score_stats.chronic_count or 0,
        confidence_tier_counts=conf_counts,
        persistence_tier_counts=pers_counts,
        normalization_constants=NormalizationConstants(),
    )


@router.get("/lst-stats", response_model=LSTStatsResponse)
def get_heat_priority_lst_stats(
    response: Response,
    season: Season = Query(Season.summer, description="Observation season (summer, winter, post_monsoon, monsoon)"),
    year: int | None = Query(None, ge=2020, le=2030, description="Observation year (defaults to 2026, or 2025 for post_monsoon)"),
    db: Session = Depends(get_db),
) -> LSTStatsResponse:
    """Retrieve dynamic aggregate LST statistics across the authoritative SMC grid domain.

    Computes count, mean, min, max, and p90 from stage_c_grid_observations joined to stage_c_grid_cells.
    """
    total_cells = db.scalar(select(func.count(StageCGridCell.pixel_id))) or 49747

    if season == Season.post_monsoon and (year is None or year == 2026):
        effective_year = 2025
        req_year = year or 2026
    else:
        effective_year = year or 2026
        req_year = effective_year

    q = (
        select(
            func.count(StageCGridObservation.observed_lst_c).label("n_valid"),
            func.avg(StageCGridObservation.observed_lst_c).label("mean_c"),
            func.min(StageCGridObservation.observed_lst_c).label("min_c"),
            func.max(StageCGridObservation.observed_lst_c).label("max_c"),
            func.percentile_cont(0.90).within_group(StageCGridObservation.observed_lst_c).label("p90_c"),
        )
        .join(StageCGridCell, StageCGridCell.pixel_id == StageCGridObservation.pixel_id)
        .where(StageCGridObservation.season == season.value)
        .where(StageCGridObservation.year == effective_year)
    )
    res = db.execute(q).one()

    if not res or res.n_valid == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No LST observation records found for season '{season.value}' and year {effective_year}.",
        )

    is_partial = bool(res.n_valid < total_cells)
    valid_fraction = round(float(res.n_valid / total_cells), 4) if total_cells > 0 else 0.0
    prov = SEASON_PROVENANCE.get((season.value, effective_year), {})

    response.headers["Cache-Control"] = "public, max-age=1800, must-revalidate"
    response.headers["ETag"] = f'"lst-stats-{season.value}-{effective_year}"'

    return LSTStatsResponse(
        season=season,
        year=req_year,
        effective_year=effective_year,
        n_cells=total_cells,
        n_valid=res.n_valid,
        valid_fraction=valid_fraction,
        mean_c=safe_float(res.mean_c, 2),
        min_c=safe_float(res.min_c, 2),
        max_c=safe_float(res.max_c, 2),
        p90_c=safe_float(res.p90_c, 2),
        source="stage_c_grid_observations",
        is_partial=is_partial,
        n_scenes=prov.get("n_scenes"),
        first_acquisition_date=prov.get("first_acquisition_date"),
        last_acquisition_date=prov.get("last_acquisition_date"),
        date_window=prov.get("date_window"),
    )


@router.get("/cells", response_model=GridCellsPaginatedResponse)
def get_grid_cells(
    response: Response,
    scoring_period: str = Query("2026_summer_operational", description="Scoring period identifier"),
    spec_version: str = Query("v2.0", description="Specification version"),
    season: Season = Query(Season.summer, description="Observation season to join (summer, winter, post_monsoon, monsoon)"),
    year: int = Query(2026, ge=2020, le=2030, description="Observation year to join"),
    min_hpi: float | None = Query(None, ge=0.0, le=100.0, description="Filter cells with HPI >= min_hpi"),
    is_chronic_hotspot: bool | None = Query(None, description="Filter by chronic hotspot flag"),
    confidence_tier: str | None = Query(
        None,
        pattern=r"^(HIGH|MODERATE|LOW|INSUFFICIENT)$",
        description="Filter by confidence tier (HIGH, MODERATE, LOW, INSUFFICIENT)",
    ),
    persistence_tier: str | None = Query(
        None,
        pattern=r"^(chronic_hotspot|frequent_hotspot|occasional_hotspot|transient_extreme|non_hotspot)$",
        description="Filter by persistence tier",
    ),
    locality: str | None = Query(None, min_length=1, max_length=100, description="Filter by OSM place name substring"),
    min_lat: float | None = Query(None, description="Minimum latitude for viewport bounding box"),
    max_lat: float | None = Query(None, description="Maximum latitude for viewport bounding box"),
    min_lon: float | None = Query(None, description="Minimum longitude for viewport bounding box"),
    max_lon: float | None = Query(None, description="Maximum longitude for viewport bounding box"),
    bbox: str | None = Query(None, description="Bounding box filter as 'min_lon,min_lat,max_lon,max_lat'"),
    limit: int = Query(50, ge=1, le=500, description="Page limit (1 to 500)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0)"),
    db: Session = Depends(get_db),
) -> GridCellsPaginatedResponse:
    """Retrieve paginated grid cells with their HPI scores, observations, and spatial properties."""
    effective_year = 2025 if season == Season.post_monsoon and year == 2026 else year
    query = (
        select(
            StageCGridCell.pixel_id,
            StageCGridCell.row_idx,
            StageCGridCell.col_idx,
            StageCGridCell.latitude,
            StageCGridCell.longitude,
            StageCGridCell.nearest_osm_place_name,
            StageCGridCell.nearest_osm_distance_m,
            StageCHeatPriorityScore.heat_priority_score,
            StageCHeatPriorityScore.thermal_severity_component,
            StageCHeatPriorityScore.persistence_component,
            StageCHeatPriorityScore.vegetation_deficit_component,
            StageCHeatPriorityScore.built_density_component,
            StageCHeatPriorityScore.confidence_index,
            StageCHeatPriorityScore.confidence_tier,
            StageCHeatPriorityScore.persistence_tier,
            StageCHeatPriorityScore.is_chronic_hotspot,
            StageCHeatPriorityScore.hotspot_frequency,
            StageCHeatPriorityScore.eligibility_status,
            StageCGridObservation.observed_lst_c,
            StageCGridObservation.optical_imputation_flag,
        )
        .join(
            StageCHeatPriorityScore,
            StageCGridCell.pixel_id == StageCHeatPriorityScore.pixel_id,
        )
        .outerjoin(
            StageCGridObservation,
            (StageCGridCell.pixel_id == StageCGridObservation.pixel_id)
            & (StageCGridObservation.year == effective_year)
            & (StageCGridObservation.season == season.value),
        )
        .where(StageCHeatPriorityScore.scoring_period == scoring_period)
        .where(StageCHeatPriorityScore.spec_version == spec_version)
    )

    if min_hpi is not None:
        query = query.where(StageCHeatPriorityScore.heat_priority_score >= min_hpi)
    if is_chronic_hotspot is not None:
        query = query.where(StageCHeatPriorityScore.is_chronic_hotspot == is_chronic_hotspot)
    if confidence_tier is not None:
        query = query.where(StageCHeatPriorityScore.confidence_tier == confidence_tier)
    if persistence_tier is not None:
        query = query.where(StageCHeatPriorityScore.persistence_tier == persistence_tier)
    if locality is not None:
        query = query.where(StageCGridCell.nearest_osm_place_name.ilike(f"%{locality}%"))

    # Viewport Bounding Box filters
    if bbox:
        try:
            parts = [float(p.strip()) for p in bbox.split(",")]
            if len(parts) == 4:
                b_min_lon, b_min_lat, b_max_lon, b_max_lat = parts
                if not (-180.0 <= b_min_lon <= 180.0 and -180.0 <= b_max_lon <= 180.0 and -90.0 <= b_min_lat <= 90.0 and -90.0 <= b_max_lat <= 90.0):
                    raise HTTPException(status_code=400, detail="Bounding box coordinates out of range [-180, 180] lon, [-90, 90] lat.")
                if b_min_lon > b_max_lon or b_min_lat > b_max_lat:
                    raise HTTPException(status_code=400, detail="Reversed bounding box extent: min exceeds max.")
                query = (
                    query.where(StageCGridCell.latitude >= b_min_lat)
                    .where(StageCGridCell.latitude <= b_max_lat)
                    .where(StageCGridCell.longitude >= b_min_lon)
                    .where(StageCGridCell.longitude <= b_max_lon)
                )
            else:
                raise HTTPException(status_code=400, detail="Bounding box must contain exactly 4 coordinates: min_lon,min_lat,max_lon,max_lat.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bounding box format. Expected float coordinates.")
    else:
        if min_lat is not None:
            query = query.where(StageCGridCell.latitude >= min_lat)
        if max_lat is not None:
            query = query.where(StageCGridCell.latitude <= max_lat)
        if min_lon is not None:
            query = query.where(StageCGridCell.longitude >= min_lon)
        if max_lon is not None:
            query = query.where(StageCGridCell.longitude <= max_lon)

    # Count total matching
    count_subq = query.subquery()
    total = db.scalar(select(func.count()).select_from(count_subq)) or 0

    # Paginate and order by heat_priority_score descending
    results = db.execute(
        query.order_by(StageCHeatPriorityScore.heat_priority_score.desc().nullslast()).offset(offset).limit(limit)
    ).all()

    items = [
        GridCellScoreItem(
            pixel_id=r.pixel_id,
            row_idx=r.row_idx,
            col_idx=r.col_idx,
            latitude=r.latitude,
            longitude=r.longitude,
            nearest_osm_place_name=r.nearest_osm_place_name,
            nearest_osm_distance_m=safe_float(r.nearest_osm_distance_m, 1),
            heat_priority_score=safe_float(r.heat_priority_score, 2),
            thermal_severity_component=safe_float(r.thermal_severity_component, 4),
            persistence_component=safe_float(r.persistence_component, 4),
            vegetation_deficit_component=safe_float(r.vegetation_deficit_component, 4),
            built_density_component=safe_float(r.built_density_component, 4),
            confidence_index=safe_float(r.confidence_index, 4),
            confidence_tier=r.confidence_tier,
            persistence_tier=r.persistence_tier,
            is_chronic_hotspot=bool(r.is_chronic_hotspot) if r.is_chronic_hotspot is not None else False,
            hotspot_frequency=safe_float(r.hotspot_frequency, 4),
            eligibility_status=r.eligibility_status,
            observed_lst_c=safe_float(r.observed_lst_c, 2),
            optical_imputation_flag=r.optical_imputation_flag,
        )
        for r in results
    ]

    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"

    return GridCellsPaginatedResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=items,
    )


@router.get("/cell/{pixel_id}", response_model=GridCellScoreItem)
def get_grid_cell_detail(
    response: Response,
    pixel_id: str = Path(..., min_length=1, max_length=16, description="Canonical grid cell identifier (e.g., R045_C067)"),
    scoring_period: str = Query("2026_summer_operational", description="Scoring period identifier"),
    spec_version: str = Query("v2.0", description="Specification version"),
    season: Season = Query(Season.summer, description="Observation season to join"),
    year: int = Query(2026, ge=2020, le=2030, description="Observation year to join"),
    db: Session = Depends(get_db),
) -> GridCellScoreItem:
    """Retrieve detailed Stage C HPI score and components for a specific grid cell."""
    effective_year = 2025 if season == Season.post_monsoon and year == 2026 else year
    cell_query = (
        select(
            StageCGridCell.pixel_id,
            StageCGridCell.row_idx,
            StageCGridCell.col_idx,
            StageCGridCell.latitude,
            StageCGridCell.longitude,
            StageCGridCell.nearest_osm_place_name,
            StageCGridCell.nearest_osm_distance_m,
            StageCHeatPriorityScore.heat_priority_score,
            StageCHeatPriorityScore.thermal_severity_component,
            StageCHeatPriorityScore.persistence_component,
            StageCHeatPriorityScore.vegetation_deficit_component,
            StageCHeatPriorityScore.built_density_component,
            StageCHeatPriorityScore.confidence_index,
            StageCHeatPriorityScore.confidence_tier,
            StageCHeatPriorityScore.persistence_tier,
            StageCHeatPriorityScore.is_chronic_hotspot,
            StageCHeatPriorityScore.hotspot_frequency,
            StageCHeatPriorityScore.eligibility_status,
            StageCGridObservation.observed_lst_c,
            StageCGridObservation.optical_imputation_flag,
        )
        .outerjoin(
            StageCHeatPriorityScore,
            (StageCGridCell.pixel_id == StageCHeatPriorityScore.pixel_id)
            & (StageCHeatPriorityScore.scoring_period == scoring_period)
            & (StageCHeatPriorityScore.spec_version == spec_version),
        )
        .outerjoin(
            StageCGridObservation,
            (StageCGridCell.pixel_id == StageCGridObservation.pixel_id)
            & (StageCGridObservation.year == effective_year)
            & (StageCGridObservation.season == season.value),
        )
        .where(StageCGridCell.pixel_id == pixel_id)
    )

    r = db.execute(cell_query).first()
    if not r:
        raise HTTPException(
            status_code=404,
            detail=f"Grid cell '{pixel_id}' does not exist.",
        )

    response.headers["Cache-Control"] = "public, max-age=1800, must-revalidate"
    response.headers["ETag"] = f'"cell-{pixel_id}-{scoring_period}-{spec_version}-{season.value}-{effective_year}"'

    return GridCellScoreItem(
        pixel_id=r.pixel_id,
        row_idx=r.row_idx,
        col_idx=r.col_idx,
        latitude=r.latitude,
        longitude=r.longitude,
        nearest_osm_place_name=r.nearest_osm_place_name,
        nearest_osm_distance_m=safe_float(r.nearest_osm_distance_m, 1),
        heat_priority_score=safe_float(r.heat_priority_score, 2),
        thermal_severity_component=safe_float(r.thermal_severity_component, 4),
        persistence_component=safe_float(r.persistence_component, 4),
        vegetation_deficit_component=safe_float(r.vegetation_deficit_component, 4),
        built_density_component=safe_float(r.built_density_component, 4),
        confidence_index=safe_float(r.confidence_index, 4),
        confidence_tier=r.confidence_tier,
        persistence_tier=r.persistence_tier,
        is_chronic_hotspot=bool(r.is_chronic_hotspot) if r.is_chronic_hotspot is not None else False,
        hotspot_frequency=safe_float(r.hotspot_frequency, 4),
        eligibility_status=r.eligibility_status,
        observed_lst_c=safe_float(r.observed_lst_c, 2),
        optical_imputation_flag=r.optical_imputation_flag,
    )


@router.get("/model-validation", response_model=dict[str, Any])
def get_model_validation_summary(response: Response) -> dict[str, Any]:
    """Retrieve frozen ML model quality control, spatial holdout benchmarks, and sensor provenance."""
    qc_path = PROJECT_ROOT / "artifacts" / "ml_freeze" / "qc_summary.json"
    meta_path = PROJECT_ROOT / "artifacts" / "ml_freeze" / "model_metadata.json"
    if not qc_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Model validation artifact qc_summary.json not found.",
        )
    with open(qc_path, encoding="utf-8") as f:
        qc_data = json.load(f)
    model_meta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            with open(meta_path, encoding="utf-8") as f:
                model_meta = json.load(f)
        except Exception:
            pass

    comparison_path = PROJECT_ROOT / "data" / "diagnostics" / "ml" / "model_comparison_rf_xgb.csv"
    model_comparison: list[dict[str, Any]] = []
    if comparison_path.exists():
        try:
            import csv
            with open(comparison_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    model_comparison.append({
                        "model": row["model"],
                        "mean_mae": float(row["mean_MAE"]),
                        "std_mae": float(row["std_MAE"]),
                        "mean_rmse": float(row["mean_RMSE"]),
                        "std_rmse": float(row["std_RMSE"]),
                        "mean_r2": float(row["mean_R2"]),
                        "std_r2": float(row["std_R2"]),
                    })
        except Exception:
            pass

    exp_path = PROJECT_ROOT / "artifacts" / "ml_experiments" / "ml_experimental_evaluation.json"
    conformal_calibration: dict[str, Any] | None = None
    if exp_path.exists():
        try:
            with open(exp_path, encoding="utf-8") as f:
                exp_json = json.load(f)
                conformal_calibration = exp_json.get("experiments", {}).get("conformal_calibration")
        except Exception:
            pass

    response.headers["Cache-Control"] = "public, max-age=86400, must-revalidate"
    response.headers["ETag"] = '"ml-validation-frozen-v1"'

    return {
        "qc_summary": qc_data,
        "model_metadata": model_meta,
        "model_comparison": model_comparison,
        "conformal_calibration": conformal_calibration,
    }

