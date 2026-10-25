"""Hard Feasibility Constraints Engine for HEATSENSE AI (Stage D).

Enforces strict legal, physical, and environmental constraints prior to optimization:
1. Boundary Containment (strictly inside Surat Municipal Corporation boundary).
2. Usable Area Minimums (rejects micro-slivers < 100 m²).
3. Water Body / Wetland Conflict (rejects candidates intersecting water, NDWI > 0.05).
4. Evidence Sufficiency (rejects unscored cells with missing HPI).
5. Land-Cover Suitability:
   - Roof interventions require built-up context (NDBI > -0.10).
   - Tree planting requires available non-saturated canopy space (NDVI < 0.55).
6. Structured rejection logging for every excluded candidate.
"""

from __future__ import annotations

from typing import Any
from gis.interventions import (
    FeasibilityStatus,
    InterventionCandidate,
    InterventionType,
    RejectionReason,
)

MIN_USABLE_AREA_M2 = 100.0
MAX_WATER_NDWI_THRESHOLD = 0.05
MIN_HPI_ELIGIBILITY = 0.30
MAX_EXISTING_CANOPY_NDVI = 0.55
MIN_BUILT_NDBI_FOR_ROOF = -0.10


def evaluate_candidate_feasibility(
    candidate: InterventionCandidate,
    ndvi: float | None = None,
    ndbi: float | None = None,
    ndwi: float | None = None,
    is_inside_smc_boundary: bool = True,
) -> tuple[FeasibilityStatus, RejectionReason, str]:
    """
    Evaluate candidate against hard constraints.

    Returns
    -------
    tuple[FeasibilityStatus, RejectionReason, str]
        (status, rejection_reason, diagnostic_explanation)
    """
    # 1. Study boundary containment
    if not is_inside_smc_boundary:
        return (
            FeasibilityStatus.REJECTED,
            RejectionReason.OUTSIDE_STUDY_BOUNDARY,
            "Candidate falls outside Surat Municipal Corporation authoritative boundary.",
        )

    # 2. Minimum usable area
    if candidate.usable_area_m2 < MIN_USABLE_AREA_M2:
        return (
            FeasibilityStatus.REJECTED,
            RejectionReason.INSUFFICIENT_USABLE_AREA,
            f"Usable area {candidate.usable_area_m2:.1f} m² is below the minimum threshold ({MIN_USABLE_AREA_M2} m²).",
        )

    # 3. Water body conflict
    if ndwi is not None and ndwi > MAX_WATER_NDWI_THRESHOLD:
        return (
            FeasibilityStatus.REJECTED,
            RejectionReason.WATER_BODY_CONFLICT,
            f"Location conflicts with water body or wetland (NDWI = {ndwi:.3f} > {MAX_WATER_NDWI_THRESHOLD}).",
        )

    # 4. Missing HPI evidence
    if candidate.baseline_hpi is None or candidate.baseline_hpi < MIN_HPI_ELIGIBILITY:
        if not candidate.is_chronic_hotspot:
            return (
                FeasibilityStatus.REJECTED,
                RejectionReason.INSUFFICIENT_THERMAL_PRIORITY,
                f"Baseline Heat Priority Index ({candidate.baseline_hpi}) is below intervention threshold ({MIN_HPI_ELIGIBILITY}).",
            )

    # 5. Land-cover suitability & structural typology checks
    typology = getattr(candidate, "landuse_typology", "unclassified")

    # Constraint A: Open vacant public/private land NEVER gets cool roof or green roof
    if typology in ("vacant_public_open_land", "vacant_private_land"):
        if candidate.intervention_type in (InterventionType.COOL_ROOF, InterventionType.GREEN_ROOF):
            return (
                FeasibilityStatus.REJECTED,
                RejectionReason.NO_ROOF_STRUCTURE_ON_OPEN_LAND,
                f"Open plot ({typology}) contains no building rooftop structure for {candidate.intervention_type.value}.",
            )

    # Constraint B: Industrial corrugated tin shed NEVER gets green roof (dead load collapse hazard)
    if typology == "industrial_shed_roof" and candidate.intervention_type == InterventionType.GREEN_ROOF:
        return (
            FeasibilityStatus.REJECTED,
            RejectionReason.STRUCTURAL_LOAD_COLLAPSE_RISK,
            "CRITICAL STRUCTURAL SAFETY VIOLATION: Industrial corrugated metal/asbestos shed has live load capacity < 25 kg/m²; green roof dead load (100-150 kg/m²) causes roof collapse.",
        )

    # Constraint C: Rainwater-fed pond strictly rejected without documented water source
    if candidate.intervention_type == InterventionType.RAINWATER_FED_POND:
        has_water_source = getattr(candidate, "has_documented_water_source", False)
        # Check if explicitly provided in candidate or kwargs
        if not has_water_source:
            return (
                FeasibilityStatus.REJECTED,
                RejectionReason.UNVERIFIED_WATER_SOURCE_FOR_POND,
                "Rainwater-fed pond strictly rejected: requires verified, documented stormwater catchment (>= 5x pond area) or treated wastewater supply to prevent dry stagnant dust bowls.",
            )

    # Constraint D: Ambiguous / unclassified parcel requires on-site survey before mechanical approval
    if typology == "unclassified" or getattr(candidate, "needs_site_survey", False):
        return (
            FeasibilityStatus.REJECTED,
            RejectionReason.SITE_SURVEY_REQUIRED,
            "Classification uncertain: site flagged for mandatory on-site structural and land-tenure survey before permit issuance.",
        )

    # Standard biophysical checks
    if candidate.intervention_type in (InterventionType.COOL_ROOF, InterventionType.GREEN_ROOF):
        if ndbi is not None and ndbi < MIN_BUILT_NDBI_FOR_ROOF:
            return (
                FeasibilityStatus.REJECTED,
                RejectionReason.LOW_BUILT_DENSITY_FOR_ROOF,
                f"Insufficient built-up density for rooftop intervention (NDBI = {ndbi:.3f} < {MIN_BUILT_NDBI_FOR_ROOF}).",
            )
        if ndvi is not None and ndvi > MAX_EXISTING_CANOPY_NDVI:
            return (
                FeasibilityStatus.REJECTED,
                RejectionReason.HIGH_VEGETATION_CONFLICT_FOR_ROOF,
                f"Existing dense canopy covers structure (NDVI = {ndvi:.3f} > {MAX_EXISTING_CANOPY_NDVI}).",
            )

    elif candidate.intervention_type in (
        InterventionType.TREE_CANOPY,
        InterventionType.PUBLIC_PARK_NATIVE_TREES,
        InterventionType.DENSE_MIYAWAKI_PLANTATION,
    ):
        if ndvi is not None and ndvi >= MAX_EXISTING_CANOPY_NDVI:
            return (
                FeasibilityStatus.REJECTED,
                RejectionReason.HIGH_VEGETATION_CONFLICT_FOR_ROOF,
                f"Site already saturated with mature canopy (NDVI = {ndvi:.3f} >= {MAX_EXISTING_CANOPY_NDVI}).",
            )

    return (
        FeasibilityStatus.FEASIBLE,
        RejectionReason.NONE,
        "Candidate satisfies all statutory, physical, and environmental feasibility criteria.",
    )


def filter_feasible_candidates(
    candidates: list[InterventionCandidate],
    cell_environmental_context: dict[str, dict[str, float]] | None = None,
) -> tuple[list[InterventionCandidate], list[InterventionCandidate]]:
    """
    Filter candidate list into feasible and rejected candidate lists, updating statuses in place.
    """
    feasible: list[InterventionCandidate] = []
    rejected: list[InterventionCandidate] = []

    for cand in candidates:
        ctx = cell_environmental_context.get(cand.cell_id, {}) if cell_environmental_context else {}
        ndvi = ctx.get("ndvi")
        ndbi = ctx.get("ndbi")
        ndwi = ctx.get("ndwi")
        is_inside = ctx.get("is_inside", True)

        status, reason, _ = evaluate_candidate_feasibility(
            candidate=cand,
            ndvi=ndvi,
            ndbi=ndbi,
            ndwi=ndwi,
            is_inside_smc_boundary=is_inside,
        )
        cand.feasibility_status = status
        cand.rejection_reason = reason

        if status == FeasibilityStatus.FEASIBLE:
            feasible.append(cand)
        else:
            rejected.append(cand)

    return feasible, rejected
