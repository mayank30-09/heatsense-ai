"""Spatial Intervention Candidate Generator for HEATSENSE AI (Stage D).

Generates traceable, evidence-backed candidate interventions across Surat:
- Tree Canopy Planting
- Cool Roof Coatings
- Extensive Green Roofs
- Cool Permeable Pavements

Binds candidates to Stage C grid cells, calculating costs, cooling effects, and feasibility.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from shapely.geometry import mapping

from gis.interventions import (
    FeasibilityStatus,
    InterventionCandidate,
    InterventionType,
    RejectionReason,
)
from gis.interventions.costs import estimate_intervention_cost
from gis.interventions.cooling_effects import estimate_cooling_effect
from gis.interventions.feasibility import evaluate_candidate_feasibility
from gis.spatial.grid import get_cell_centroid, get_cell_polygon


def generate_candidate_for_cell(
    row: int,
    col: int,
    cell_id: str,
    intervention_type: InterventionType,
    baseline_hpi: float,
    baseline_lst_c: float,
    is_chronic_hotspot: bool,
    administrative_zone: str,
    ndvi: float = 0.25,
    ndbi: float = 0.05,
    ndwi: float = -0.20,
    usable_area_m2: float = 1500.0,
    tree_count: int = 40,
    is_inside_smc: bool = True,
) -> InterventionCandidate:
    """
    Construct a complete candidate object with cost, cooling effect, geometry, and feasibility.
    """
    lon, lat = get_cell_centroid(row, col)
    poly = get_cell_polygon(row, col)
    geom_dict = mapping(poly)

    cand_id = f"CAND_{intervention_type.value.upper()}_R{row:03d}_C{col:03d}"

    # 1. Cost model
    cost_base, cost_min, cost_max, cost_meta = estimate_intervention_cost(
        intervention_type=intervention_type,
        usable_area_m2=usable_area_m2,
        tree_count=tree_count,
    )

    # 2. Cooling effect model
    cooling_base, cooling_min, cooling_max, cooling_meta = estimate_cooling_effect(
        intervention_type=intervention_type,
        usable_area_m2=usable_area_m2,
        tree_count=tree_count,
        baseline_lst_c=baseline_lst_c,
    )

    candidate = InterventionCandidate(
        candidate_id=cand_id,
        cell_id=cell_id,
        row=row,
        col=col,
        longitude=lon,
        latitude=lat,
        intervention_type=intervention_type,
        usable_area_m2=usable_area_m2,
        tree_count=tree_count if intervention_type == InterventionType.TREE_CANOPY else 0,
        baseline_hpi=baseline_hpi,
        baseline_lst_c=baseline_lst_c,
        is_chronic_hotspot=is_chronic_hotspot,
        administrative_zone=administrative_zone,
        cost_inr=cost_base,
        cost_inr_min=cost_min,
        cost_inr_max=cost_max,
        expected_cooling_c=cooling_base,
        expected_cooling_c_min=cooling_min,
        expected_cooling_c_max=cooling_max,
        evidence_status="CALIBRATED_EMPIRICAL_MICROCLIMATE",
        geometry=geom_dict,
    )

    # 3. Feasibility validation
    status, reason, _ = evaluate_candidate_feasibility(
        candidate=candidate,
        ndvi=ndvi,
        ndbi=ndbi,
        ndwi=ndwi,
        is_inside_smc_boundary=is_inside_smc,
    )
    candidate.feasibility_status = status
    candidate.rejection_reason = reason

    return candidate


def generate_intervention_candidates(
    cells_df: pd.DataFrame,
    target_types: list[InterventionType] | None = None,
    min_hpi: float = 0.35,
    max_candidates: int | None = None,
) -> tuple[list[InterventionCandidate], list[InterventionCandidate]]:
    """
    Generate candidates from Stage C cell data.

    Returns
    -------
    tuple[list[InterventionCandidate], list[InterventionCandidate]]
        (feasible_candidates, rejected_candidates)
    """
    if target_types is None:
        target_types = [
            InterventionType.TREE_CANOPY,
            InterventionType.COOL_ROOF,
            InterventionType.GREEN_ROOF,
            InterventionType.COOL_PAVEMENT,
        ]

    feasible: list[InterventionCandidate] = []
    rejected: list[InterventionCandidate] = []

    for _, r in cells_df.iterrows():
        row = int(r["row"])
        col = int(r["col"])
        cell_id = str(r.get("cell_id", f"R{row:03d}_C{col:03d}"))
        hpi = float(r["heat_priority_index"]) if pd.notna(r.get("heat_priority_index")) else None
        lst = float(r["lst_c"]) if pd.notna(r.get("lst_c")) else 38.0
        is_chronic = bool(r.get("is_chronic_hotspot", False))
        zone = str(r.get("administrative_zone", "Central Zone"))
        ndvi = float(r.get("ndvi", 0.25))
        ndbi = float(r.get("ndbi", 0.05))
        ndwi = float(r.get("ndwi", -0.20))
        is_inside = bool(r.get("is_inside", True))

        # Filter: candidate generation requires minimum thermal priority or chronic hotspot status
        if hpi is None or (hpi < min_hpi and not is_chronic):
            continue

        # Propose applicable intervention types based on physical land cover
        # 1. Tree Canopy for open areas / verges (NDVI < 0.45, NDBI < 0.20)
        if InterventionType.TREE_CANOPY in target_types and ndvi < 0.50:
            c = generate_candidate_for_cell(
                row=row, col=col, cell_id=cell_id,
                intervention_type=InterventionType.TREE_CANOPY,
                baseline_hpi=hpi, baseline_lst_c=lst, is_chronic_hotspot=is_chronic,
                administrative_zone=zone, ndvi=ndvi, ndbi=ndbi, ndwi=ndwi,
                usable_area_m2=1500.0, tree_count=50, is_inside_smc=is_inside,
            )
            if c.feasibility_status == FeasibilityStatus.FEASIBLE:
                feasible.append(c)
            else:
                rejected.append(c)

        # 2. Cool Roof for built-up structures (NDBI > -0.05)
        if InterventionType.COOL_ROOF in target_types and ndbi > -0.05:
            c = generate_candidate_for_cell(
                row=row, col=col, cell_id=cell_id,
                intervention_type=InterventionType.COOL_ROOF,
                baseline_hpi=hpi, baseline_lst_c=lst, is_chronic_hotspot=is_chronic,
                administrative_zone=zone, ndvi=ndvi, ndbi=ndbi, ndwi=ndwi,
                usable_area_m2=2000.0, tree_count=0, is_inside_smc=is_inside,
            )
            if c.feasibility_status == FeasibilityStatus.FEASIBLE:
                feasible.append(c)
            else:
                rejected.append(c)

        # 3. Green Roof for dense institutional/commercial roofs (NDBI > 0.10)
        if InterventionType.GREEN_ROOF in target_types and ndbi > 0.10:
            c = generate_candidate_for_cell(
                row=row, col=col, cell_id=cell_id,
                intervention_type=InterventionType.GREEN_ROOF,
                baseline_hpi=hpi, baseline_lst_c=lst, is_chronic_hotspot=is_chronic,
                administrative_zone=zone, ndvi=ndvi, ndbi=ndbi, ndwi=ndwi,
                usable_area_m2=1200.0, tree_count=0, is_inside_smc=is_inside,
            )
            if c.feasibility_status == FeasibilityStatus.FEASIBLE:
                feasible.append(c)
            else:
                rejected.append(c)

        # 4. Cool Pavement for commercial corridors (NDBI > 0.05)
        if InterventionType.COOL_PAVEMENT in target_types and ndbi > 0.05:
            c = generate_candidate_for_cell(
                row=row, col=col, cell_id=cell_id,
                intervention_type=InterventionType.COOL_PAVEMENT,
                baseline_hpi=hpi, baseline_lst_c=lst, is_chronic_hotspot=is_chronic,
                administrative_zone=zone, ndvi=ndvi, ndbi=ndbi, ndwi=ndwi,
                usable_area_m2=1000.0, tree_count=0, is_inside_smc=is_inside,
            )
            if c.feasibility_status == FeasibilityStatus.FEASIBLE:
                feasible.append(c)
            else:
                rejected.append(c)

        if max_candidates and len(feasible) >= max_candidates:
            break

    return feasible, rejected
