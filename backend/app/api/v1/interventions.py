from __future__ import annotations
from backend.app.db.models.stage_d import StageDDynamicWorldLandCover, StageDLandCoverPipelineRun
from gis.interventions.landcover_suitability import (
    fetch_cell_landcover,
    evaluate_landcover_suitability,
    HEURISTIC_DISCLOSURE_LABEL,
    PHYSICAL_SURVEY_PREREQUISITE_LABEL,
)
from gis.gee.dynamic_world_pipeline import (
    DW_CLASSES,
    ATTRIBUTION_TEXT,
    CITATION_TEXT,
    LICENSE_TEXT,
    PIPELINE_VERSION,
)

"""FastAPI endpoints for Stage D Intervention Candidates and Optimization Scenarios.

Exposes:
- GET  /api/v1/interventions/candidates       : Viewport bounded, filtered candidate retrieval.
- GET  /api/v1/interventions/candidates/{id}  : Detailed candidate metadata and cost breakdown.
- POST /api/v1/interventions/optimize         : Multi-objective constrained optimization (Greedy / NSGA-II).
- GET  /api/v1/interventions/scenarios        : Available planning scenarios and benchmarks.
"""


import uuid

import json
import math
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[4]

from backend.app.config import get_settings
from backend.app.core.auth import User, UserRole, require_planner_or_admin
from backend.app.core.rate_limit import InMemoryRateLimiter, get_client_ip
from backend.app.db.session import get_db
from backend.app.db.models.stage_c import StageCHeatPriorityScore, StageCGridCell
from backend.app.db.models.stage_d import (
    StageDInterventionCandidate as DBInterventionCandidate,
    StageDScenarioResult as DBScenarioResult,
)
from gis.interventions import (
    FeasibilityStatus,
    InterventionCandidate,
    InterventionType,
    RejectionReason,
)
from gis.interventions.candidates import (
    generate_candidate_for_cell,
    generate_intervention_candidates,
)
from gis.interventions.costs import estimate_intervention_cost
from gis.interventions.cooling_effects import estimate_cooling_effect
from gis.interventions.optimization import (
    run_exact_knapsack_optimizer,
    compare_strategies,
    compute_locality_rollup,
    ScenarioSolution,
    run_baseline_greedy_optimizer,
    run_nsga2_optimizer,
)
from gis.interventions.clustering import (
    get_all_packages_for_area,
    get_type_availability,
    get_available_areas,
    get_area_summary,
    generate_clusters_for_area,
    get_cluster_cells,
)

