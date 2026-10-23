"""FastAPI endpoints for Stage D Intervention Candidates and Optimization Scenarios.

Exposes:
- GET  /api/v1/interventions/candidates       : Viewport bounded, filtered candidate retrieval.
- GET  /api/v1/interventions/candidates/{id}  : Detailed candidate metadata and cost breakdown.
- POST /api/v1/interventions/optimize         : Multi-objective constrained optimization (Greedy / NSGA-II).
- GET  /api/v1/interventions/scenarios        : Available planning scenarios and benchmarks.
"""

from __future__ import annotations

import math
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.core.auth import User, UserRole, require_planner_or_admin
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
    ScenarioSolution,
    run_baseline_greedy_optimizer,
    run_nsga2_optimizer,
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


class CandidateListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    items: list[CandidateResponse]


class OptimizeRequest(BaseModel):
    budget_inr: float = Field(
        default=50000000.0,
        gt=0.0,
        le=10_000_000_000.0,
        description="Total intervention budget in INR (must be positive, default: 5 Crore)",
    )
    algorithm: str = Field(default="nsga2", description="Optimization algorithm: 'nsga2' (Pareto) or 'greedy' (Knapsack)")
    target_types: list[str] | None = Field(default=None, description="Optional filter of allowed intervention types")
    max_candidates: int = Field(default=80, ge=10, le=500, description="Candidate search pool size")
    generations: int = Field(default=20, ge=5, le=100, description="NSGA-II generations")


class SolutionResponse(BaseModel):
    solution_id: str = Field(description="Unique identifier for the optimization scenario solution")
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
    algorithm: str
    budget_inr: float
    solutions_count: int
    solutions: list[SolutionResponse]


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
    treated_cells_count: int
    treated_area_m2: float
    mean_local_cooling_c: float
    citywide_cooling_c: float
    heat_priority_weighted_benefit_c_m2: float
    chronic_hotspots_count: int
    trees_count: int
    cool_roof_m2: float
    cool_paver_m2: float
    green_roof_m2: float


class DiminishingReturnsResponse(BaseModel):
    algorithm: str
    curve_points: list[DiminishingReturnsPoint]
    parameters: dict[str, Any]


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


@router.post("/optimize", response_model=OptimizationResultResponse)
def optimize_interventions(
    payload: OptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner_or_admin),
):
    """Execute multi-objective optimization (Greedy Knapsack or NSGA-II Pareto)."""
    algo = payload.algorithm.lower()
    if algo not in ("greedy", "nsga2", "nsga-ii", "pareto"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported algorithm '{payload.algorithm}'. Choose 'nsga2' or 'greedy'.",
        )

    # Fetch top heat priority cells from DB as optimization candidates
    query = (
        select(StageCHeatPriorityScore, StageCGridCell)
        .join(StageCGridCell, StageCHeatPriorityScore.pixel_id == StageCGridCell.pixel_id)
        .where(StageCHeatPriorityScore.heat_priority_score >= 35.0)
        .order_by(StageCHeatPriorityScore.heat_priority_score.desc())
        .limit(payload.max_candidates)
    )
    rows = db.execute(query).all()

    if not rows:
        raise HTTPException(status_code=404, detail="No qualifying Stage C heat priority cells found for optimization.")

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

    if algo == "greedy":
        sol = run_baseline_greedy_optimizer(
            candidates=pool,
            budget_inr=payload.budget_inr,
            enforce_cell_exclusivity=True,
        )
        solutions = [sol]
    else:
        solutions = run_nsga2_optimizer(
            candidates=pool,
            budget_inr=payload.budget_inr,
            population_size=20,
            generations=payload.generations,
            random_seed=42,
        )

    return OptimizationResultResponse(
        algorithm=payload.algorithm.upper(),
        budget_inr=payload.budget_inr,
        solutions_count=len(solutions),
        solutions=[SolutionResponse(**s.to_dict()) for s in solutions],
    )


