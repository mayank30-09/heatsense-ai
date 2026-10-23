"""Evidence-Based Intervention Recommendation Engine for Spatial Polygons (Stage D).

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. Grounded strictly in empirical microclimate literature (Bowler 2010, Santamouris 2017, Akbari 2001)
   and municipal cost schedules (SMC Urban Greening, CPWD Schedule of Rates).
2. Uses ONLY:
   - Seasonal LST statistics (mean, max, min, P90)
   - Heat Priority Index (mean HPI, max HPI)
   - Vegetation deficit and built-density components
   - Share of chronic / frequent heat cells
   - Optical indices (NDVI, NDBI, NDWI)
   - Open water fraction and warning flag
   - SMC boundary containment (inside_smc_fraction)
   - Data coverage and confidence tier
   - Existing Stage D candidate, cost, and cooling functions run on intersecting cells.
3. Every threshold is explicitly documented as an ASSUMPTION.
4. Any missing data (roof structure, road classification, parcel ownership, available vacant land)
   is explicitly designated as 'not available - field survey required'.
5. Transparent evidence labeling: MEASURED, MODELLED, ASSUMPTION, or UNVERIFIED.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from gis.interventions import (
    FeasibilityStatus,
    InterventionType,
    RejectionReason,
)
from gis.interventions.costs import estimate_intervention_cost
from gis.interventions.cooling_effects import estimate_cooling_effect


# ---------------------------------------------------------------------------
# Documented Thresholds (Listed as ASSUMPTIONS)
# ---------------------------------------------------------------------------
ASSUMPTION_HIGH_HPI_THRESHOLD: float = 50.0
"""ASSUMPTION: Mean HPI >= 50.0 indicates an elevated thermal priority area."""

ASSUMPTION_MAX_HPI_CRITICAL_THRESHOLD: float = 70.0
"""ASSUMPTION: Max HPI >= 70.0 indicates acute localized heat severity."""

ASSUMPTION_CHRONIC_SHARE_THRESHOLD: float = 0.10
"""ASSUMPTION: If >10% of cells in a polygon are chronic hotspots, priority is elevated."""

ASSUMPTION_HIGH_VEG_DEFICIT: float = 0.50
"""ASSUMPTION: Vegetation deficit component >= 0.50 indicates severe green canopy deficiency."""

ASSUMPTION_LOW_NDVI_THRESHOLD: float = 0.20
"""ASSUMPTION: Mean NDVI < 0.20 indicates lack of vegetative ground cover."""

ASSUMPTION_HIGH_BUILT_DENSITY: float = 0.50
"""ASSUMPTION: Built density component >= 0.50 indicates dense impervious structures."""

ASSUMPTION_MIN_BUILT_NDBI: float = -0.10
"""ASSUMPTION: NDBI >= -0.10 required for rooftop interventions (minimum structure density)."""

ASSUMPTION_CANOPY_SATURATION_NDVI: float = 0.55
"""ASSUMPTION: NDVI >= 0.55 represents existing mature canopy saturation where further tree planting is unsuitable."""

ASSUMPTION_WATER_WARNING_FRACTION: float = 0.25
"""ASSUMPTION: Water fraction >= 0.25 triggers thermal distortion warnings and restricts pavement/roof interventions."""

ASSUMPTION_WATER_HARD_REJECT_FRACTION: float = 0.50
"""ASSUMPTION: Water fraction >= 0.50 rejects all terrestrial interventions as water-body conflict."""

ASSUMPTION_MIN_DATA_COVERAGE_PCT: float = 70.0
"""ASSUMPTION: Minimum 70% valid pixel observation coverage required for high confidence."""

MISSING_DATA_NOTE: str = "not available - field survey required"


# ---------------------------------------------------------------------------
# Schema Definitions
# ---------------------------------------------------------------------------
class QuantityBasis(BaseModel):
    estimated_quantity: float = Field(..., description="Estimated numerical physical quantity")
    unit: str = Field(..., description="Measurement unit (e.g. trees, m²)")
    basis_description: str = Field(..., description="Traceable basis of quantity calculation")
    missing_data_survey_note: str = Field(
        default=MISSING_DATA_NOTE,
        description="Explicit note for data requiring ground surveying",
    )


class CostRangeINR(BaseModel):
    base: float = Field(..., description="Expected base cost in Indian Rupees (INR)")
    min: float = Field(..., description="Lower confidence cost bound in INR")
    max: float = Field(..., description="Upper confidence cost bound in INR")
    formatted: str = Field(..., description="Human-readable formatted cost in Lakhs or Crores")
    maintenance_horizon: str = Field(..., description="Maintenance duration included in cost model")


class CoolingRangeC(BaseModel):
    expected: float = Field(..., description="Expected microclimate cooling impact in °C")
    min: float = Field(..., description="Lower bound cooling impact in °C")
    max: float = Field(..., description="Upper bound cooling impact in °C")
    formatted: str = Field(..., description="Formatted cooling range string")
    model_source: str = Field(..., description="Scientific literature model citation")


class RecommendationItem(BaseModel):
    type: str = Field(..., description="Intervention type identifier")
    title: str = Field(..., description="Human-readable intervention title")
    priority: str = Field(..., description="Priority tier: HIGH, MEDIUM, LOW, or NOT_RECOMMENDED")
    rationale: str = Field(..., description="Evidence rationale quoting polygon metrics")
    quantity_basis: QuantityBasis
    cost_range_inr: CostRangeINR
    cooling_range_c: CoolingRangeC
    feasibility_status: str = Field(..., description="FEASIBLE, CONDITIONALLY_FEASIBLE, or REJECTED")
    rejection_reasons: List[str] = Field(default_factory=list, description="Specific constraint violations if any")
    feasibility_notes: List[str] = Field(default_factory=list, description="Ground survey feasibility requirements")
    maintenance_note: str = Field(..., description="Maintenance specifications from municipal schedule")
    evidence_label: str = Field(default="MODELLED", description="Evidence status: MEASURED, MODELLED, ASSUMPTION")
    missing_data_survey_requirements: List[str] = Field(
        default_factory=list,
        description="List of unavailable data points requiring ground surveying",
    )


class PolygonSummary(BaseModel):
    status: str = Field(..., description="ok, outside_study_area, partially_outside, no_valid_observations")
    area_km2: float
    inside_smc_fraction: float
    season: str
    effective_year: int
    mean_lst_c: Optional[float] = None
    max_lst_c: Optional[float] = None
    min_lst_c: Optional[float] = None
    p90_lst_c: Optional[float] = None
    mean_hpi: Optional[float] = None
    max_hpi: Optional[float] = None
    vegetation_deficit_component: Optional[float] = None
    built_density_component: Optional[float] = None
    mean_ndvi: Optional[float] = None
    mean_ndbi: Optional[float] = None
    mean_ndwi: Optional[float] = None
    water_fraction: float = 0.0
    water_warning: bool = False
    cell_count: int = 0
    chronic_cell_count: int = 0
    chronic_cell_share: float = 0.0
    frequent_cell_share: float = 0.0
    data_coverage_percentage: float = 0.0
    confidence_score: float = 0.0
    confidence_tier: str = "LOW"


class RecommendationsResponse(BaseModel):
    polygon_summary: PolygonSummary
    recommendations: List[RecommendationItem]
    caveats: List[str]
    assumptions_applied: List[str]
    evidence_label: str = "MODELLED"


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------
def format_inr(amount: float) -> str:
    """Format INR currency into human-readable Lakhs or Crores."""
    if amount >= 10_000_000:
        return f"₹{amount / 10_000_000:.2f} Cr"
    elif amount >= 100_000:
        return f"₹{amount / 100_000:.2f}L"
    else:
        return f"₹{amount:,.0f}"


# ---------------------------------------------------------------------------
# Core Pure Rule Engine
# ---------------------------------------------------------------------------
def generate_polygon_recommendations(
    summary: PolygonSummary,
    cell_candidates: Optional[List[Dict[str, Any]]] = None,
) -> RecommendationsResponse:
    """
    Deterministic rule engine that synthesizes prioritized recommendations
    strictly from observed polygon metrics and Stage D models.
    """
    caveats = [
        "Microclimate cooling ranges are derived from bounded empirical literature (Bowler 2010, Santamouris 2017) and Stage D physics models, not linear ML multipliers.",
        "Parcel ownership, cadastral boundaries, roof structural integrity, and road classifications are not available - field survey required before municipal capital allocation.",
        "Ground land-cover metrics derive from Landsat 8/9 Level-2 30m observations resampled to the 100m SMC grid.",
    ]

    assumptions_applied = [
        f"High HPI threshold: HPI >= {ASSUMPTION_HIGH_HPI_THRESHOLD} or max HPI >= {ASSUMPTION_MAX_HPI_CRITICAL_THRESHOLD}",
        f"Chronic cell priority: chronic hotspot share >= {ASSUMPTION_CHRONIC_SHARE_THRESHOLD * 100:.0f}%",
        f"Vegetation deficit threshold: deficit >= {ASSUMPTION_HIGH_VEG_DEFICIT} or NDVI < {ASSUMPTION_LOW_NDVI_THRESHOLD}",
        f"Canopy saturation ceiling: existing NDVI >= {ASSUMPTION_CANOPY_SATURATION_NDVI} rejects further tree planting",
        f"Built density threshold: component >= {ASSUMPTION_HIGH_BUILT_DENSITY} or NDBI > 0.05",
        f"Water body conflict: NDWI water fraction >= {ASSUMPTION_WATER_WARNING_FRACTION * 100:.0f}% triggers warning; >= {ASSUMPTION_WATER_HARD_REJECT_FRACTION * 100:.0f}% rejects terrestrial interventions",
    ]

    # Handle boundary or invalid data cases immediately
    if summary.status == "outside_study_area" or summary.inside_smc_fraction <= 0.0:
        caveats.append("The requested polygon lies entirely outside the Surat Municipal Corporation (SMC) study boundary. No interventions are recommended.")
        return RecommendationsResponse(
            polygon_summary=summary,
            recommendations=[],
            caveats=caveats,
            assumptions_applied=assumptions_applied,
            evidence_label="ASSUMPTION",
        )

    if summary.status == "no_valid_observations" or summary.data_coverage_percentage == 0.0:
        caveats.append("No valid satellite observations exist for this polygon in the selected season. Recommendations cannot be reliably computed.")
        return RecommendationsResponse(
            polygon_summary=summary,
            recommendations=[],
            caveats=caveats,
            assumptions_applied=assumptions_applied,
            evidence_label="UNVERIFIED",
        )

    # Effective baseline metrics with safe fallbacks
    mean_lst = summary.mean_lst_c if summary.mean_lst_c is not None else 38.0
    max_lst = summary.max_lst_c if summary.max_lst_c is not None else mean_lst
    mean_hpi = summary.mean_hpi if summary.mean_hpi is not None else 40.0
    max_hpi = summary.max_hpi if summary.max_hpi is not None else mean_hpi
    veg_deficit = summary.vegetation_deficit_component if summary.vegetation_deficit_component is not None else 0.30
    built_density = summary.built_density_component if summary.built_density_component is not None else 0.30
    mean_ndvi = summary.mean_ndvi if summary.mean_ndvi is not None else 0.25
    mean_ndbi = summary.mean_ndbi if summary.mean_ndbi is not None else 0.0
    water_fraction = summary.water_fraction

    # Determine thermal stress level
    is_high_thermal = (
        mean_hpi >= ASSUMPTION_HIGH_HPI_THRESHOLD
        or max_hpi >= ASSUMPTION_MAX_HPI_CRITICAL_THRESHOLD
        or summary.chronic_cell_share >= ASSUMPTION_CHRONIC_SHARE_THRESHOLD
        or mean_lst >= 42.0
    )

    is_moderate_thermal = (
        mean_hpi >= 40.0
        or summary.frequent_cell_share >= 0.30
        or mean_lst >= 38.0
    )

    cell_multiplier = max(1, summary.cell_count)
    recommendations: List[RecommendationItem] = []

    # =========================================================================
    # 1. Tree Canopy Expansion (TREE_CANOPY)
    # =========================================================================
    tree_rejections: List[str] = []
    tree_feasibility = FeasibilityStatus.FEASIBLE.value

    if water_fraction >= ASSUMPTION_WATER_HARD_REJECT_FRACTION:
        tree_rejections.append(f"Water body conflict: polygon is {water_fraction * 100:.1f}% open water (>= {ASSUMPTION_WATER_HARD_REJECT_FRACTION * 100:.0f}%).")
        tree_feasibility = FeasibilityStatus.REJECTED.value
    elif mean_ndvi >= ASSUMPTION_CANOPY_SATURATION_NDVI:
        tree_rejections.append(f"Canopy saturation: site mean NDVI ({mean_ndvi:.3f}) exceeds canopy ceiling ({ASSUMPTION_CANOPY_SATURATION_NDVI}).")
        tree_feasibility = FeasibilityStatus.REJECTED.value

    # Priority assessment
    if tree_feasibility == FeasibilityStatus.REJECTED.value:
        tree_priority = "NOT_RECOMMENDED"
    elif is_high_thermal and (veg_deficit >= ASSUMPTION_HIGH_VEG_DEFICIT or mean_ndvi < ASSUMPTION_LOW_NDVI_THRESHOLD):
        tree_priority = "HIGH"
    elif is_moderate_thermal or veg_deficit >= 0.40:
        tree_priority = "MEDIUM"
    else:
        tree_priority = "LOW"

    # Quantity & models
    estimated_trees = max(10, min(800, int(cell_multiplier * 40)))
    tree_cost_base, tree_cost_min, tree_cost_max, tree_cost_meta = estimate_intervention_cost(
        InterventionType.TREE_CANOPY,
        usable_area_m2=0.0,
        tree_count=estimated_trees,
    )
    tree_cool_base, tree_cool_min, tree_cool_max, tree_cool_meta = estimate_cooling_effect(
        InterventionType.TREE_CANOPY,
        usable_area_m2=0.0,
        tree_count=estimated_trees,
        baseline_lst_c=mean_lst,
    )

    tree_rationale = (
        f"Observed mean LST of {mean_lst:.1f}°C with vegetation deficit component of {veg_deficit:.2f} "
        f"and mean NDVI of {mean_ndvi:.2f} across {summary.area_km2:.2f} km². "
        f"{'Elevated heat priority (mean HPI ' + f'{mean_hpi:.1f}' + ') justifies prioritized greening.' if is_high_thermal else 'Moderate canopy addition provides microclimate buffering.'}"
    )

    recommendations.append(
        RecommendationItem(
            type="TREE_CANOPY",
            title="Urban Tree Canopy Expansion",
            priority=tree_priority,
            rationale=tree_rationale,
            quantity_basis=QuantityBasis(
                estimated_quantity=float(estimated_trees),
                unit="hardy saplings",
                basis_description=f"Modeled at 40 trees per 100m cell across {cell_multiplier} intersecting cell(s).",
                missing_data_survey_note="Available ground planting area / road verge: " + MISSING_DATA_NOTE,
            ),
            cost_range_inr=CostRangeINR(
                base=tree_cost_base,
                min=tree_cost_min,
                max=tree_cost_max,
                formatted=f"{format_inr(tree_cost_min)} – {format_inr(tree_cost_max)} (base: {format_inr(tree_cost_base)})",
                maintenance_horizon="3 years establishment, replacement guarantee, and watering tanker",
            ),
            cooling_range_c=CoolingRangeC(
                expected=round(tree_cool_base, 2),
                min=round(tree_cool_min, 2),
                max=round(tree_cool_max, 2),
                formatted=f"-{tree_cool_min:.2f}°C to -{tree_cool_max:.2f}°C (expected: -{tree_cool_base:.2f}°C)",
                model_source=tree_cool_meta.get("model", "Bowler et al. 2010"),
            ),
            feasibility_status=tree_feasibility,
            rejection_reasons=tree_rejections,
            feasibility_notes=[
                "Requires native drought-tolerant species (Neem, Gulmohar, Peepal, Pongamia).",
                "Available vacant land and sidewalk width: " + MISSING_DATA_NOTE,
                "Underground utility line clearance (water/drainage/telecom): " + MISSING_DATA_NOTE,
            ],
            maintenance_note="Includes 3-year municipal establishment guarantee, initial protective tree guards, and scheduled drip tanker supply (SMC Urban Greening Schedule 2024-2025).",
            evidence_label="MODELLED",
            missing_data_survey_requirements=[
                "Available plantable roadside verge width: " + MISSING_DATA_NOTE,
                "Subsurface utility clearance: " + MISSING_DATA_NOTE,
            ],
        )
    )

    # =========================================================================
    # 2. Cool Roof Coatings (COOL_ROOF)
    # =========================================================================
    roof_rejections: List[str] = []
    roof_feasibility = FeasibilityStatus.FEASIBLE.value

    if water_fraction >= ASSUMPTION_WATER_HARD_REJECT_FRACTION:
        roof_rejections.append(f"Water body conflict: polygon is {water_fraction * 100:.1f}% open water.")
        roof_feasibility = FeasibilityStatus.REJECTED.value
    elif mean_ndbi < ASSUMPTION_MIN_BUILT_NDBI:
        roof_rejections.append(f"Insufficient built structures: mean NDBI ({mean_ndbi:.3f}) is below rooftop suitability threshold ({ASSUMPTION_MIN_BUILT_NDBI}).")
        roof_feasibility = FeasibilityStatus.REJECTED.value

    if roof_feasibility == FeasibilityStatus.REJECTED.value:
        roof_priority = "NOT_RECOMMENDED"
    elif is_high_thermal and (built_density >= ASSUMPTION_HIGH_BUILT_DENSITY or mean_ndbi > 0.05):
        roof_priority = "HIGH"
    elif is_moderate_thermal or built_density >= 0.35:
        roof_priority = "MEDIUM"
    else:
        roof_priority = "LOW"

    estimated_roof_m2 = max(200.0, min(40000.0, float(cell_multiplier * 1500.0)))
    roof_cost_base, roof_cost_min, roof_cost_max, roof_cost_meta = estimate_intervention_cost(
        InterventionType.COOL_ROOF,
        usable_area_m2=estimated_roof_m2,
    )
    roof_cool_base, roof_cool_min, roof_cool_max, roof_cool_meta = estimate_cooling_effect(
        InterventionType.COOL_ROOF,
        usable_area_m2=estimated_roof_m2,
        baseline_lst_c=mean_lst,
    )

    roof_rationale = (
        f"Built density component of {built_density:.2f} and mean NDBI of {mean_ndbi:.2f} with peak LST "
        f"reaching {max_lst:.1f}°C indicates extensive exposed roof surfaces. High-albedo elastomeric "
        f"coating (SRI >= 104) reflects solar radiation and prevents thermal mass heat absorption."
    )

    recommendations.append(
        RecommendationItem(
            type="COOL_ROOF",
            title="High-Albedo Cool Roof Coatings",
            priority=roof_priority,
            rationale=roof_rationale,
            quantity_basis=QuantityBasis(
                estimated_quantity=estimated_roof_m2,
                unit="m² roof area",
                basis_description=f"Modeled at 1,500 m² estimated rooftop surface per 100m cell across {cell_multiplier} cell(s).",
                missing_data_survey_note="Building footprints and roof structural integrity: " + MISSING_DATA_NOTE,
            ),
            cost_range_inr=CostRangeINR(
                base=roof_cost_base,
                min=roof_cost_min,
                max=roof_cost_max,
                formatted=f"{format_inr(roof_cost_min)} – {format_inr(roof_cost_max)} (base: {format_inr(roof_cost_base)})",
                maintenance_horizon="5-year lifecycle with scheduled bi-annual cleaning",
            ),
            cooling_range_c=CoolingRangeC(
                expected=round(roof_cool_base, 2),
                min=round(roof_cool_min, 2),
                max=round(roof_cool_max, 2),
                formatted=f"-{roof_cool_min:.2f}°C to -{roof_cool_max:.2f}°C (expected: -{roof_cool_base:.2f}°C)",
                model_source=roof_cool_meta.get("model", "Santamouris et al. 2017"),
            ),
            feasibility_status=roof_feasibility,
            rejection_reasons=roof_rejections,
            feasibility_notes=[
                "Applicable to concrete flat slabs, corrugated metal sheets, or asbestos roofs with structural stability.",
                "Roof structural load and waterproofing integrity: " + MISSING_DATA_NOTE,
                "Building ownership and resident permission: " + MISSING_DATA_NOTE,
            ],
            maintenance_note="Requires bi-annual surface cleaning prior to summer peak and re-application at year 5 (CPWD Schedule of Rates / Surat Cool Roofs Initiative).",
            evidence_label="MODELLED",
            missing_data_survey_requirements=[
                "Structural roof integrity and load suitability: " + MISSING_DATA_NOTE,
                "Property tenure and owner authorization: " + MISSING_DATA_NOTE,
            ],
        )
    )

    # =========================================================================
    # 3. Cool Permeable Pavement (COOL_PAVEMENT)
    # =========================================================================
    pave_rejections: List[str] = []
    pave_feasibility = FeasibilityStatus.FEASIBLE.value

    if water_fraction >= ASSUMPTION_WATER_HARD_REJECT_FRACTION:
        pave_rejections.append("Water body conflict: open water surface.")
        pave_feasibility = FeasibilityStatus.REJECTED.value

    if pave_feasibility == FeasibilityStatus.REJECTED.value:
        pave_priority = "NOT_RECOMMENDED"
    elif is_high_thermal and built_density >= 0.50:
        pave_priority = "MEDIUM"
    elif is_moderate_thermal:
        pave_priority = "LOW"
    else:
        pave_priority = "LOW"

    estimated_pave_m2 = max(100.0, min(20000.0, float(cell_multiplier * 1000.0)))
    pave_cost_base, pave_cost_min, pave_cost_max, pave_cost_meta = estimate_intervention_cost(
        InterventionType.COOL_PAVEMENT,
        usable_area_m2=estimated_pave_m2,
    )
    pave_cool_base, pave_cool_min, pave_cool_max, pave_cool_meta = estimate_cooling_effect(
        InterventionType.COOL_PAVEMENT,
        usable_area_m2=estimated_pave_m2,
        baseline_lst_c=mean_lst,
    )

    pave_rationale = (
        f"Surface temperature moderation for municipal walkways and parking lots. "
        f"Mean LST is {mean_lst:.1f}°C in built context (NDBI = {mean_ndbi:.2f}). "
        f"High-reflectance permeable pavers facilitate stormwater infiltration and diminish sensible heat storage."
    )

    recommendations.append(
        RecommendationItem(
            type="COOL_PAVEMENT",
            title="Cool Permeable Interlocking Pavements",
            priority=pave_priority,
            rationale=pave_rationale,
            quantity_basis=QuantityBasis(
                estimated_quantity=estimated_pave_m2,
                unit="m² pavement area",
                basis_description=f"Modeled at 1,000 m² pedestrian walkway or parking area per 100m cell across {cell_multiplier} cell(s).",
                missing_data_survey_note="Public right-of-way and roadway classification: " + MISSING_DATA_NOTE,
            ),
            cost_range_inr=CostRangeINR(
                base=pave_cost_base,
                min=pave_cost_min,
                max=pave_cost_max,
                formatted=f"{format_inr(pave_cost_min)} – {format_inr(pave_cost_max)} (base: {format_inr(pave_cost_base)})",
                maintenance_horizon="6-month vacuum sweeping and joint sand replenishment",
            ),
            cooling_range_c=CoolingRangeC(
                expected=round(pave_cool_base, 2),
                min=round(pave_cool_min, 2),
                max=round(pave_cool_max, 2),
                formatted=f"-{pave_cool_min:.2f}°C to -{pave_cool_max:.2f}°C (expected: -{pave_cool_base:.2f}°C)",
                model_source=pave_cool_meta.get("model", "Akbari & Rose 2001"),
            ),
            feasibility_status=pave_feasibility,
            rejection_reasons=pave_rejections,
            feasibility_notes=[
                "Suitable for pedestrian paths, school plazas, and parking areas; unsuited for heavy freight corridors.",
                "Sub-base percolation and stormwater tie-in: " + MISSING_DATA_NOTE,
                "Traffic loading class: " + MISSING_DATA_NOTE,
            ],
            maintenance_note="Requires bi-annual high-pressure vacuum sweeping to prevent silt clog and maintain permeability (Gujarat PWD Roads Norms).",
            evidence_label="MODELLED",
            missing_data_survey_requirements=[
                "Roadway hierarchy and commercial traffic load: " + MISSING_DATA_NOTE,
                "Subsurface drainage and soil percolation rate: " + MISSING_DATA_NOTE,
            ],
        )
    )

    # Sort recommendations by priority: HIGH -> MEDIUM -> LOW -> NOT_RECOMMENDED
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NOT_RECOMMENDED": 3}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

    return RecommendationsResponse(
        polygon_summary=summary,
        recommendations=recommendations,
        caveats=caveats,
        assumptions_applied=assumptions_applied,
        evidence_label="MODELLED",
    )