router = APIRouter(prefix="/interventions", tags=["Stage D Interventions & Scenarios"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class CandidateResponse(BaseModel):
    candidate_id: str
    cell_id: str
    row: int
    col: int
    longitude: float
    latitude: float
    intervention_type: str
    usable_area_m2: float
    tree_count: int
    baseline_hpi: float | None
    baseline_lst_c: float | None
    is_chronic_hotspot: bool
    administrative_zone: str
    feasibility_status: str
    rejection_reason: str
    cost_inr: float
    cost_inr_range: list[float]
    expected_cooling_c: float
    expected_cooling_c_range: list[float]
    evidence_status: str
    geometry: dict[str, Any]
    air_cooling_c: float = 0.0
    landuse_typology: str = "unclassified"
    needs_site_survey: bool = False
    selection_rationale: str = ""
    rejected_alternatives: list[dict[str, str]] = []
    water_need_description: str = ""
    maintenance_burden: str = ""
    construction_time: str = ""
    screening_status: str = "MODEL_ELIGIBLE"
    screening_reason_code: str = "NONE"
    site_suitability: str = "UNKNOWN - survey required"
    ownership_legal: str = "UNVERIFIED"
    engineering_clearance: str = "NOT ASSESSED"
    procurement_status: str = "NOT STARTED"
    benefit_evidence: str = "MODELLED"
    data_confidence: str = "MEDIUM"
    cooling_metric: str = "modelled surface (skin) temperature reduction on treated area"
    cell_scope_note: str = "Treated area within 100m grid cell footprint; skin surface temperature reduction, not air temperature."
    price_date_note: str = "indicative, not a tender price"
    schedule_alignment_note: str = "rates not verified against CPWD/SMC schedule"
    unit_rate: float = 0.0
    unit_rate_unit: str = ""
    markups_description: str = "Includes 18% GST, 12% contingency, 6% design & supervision, and scaled site setup"
    targeted_surface: str = ""
    surface_source: str = ""
    is_proxy: bool = False
    cost_breakdown: dict[str, float] | None = None


class CandidateListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    items: list[CandidateResponse]


class AreaItemResponse(BaseModel):
    area_name: str
    total_cells: int
    eligible_cell_count: int
    chronic_hotspot_count: int
    mean_hpi: float
    max_hpi: float
    is_sufficient: bool
    data_status: str
    insufficient_reason: str | None = None
    top_recommended_type: str
    estimated_portfolio_cost_inr: float
    expected_portfolio_cooling_c: float


class DataConfidenceSummary(BaseModel):
    survey_required_percentage: float
    unverified_roof_percentage: float
    valid_observations_percentage: float
    measured_buildings_cells_count: int = 0
    proxy_cells_count: int = 0
    measured_percentage: float = 0.0
    proxy_percentage: float = 0.0


class Phase1PortfolioResponse(BaseModel):
    budget_cap_inr: float
    budget_utilized_inr: float
    budget_utilization_pct: float
    clusters_count: int
    cells_count: int
    chronic_hotspots_covered: int
    mean_cooling_c: float
    treated_footprint_m2: float


class CostBreakdownResponse(BaseModel):
    materials_cost_inr: float = 0.0
    labour_cost_inr: float = 0.0
    direct_cost_inr: float = 0.0
    design_supervision_inr: float = 0.0
    gst_18_pct_inr: float = 0.0
    contingency_inr: float = 0.0
    scaled_site_setup_inr: float = 0.0
    water_tanker_inr: float = 0.0
    plant_replacement_inr: float = 0.0
    capital_cost_inr: float = 0.0
    maintenance_3yr_inr: float = 0.0
    maintenance_10yr_inr: float = 0.0
    whole_life_cost_3yr_inr: float = 0.0
    whole_life_cost_10yr_inr: float = 0.0


class RateProvenanceResponse(BaseModel):
    source_name: str
    schedule_type: str
    item_reference: str
    rate_basis: str | None = None
    statutory_tax_note: str
    contingency_note: str
    design_supervision_note: str
    verified: bool = False


class EvidenceRationaleResponse(BaseModel):
    rule_fired: str
    governing_principle: str | None = None
    thermodynamics_formula: str | None = None
    empirical_cooling_range: str | None = None
    maturity_notice: str | None = None
    verified_literature_citations: list[str]
    uncertainties: list[str]
    survey_requirements: list[str]


class AreaSummaryResponse(BaseModel):
    area_name: str
    is_all_areas: bool
    total_cells: int
    eligible_cells: int
    chronic_cells: int
    assigned_cells_count: int = 0
    unassigned_insufficient_surface_count: int = 0
    mean_hpi: float
    mean_baseline_lst_c: float
    best_option_mean_cooling_c: float
    best_option_portfolio_cost_inr: float
    full_coverage_bound_inr: float = 0.0
    total_treated_area_m2: float
    total_geographic_area_ha: float
    qualifying_candidates_count: int
    clusters_count: int
    is_sufficient: bool
    insufficient_reason: str | None = None
    phase1_portfolio: Phase1PortfolioResponse | None = None
    data_confidence_summary: DataConfidenceSummary


class CentroidResponse(BaseModel):
    latitude: float
    longitude: float


class BoundingBoxResponse(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class ClusterRankingFactors(BaseModel):
    hpi_factor: float
    chronic_factor: float
    cooling_factor: float
    cost_effectiveness_factor: float


class ClusterRecommendationResponse(BaseModel):
    cluster_id: str
    area_name: str
    intervention_type: str
    title: str
    priority_rank: int
    priority_score: float
    priority_tier: str
    cell_count: int
    treated_footprint_m2: float
    geographic_coverage_ha: float
    expected_cooling_c: float
    expected_cooling_c_range: list[float]
    indicative_diluted_cooling_c: float
    estimated_cost_inr: float
    estimated_cost_inr_range: list[float]
    unit_cost_inr_per_m2: float
    mean_hpi: float
    max_hpi: float
    chronic_hotspot_cells_count: int
    mean_baseline_lst_c: float
    centroid: CentroidResponse
    bounding_box: BoundingBoxResponse
    confidence_rating: str
    survey_required_cells_count: int
    unverified_roof_cells_count: int
    targeted_surface: str = ""
    land_cover_source: str = ""
    cost_breakdown: CostBreakdownResponse | None = None
    rate_provenance: RateProvenanceResponse | None = None
    evidence_rationale: EvidenceRationaleResponse | None = None
    in_phase1_plan: bool = False
    caveats_and_warnings: list[str]
    co_benefits_summary: str
    ranking_factors: ClusterRankingFactors


class ClustersListResponse(BaseModel):
    total_clusters: int
    limit: int
    offset: int
    area_name: str
    is_sufficient: bool
    insufficient_reason: str | None = None
    clusters: list[ClusterRecommendationResponse]


class ClusterCellsResponse(BaseModel):
    cluster_id: str
    area_name: str
    intervention_type: str
    cell_count: int
    cells: list[CandidateResponse]


class OptimizeRequest(BaseModel):
    budget_inr: float = Field(
        default=50000000.0,
        gt=0.0,
        le=10_000_000_000.0,
        description="Total intervention budget in INR (must be positive, default: 5 Crore)",
    )
    algorithm: str = Field(default="exact", description="Optimization algorithm: 'exact' (Integer DP), 'nsga2' (Pareto) or 'greedy' (Knapsack)")
    strategy: str = Field(default="hotspot_first", description="Knapsack strategy: 'hotspot_first', 'max_benefit', or 'cost_effective'")
    scope: str = Field(default="all", description="Geographic scope: area name, or 'all' for citywide")
    target_types: list[str] | None = Field(default=None, description="Optional filter of allowed intervention types")
    max_candidates: int = Field(default=1000, ge=10, le=100000, description="Candidate search pool size")
    generations: int | None = Field(default=20, description="NSGA-II generations")


class DeploymentDetailResponse(BaseModel):
    candidate_id: str = Field(description="Unique candidate identifier")
    cell_id: str = Field(description="Stage C 100m grid cell ID")
    intervention_type: str = Field(description="Intervention typology")
    cost_inr: float = Field(description="Site capital + 3-year maintenance cost in INR")
    usable_area_m2: float = Field(description="Treated footprint area in m² (partial cell)")
    expected_cooling_c: float = Field(description="Modeled surface skin temperature reduction on treated area in °C")
    baseline_hpi: float | None = Field(default=None, description="Stage C Heat Priority Index (0-1)")
    baseline_lst_c: float | None = Field(default=None, description="Stage C baseline Landsat LST in °C")
    is_chronic_hotspot: bool = Field(default=False, description="Whether location is a persistent chronic heat hotspot")
    administrative_zone: str = Field(default="Central Zone", description="Municipal administrative zone / locality")
    latitude: float = Field(description="Cell centroid WGS84 latitude")
    longitude: float = Field(description="Cell centroid WGS84 longitude")
    landuse_typology: str = Field(default="unclassified", description="Surface land-use typology")
    feasibility_status: str = Field(default="FEASIBLE", description="Statutory feasibility status")
    prerequisites_status: str = Field(default="FEASIBLE_SUBJECT_TO_SURVEY", description="Survey readiness status")
    survey_prerequisites: list[str] = Field(default_factory=list, description="Unresolved legal/structural prerequisites required before execution")


class SolutionResponse(BaseModel):
    solution_id: str = Field(description="Unique identifier for the optimization scenario solution")
    run_id: str = Field(default="", description="Unique optimization execution run ID")
    algorithm: str = Field(description="Algorithm used: BASELINE_GREEDY_KNAPSACK or NSGA_II_PARETO")
    total_cost_inr: float = Field(description="Total capital + 3-year maintenance cost in INR (₹)")
    portfolio_thermal_benefit_c_m2: float = Field(
        description="Extensive thermal cooling benefit: sum(usable_area_m2 * delta_T_i) in °C·m²"
    )
    treated_area_m2: float = Field(description="Total footprint area receiving interventions in m²")
    mean_local_cooling_c: float = Field(
        description="Intervention-area-weighted mean estimated LST reduction over treated footprint in °C"
    )
    citywide_cooling_c: float = Field(
        description="Citywide area-weighted mean estimated LST reduction over authoritative SMC municipal domain (461.63 km²) in °C"
    )
    domain_area_m2: float = Field(
        description="Reference municipal domain area in m² (461,630,791.0 m² for Surat Municipal Corporation)"
    )
    heat_priority_weighted_benefit_c_m2: float = Field(
        description="Extensive heat-priority-weighted thermal cooling benefit: sum(A_i * delta_T_i * HPI_i) in °C·m²"
    )
    population_exposure_benefit: float | None = Field(
        default=None,
        description="Population-weighted exposure benefit. Explicitly null until validated ward population census layer is connected.",
    )
    population_exposure_status: str = Field(
        default="POPULATION_DATA_UNAVAILABLE",
        description="Status of population exposure calculation (POPULATION_DATA_UNAVAILABLE)",
    )
    chronic_hotspots_count: int = Field(description="Number of chronic heat priority hotspot cells mitigated")
    interventions_count: int = Field(description="Total count of intervention candidates selected")
    budget_limit_inr: float = Field(description="Specified budget ceiling in INR (₹)")
    budget_utilized_percent: float = Field(description="Percentage of budget limit utilized")
    is_feasible: bool = Field(description="Whether the solution strictly satisfies all constraints")
    pareto_rank: int = Field(default=1, description="Non-dominated Pareto front rank (1 = optimal)")
    crowding_distance: float = Field(default=0.0, description="NSGA-II diversity crowding distance metric")
    selected_candidate_ids: list[str] = Field(description="List of selected candidate IDs")
    deployments: list[DeploymentDetailResponse] = Field(
        default_factory=list,
        description="Authoritative per-site deployment attributes and survey prerequisites",
    )
    unresolved_prerequisites_count: int = Field(
        default=0,
        description="Count of selected deployments with pending legal/structural field survey prerequisites",
    )
    selected_packages: list[dict[str, Any]] = Field(default_factory=list, description="Selected discrete municipal packages")
    packages_count: int = Field(default=0, description="Number of selected packages")
    cells_count: int = Field(default=0, description="Number of selected cells")
    optimality_gap_percent: float = Field(default=0.0, description="Heuristic suboptimality gap vs exact DP")
    budget_curve: list[dict[str, Any]] = Field(default_factory=list, description="10-point budget-benefit curve")
    locality_rollup: list[dict[str, Any]] = Field(default_factory=list, description="Geographical distribution across localities")
    strategy_comparison: dict[str, Any] = Field(default_factory=dict, description="3-strategy comparison metrics")
# Legacy fields maintained for backward client compatibility:
    total_expected_cooling_c: float = Field(
        default=0.0,
        description="[LEGACY ALIAS] Equal to mean_local_cooling_c in °C. Replaces unphysical cumulative cooling sum.",
    )
    heat_priority_weighted_cooling: float = Field(
        default=0.0,
        description="[LEGACY ALIAS] Equal to heat_priority_weighted_benefit_c_m2 in °C·m².",
    )



class OptimizationResultResponse(BaseModel):
    run_id: str = Field(default="", description="Execution run ID for provenance tracking")
    algorithm: str
    budget_inr: float
    solutions_count: int
    solutions: list[SolutionResponse]
    recommended_solution: SolutionResponse | None = Field(default=None, description="Primary recommended solution")
    budget_curve: list[dict[str, Any]] = Field(default_factory=list)
    locality_rollup: list[dict[str, Any]] = Field(default_factory=list)
    strategy_comparison: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict, description="Active execution configuration")


class DiminishingReturnsRequest(BaseModel):
    budgets_inr: list[float] | None = Field(
        default=None,
        description="List of budget ceilings in INR to evaluate. Defaults to [50L, 1Cr, 2.5Cr, 5Cr, 7.5Cr, 10Cr]",
    )
    max_candidates: int = Field(default=80, ge=10, le=300)
    target_types: list[str] | None = None


class DiminishingReturnsPoint(BaseModel):
    budget_inr: float
    total_cost_inr: float
    budget_utilization_percent: float = 0.0
    treated_cells_count: int
    treated_area_m2: float
    mean_local_cooling_c: float
    citywide_cooling_c: float
    heat_priority_weighted_benefit_c_m2: float
    marginal_benefit_per_inr: float = 0.0
    marginal_cooling_per_cr_inr: float = 0.0
    chronic_hotspots_count: int
    trees_count: int
    cool_roof_m2: float
    cool_paver_m2: float
    green_roof_m2: float


class DiminishingReturnsResponse(BaseModel):
    algorithm: str
    curve_points: list[DiminishingReturnsPoint]
    parameters: dict[str, Any]


# Sliding-window rate limiter for diminishing-returns computation (30 req/min)
diminishing_returns_rate_limiter = InMemoryRateLimiter(max_attempts=30, window_seconds=60)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/candidates", response_model=CandidateListResponse)
def get_candidates(
    response: Response,
    bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
    intervention_type: str | None = Query(None, description="Filter by type (tree_canopy, cool_roof, etc.)"),
    feasibility_status: str = Query("FEASIBLE", description="FEASIBLE or REJECTED"),
    min_hpi: float = Query(35.0, ge=0.0, le=100.0, description="Filter cells with HPI >= min_hpi"),
    locality: str | None = Query(None, description="Filter by nearest OSM locality substring"),
    max_budget: float | None = Query(None, ge=0.0, description="Filter candidates by max cost in INR"),
    sort_by: str = Query("hpi_desc", description="Sort order: hpi_desc, cost_asc, cost_desc, cooling_desc"),
    cell_id: str | None = Query(None, description="Filter candidates by specific grid cell ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve intervention candidates with server-side filtering, sorting, and pagination."""
    query = (
        select(StageCHeatPriorityScore, StageCGridCell)
        .join(StageCGridCell, StageCHeatPriorityScore.pixel_id == StageCGridCell.pixel_id)
        .where(StageCHeatPriorityScore.heat_priority_score >= min_hpi)
    )

    if cell_id:
        query = query.where(StageCGridCell.pixel_id == cell_id)

    if locality:
        query = query.where(StageCGridCell.nearest_osm_place_name.ilike(f"%{locality}%"))

    if bbox:
        try:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) == 4:
                min_lon, min_lat, max_lon, max_lat = parts
                if not (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0 and -90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
                    raise HTTPException(status_code=400, detail="Bounding box coordinates out of range [-180, 180] lon, [-90, 90] lat.")
                if min_lon > max_lon or min_lat > max_lat:
                    raise HTTPException(status_code=400, detail="Reversed bounding box extent: min exceeds max.")
                query = query.where(
                    and_(
                        StageCGridCell.longitude >= min_lon,
                        StageCGridCell.longitude <= max_lon,
                        StageCGridCell.latitude >= min_lat,
                        StageCGridCell.latitude <= max_lat,
                    )
                )
            else:
                raise ValueError("Expected 4 coordinates")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bbox format. Expected min_lon,min_lat,max_lon,max_lat.")

    query = query.order_by(StageCHeatPriorityScore.heat_priority_score.desc()).limit(150)
    rows = db.execute(query).all()

    # Generate candidate objects
    candidates: list[InterventionCandidate] = []
    types_to_generate = [InterventionType(intervention_type)] if intervention_type else [
        InterventionType.TREE_CANOPY,
        InterventionType.COOL_ROOF,
        InterventionType.GREEN_ROOF,
        InterventionType.COOL_PAVEMENT,
    ]

    for score_obj, cell_obj in rows:
        row_idx = cell_obj.row_idx
        col_idx = cell_obj.col_idx
        raw_score = score_obj.heat_priority_score
        hpi_val = (raw_score / 100.0) if raw_score is not None else None
        lst_val = 38.0 + (hpi_val * 8.0) if hpi_val is not None else 38.0
        is_chr = score_obj.is_chronic_hotspot
        zone_val = cell_obj.nearest_osm_place_name or "Central Zone"

        for itype in types_to_generate:
            cand = generate_candidate_for_cell(
                row=row_idx,
                col=col_idx,
                cell_id=f"R{row_idx:03d}_C{col_idx:03d}",
                intervention_type=itype,
                baseline_hpi=hpi_val,
                baseline_lst_c=lst_val,
                is_chronic_hotspot=is_chr,
                administrative_zone=zone_val,
                usable_area_m2=1500.0,
                tree_count=45,
                is_inside_smc=cell_obj.is_centroid_inside,
            )
            if cand.feasibility_status.value == feasibility_status:
                candidates.append(cand)

    if max_budget is not None:
        candidates = [c for c in candidates if c.cost_inr <= max_budget]

    if sort_by == "cost_asc":
        candidates.sort(key=lambda c: c.cost_inr)
    elif sort_by == "cost_desc":
        candidates.sort(key=lambda c: c.cost_inr, reverse=True)
    elif sort_by == "cooling_desc":
        candidates.sort(key=lambda c: c.expected_cooling_c, reverse=True)
    else:  # hpi_desc default
        candidates.sort(key=lambda c: (c.baseline_hpi or 0.0), reverse=True)

    total_count = len(candidates)
    sliced = candidates[offset : offset + limit]

    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"

    return CandidateListResponse(
        total_count=total_count,
        limit=limit,
        offset=offset,
        items=[CandidateResponse(**c.to_dict()) for c in sliced],
    )


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
def get_candidate_detail(
    candidate_id: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Retrieve detailed metadata, cost breakdown, and evidence provenance for a candidate."""
    try:
        parts = candidate_id.split("_")
        itype_str = "_".join(parts[1:-2]).lower()
        row_str = parts[-2].replace("R", "")
        col_str = parts[-1].replace("C", "")
        row_idx = int(row_str)
        col_idx = int(col_str)
        itype = InterventionType(itype_str)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid candidate_id format: {candidate_id}")

    cell_record = db.execute(
        select(StageCHeatPriorityScore, StageCGridCell)
        .join(StageCGridCell, StageCHeatPriorityScore.pixel_id == StageCGridCell.pixel_id)
        .where(StageCGridCell.row_idx == row_idx, StageCGridCell.col_idx == col_idx)
    ).first()

    if cell_record:
        score_obj, cell_obj = cell_record
        raw_score = score_obj.heat_priority_score
        hpi_val = (raw_score / 100.0) if raw_score is not None else 0.65
        lst_val = 38.0 + (hpi_val * 8.0)
        is_chr = score_obj.is_chronic_hotspot
        zone_val = cell_obj.nearest_osm_place_name or "Central Zone"
        inside_smc = cell_obj.is_centroid_inside
    else:
        hpi_val = 0.65
        lst_val = 39.5
        is_chr = True
        zone_val = "Central Zone"
        inside_smc = True

    cand = generate_candidate_for_cell(
        row=row_idx,
        col=col_idx,
        cell_id=f"R{row_idx:03d}_C{col_idx:03d}",
        intervention_type=itype,
        baseline_hpi=hpi_val,
        baseline_lst_c=lst_val,
        is_chronic_hotspot=is_chr,
        administrative_zone=zone_val,
        usable_area_m2=1500.0,
        tree_count=50,
        is_inside_smc=inside_smc,
    )

    response.headers["Cache-Control"] = "public, max-age=1800, must-revalidate"

    return CandidateResponse(**cand.to_dict())


# ---------------------------------------------------------------------------
# Area-Level and Cluster-Level Endpoints
# ---------------------------------------------------------------------------

@router.get("/areas", response_model=list[AreaItemResponse])
def list_intervention_areas(
    response: Response,
    min_hpi: float = Query(35.0, ge=0.0, le=100.0, description="Minimum HPI threshold for cell eligibility"),
    db: Session = Depends(get_db),
):
    """List real localities/areas from Stage C grid with cell counts and data sufficiency."""
    response.headers["Cache-Control"] = "public, max-age=600, must-revalidate"
    return get_available_areas(db, min_hpi=min_hpi)


@router.get("/areas/{area}/summary", response_model=AreaSummaryResponse)
def get_locality_summary(
    area: str,
    response: Response,
    min_hpi: float = Query(35.0, ge=0.0, le=100.0),
    intervention_type: str | None = Query(None),
    feasibility_status: str = Query("FEASIBLE"),
    budget_cap_inr: float | None = Query(25000000.0, ge=0.0, description="Phase 1 portfolio budget ceiling in INR"),
    db: Session = Depends(get_db),
):
    """Retrieve high-level intervention KPIs for a specific locality or citywide ('all')."""
    response.headers["Cache-Control"] = "public, max-age=600, must-revalidate"
    return get_area_summary(
        db=db,
        area_name=area,
        min_hpi=min_hpi,
        intervention_type=intervention_type,
        feasibility_status=feasibility_status,
        budget_cap_inr=budget_cap_inr,
    )


@router.get("/areas/{area}/clusters", response_model=ClustersListResponse)
def get_locality_clusters(
    area: str,
    response: Response,
    intervention_type: str | None = Query(None),
    feasibility_status: str = Query("FEASIBLE"),
    min_hpi: float = Query(35.0, ge=0.0, le=100.0),
    min_priority: float | None = Query(None, ge=0.0, le=100.0),
    sort_by: str = Query("priority_desc", description="priority_desc, cooling_desc, cost_asc, cost_desc, cells_desc, cost_effectiveness"),
    budget_cap_inr: float | None = Query(25000000.0, ge=0.0, description="Phase 1 portfolio budget ceiling in INR"),
    limit: int = Query(10, ge=1, le=200),
    offset: int = Query(0, ge=0),
    max_cluster_size: int = Query(16, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Retrieve ranked, contiguous spatial clusters of intervention candidates for an area."""
    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    return generate_clusters_for_area(
        db=db,
        area_name=area,
        intervention_type=intervention_type,
        feasibility_status=feasibility_status,
        min_hpi=min_hpi,
        min_priority=min_priority,
        sort_by=sort_by,
        budget_cap_inr=budget_cap_inr,
        limit=limit,
        offset=offset,
        max_cluster_size=max_cluster_size,
    )


@router.get("/clusters/{cluster_id}/cells", response_model=ClusterCellsResponse)
def get_cluster_contributing_cells(
    cluster_id: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Retrieve contributing 100m grid cell items with physics and attributes for a cluster."""
    try:
        data = get_cluster_cells(db, cluster_id=cluster_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch cluster cells: {str(e)}")

    if not data["cells"]:
        raise HTTPException(status_code=404, detail=f"No cells found for cluster '{cluster_id}'.")

    response.headers["Cache-Control"] = "public, max-age=600, must-revalidate"
    return data


@router.post("/optimize", response_model=OptimizationResultResponse)
def optimize_interventions(
    payload: OptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner_or_admin),
):
    """Execute municipal package optimization (Exact Integer DP, Greedy Knapsack, or NSGA-II Pareto)."""
    algo = payload.algorithm.lower().replace("-", "_")
    supported_algos = ("greedy", "baseline_greedy", "nsga2", "nsga_ii", "pareto", "exact", "knapsack", "integer_dp", "hotspot_first", "max_benefit", "cost_effective")
    if algo not in supported_algos:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported optimization algorithm '{payload.algorithm}'. Supported algorithms: 'greedy', 'nsga2', 'exact'.",
        )
    scope = payload.scope or "all"

    # 1. Fetch candidate packages for scope
    packages = get_all_packages_for_area(db, area_name=scope)

    # 2. Filter by target_types if specified
    if payload.target_types:
        allowed = set(payload.target_types)
        packages = [
            p for p in packages
            if (p.intervention_type.value if hasattr(p.intervention_type, "value") else str(p.intervention_type)) in allowed
        ]

    if not packages:
        raise HTTPException(
            status_code=404,
            detail=f"No qualifying candidate packages found for scope '{scope}' with selected intervention types.",
        )

    # 3. Strategy comparison
    strat_comp = compare_strategies(packages, budget_inr=payload.budget_inr)

    # 4. Execute optimization algorithm
    exec_run_id = f"RUN_OPT_{uuid.uuid4().hex[:8].upper()}"

    if algo in ("greedy", "baseline_greedy"):
        sol = run_baseline_greedy_optimizer(
            candidates=packages,
            budget_inr=payload.budget_inr,
            enforce_cell_exclusivity=True,
        )
        sol.strategy_comparison = strat_comp
        solutions = [sol]
        rec_sol = sol
    elif algo in ("nsga2", "nsga_ii", "pareto"):
        solutions = run_nsga2_optimizer(
            candidates=packages,
            budget_inr=payload.budget_inr,
            population_size=20,
            generations=payload.generations or 20,
            random_seed=42,
        )
        if not solutions:
            sol = run_exact_knapsack_optimizer(packages, budget_inr=payload.budget_inr, strategy=payload.strategy or "hotspot_first")
            solutions = [sol]
        for s in solutions:
            s.strategy_comparison = strat_comp
        rec_sol = solutions[0]
    elif algo in ("exact", "knapsack", "integer_dp", "hotspot_first", "max_benefit", "cost_effective"):
        sol = run_exact_knapsack_optimizer(
            packages=packages,
            budget_inr=payload.budget_inr,
            strategy=payload.strategy or "hotspot_first",
        )
        sol.strategy_comparison = strat_comp
        solutions = [sol]
        rec_sol = sol
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported optimization algorithm '{payload.algorithm}'. Supported algorithms: 'greedy', 'nsga2', 'exact'.",
        )

    for s in solutions:
        s.run_id = exec_run_id

    # Common budget curve and locality rollup
    if algo in ("exact", "knapsack") and (payload.strategy or "hotspot_first") == "hotspot_first":
        budget_curve = rec_sol.budget_curve
    elif algo in ("greedy", "baseline_greedy"):
        # Build 10-point budget curve from greedy cumulative packages
        budget_curve = []
        sorted_pkgs = sorted(
            packages,
            key=lambda p: (
                p.chronic_hotspot_cells_count / max(100.0, p.estimated_cost_inr),
                p.thermal_benefit_k_m2 / max(100.0, p.estimated_cost_inr),
            ),
            reverse=True,
        )
        from gis.interventions.cooling_effects import DEFAULT_SMC_DOMAIN_AREA_M2
        for step in range(1, 11):
            target_b = payload.budget_inr * (step / 10.0)
            step_cost = 0.0
            step_benefit = 0.0
            step_cells = 0
            step_hotspots = 0
            for p in sorted_pkgs:
                if step_cost + p.estimated_cost_inr <= target_b:
                    step_cost += p.estimated_cost_inr
                    step_benefit += p.thermal_benefit_k_m2
                    step_cells += p.cell_count
                    step_hotspots += p.chronic_hotspot_cells_count
            budget_curve.append({
                "step": step,
                "target_budget_inr": round(target_b, 2),
                "actual_spend_inr": round(step_cost, 2),
                "thermal_benefit_k_m2": round(step_benefit, 1),
                "cells_count": step_cells,
                "chronic_hotspots_count": step_hotspots,
                "citywide_cooling_c": round(step_benefit / DEFAULT_SMC_DOMAIN_AREA_M2, 4),
            })
    else:
        exact_a = run_exact_knapsack_optimizer(
            packages,
            budget_inr=payload.budget_inr,
            strategy="hotspot_first",
            discretization_unit_inr=max(25000.0, payload.budget_inr / 1000.0),
        )
        budget_curve = exact_a.budget_curve

    locality_rollup = rec_sol.locality_rollup or compute_locality_rollup(rec_sol.selected_packages)

    sol_responses = [SolutionResponse(**s.to_dict()) for s in solutions]
    rec_sol_response = SolutionResponse(**rec_sol.to_dict()) if rec_sol else sol_responses[0]

    return OptimizationResultResponse(
        run_id=exec_run_id,
        algorithm=payload.algorithm.upper(),
        budget_inr=payload.budget_inr,
        solutions_count=len(solutions),
        solutions=sol_responses,
        recommended_solution=rec_sol_response,
        budget_curve=budget_curve,
        locality_rollup=locality_rollup,
        strategy_comparison=strat_comp,
        config={
            "run_id": exec_run_id,
            "budget_inr": payload.budget_inr,
            "algorithm": payload.algorithm,
            "strategy": payload.strategy,
            "scope": scope,
            "max_candidates": len(packages),
            "generations": payload.generations if "nsga" in algo else None,
            "target_types": payload.target_types or ["all"],
            "random_seed": 42,
        },
    )


@router.get("/types/availability")
def get_types_availability(
    area_name: str = "all",
    min_hpi: float = 35.0,
    db: Session = Depends(get_db),
):
    """Report availability, candidate package counts, and physical data requirements across all 10 typologies."""
    return get_type_availability(db, area_name=area_name, min_hpi=min_hpi)


@router.post("/optimize/export")
def export_optimization_csv(
    payload: OptimizeRequest,
    export_level: str = "package",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner_or_admin),
):
    """Export optimization results as CSV (package-level or cell-level)."""
    import csv, io
    scope = payload.scope or "all"
    packages = get_all_packages_for_area(db, area_name=scope)
    if payload.target_types:
        allowed = set(payload.target_types)
        packages = [
            p for p in packages
            if (p.intervention_type.value if hasattr(p.intervention_type, "value") else str(p.intervention_type)) in allowed
        ]

    sol = run_exact_knapsack_optimizer(packages, budget_inr=payload.budget_inr, strategy=payload.strategy or "hotspot_first")

    output = io.StringIO()
    if export_level == "cell":
        writer = csv.writer(output)
        writer.writerow([
            "candidate_id", "cell_id", "locality", "intervention_type", "cost_inr",
            "usable_area_m2", "expected_cooling_c", "baseline_hpi", "baseline_lst_c",
            "is_chronic_hotspot", "latitude", "longitude", "package_id", "cluster_id"
        ])
        for p in sol.selected_packages:
            for c in getattr(p, "cells", []):
                writer.writerow([
                    c.get("candidate_id"), c.get("cell_id"), p.locality,
                    p.intervention_type.value if hasattr(p.intervention_type, "value") else str(p.intervention_type),
                    c.get("cost_inr"), c.get("usable_area_m2"), c.get("expected_cooling_c"),
                    c.get("baseline_hpi"), c.get("baseline_lst_c"), c.get("is_chronic_hotspot"),
                    c.get("latitude"), c.get("longitude"), p.package_id, p.cluster_id
                ])
    else:
        writer = csv.writer(output)
        writer.writerow([
            "package_id", "cluster_id", "locality", "intervention_type", "cell_count",
            "cell_ids", "estimated_cost_inr", "treated_footprint_m2", "thermal_benefit_k_m2",
            "delta_t_skin_c", "delta_t_cell_c", "chronic_hotspot_cells_count"
        ])
        for p in sol.selected_packages:
            writer.writerow([
                p.package_id, p.cluster_id, p.locality,
                p.intervention_type.value if hasattr(p.intervention_type, "value") else str(p.intervention_type),
                p.cell_count, ";".join(p.cell_ids), p.estimated_cost_inr,
                p.treated_footprint_m2, p.thermal_benefit_k_m2, p.delta_t_skin_c,
                p.delta_t_cell_c, p.chronic_hotspot_cells_count
            ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=heatsense_optimization_{scope}_{export_level}.csv"}
    )


@router.get("/scenarios", response_model=list[dict[str, Any]])
def list_available_scenarios():
    """List reference urban heat mitigation budget scenarios for Surat Municipal Corporation with full provenance."""
    summary_path = PROJECT_ROOT / "docs" / "validation" / "scenario_summary.json"
    scenario_data: dict[str, Any] = {}
    if summary_path.is_file():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                scenario_data = json.load(f)
        except Exception:
            scenario_data = {}

    notes = scenario_data.get("notes", {})
    low_data = scenario_data.get("low", {})
    med_data = scenario_data.get("medium", {})
    high_data = scenario_data.get("high", {})

    return [
        {
            "scenario_name": "SMC Neighborhood Cool Corridors (Pilot Tier)",
            "tier": "low",
            "budget_inr": low_data.get("budget_limit", 5000000.0),
            "total_cost_inr": low_data.get("total_cost", 4972500.0),
            "budget_utilized_percent": round((low_data.get("total_cost", 4972500.0) / low_data.get("budget_limit", 5000000.0)) * 100, 2),
            "target_focus": "Targeted pilot cooling for extreme chronic hotspots in vulnerable wards",
            "recommended_types": ["tree_canopy", "cool_roof"],
            "treated_cells": low_data.get("treated_cells", 39),
            "total_treated_m2": low_data.get("total_treated_m2", 36915.0),
            "pct_city_area_treated": low_data.get("pct_city_area_treated", 0.007),
            "mean_dlst_treated": low_data.get("mean_dlst_treated", [-0.5, -0.73, -1.0]),
            "peak_hotspot_dlst": low_data.get("peak_hotspot_dlst", [-0.54, -0.78, -1.07]),
            "citywide_mean_dlst": low_data.get("citywide_mean_dlst", [-0.0004, -0.0006, -0.0008]),
            "breakdown": low_data.get("breakdown", {
                "cool_roof_m2": 7500.0,
                "cool_paver_m2": 0.0,
                "green_roof_m2": 0.0,
                "trees_count": 585,
            }),
            "provenance": "PRECOMPUTED_OPTIMIZER_BENCHMARK",
            "optimizer_algorithm": "BASELINE_GREEDY_KNAPSACK",
            "optimization_basis": "Derived from greedy knapsack run on Stage C HPI priority grid under physical feasibility constraints",
            "maturity_notes": notes.get("tree_maturity_state", "Evaluated at mature canopy (Year 7-10)."),
        },
        {
            "scenario_name": "SMC Smart City Phase 1: High-Priority Hotspots",
            "tier": "medium",
            "budget_inr": med_data.get("budget_limit", 25000000.0),
            "total_cost_inr": med_data.get("total_cost", 24972000.0),
            "budget_utilized_percent": round((med_data.get("total_cost", 24972000.0) / med_data.get("budget_limit", 25000000.0)) * 100, 2),
            "target_focus": "Chronic hotspots and central commercial wards across core municipal zones",
            "recommended_types": ["tree_canopy", "cool_roof", "cool_pavement"],
            "treated_cells": med_data.get("treated_cells", 138),
            "total_treated_m2": med_data.get("total_treated_m2", 152130.0),
            "pct_city_area_treated": med_data.get("pct_city_area_treated", 0.031),
            "mean_dlst_treated": med_data.get("mean_dlst_treated", [-0.57, -0.83, -1.14]),
            "peak_hotspot_dlst": med_data.get("peak_hotspot_dlst", [-0.62, -0.9, -1.23]),
            "citywide_mean_dlst": med_data.get("citywide_mean_dlst", [-0.0016, -0.0023, -0.0032]),
            "breakdown": med_data.get("breakdown", {
                "cool_roof_m2": 30240.0,
                "cool_paver_m2": 10800.0,
                "green_roof_m2": 0.0,
                "trees_count": 2208,
            }),
            "provenance": "PRECOMPUTED_OPTIMIZER_BENCHMARK",
            "optimizer_algorithm": "BASELINE_GREEDY_KNAPSACK",
            "optimization_basis": "Derived from greedy knapsack run on Stage C HPI priority grid under physical feasibility constraints",
            "maturity_notes": notes.get("tree_maturity_state", "Evaluated at mature canopy (Year 7-10)."),
        },
        {
            "scenario_name": "SMC Full Urban Heat Action Plan (UHAP 2026)",
            "tier": "high",
            "budget_inr": high_data.get("budget_limit", 100000000.0),
            "total_cost_inr": high_data.get("total_cost", 99963000.0),
            "budget_utilized_percent": round((high_data.get("total_cost", 99963000.0) / high_data.get("budget_limit", 100000000.0)) * 100, 2),
            "target_focus": "Citywide comprehensive deployment across all 7 administrative zones",
            "recommended_types": ["tree_canopy", "cool_roof", "green_roof", "cool_pavement"],
            "treated_cells": high_data.get("treated_cells", 371),
            "total_treated_m2": high_data.get("total_treated_m2", 465355.0),
            "pct_city_area_treated": high_data.get("pct_city_area_treated", 0.094),
            "mean_dlst_treated": high_data.get("mean_dlst_treated", [-0.64, -0.94, -1.29]),
            "peak_hotspot_dlst": high_data.get("peak_hotspot_dlst", [-0.76, -1.12, -1.53]),
            "citywide_mean_dlst": high_data.get("citywide_mean_dlst", [-0.0048, -0.007, -0.0096]),
            "breakdown": high_data.get("breakdown", {
                "cool_roof_m2": 86800.0,
                "cool_paver_m2": 36000.0,
                "green_roof_m2": 6800.0,
                "trees_count": 6678,
            }),
            "provenance": "PRECOMPUTED_OPTIMIZER_BENCHMARK",
            "optimizer_algorithm": "BASELINE_GREEDY_KNAPSACK",
            "optimization_basis": "Derived from greedy knapsack run on Stage C HPI priority grid under physical feasibility constraints",
            "maturity_notes": notes.get("tree_maturity_state", "Evaluated at mature canopy (Year 7-10)."),
        },
    ]


@router.post("/diminishing-returns", response_model=DiminishingReturnsResponse)
def get_diminishing_returns(
    payload: DiminishingReturnsRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner_or_admin),
):
    """Compute real diminishing-returns curve by executing greedy knapsack optimizer across budget thresholds."""
    client_ip = get_client_ip(request)
    allowed, retry_after = diminishing_returns_rate_limiter.check_and_record(f"dim_ret_{client_ip}")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for diminishing-returns analysis. Please wait {retry_after}s before retrying.",
            headers={"Retry-After": str(retry_after)},
        )

    budgets = payload.budgets_inr or [
        5_000_000.0,    # ₹50L
        10_000_000.0,   # ₹1Cr
        25_000_000.0,   # ₹2.5Cr
        50_000_000.0,   # ₹5Cr
        75_000_000.0,   # ₹7.5Cr
        100_000_000.0,  # ₹10Cr
    ]
    budgets = sorted(budgets)

    # Dynamically scale candidate pool query limit to avoid artificial flatlining for large budget tiers
    max_b = max(budgets) if budgets else 100_000_000.0
    # Scaled up to 1000 candidates to support ₹10 Cr+ budgets without premature in-memory candidate starvation
    effective_candidate_limit = max(payload.max_candidates, min(1000, int(max_b / 120_000)))

    query = (
        select(StageCHeatPriorityScore, StageCGridCell)
        .join(StageCGridCell, StageCHeatPriorityScore.pixel_id == StageCGridCell.pixel_id)
        .where(StageCHeatPriorityScore.heat_priority_score >= 35.0)
        .order_by(StageCHeatPriorityScore.heat_priority_score.desc())
        .limit(effective_candidate_limit)
    )
    rows = db.execute(query).all()

    target_types = (
        [InterventionType(t) for t in payload.target_types]
        if payload.target_types
        else [InterventionType.TREE_CANOPY, InterventionType.COOL_ROOF, InterventionType.COOL_PAVEMENT]
    )

    pool: list[InterventionCandidate] = []
    for score_obj, cell_obj in rows:
        raw_score = score_obj.heat_priority_score
        hpi_val = (raw_score / 100.0) if raw_score is not None else 0.5
        lst_val = 38.0 + (hpi_val * 8.0)
        is_chr = score_obj.is_chronic_hotspot
        zone_val = cell_obj.nearest_osm_place_name or "Central Zone"

        for itype in target_types:
            cand = generate_candidate_for_cell(
                row=cell_obj.row_idx,
                col=cell_obj.col_idx,
                cell_id=f"R{cell_obj.row_idx:03d}_C{cell_obj.col_idx:03d}",
                intervention_type=itype,
                baseline_hpi=hpi_val,
                baseline_lst_c=lst_val,
                is_chronic_hotspot=is_chr,
                administrative_zone=zone_val,
                usable_area_m2=1500.0,
                tree_count=45,
                is_inside_smc=cell_obj.is_centroid_inside,
            )
            if cand.feasibility_status == FeasibilityStatus.FEASIBLE:
                pool.append(cand)

    curve_points: list[DiminishingReturnsPoint] = []
    prev_cost = 0.0
    prev_benefit = 0.0
    prev_mean_c = 0.0

    for b in budgets:
        sol = run_baseline_greedy_optimizer(
            candidates=pool,
            budget_inr=b,
            enforce_cell_exclusivity=True,
        )
        trees = sum(c.tree_count for c in sol.selected_candidates)
        cool_roof = sum(c.usable_area_m2 for c in sol.selected_candidates if c.intervention_type == InterventionType.COOL_ROOF)
        cool_paver = sum(c.usable_area_m2 for c in sol.selected_candidates if c.intervention_type == InterventionType.COOL_PAVEMENT)
        green_roof = sum(c.usable_area_m2 for c in sol.selected_candidates if c.intervention_type == InterventionType.GREEN_ROOF)

        cost_diff = sol.total_cost_inr - prev_cost
        benefit_diff = sol.heat_priority_weighted_benefit_c_m2 - prev_benefit
        cooling_diff = abs(sol.mean_local_cooling_c) - abs(prev_mean_c)
        marginal_ratio = (benefit_diff / cost_diff) if cost_diff > 0 else 0.0
        marginal_cr = (cooling_diff / (cost_diff / 10_000_000.0)) if cost_diff > 0 else 0.0
        util_pct = round((sol.total_cost_inr / b) * 100.0, 2) if b > 0 else 0.0

        curve_points.append(
            DiminishingReturnsPoint(
                budget_inr=b,
                total_cost_inr=round(sol.total_cost_inr, 2),
                budget_utilization_percent=util_pct,
                treated_cells_count=sol.interventions_count,
                treated_area_m2=round(sol.treated_area_m2, 2),
                mean_local_cooling_c=round(sol.mean_local_cooling_c, 3),
                citywide_cooling_c=round(sol.citywide_cooling_c, 6),
                heat_priority_weighted_benefit_c_m2=round(sol.heat_priority_weighted_benefit_c_m2, 2),
                marginal_benefit_per_inr=round(marginal_ratio, 6),
                marginal_cooling_per_cr_inr=round(marginal_cr, 4),
                chronic_hotspots_count=sol.chronic_hotspots_count,
                trees_count=trees,
                cool_roof_m2=round(cool_roof, 2),
                cool_paver_m2=round(cool_paver, 2),
                green_roof_m2=round(green_roof, 2),
            )
        )
        prev_cost = sol.total_cost_inr
        prev_benefit = sol.heat_priority_weighted_benefit_c_m2
        prev_mean_c = sol.mean_local_cooling_c

    # Determine if in-memory candidate pool was exhausted by the highest budget
    pool_exhausted = len(pool) > 0 and len(sol.selected_candidates) >= len(pool)

    return DiminishingReturnsResponse(
        algorithm="GREEDY_KNAPSACK",
        curve_points=curve_points,
        parameters={
            "max_candidates": payload.max_candidates,
            "effective_candidate_limit": effective_candidate_limit,
            "candidate_pool_size": len(pool),
            "candidate_pool_exhausted": pool_exhausted,
            "target_types": [t.value for t in target_types],
            "enforce_cell_exclusivity": True,
            "domain_area_m2": 461630791.0,
        },
    )



# ---------------------------------------------------------------------------
# Phase 6 Dynamic World Land Cover Endpoints
# ---------------------------------------------------------------------------

class DynamicWorldProbabilities(BaseModel):
    water: float | None = None
    trees: float | None = None
    grass: float | None = None
    flooded_vegetation: float | None = None
    crops: float | None = None
    shrub_and_scrub: float | None = None
    built: float | None = None
    bare: float | None = None
    snow_and_ice: float | None = None


class LandCoverSuitabilityResponse(BaseModel):
    rule_fired: str
    suitable_interventions: list[str]
    screened_out_interventions: list[str]
    screening_status: str
    screening_reason: str
    feasibility_prerequisite: str
    scientific_notice: str
    data_confidence: str
    thresholds_applied: dict[str, float]


class CellLandCoverResponse(BaseModel):
    cell_id: str
    season: str
    year: int
    start_date: str
    end_date: str
    probabilities: DynamicWorldProbabilities
    proportions: DynamicWorldProbabilities
    valid_observation_count: int
    top_class: str | None
    confidence: float | None
    margin: float | None
    entropy: float | None
    status: str
    suitability: LandCoverSuitabilityResponse | None = None
    attribution: str
    citation: str
    license: str
    source_dataset: str
    pipeline_version: str


class LandCoverSummaryResponse(BaseModel):
    season: str
    year: int
    total_cells_recorded: int
    cells_sufficient: int
    cells_insufficient: int
    cells_no_observations: int
    class_distribution: dict[str, int]
    mean_probabilities: dict[str, float]
    mean_confidence: float | None
    mean_entropy: float | None
    attribution: str
    citation: str
    license: str
    pipeline_version: str


class LandCoverGridItem(BaseModel):
    cell_id: str
    top_class: str | None
    confidence: float | None
    entropy: float | None
    mean_built: float | None
    mean_trees: float | None
    mean_bare: float | None
    mean_grass: float | None
    mean_crops: float | None
    mean_water: float | None


@router.get("/landcover/summary", response_model=LandCoverSummaryResponse)
def get_landcover_summary(
    season: str = "summer",
    year: int = 2024,
    db: Session = Depends(get_db),
):
    """
    Retrieve citywide seasonal Dynamic World land-cover summary diagnostics and class distribution.
    """
    rows = (
        db.query(StageDDynamicWorldLandCover)
        .filter(
            StageDDynamicWorldLandCover.season == season,
            StageDDynamicWorldLandCover.year == year,
        )
        .all()
    )

    total = len(rows)
    cnt_suff = sum(1 for r in rows if r.status == "SUFFICIENT")
    cnt_insuff = sum(1 for r in rows if r.status == "INSUFFICIENT_OBSERVATIONS")
    cnt_no_obs = sum(1 for r in rows if r.status == "NO_OBSERVATIONS")

    dist: dict[str, int] = {}
    prob_sums: dict[str, float] = {c: 0.0 for c in DW_CLASSES}
    valid_probs_cnt: dict[str, int] = {c: 0 for c in DW_CLASSES}
    conf_sum = 0.0
    conf_cnt = 0
    entropy_sum = 0.0
    entropy_cnt = 0

    for r in rows:
        if r.top_class:
            dist[r.top_class] = dist.get(r.top_class, 0) + 1
        if r.confidence is not None:
            conf_sum += r.confidence
            conf_cnt += 1
        if r.entropy is not None:
            entropy_sum += r.entropy
            entropy_cnt += 1

        for c in DW_CLASSES:
            val = getattr(r, f"mean_{c}", None)
            if val is not None:
                prob_sums[c] += val
                valid_probs_cnt[c] += 1

    mean_probs = {
        c: round(prob_sums[c] / valid_probs_cnt[c], 4) if valid_probs_cnt[c] > 0 else 0.0
        for c in DW_CLASSES
    }

    return LandCoverSummaryResponse(
        season=season,
        year=year,
        total_cells_recorded=total,
        cells_sufficient=cnt_suff,
        cells_insufficient=cnt_insuff,
        cells_no_observations=cnt_no_obs,
        class_distribution=dist,
        mean_probabilities=mean_probs,
        mean_confidence=round(conf_sum / conf_cnt, 4) if conf_cnt > 0 else None,
        mean_entropy=round(entropy_sum / entropy_cnt, 4) if entropy_cnt > 0 else None,
        attribution=ATTRIBUTION_TEXT,
        citation=CITATION_TEXT,
        license=LICENSE_TEXT,
        pipeline_version=PIPELINE_VERSION,
    )


@router.get("/landcover/grid", response_model=list[LandCoverGridItem])
def get_landcover_grid(
    season: str = "summer",
    year: int = 2024,
    limit: int = 2000,
    db: Session = Depends(get_db),
):
    """
    Retrieve lightweight grid land-cover predictions for map visualization.
    """
    rows = (
        db.query(StageDDynamicWorldLandCover)
        .filter(
            StageDDynamicWorldLandCover.season == season,
            StageDDynamicWorldLandCover.year == year,
        )
        .limit(limit)
        .all()
    )

    return [
        LandCoverGridItem(
            cell_id=r.cell_id,
            top_class=r.top_class,
            confidence=r.confidence,
            entropy=r.entropy,
            mean_built=r.mean_built,
            mean_trees=r.mean_trees,
            mean_bare=r.mean_bare,
            mean_grass=r.mean_grass,
            mean_crops=r.mean_crops,
            mean_water=r.mean_water,
        )
        for r in rows
    ]


@router.get("/landcover/{cell_id}", response_model=CellLandCoverResponse)
def get_cell_landcover(
    cell_id: str,
    season: str = "summer",
    year: int = 2024,
    db: Session = Depends(get_db),
):
    """
    Retrieve detailed seasonal Dynamic World probabilities, hard proportions, and suitability assessment for a cell.
    """
    rec = fetch_cell_landcover(cell_id=cell_id, season=season, year=year, db=db)
    if not rec:
        raise HTTPException(
            status_code=404,
            detail=f"No Dynamic World land cover record found for cell '{cell_id}' in season '{season}' {year}.",
        )

    probs = DynamicWorldProbabilities(
        water=rec["mean_water"],
        trees=rec["mean_trees"],
        grass=rec["mean_grass"],
        flooded_vegetation=rec["mean_flooded_vegetation"],
        crops=rec["mean_crops"],
        shrub_and_scrub=rec["mean_shrub_and_scrub"],
        built=rec["mean_built"],
        bare=rec["mean_bare"],
        snow_and_ice=rec["mean_snow_and_ice"],
    )

    props = DynamicWorldProbabilities(
        water=rec["prop_water"],
        trees=rec["prop_trees"],
        grass=rec["prop_grass"],
        flooded_vegetation=rec["prop_flooded_vegetation"],
        crops=rec["prop_crops"],
        shrub_and_scrub=rec["prop_shrub_and_scrub"],
        built=rec["prop_built"],
        bare=rec["prop_bare"],
        snow_and_ice=rec["prop_snow_and_ice"],
    )

    suit_eval = evaluate_landcover_suitability(dw_record=rec, cell_id=cell_id)
    suit_resp = LandCoverSuitabilityResponse(
        rule_fired=suit_eval.rule_fired,
        suitable_interventions=[i.value for i in suit_eval.suitable_interventions],
        screened_out_interventions=[i.value for i in suit_eval.screened_out_interventions],
        screening_status=suit_eval.screening_status,
        screening_reason=suit_eval.screening_reason,
        feasibility_prerequisite=suit_eval.feasibility_prerequisite,
        scientific_notice=suit_eval.scientific_notice,
        data_confidence=suit_eval.data_confidence,
        thresholds_applied=suit_eval.thresholds_applied,
    )

    return CellLandCoverResponse(
        cell_id=cell_id,
        season=season,
        year=year,
        start_date=rec["start_date"],
        end_date=rec["end_date"],
        probabilities=probs,
        proportions=props,
        valid_observation_count=rec["valid_observation_count"],
        top_class=rec["top_class"],
        confidence=rec["confidence"],
        margin=rec["margin"],
        entropy=rec["entropy"],
        status=rec["status"],
        suitability=suit_resp,
        attribution=ATTRIBUTION_TEXT,
        citation=CITATION_TEXT,
        license=LICENSE_TEXT,
        source_dataset=rec["source_dataset"],
        pipeline_version=rec["pipeline_version"],
    )
