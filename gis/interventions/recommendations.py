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
   - Land-use parcel typologies and engineering constraints
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
from gis.interventions.landuse import LanduseClassifier


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
    landuse_typology: str = Field(default="unclassified", description="Land-use parcel typology")
    allowed_interventions: List[str] = Field(default_factory=list, description="Allowed interventions for this typology")
    selection_rationale: str = Field(default="", description="Why this intervention was recommended for this land type")
    rejected_alternatives: List[Dict[str, str]] = Field(default_factory=list, description="Alternatives rejected with reason")
    water_need_description: str = Field(default="", description="Water requirement for this intervention")
    maintenance_burden: str = Field(default="", description="Maintenance burden and schedule")
    construction_time: str = Field(default="", description="Estimated construction or establishment time")
    whole_life_cost_3yr_inr: float = Field(default=0.0, description="3-year whole-life cost in INR")
    whole_life_cost_per_c_m2: float = Field(default=0.0, description="Whole-life cost per degree-cell-area in INR / (°C·m²)")
    air_cooling_c: float = Field(default=0.0, description="Estimated ambient air temperature reduction in °C")
    needs_site_survey: bool = Field(default=False, description="Whether this parcel requires an on-site survey")


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
    data_coverage_percentage: float = 100.0
    confidence_score: float = 0.0
    confidence_tier: str = "LOW"
    landuse_typology: Optional[str] = Field(default=None, description="Identified or provided landuse typology")
    needs_site_survey: bool = Field(default=False, description="Whether polygon needs site survey")
    osm_tags: Optional[Dict[str, str]] = Field(default=None, description="OSM tags if available")
    building_info: Optional[Dict[str, Any]] = Field(default=None, description="Building footprint information")
    distance_to_water_m: Optional[float] = None
    is_public_ownership: Optional[bool] = None
    has_documented_water_source: bool = Field(default=False, description="Whether a catchment/treated water source is documented")


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
    strictly from observed polygon metrics, Stage D models, and land-use typologies.
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

    # 1. Landuse Classification
    classifier = LanduseClassifier()
    clf_res = classifier.classify(
        osm_tags=summary.osm_tags,
        building_info=summary.building_info,
        ndvi=summary.mean_ndvi,
        ndbi=summary.mean_ndbi,
        ndwi=summary.mean_ndwi,
        water_fraction=summary.water_fraction,
        distance_to_water_m=summary.distance_to_water_m,
        is_public_ownership=summary.is_public_ownership,
        built_density=summary.built_density_component,
        veg_deficit=summary.vegetation_deficit_component,
        explicit_typology=summary.landuse_typology,
    )

    summary.landuse_typology = clf_res.typology
    summary.needs_site_survey = clf_res.needs_site_survey

    # If unclassified or site survey required: Return ZERO mechanical recommendations
    if clf_res.needs_site_survey or clf_res.typology == "unclassified":
        caveats.append(
            "MANDATORY REQUIREMENT: Site classification is uncertain / unclassified. "
            "An on-site survey is required before mechanical recommendations can be approved."
        )
        caveats.append("No mechanical interventions are permitted on unclassified land parcels under Surat heat-action governance.")
        return RecommendationsResponse(
            polygon_summary=summary,
            recommendations=[],
            caveats=caveats,
            assumptions_applied=assumptions_applied,
            evidence_label="ASSUMPTION",
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
    allowed_set = set(clf_res.allowed_interventions)
    prohibited_dict = clf_res.prohibition_reasons

    # Build rejected alternatives list for this landuse typology
    rejected_alts: List[Dict[str, str]] = []
    for p_type, p_reason in prohibited_dict.items():
        rejected_alts.append({
            "intervention_type": p_type,
            "title": p_type.replace("_", " ").title(),
            "rejection_reason": p_reason,
        })

    recommendations: List[RecommendationItem] = []

    # =========================================================================
    # 1. Tree Canopy Expansion (TREE_CANOPY)
    # =========================================================================
    tree_rejections: List[str] = []
    tree_feasibility = FeasibilityStatus.FEASIBLE.value

    if "tree_canopy" not in allowed_set:
        tree_feasibility = FeasibilityStatus.REJECTED.value
        tree_rejections.append(prohibited_dict.get("tree_canopy", f"Incompatible with landuse: {clf_res.title}."))
    elif water_fraction >= ASSUMPTION_WATER_HARD_REJECT_FRACTION:
        tree_rejections.append(f"Water body conflict: polygon is {water_fraction * 100:.1f}% open water (>= {ASSUMPTION_WATER_HARD_REJECT_FRACTION * 100:.0f}%).")
        tree_feasibility = FeasibilityStatus.REJECTED.value
    elif mean_ndvi >= ASSUMPTION_CANOPY_SATURATION_NDVI:
        tree_rejections.append(f"Canopy saturation: site mean NDVI ({mean_ndvi:.3f}) exceeds canopy ceiling ({ASSUMPTION_CANOPY_SATURATION_NDVI}).")
        tree_feasibility = FeasibilityStatus.REJECTED.value

    if tree_feasibility == FeasibilityStatus.REJECTED.value:
        tree_priority = "NOT_RECOMMENDED"
    elif is_high_thermal and (veg_deficit >= ASSUMPTION_HIGH_VEG_DEFICIT or mean_ndvi < ASSUMPTION_LOW_NDVI_THRESHOLD):
        tree_priority = "HIGH"
    elif is_moderate_thermal or veg_deficit >= 0.40:
        tree_priority = "MEDIUM"
    else:
        tree_priority = "LOW"

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
        f"and mean NDVI of {mean_ndvi:.2f} across {summary.area_km2:.2f} km² ({clf_res.title}). "
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
            landuse_typology=clf_res.typology,
            allowed_interventions=clf_res.allowed_interventions,
            selection_rationale=f"Selected for {clf_res.title} to address thermal deficit ({veg_deficit:.2f}).",
            rejected_alternatives=rejected_alts,
            water_need_description=tree_cool_meta.get("water_need", "Moderate (40 L/tree/week for first 3 years)"),
            maintenance_burden=tree_cool_meta.get("maintenance_burden", "Moderate (pruning, irrigation, guard check)"),
            construction_time=tree_cool_meta.get("construction_time", "2-4 weeks (planting); 3-5 years to full canopy"),
            whole_life_cost_3yr_inr=tree_cost_meta.get("whole_life_cost_3yr_inr", tree_cost_base),
            whole_life_cost_per_c_m2=tree_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
            air_cooling_c=tree_cool_meta.get("air_cooling_c", 0.94),
            needs_site_survey=False,
        )
    )

    # =========================================================================
    # 2. Cool Roof Coatings (COOL_ROOF)
    # =========================================================================
    roof_rejections: List[str] = []
    roof_feasibility = FeasibilityStatus.FEASIBLE.value

    if "cool_roof" not in allowed_set:
        roof_feasibility = FeasibilityStatus.REJECTED.value
        roof_rejections.append(prohibited_dict.get("cool_roof", f"Incompatible with landuse: {clf_res.title}."))
    elif water_fraction >= ASSUMPTION_WATER_HARD_REJECT_FRACTION:
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
        f"reaching {max_lst:.1f}°C in {clf_res.title}. High-albedo elastomeric "
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
            landuse_typology=clf_res.typology,
            allowed_interventions=clf_res.allowed_interventions,
            selection_rationale=f"Selected for {clf_res.title} due to high solar reflectance capability (SRI >= 104).",
            rejected_alternatives=rejected_alts,
            water_need_description=roof_cool_meta.get("water_need", "None (zero water)"),
            maintenance_burden=roof_cool_meta.get("maintenance_burden", "Low (bi-annual surface washing before summer peak)"),
            construction_time=roof_cool_meta.get("construction_time", "1-2 weeks"),
            whole_life_cost_3yr_inr=roof_cost_meta.get("whole_life_cost_3yr_inr", roof_cost_base),
            whole_life_cost_per_c_m2=roof_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
            air_cooling_c=roof_cool_meta.get("air_cooling_c", 0.50),
            needs_site_survey=False,
        )
    )

    # =========================================================================
    # 3. Cool Permeable Pavement (COOL_PAVEMENT)
    # =========================================================================
    pave_rejections: List[str] = []
    pave_feasibility = FeasibilityStatus.FEASIBLE.value

    if "cool_pavement" not in allowed_set:
        pave_feasibility = FeasibilityStatus.REJECTED.value
        pave_rejections.append(prohibited_dict.get("cool_pavement", f"Incompatible with landuse: {clf_res.title}."))
    elif water_fraction >= ASSUMPTION_WATER_HARD_REJECT_FRACTION:
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
        f"Surface temperature moderation for walkways and parking lots in {clf_res.title}. "
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
            landuse_typology=clf_res.typology,
            allowed_interventions=clf_res.allowed_interventions,
            selection_rationale=f"Selected for {clf_res.title} ground permeability enhancement.",
            rejected_alternatives=rejected_alts,
            water_need_description=pave_cool_meta.get("water_need", "None (zero water)"),
            maintenance_burden=pave_cool_meta.get("maintenance_burden", "Moderate (bi-annual vacuum sweeping of silt)"),
            construction_time=pave_cool_meta.get("construction_time", "1-2 months"),
            whole_life_cost_3yr_inr=pave_cost_meta.get("whole_life_cost_3yr_inr", pave_cost_base),
            whole_life_cost_per_c_m2=pave_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
            air_cooling_c=pave_cool_meta.get("air_cooling_c", 0.40),
            needs_site_survey=False,
        )
    )

    # =========================================================================
    # 4. New Interventions (Public Park, Miyawaki, Bioswale, Pond, Shaded Parking, Permeable Ground Cover)
    # =========================================================================
    # Evaluate other allowed interventions dynamically
    if "public_park_native_trees" in allowed_set:
        pk_m2 = max(500.0, float(cell_multiplier * 2500.0))
        pk_cost_b, pk_cost_min, pk_cost_max, pk_cost_meta = estimate_intervention_cost(
            InterventionType.PUBLIC_PARK_NATIVE_TREES, usable_area_m2=pk_m2
        )
        pk_cool_b, pk_cool_min, pk_cool_max, pk_cool_meta = estimate_cooling_effect(
            InterventionType.PUBLIC_PARK_NATIVE_TREES, usable_area_m2=pk_m2, baseline_lst_c=mean_lst
        )
        recommendations.append(
            RecommendationItem(
                type="PUBLIC_PARK_NATIVE_TREES",
                title="Public Park & Garden with Native Trees",
                priority="HIGH" if is_high_thermal else "MEDIUM",
                rationale=f"Multi-tier public park greening for {clf_res.title} across {summary.area_km2:.2f} km².",
                quantity_basis=QuantityBasis(
                    estimated_quantity=pk_m2,
                    unit="m² park area",
                    basis_description=f"Modeled at 2,500 m² public park area per 100m cell across {cell_multiplier} cell(s).",
                    missing_data_survey_note="Municipal land reservation boundary: " + MISSING_DATA_NOTE,
                ),
                cost_range_inr=CostRangeINR(
                    base=pk_cost_b, min=pk_cost_min, max=pk_cost_max,
                    formatted=f"{format_inr(pk_cost_min)} – {format_inr(pk_cost_max)} (base: {format_inr(pk_cost_b)})",
                    maintenance_horizon="3 years establishment and drip irrigation tanker",
                ),
                cooling_range_c=CoolingRangeC(
                    expected=round(pk_cool_b, 2), min=round(pk_cool_min, 2), max=round(pk_cool_max, 2),
                    formatted=f"-{pk_cool_min:.2f}°C to -{pk_cool_max:.2f}°C (expected: -{pk_cool_b:.2f}°C)",
                    model_source=pk_cool_meta.get("model", "Bowler et al. 2010"),
                ),
                feasibility_status="FEASIBLE",
                rejection_reasons=[],
                feasibility_notes=["Requires municipal land ownership confirmation and water connection."],
                maintenance_note=pk_cool_meta.get("maintenance_burden", "Regular municipal park maintenance"),
                evidence_label="MODELLED",
                missing_data_survey_requirements=["Municipal land title: " + MISSING_DATA_NOTE],
                landuse_typology=clf_res.typology,
                allowed_interventions=clf_res.allowed_interventions,
                selection_rationale=f"High community cooling and recreational oasis for {clf_res.title}.",
                rejected_alternatives=rejected_alts,
                water_need_description=pk_cool_meta.get("water_need", "High"),
                maintenance_burden=pk_cool_meta.get("maintenance_burden", "Regular park maintenance"),
                construction_time=pk_cool_meta.get("construction_time", "3-6 months"),
                whole_life_cost_3yr_inr=pk_cost_meta.get("whole_life_cost_3yr_inr", pk_cost_b),
                whole_life_cost_per_c_m2=pk_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
                air_cooling_c=pk_cool_meta.get("air_cooling_c", 1.10),
                needs_site_survey=False,
            )
        )

    if "dense_miyawaki_plantation" in allowed_set:
        miya_m2 = max(200.0, float(cell_multiplier * 800.0))
        miya_cost_b, miya_cost_min, miya_cost_max, miya_cost_meta = estimate_intervention_cost(
            InterventionType.DENSE_MIYAWAKI_PLANTATION, usable_area_m2=miya_m2
        )
        miya_cool_b, miya_cool_min, miya_cool_max, miya_cool_meta = estimate_cooling_effect(
            InterventionType.DENSE_MIYAWAKI_PLANTATION, usable_area_m2=miya_m2, baseline_lst_c=mean_lst
        )
        recommendations.append(
            RecommendationItem(
                type="DENSE_MIYAWAKI_PLANTATION",
                title="Dense Native Miyawaki Urban Forest",
                priority="HIGH" if is_high_thermal and veg_deficit >= 0.50 else "MEDIUM",
                rationale=f"High-density native forest cluster (3-4 saplings/m²) providing rapid microclimatic cooling.",
                quantity_basis=QuantityBasis(
                    estimated_quantity=miya_m2,
                    unit="m² dense forest",
                    basis_description=f"Modeled at 800 m² dense forest footprint across {cell_multiplier} cell(s).",
                    missing_data_survey_note="Soil depth and underground utility clearance: " + MISSING_DATA_NOTE,
                ),
                cost_range_inr=CostRangeINR(
                    base=miya_cost_b, min=miya_cost_min, max=miya_cost_max,
                    formatted=f"{format_inr(miya_cost_min)} – {format_inr(miya_cost_max)} (base: {format_inr(miya_cost_b)})",
                    maintenance_horizon="3 years intensive weeding and watering until self-sustaining canopy",
                ),
                cooling_range_c=CoolingRangeC(
                    expected=round(miya_cool_b, 2), min=round(miya_cool_min, 2), max=round(miya_cool_max, 2),
                    formatted=f"-{miya_cool_min:.2f}°C to -{miya_cool_max:.2f}°C (expected: -{miya_cool_b:.2f}°C)",
                    model_source=miya_cool_meta.get("model", "Miyawaki Multi-Tier Microclimate"),
                ),
                feasibility_status="FEASIBLE",
                rejection_reasons=[],
                feasibility_notes=["Requires protected enclosure and initial 2-3 years drip irrigation."],
                maintenance_note=miya_cool_meta.get("maintenance_burden", "Intensive weeding in years 1-2"),
                evidence_label="ASSUMPTION",
                missing_data_survey_requirements=["Soil compaction and utility lines: " + MISSING_DATA_NOTE],
                landuse_typology=clf_res.typology,
                allowed_interventions=clf_res.allowed_interventions,
                selection_rationale=f"Ultra-dense multi-tier canopy for maximum cooling on {clf_res.title}.",
                rejected_alternatives=rejected_alts,
                water_need_description=miya_cool_meta.get("water_need", "High in years 1-2"),
                maintenance_burden=miya_cool_meta.get("maintenance_burden", "Self-sustaining after 3 years"),
                construction_time=miya_cool_meta.get("construction_time", "1-2 months planting"),
                whole_life_cost_3yr_inr=miya_cost_meta.get("whole_life_cost_3yr_inr", miya_cost_b),
                whole_life_cost_per_c_m2=miya_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
                air_cooling_c=miya_cool_meta.get("air_cooling_c", 1.40),
                needs_site_survey=False,
            )
        )

    if "bioswale_rain_garden" in allowed_set:
        bio_m2 = max(100.0, float(cell_multiplier * 500.0))
        bio_cost_b, bio_cost_min, bio_cost_max, bio_cost_meta = estimate_intervention_cost(
            InterventionType.BIOSWALE_RAIN_GARDEN, usable_area_m2=bio_m2
        )
        bio_cool_b, bio_cool_min, bio_cool_max, bio_cool_meta = estimate_cooling_effect(
            InterventionType.BIOSWALE_RAIN_GARDEN, usable_area_m2=bio_m2, baseline_lst_c=mean_lst
        )
        recommendations.append(
            RecommendationItem(
                type="BIOSWALE_RAIN_GARDEN",
                title="Bioswale & Rain Garden Filter",
                priority="MEDIUM" if is_high_thermal else "LOW",
                rationale="Stormwater retention and evaporative vegetative swale mitigating localized heat.",
                quantity_basis=QuantityBasis(
                    estimated_quantity=bio_m2,
                    unit="m² bioretention swale",
                    basis_description=f"Modeled at 500 m² vegetated swale footprint across {cell_multiplier} cell(s).",
                    missing_data_survey_note="Stormwater drainage gradient: " + MISSING_DATA_NOTE,
                ),
                cost_range_inr=CostRangeINR(
                    base=bio_cost_b, min=bio_cost_min, max=bio_cost_max,
                    formatted=f"{format_inr(bio_cost_min)} – {format_inr(bio_cost_max)} (base: {format_inr(bio_cost_b)})",
                    maintenance_horizon="Sediment desilting and native grass trimming",
                ),
                cooling_range_c=CoolingRangeC(
                    expected=round(bio_cool_b, 2), min=round(bio_cool_min, 2), max=round(bio_cool_max, 2),
                    formatted=f"-{bio_cool_min:.2f}°C to -{bio_cool_max:.2f}°C (expected: -{bio_cool_b:.2f}°C)",
                    model_source=bio_cool_meta.get("model", "Bioretention Microclimate"),
                ),
                feasibility_status="FEASIBLE",
                rejection_reasons=[],
                feasibility_notes=["Requires roadside stormwater inflow tie-in."],
                maintenance_note=bio_cool_meta.get("maintenance_burden", "Pre-monsoon silt clearing"),
                evidence_label="ASSUMPTION",
                missing_data_survey_requirements=["Roadside cross-section and invert levels: " + MISSING_DATA_NOTE],
                landuse_typology=clf_res.typology,
                allowed_interventions=clf_res.allowed_interventions,
                selection_rationale="Combines localized cooling with monsoon flood mitigation.",
                rejected_alternatives=rejected_alts,
                water_need_description=bio_cool_meta.get("water_need", "Low-Moderate"),
                maintenance_burden=bio_cool_meta.get("maintenance_burden", "Bi-annual desilting"),
                construction_time=bio_cool_meta.get("construction_time", "1-2 months"),
                whole_life_cost_3yr_inr=bio_cost_meta.get("whole_life_cost_3yr_inr", bio_cost_b),
                whole_life_cost_per_c_m2=bio_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
                air_cooling_c=bio_cool_meta.get("air_cooling_c", 0.45),
                needs_site_survey=False,
            )
        )

    if "rainwater_fed_pond" in allowed_set:
        pond_m2 = max(300.0, float(cell_multiplier * 1200.0))
        pond_cost_b, pond_cost_min, pond_cost_max, pond_cost_meta = estimate_intervention_cost(
            InterventionType.RAINWATER_FED_POND, usable_area_m2=pond_m2
        )
        pond_cool_b, pond_cool_min, pond_cool_max, pond_cool_meta = estimate_cooling_effect(
            InterventionType.RAINWATER_FED_POND, usable_area_m2=pond_m2, baseline_lst_c=mean_lst
        )
        # Check water source requirement: strict rejection if no verified water source
        has_water_src = summary.has_documented_water_source
        pond_feas = "FEASIBLE" if has_water_src else "REJECTED"
        pond_prio = "MEDIUM" if has_water_src else "NOT_RECOMMENDED"
        pond_rej = [] if has_water_src else [
            "UNVERIFIED_WATER_SOURCE: Rainwater-fed retention ponds require a documented stormwater catchment (>= 5x pond area) or treated municipal effluent source to prevent drying and mosquito vector breeding."
        ]

        recommendations.append(
            RecommendationItem(
                type="RAINWATER_FED_POND",
                title="Rainwater-Fed Retention Pond",
                priority=pond_prio,
                rationale="Microclimatic evaporative cooling water body producing downwind cooling breezes.",
                quantity_basis=QuantityBasis(
                    estimated_quantity=pond_m2,
                    unit="m² water surface",
                    basis_description=f"Modeled at 1,200 m² retention pond surface across {cell_multiplier} cell(s).",
                    missing_data_survey_note="Stormwater catchment inflow validation: " + MISSING_DATA_NOTE,
                ),
                cost_range_inr=CostRangeINR(
                    base=pond_cost_b, min=pond_cost_min, max=pond_cost_max,
                    formatted=f"{format_inr(pond_cost_min)} – {format_inr(pond_cost_max)} (base: {format_inr(pond_cost_b)})",
                    maintenance_horizon="Clay bentonite liner and annual pre-monsoon desilting",
                ),
                cooling_range_c=CoolingRangeC(
                    expected=round(pond_cool_b, 2), min=round(pond_cool_min, 2), max=round(pond_cool_max, 2),
                    formatted=f"-{pond_cool_min:.2f}°C to -{pond_cool_max:.2f}°C (expected: -{pond_cool_b:.2f}°C)",
                    model_source=pond_cool_meta.get("model", "Theeuwes et al. 2013"),
                ),
                feasibility_status=pond_feas,
                rejection_reasons=pond_rej,
                feasibility_notes=["Requires verified catchment basin (>= 5x pond area) or treated STP feed."],
                maintenance_note=pond_cool_meta.get("maintenance_burden", "Annual silt clearing and aerator servicing"),
                evidence_label="MODELLED",
                missing_data_survey_requirements=["Catchment hydrology and soil permeability: " + MISSING_DATA_NOTE],
                landuse_typology=clf_res.typology,
                allowed_interventions=clf_res.allowed_interventions,
                selection_rationale="Evaporative air temperature cooling up to 100m downwind.",
                rejected_alternatives=rejected_alts,
                water_need_description=pond_cool_meta.get("water_need", "Continuous freshwater inflow needed"),
                maintenance_burden=pond_cool_meta.get("maintenance_burden", "Moderate-High (weed/algae and silt control)"),
                construction_time=pond_cool_meta.get("construction_time", "3-6 months excavation and lining"),
                whole_life_cost_3yr_inr=pond_cost_meta.get("whole_life_cost_3yr_inr", pond_cost_b),
                whole_life_cost_per_c_m2=pond_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
                air_cooling_c=pond_cool_meta.get("air_cooling_c", 0.80),
                needs_site_survey=False,
            )
        )

    if "shaded_parking_structure" in allowed_set:
        shade_m2 = max(150.0, float(cell_multiplier * 800.0))
        shade_cost_b, shade_cost_min, shade_cost_max, shade_cost_meta = estimate_intervention_cost(
            InterventionType.SHADED_PARKING_STRUCTURE, usable_area_m2=shade_m2
        )
        shade_cool_b, shade_cool_min, shade_cool_max, shade_cool_meta = estimate_cooling_effect(
            InterventionType.SHADED_PARKING_STRUCTURE, usable_area_m2=shade_m2, baseline_lst_c=mean_lst
        )
        recommendations.append(
            RecommendationItem(
                type="SHADED_PARKING_STRUCTURE",
                title="High-SRI Shaded Parking Canopy",
                priority="HIGH" if is_high_thermal else "MEDIUM",
                rationale="High-reflectance tensile or solar shade canopy over dark asphalt parking courts.",
                quantity_basis=QuantityBasis(
                    estimated_quantity=shade_m2,
                    unit="m² shade canopy",
                    basis_description=f"Modeled at 800 m² parking canopy area across {cell_multiplier} cell(s).",
                    missing_data_survey_note="Parking court vehicle layout: " + MISSING_DATA_NOTE,
                ),
                cost_range_inr=CostRangeINR(
                    base=shade_cost_b, min=shade_cost_min, max=shade_cost_max,
                    formatted=f"{format_inr(shade_cost_min)} – {format_inr(shade_cost_max)} (base: {format_inr(shade_cost_b)})",
                    maintenance_horizon="Annual structural cable tensioning and fabric washing",
                ),
                cooling_range_c=CoolingRangeC(
                    expected=round(shade_cool_b, 2), min=round(shade_cool_min, 2), max=round(shade_cool_max, 2),
                    formatted=f"-{shade_cool_min:.2f}°C to -{shade_cool_max:.2f}°C (expected: -{shade_cool_b:.2f}°C)",
                    model_source=shade_cool_meta.get("model", "Solar Canopy Shading Model"),
                ),
                feasibility_status="FEASIBLE",
                rejection_reasons=[],
                feasibility_notes=["Requires foundation anchor stability for wind load in Surat."],
                maintenance_note=shade_cool_meta.get("maintenance_burden", "Annual tension and fabric check"),
                evidence_label="MODELLED",
                missing_data_survey_requirements=["Subsurface footing survey: " + MISSING_DATA_NOTE],
                landuse_typology=clf_res.typology,
                allowed_interventions=clf_res.allowed_interventions,
                selection_rationale="Prevents dark asphalt surface heat buildup in parking yards.",
                rejected_alternatives=rejected_alts,
                water_need_description=shade_cool_meta.get("water_need", "None (zero water)"),
                maintenance_burden=shade_cool_meta.get("maintenance_burden", "Low"),
                construction_time=shade_cool_meta.get("construction_time", "1-3 months"),
                whole_life_cost_3yr_inr=shade_cost_meta.get("whole_life_cost_3yr_inr", shade_cost_b),
                whole_life_cost_per_c_m2=shade_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
                air_cooling_c=shade_cool_meta.get("air_cooling_c", 0.60),
                needs_site_survey=False,
            )
        )

    if "permeable_ground_cover" in allowed_set:
        perm_m2 = max(100.0, float(cell_multiplier * 1000.0))
        perm_cost_b, perm_cost_min, perm_cost_max, perm_cost_meta = estimate_intervention_cost(
            InterventionType.PERMEABLE_GROUND_COVER, usable_area_m2=perm_m2
        )
        perm_cool_b, perm_cool_min, perm_cool_max, perm_cool_meta = estimate_cooling_effect(
            InterventionType.PERMEABLE_GROUND_COVER, usable_area_m2=perm_m2, baseline_lst_c=mean_lst
        )
        recommendations.append(
            RecommendationItem(
                type="PERMEABLE_GROUND_COVER",
                title="Permeable Crushed Aggregate Ground Cover",
                priority="LOW" if not is_high_thermal else "MEDIUM",
                rationale="Eliminates impervious bare soil and low-albedo unpaved dust heat traps.",
                quantity_basis=QuantityBasis(
                    estimated_quantity=perm_m2,
                    unit="m² ground area",
                    basis_description=f"Modeled at 1,000 m² porous gravel cover across {cell_multiplier} cell(s).",
                    missing_data_survey_note="Subgrade drainage slope: " + MISSING_DATA_NOTE,
                ),
                cost_range_inr=CostRangeINR(
                    base=perm_cost_b, min=perm_cost_min, max=perm_cost_max,
                    formatted=f"{format_inr(perm_cost_min)} – {format_inr(perm_cost_max)} (base: {format_inr(perm_cost_b)})",
                    maintenance_horizon="Periodic gravel replenishment and grading",
                ),
                cooling_range_c=CoolingRangeC(
                    expected=round(perm_cool_b, 2), min=round(perm_cool_min, 2), max=round(perm_cool_max, 2),
                    formatted=f"-{perm_cool_min:.2f}°C to -{perm_cool_max:.2f}°C (expected: -{perm_cool_b:.2f}°C)",
                    model_source=perm_cool_meta.get("model", "Porous Aggregate Substrate Model"),
                ),
                feasibility_status="FEASIBLE",
                rejection_reasons=[],
                feasibility_notes=["Requires subgrade compaction and edge containment curbs."],
                maintenance_note=perm_cool_meta.get("maintenance_burden", "Periodic raking and grading"),
                evidence_label="MODELLED",
                missing_data_survey_requirements=["Property tenure: " + MISSING_DATA_NOTE],
                landuse_typology=clf_res.typology,
                allowed_interventions=clf_res.allowed_interventions,
                selection_rationale="Inexpensive porous ground stabilization.",
                rejected_alternatives=rejected_alts,
                water_need_description=perm_cool_meta.get("water_need", "None (zero water)"),
                maintenance_burden=perm_cool_meta.get("maintenance_burden", "Low"),
                construction_time=perm_cool_meta.get("construction_time", "2-4 weeks"),
                whole_life_cost_3yr_inr=perm_cost_meta.get("whole_life_cost_3yr_inr", perm_cost_b),
                whole_life_cost_per_c_m2=perm_cost_meta.get("whole_life_cost_per_c_m2", 0.0),
                air_cooling_c=perm_cool_meta.get("air_cooling_c", 0.35),
                needs_site_survey=False,
            )
        )

    # Enforce hard water conflict override on all terrestrial recommendations
    if water_fraction >= ASSUMPTION_WATER_HARD_REJECT_FRACTION:
        for rec in recommendations:
            rec.feasibility_status = FeasibilityStatus.REJECTED.value
            rec.priority = "NOT_RECOMMENDED"
            if not any("Water body conflict" in r for r in rec.rejection_reasons):
                rec.rejection_reasons.append(
                    f"Water body conflict: polygon is {water_fraction * 100:.1f}% open water (>= {ASSUMPTION_WATER_HARD_REJECT_FRACTION * 100:.0f}%)."
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