@router.get("/scenarios", response_model=list[dict[str, Any]])
def list_available_scenarios():
    """List reference urban heat mitigation budget scenarios for Surat Municipal Corporation."""
    return [
        {
            "scenario_name": "SMC Neighborhood Cool Corridors (Pilot Tier)",
            "tier": "low",
            "budget_inr": 5000000.0,  # 50 Lakhs INR
            "target_focus": "Targeted pilot cooling for extreme chronic hotspots in vulnerable wards",
            "recommended_types": ["tree_canopy", "cool_roof"],
            "treated_cells": 39,
            "total_treated_m2": 36915.0,
            "mean_dlst_treated": [-0.5, -0.73, -1.0],
            "peak_hotspot_dlst": [-0.54, -0.78, -1.07],
            "breakdown": {
                "cool_roof_m2": 7500.0,
                "cool_paver_m2": 0.0,
                "green_roof_m2": 0.0,
                "trees_count": 585,
            },
        },
        {
            "scenario_name": "SMC Smart City Phase 1: High-Priority Hotspots",
            "tier": "medium",
            "budget_inr": 25000000.0,  # 2.5 Crore INR
            "target_focus": "Chronic hotspots and central commercial wards across core municipal zones",
            "recommended_types": ["tree_canopy", "cool_roof", "cool_pavement"],
            "treated_cells": 138,
            "total_treated_m2": 152130.0,
            "mean_dlst_treated": [-0.57, -0.83, -1.14],
            "peak_hotspot_dlst": [-0.62, -0.9, -1.23],
            "breakdown": {
                "cool_roof_m2": 30240.0,
                "cool_paver_m2": 10800.0,
                "green_roof_m2": 0.0,
                "trees_count": 2208,
            },
        },
        {
            "scenario_name": "SMC Full Urban Heat Action Plan (UHAP 2026)",
            "tier": "high",
            "budget_inr": 100000000.0,  # 10 Crore INR
            "target_focus": "Citywide comprehensive deployment across all 7 administrative zones",
            "recommended_types": ["tree_canopy", "cool_roof", "green_roof", "cool_pavement"],
            "treated_cells": 371,
            "total_treated_m2": 465355.0,
            "mean_dlst_treated": [-0.64, -0.94, -1.29],
            "peak_hotspot_dlst": [-0.76, -1.12, -1.53],
            "breakdown": {
                "cool_roof_m2": 86800.0,
                "cool_paver_m2": 36000.0,
                "green_roof_m2": 6800.0,
                "trees_count": 6678,
            },
        },
    ]


@router.post("/diminishing-returns", response_model=DiminishingReturnsResponse)
def get_diminishing_returns(
    payload: DiminishingReturnsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner_or_admin),
):
    """Compute real diminishing-returns curve by executing greedy knapsack optimizer across budget thresholds."""
    budgets = payload.budgets_inr or [
        5_000_000.0,    # ₹50L
        10_000_000.0,   # ₹1Cr
        25_000_000.0,   # ₹2.5Cr
        50_000_000.0,   # ₹5Cr
        75_000_000.0,   # ₹7.5Cr
        100_000_000.0,  # ₹10Cr
    ]
    budgets = sorted(budgets)

    query = (
        select(StageCHeatPriorityScore, StageCGridCell)
        .join(StageCGridCell, StageCHeatPriorityScore.pixel_id == StageCGridCell.pixel_id)
        .where(StageCHeatPriorityScore.heat_priority_score >= 35.0)
        .order_by(StageCHeatPriorityScore.heat_priority_score.desc())
        .limit(payload.max_candidates)
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

        curve_points.append(
            DiminishingReturnsPoint(
                budget_inr=b,
                total_cost_inr=sol.total_cost_inr,
                treated_cells_count=sol.interventions_count,
                treated_area_m2=sol.treated_area_m2,
                mean_local_cooling_c=round(sol.mean_local_cooling_c, 3),
                citywide_cooling_c=round(sol.citywide_cooling_c, 4),
                heat_priority_weighted_benefit_c_m2=round(sol.heat_priority_weighted_benefit_c_m2, 2),
                chronic_hotspots_count=sol.chronic_hotspots_count,
                trees_count=trees,
                cool_roof_m2=cool_roof,
                cool_paver_m2=cool_paver,
                green_roof_m2=green_roof,
            )
        )

    return DiminishingReturnsResponse(
        algorithm="GREEDY_KNAPSACK",
        curve_points=curve_points,
        parameters={
            "max_candidates": payload.max_candidates,
            "target_types": [t.value for t in target_types],
            "enforce_cell_exclusivity": True,
            "domain_area_m2": 461630791.0,
        },
    )

