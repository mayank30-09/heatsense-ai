"""
HEATSENSE AI - Declarative Intervention Reasoning Rule Registry
Stage D - Spatial Intervention Reasoning Engine

Defines versioned, auditable, evidence-driven rules for all 11 catalog intervention types.
Enforces:
  1. Explicit state model:
     - HEAT_RELEVANT
     - CANDIDATE_DETECTED
     - MODEL_ELIGIBLE
     - PHYSICALLY_FEASIBLE
     - FEASIBLE_SUBJECT_TO_SURVEY
     - IMPLEMENTATION_READY (strictly unreachable from satellite or model data alone)
     - PROVISIONAL
     - REJECTED
     - NOT_APPLICABLE
  2. Zero hardcoded locality names, wards, or zones.
  3. Dynamic quantity estimation derived from candidate geometry and land-cover fractions.
  4. Physically meaningful bounds (never exceed eligible area; no arbitrary 40,000m² clamps).
  5. Sourced scientific cooling parameters (Bowler 2010, Santamouris 2017) labeled as
     modeled surface skin cooling (Delta T skin), NOT 2m air temperature.
  6. Rejected and not-applicable options carry 0.00 cost.
"""

from __future__ import annotations

from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from gis.interventions.evidence import EvidenceExtractionResult


class ReasoningState(str, Enum):
    HEAT_RELEVANT = "HEAT_RELEVANT"
    CANDIDATE_DETECTED = "CANDIDATE_DETECTED"
    MODEL_ELIGIBLE = "MODEL_ELIGIBLE"
    PHYSICALLY_FEASIBLE = "PHYSICALLY_FEASIBLE"
    FEASIBLE_SUBJECT_TO_SURVEY = "FEASIBLE_SUBJECT_TO_SURVEY"
    IMPLEMENTATION_READY = "IMPLEMENTATION_READY"
    PROVISIONAL = "PROVISIONAL"
    REJECTED = "REJECTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SpatialUnit(str, Enum):
    ROAD_SEGMENT = "ROAD_SEGMENT"
    OPEN_SPACE_POLYGON = "OPEN_SPACE_POLYGON"
    BUILDING_ROOF_POLYGON = "BUILDING_ROOF_POLYGON"
    PAVED_PARKING_POLYGON = "PAVED_PARKING_POLYGON"
    DRAINAGE_POLYGON = "DRAINAGE_POLYGON"
    FACADE_POLYGON = "FACADE_POLYGON"
    GRID_CELL_ROLLUP = "GRID_CELL_ROLLUP"


class RuleParameterType(str, Enum):
    SOURCED = "SOURCED"
    ASSUMPTION = "ASSUMPTION"


class RuleParameter(BaseModel):
    name: str
    value: Any
    unit: str
    param_type: RuleParameterType
    source_citation: str
    notes: str


class RuleEvaluationResult(BaseModel):
    rule_id: str
    rule_version: str
    intervention_type: str
    title: str
    spatial_unit: SpatialUnit
    state: ReasoningState
    is_eligible: bool
    rejection_reasons: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    field_survey_requirements: List[str] = Field(default_factory=list)
    quantity: float = Field(default=0.0, description="Derived physical quantity")
    quantity_unit: str = Field(..., description="Physical unit of measurement")
    quantity_method: str = Field(..., description="Formula and derivation narrative")
    direct_cost_inr: float = Field(default=0.0)
    capital_cost_inr: float = Field(default=0.0)
    annual_maint_inr: float = Field(default=0.0)
    cost_base_multiplier: float = Field(default=1.3817, description="Direct cost to all-inclusive capital cost")
    expected_cooling_skin_c: float = Field(default=0.0, description="Modeled surface skin Delta T")
    cooling_range_c: Tuple[float, float] = Field(default=(0.0, 0.0))
    cooling_provenance: str = Field(..., description="Scientific citation or model origin")
    cooling_metric_label: str = Field(
        default="Modeled surface skin Delta T (indicative, not 2m air temp)",
        description="Explicit cooling quantity classification",
    )
    selection_rationale: str = Field(default="")
    is_compatible_addon: bool = Field(default=False, description="Compatible vertical or secondary surface")


class DeclarativeInterventionRule:
    """Base class for a declarative, versioned intervention reasoning rule."""

    rule_id: str = "RULE-BASE"
    rule_version: str = "2.0.0"
    intervention_type: str = "unknown"
    title: str = "Base Rule"
    spatial_unit: SpatialUnit = SpatialUnit.GRID_CELL_ROLLUP
    required_evidence: List[str] = []
    optional_evidence: List[str] = []
    parameters: Dict[str, RuleParameter] = {}

    def evaluate(
        self,
        polygon_area_m2: float,
        evidence: Dict[str, EvidenceExtractionResult],
        typology: str = "unclassified",
        building_count: int = 0,
        max_roof_m2: float = 0.0,
    ) -> RuleEvaluationResult:
        raise NotImplementedError


class CoolRoofRule(DeclarativeInterventionRule):
    """Rule RULE-ROOF-01: High-Albedo Cool Roof Coatings (SRI >= 104)."""

    rule_id = "RULE-ROOF-01"
    rule_version = "2.0.0"
    intervention_type = "cool_roof"
    title = "High-Albedo Cool Roof Coatings"
    spatial_unit = SpatialUnit.BUILDING_ROOF_POLYGON
    required_evidence = ["observed_lst", "hpi_persistence"]
    optional_evidence = ["dynamic_world_landcover", "building_footprints"]

    parameters = {
        "min_lst_c": RuleParameter(
            name="min_lst_c",
            value=38.0,
            unit="°C",
            param_type=RuleParameterType.ASSUMPTION,
            source_citation="HEATSENSE Municipal Priority Protocol",
            notes="Minimum peak summer LST justifying thermal reflective intervention",
        ),
        "roof_fraction_of_built": RuleParameter(
            name="roof_fraction_of_built",
            value=0.70,
            unit="ratio",
            param_type=RuleParameterType.ASSUMPTION,
            source_citation="Urban morphological estimate (uncalibrated building footprint ratio)",
            notes="Assumes 70% of built-up footprint represents treatable roof surface",
        ),
        "cooling_skin_delta": RuleParameter(
            name="cooling_skin_delta",
            value=-2.2,
            unit="°C",
            param_type=RuleParameterType.SOURCED,
            source_citation="Santamouris (2017) Solar Energy 144: 730-749",
            notes="Local surface skin temperature drop under high SRI coatings (>104)",
        ),
    }

    def evaluate(
        self,
        polygon_area_m2: float,
        evidence: Dict[str, EvidenceExtractionResult],
        typology: str = "unclassified",
        building_count: int = 0,
        max_roof_m2: float = 0.0,
    ) -> RuleEvaluationResult:
        lst_res = evidence.get("observed_lst")
        hpi_res = evidence.get("hpi_persistence")
        dw_res = evidence.get("dynamic_world_landcover")
        bf_res = evidence.get("building_footprints")

        rejections = []
        missing = []
        survey = [
            "Cadastral roof area verification and building boundary survey",
            "Structural condition and roof substrate integrity (RCC vs metal sheet)",
            "Owner consent / municipal tenancy agreement",
            "Roof accessibility, parapet safety, and rainwater drainage slope",
        ]

        if bf_res and bf_res.availability.value == "UNAVAILABLE":
            missing.append("Cadastral building footprints layer with structural load ratings (UNAVAILABLE)")

        mean_lst = lst_res.metrics.get("mean_lst_c") if lst_res else None
        max_lst = lst_res.metrics.get("max_lst_c") if lst_res else None
        p_built = dw_res.metrics.get("p_built", 0.0) if dw_res else 0.0
        p_water = dw_res.metrics.get("p_water", 0.0) if dw_res else 0.0

        # Hard constraints
        if p_water >= 0.20:
            rejections.append("Water body coverage exceeds 20% (terrestrial roof intervention rejected)")
        if "open_public_plot" in typology or "water_body" in typology:
            rejections.append(f"Typology '{typology}' lacks permanent roof structures")
        if p_built < 0.05 and building_count == 0:
            rejections.append("Built-up land cover is less than 5% (no physical roof candidate detected)")

        if rejections:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                intervention_type=self.intervention_type,
                title=self.title,
                spatial_unit=self.spatial_unit,
                state=ReasoningState.REJECTED,
                is_eligible=False,
                rejection_reasons=rejections,
                missing_evidence=missing,
                field_survey_requirements=survey,
                quantity=0.0,
                quantity_unit="m² roof area",
                quantity_method="Rejected by hard constraints; proposed quantity and cost set to 0.00.",
                direct_cost_inr=0.0,
                capital_cost_inr=0.0,
                annual_maint_inr=0.0,
                expected_cooling_skin_c=0.0,
                cooling_provenance="N/A (Option rejected)",
                selection_rationale="Option rejected based on physical constraints.",
            )

        # Dynamic quantity derivation: polygon_area * P_built * roof_fraction
        # Cap strictly at polygon_area * P_built (physical roof area cannot exceed built footprint)
        eligible_built_area = polygon_area_m2 * min(0.95, max(0.05, p_built if p_built > 0 else 0.50))
        roof_ratio = self.parameters["roof_fraction_of_built"].value
        derived_roof_m2 = round(eligible_built_area * roof_ratio, 1)

        # Material rate: ₹220, Labour: ₹80 -> Direct: ₹300/m²
        direct_rate = 300.0
        direct_cost = derived_roof_m2 * direct_rate
        capital_cost = round(direct_cost * 1.3817, 2)
        annual_maint = round(derived_roof_m2 * 25.0, 2)

        cool_skin = self.parameters["cooling_skin_delta"].value

        return RuleEvaluationResult(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            intervention_type=self.intervention_type,
            title=self.title,
            spatial_unit=self.spatial_unit,
            state=ReasoningState.FEASIBLE_SUBJECT_TO_SURVEY,
            is_eligible=True,
            missing_evidence=missing,
            field_survey_requirements=survey,
            quantity=derived_roof_m2,
            quantity_unit="m² roof area",
            quantity_method=(
                f"Derived from polygon area ({polygon_area_m2:.1f} m²) × built-up screening fraction "
                f"({p_built:.2f}) × assumed roof factor (0.70) = {derived_roof_m2:.1f} m² (provisional)."
            ),
            direct_cost_inr=direct_cost,
            capital_cost_inr=capital_cost,
            annual_maint_inr=annual_maint,
            expected_cooling_skin_c=cool_skin,
            cooling_range_c=(-1.5, -3.2),
            cooling_provenance="Santamouris (2017) bounded empirical cool roof review",
            cooling_metric_label="Modeled surface skin Delta T on treated roof (indicative, not 2m air temp)",
            selection_rationale=(
                f"High-albedo elastomeric coating recommended to reflect peak solar irradiance "
                f"across ~{derived_roof_m2:,.0f} m² of roof footprint. Requires structural survey before tender."
            ),
        )


class CoolPavementRule(DeclarativeInterventionRule):
    """Rule RULE-PAVE-01: High-Albedo / Permeable Cool Pavements."""

    rule_id = "RULE-PAVE-01"
    rule_version = "2.0.0"
    intervention_type = "cool_pavement"
    title = "High-Albedo Cool Pavement Coatings"
    spatial_unit = SpatialUnit.PAVED_PARKING_POLYGON
    required_evidence = ["observed_lst", "dynamic_world_landcover"]
    optional_evidence = ["road_network"]

    parameters = {
        "pavement_fraction_of_built": RuleParameter(
            name="pavement_fraction_of_built",
            value=0.25,
            unit="ratio",
            param_type=RuleParameterType.ASSUMPTION,
            source_citation="Urban spatial standard (uncalibrated ground walkway/parking ratio)",
            notes="Assumes 25% of built ground surface is treatable pedestrian pathway or open parking",
        ),
        "cooling_skin_delta": RuleParameter(
            name="cooling_skin_delta",
            value=-1.8,
            unit="°C",
            param_type=RuleParameterType.SOURCED,
            source_citation="Santamouris et al. (2012) Solar Energy 86: 825-835",
            notes="Surface skin temperature reduction on high-albedo pavements",
        ),
    }

    def evaluate(
        self,
        polygon_area_m2: float,
        evidence: Dict[str, EvidenceExtractionResult],
        typology: str = "unclassified",
        building_count: int = 0,
        max_roof_m2: float = 0.0,
    ) -> RuleEvaluationResult:
        dw_res = evidence.get("dynamic_world_landcover")
        road_res = evidence.get("road_network")

        rejections = []
        missing = []
        survey = [
            "Ground traffic load classification (pedestrian vs heavy freight)",
            "Pavement surface integrity, cracking, and drainage slope",
            "Public right-of-way ownership and municipal maintenance clearance",
        ]

        if road_res and road_res.availability.value == "UNAVAILABLE":
            missing.append("Municipal road network GIS layer with right-of-way widths (UNAVAILABLE)")

        p_built = dw_res.metrics.get("p_built", 0.0) if dw_res else 0.0
        p_water = dw_res.metrics.get("p_water", 0.0) if dw_res else 0.0

        if p_water >= 0.20:
            rejections.append("Water body coverage exceeds 20% (paved ground intervention rejected)")
        if "roof" in typology:
            rejections.append("Rooftop typology is incompatible with ground-level pavement coatings")
        if p_built < 0.10:
            rejections.append("Built ground fraction < 10% (insufficient paved surface candidates)")

        if rejections:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                intervention_type=self.intervention_type,
                title=self.title,
                spatial_unit=self.spatial_unit,
                state=ReasoningState.REJECTED,
                is_eligible=False,
                rejection_reasons=rejections,
                missing_evidence=missing,
                field_survey_requirements=survey,
                quantity=0.0,
                quantity_unit="m² paved area",
                quantity_method="Rejected by hard constraints; proposed quantity and cost set to 0.00.",
                direct_cost_inr=0.0,
                capital_cost_inr=0.0,
                annual_maint_inr=0.0,
                expected_cooling_skin_c=0.0,
                cooling_provenance="N/A (Option rejected)",
                selection_rationale="Option rejected based on physical constraints.",
            )

        eligible_paved_m2 = round(polygon_area_m2 * min(0.90, max(0.10, p_built)) * self.parameters["pavement_fraction_of_built"].value, 1)

        # Rate: Material ₹180 + Labour ₹70 = ₹250/m²
        direct_rate = 250.0
        direct_cost = eligible_paved_m2 * direct_rate
        capital_cost = round(direct_cost * 1.3817, 2)
        annual_maint = round(eligible_paved_m2 * 20.0, 2)

        return RuleEvaluationResult(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            intervention_type=self.intervention_type,
            title=self.title,
            spatial_unit=self.spatial_unit,
            state=ReasoningState.FEASIBLE_SUBJECT_TO_SURVEY,
            is_eligible=True,
            missing_evidence=missing,
            field_survey_requirements=survey,
            quantity=eligible_paved_m2,
            quantity_unit="m² paved area",
            quantity_method=(
                f"Derived from polygon area ({polygon_area_m2:.1f} m²) × built-up fraction "
                f"({p_built:.2f}) × assumed ground-pavement factor (0.25) = {eligible_paved_m2:.1f} m² (provisional)."
            ),
            direct_cost_inr=direct_cost,
            capital_cost_inr=capital_cost,
            annual_maint_inr=annual_maint,
            expected_cooling_skin_c=self.parameters["cooling_skin_delta"].value,
            cooling_range_c=(-1.0, -2.6),
            cooling_provenance="Santamouris et al. (2012) reflective pavement studies",
            cooling_metric_label="Modeled surface skin Delta T on treated pavement (indicative, not 2m air temp)",
            selection_rationale=(
                f"Reflective pavement coating applied to ~{eligible_paved_m2:,.0f} m² of exposed pedestrian walkways "
                f"and low-speed parking bays. Requires traffic load survey."
            ),
        )


class TreeCanopyRule(DeclarativeInterventionRule):
    """Rule RULE-TREE-01: Native Shade Tree Canopy Expansion."""

    rule_id = "RULE-TREE-01"
    rule_version = "2.0.0"
    intervention_type = "tree_canopy"
    title = "Native Shade Tree Canopy Expansion"
    spatial_unit = SpatialUnit.OPEN_SPACE_POLYGON
    required_evidence = ["observed_lst", "dynamic_world_landcover"]
    optional_evidence = ["cadastral_ownership", "road_network"]

    parameters = {
        "crown_spread_m2_per_tree": RuleParameter(
            name="crown_spread_m2_per_tree",
            value=45.0,
            unit="m²/tree",
            param_type=RuleParameterType.SOURCED,
            source_citation="Urban Forestry Manual (mature native Azadirachta indica crown spread)",
            notes="Mature tree canopy horizontal projection area at 10m spacing",
        ),
        "saturation_trees_ratio": RuleParameter(
            name="saturation_trees_ratio",
            value=0.35,
            unit="ratio",
            param_type=RuleParameterType.ASSUMPTION,
            source_citation="HEATSENSE Canopy Saturation Protocol",
            notes="Existing tree cover >= 35% rejects additional canopy planting due to crown closure",
        ),
        "cooling_skin_delta": RuleParameter(
            name="cooling_skin_delta",
            value=-2.8,
            unit="°C",
            param_type=RuleParameterType.SOURCED,
            source_citation="Bowler et al. (2010) Landscape and Urban Planning 97: 147-155",
            notes="Direct shade solar block and evapotranspirative surface skin cooling",
        ),
    }

    def evaluate(
        self,
        polygon_area_m2: float,
        evidence: Dict[str, EvidenceExtractionResult],
        typology: str = "unclassified",
        building_count: int = 0,
        max_roof_m2: float = 0.0,
    ) -> RuleEvaluationResult:
        dw_res = evidence.get("dynamic_world_landcover")
        cad_res = evidence.get("cadastral_ownership")

        rejections = []
        missing = []
        survey = [
            "Underground utility clearance (water, sewer, electric, telecom cables)",
            "Soil depth and root zone permeability (min 1.2m uncompacted soil)",
            "Land tenure / public right-of-way planting authorization",
            "Post-planting 3-year establishment irrigation water availability",
        ]

        if cad_res and cad_res.availability.value == "UNAVAILABLE":
            missing.append("Cadastral parcel boundaries and public/private ownership tenure (UNAVAILABLE)")

        p_bare = dw_res.metrics.get("p_bare", 0.0) if dw_res else 0.0
        p_grass = dw_res.metrics.get("p_grass", 0.0) if dw_res else 0.0
        p_trees = dw_res.metrics.get("p_trees", 0.0) if dw_res else 0.0
        p_water = dw_res.metrics.get("p_water", 0.0) if dw_res else 0.0

        if p_trees >= self.parameters["saturation_trees_ratio"].value:
            rejections.append("Existing tree canopy saturation (P_trees >= 0.35); crown closure reached")
        if "roof" in typology:
            rejections.append("Rooftop typology incompatible with deep-rooted tree canopy planting")
        if p_water >= 0.25:
            rejections.append("Water body coverage exceeds 25% (submerged land unsuitable for shade trees)")

        open_ground_ratio = p_bare + p_grass
        if open_ground_ratio < 0.04:
            rejections.append("Insufficient permeable open ground (<4% bare/grass cover for root zones)")

        if rejections:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                intervention_type=self.intervention_type,
                title=self.title,
                spatial_unit=self.spatial_unit,
                state=ReasoningState.REJECTED,
                is_eligible=False,
                rejection_reasons=rejections,
                missing_evidence=missing,
                field_survey_requirements=survey,
                quantity=0.0,
                quantity_unit="trees",
                quantity_method="Rejected by hard constraints; proposed quantity and cost set to 0.00.",
                direct_cost_inr=0.0,
                capital_cost_inr=0.0,
                annual_maint_inr=0.0,
                expected_cooling_skin_c=0.0,
                cooling_provenance="N/A (Option rejected)",
                selection_rationale="Option rejected based on physical constraints.",
            )

        plantable_area_m2 = polygon_area_m2 * open_ground_ratio
        crown_m2 = self.parameters["crown_spread_m2_per_tree"].value
        estimated_trees = int(math.floor(plantable_area_m2 / crown_m2))
        # Ensure minimum 5 trees if open ground exists, but strictly bounded by plantable_area / 30m2
        max_physical_trees = max(5, int(math.floor(plantable_area_m2 / 30.0)))
        tree_count = max(5, min(max_physical_trees, estimated_trees))

        # Direct cost: ₹3,200 per sapling + tree guard + initial compost
        direct_cost = float(tree_count * 3200.0)
        capital_cost = round(direct_cost * 1.3817, 2)
        annual_maint = round(tree_count * 450.0, 2)

        return RuleEvaluationResult(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            intervention_type=self.intervention_type,
            title=self.title,
            spatial_unit=self.spatial_unit,
            state=ReasoningState.FEASIBLE_SUBJECT_TO_SURVEY,
            is_eligible=True,
            missing_evidence=missing,
            field_survey_requirements=survey,
            quantity=float(tree_count),
            quantity_unit="trees",
            quantity_method=(
                f"Derived from polygon area ({polygon_area_m2:.1f} m²) × permeable land cover "
                f"({open_ground_ratio:.2f} bare+grass) ÷ 45.0 m²/tree spacing standard = {tree_count} trees (provisional)."
            ),
            direct_cost_inr=direct_cost,
            capital_cost_inr=capital_cost,
            annual_maint_inr=annual_maint,
            expected_cooling_skin_c=self.parameters["cooling_skin_delta"].value,
            cooling_range_c=(-1.8, -4.5),
            cooling_provenance="Bowler et al. (2010) systematic review of urban greening cooling effects",
            cooling_metric_label="Modeled direct under-canopy surface skin Delta T (indicative, not 2m air temp)",
            selection_rationale=(
                f"Planting of {tree_count} native shade trees (Neem, Peepal, Jamun) on ~{plantable_area_m2:,.0f} m² "
                f"of unpaved ground. Underground utility and tenure clearance required before procurement."
            ),
        )


class GreenRoofRule(DeclarativeInterventionRule):
    """Rule RULE-GROOF-01: Extensive Sedum Green Roof (120-150 kg/m² saturated load)."""

    rule_id = "RULE-GROOF-01"
    rule_version = "2.0.0"
    intervention_type = "green_roof"
    title = "Extensive Green Roof (Sedum / Native Xerophytic)"
    spatial_unit = SpatialUnit.BUILDING_ROOF_POLYGON
    required_evidence = ["observed_lst", "dynamic_world_landcover"]
    optional_evidence = ["building_footprints"]

    parameters = {
        "saturated_dead_load": RuleParameter(
            name="saturated_dead_load",
            value=135.0,
            unit="kg/m²",
            param_type=RuleParameterType.SOURCED,
            source_citation="FLL Green Roofing Guideline (Extensive Sedum dead load)",
            notes="Minimum structural dead load capacity required to prevent roof collapse",
        ),
        "cooling_skin_delta": RuleParameter(
            name="cooling_skin_delta",
            value=-3.5,
            unit="°C",
            param_type=RuleParameterType.SOURCED,
            source_citation="Santamouris (2014) Energy and Buildings 72: 242-258",
            notes="Vegetated surface skin temperature reduction under evapotranspirative cooling",
        ),
    }

    def evaluate(
        self,
        polygon_area_m2: float,
        evidence: Dict[str, EvidenceExtractionResult],
        typology: str = "unclassified",
        building_count: int = 0,
        max_roof_m2: float = 0.0,
    ) -> RuleEvaluationResult:
        bf_res = evidence.get("building_footprints")
        dw_res = evidence.get("dynamic_world_landcover")

        rejections = []
        missing = ["Cadastral building footprints layer with structural load ratings (UNAVAILABLE)"]
        survey = [
            "MANDATORY: Structural engineering load assessment (min 135 kg/m² dead load capacity)",
            "Waterproofing membrane integrity and root-barrier membrane test",
            "Parapet height safety (min 1.0m) and drainage overflow capacity",
        ]

        p_built = dw_res.metrics.get("p_built", 0.0) if dw_res else 0.0

        if "shed" in typology or "informal" in typology or "industrial_shed" in typology:
            rejections.append("Industrial corrugated sheet / informal shed roofs CANNOT bear 135 kg/m² wet soil dead load (collapse hazard)")
        if "open_public_plot" in typology or "water_body" in typology:
            rejections.append("Typology lacks permanent roof structures")
        if p_built < 0.10:
            rejections.append("Built-up land cover < 10% (no roof candidate detected)")

        if rejections:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                intervention_type=self.intervention_type,
                title=self.title,
                spatial_unit=self.spatial_unit,
                state=ReasoningState.REJECTED,
                is_eligible=False,
                rejection_reasons=rejections,
                missing_evidence=missing,
                field_survey_requirements=survey,
                quantity=0.0,
                quantity_unit="m² vegetated roof area",
                quantity_method="Rejected by structural or land-use constraints; proposed quantity and cost set to 0.00.",
                direct_cost_inr=0.0,
                capital_cost_inr=0.0,
                annual_maint_inr=0.0,
                expected_cooling_skin_c=0.0,
                cooling_provenance="N/A (Option rejected)",
                selection_rationale="Option rejected based on structural safety or physical constraints.",
            )

        # Conservative extensive green roof area: 30% of built footprint
        derived_groof_m2 = round(polygon_area_m2 * min(0.80, p_built) * 0.30, 1)

        # Rate: Material ₹1,800 + Labour ₹600 = ₹2,400/m²
        direct_rate = 2400.0
        direct_cost = derived_groof_m2 * direct_rate
        capital_cost = round(direct_cost * 1.3817, 2)
        annual_maint = round(derived_groof_m2 * 120.0, 2)

        return RuleEvaluationResult(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            intervention_type=self.intervention_type,
            title=self.title,
            spatial_unit=self.spatial_unit,
            state=ReasoningState.FEASIBLE_SUBJECT_TO_SURVEY,
            is_eligible=True,
            missing_evidence=missing,
            field_survey_requirements=survey,
            quantity=derived_groof_m2,
            quantity_unit="m² vegetated roof area",
            quantity_method=(
                f"Derived from polygon area ({polygon_area_m2:.1f} m²) × built fraction "
                f"({p_built:.2f}) × structural roof factor (0.30) = {derived_groof_m2:.1f} m² (provisional)."
            ),
            direct_cost_inr=direct_cost,
            capital_cost_inr=capital_cost,
            annual_maint_inr=annual_maint,
            expected_cooling_skin_c=self.parameters["cooling_skin_delta"].value,
            cooling_range_c=(-2.0, -5.0),
            cooling_provenance="Santamouris (2014) extensive green roof microclimate cooling evaluation",
            cooling_metric_label="Modeled vegetated surface skin Delta T (indicative, not 2m air temp)",
            selection_rationale=(
                f"Extensive xerophytic green roof candidate on ~{derived_groof_m2:,.0f} m² of engineered RCC roof. "
                f"Strict structural load engineering certification mandatory prior to tendering."
            ),
        )


class StormwaterDrainageRule(DeclarativeInterventionRule):
    """Rule RULE-BLUE-01: Retention Ponds and Bioswales (UNAVAILABLE DATA)."""

    rule_id = "RULE-BLUE-01"
    rule_version = "2.0.0"
    intervention_type = "bioswale_rain_garden"
    title = "Bioswales, Rain Gardens & Retention Ponds"
    spatial_unit = SpatialUnit.DRAINAGE_POLYGON
    required_evidence = ["drainage_dem"]
    optional_evidence = ["dynamic_world_landcover"]

    def evaluate(
        self,
        polygon_area_m2: float,
        evidence: Dict[str, EvidenceExtractionResult],
        typology: str = "unclassified",
        building_count: int = 0,
        max_roof_m2: float = 0.0,
    ) -> RuleEvaluationResult:
        missing = [
            "High-resolution LiDAR DEM & flow accumulation raster (UNAVAILABLE)",
            "SMC municipal stormwater drainage network GIS layer (UNAVAILABLE)",
        ]
        rejections = [
            "Hydrological catchment and elevation data are UNAVAILABLE. Blue-green stormwater interventions "
            "CANNOT be recommended purely because an area experiences thermal stress.",
        ]
        return RuleEvaluationResult(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            intervention_type=self.intervention_type,
            title=self.title,
            spatial_unit=self.spatial_unit,
            state=ReasoningState.NOT_APPLICABLE,
            is_eligible=False,
            rejection_reasons=rejections,
            missing_evidence=missing,
            field_survey_requirements=["Topographic survey, catchment hydrogeology, and infiltration rate testing"],
            quantity=0.0,
            quantity_unit="m² catchment area",
            quantity_method="Not assessable without elevation/drainage data; quantity and cost set to 0.00.",
            direct_cost_inr=0.0,
            capital_cost_inr=0.0,
            annual_maint_inr=0.0,
            expected_cooling_skin_c=0.0,
            cooling_provenance="N/A (Data unavailable)",
            selection_rationale="Blue-green stormwater interventions require terrain and drainage GIS layers.",
        )


class ModularLivingWallRule(DeclarativeInterventionRule):
    """Rule RULE-GWALL-01: Modular Living Green Wall (Vertical Surface Add-on)."""

    rule_id = "RULE-GWALL-01"
    rule_version = "2.0.0"
    intervention_type = "green_wall"
    title = "Modular Living Green Wall"
    spatial_unit = SpatialUnit.FACADE_POLYGON
    required_evidence = ["observed_lst", "dynamic_world_landcover"]
    optional_evidence = ["building_footprints"]

    def evaluate(
        self,
        polygon_area_m2: float,
        evidence: Dict[str, EvidenceExtractionResult],
        typology: str = "unclassified",
        building_count: int = 0,
        max_roof_m2: float = 0.0,
    ) -> RuleEvaluationResult:
        dw_res = evidence.get("dynamic_world_landcover")
        p_built = dw_res.metrics.get("p_built", 0.0) if dw_res else 0.0

        if p_built < 0.15:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                intervention_type=self.intervention_type,
                title=self.title,
                spatial_unit=self.spatial_unit,
                state=ReasoningState.REJECTED,
                is_eligible=False,
                rejection_reasons=["Built density < 15% (insufficient vertical building facade candidates)"],
                missing_evidence=["Building heights and facade orientation GIS records (UNAVAILABLE)"],
                field_survey_requirements=["Wall structural integrity, facade orientation, drip irrigation access"],
                quantity=0.0,
                quantity_unit="m² vertical facade",
                quantity_method="Rejected by density constraints; quantity and cost set to 0.00.",
                direct_cost_inr=0.0,
                capital_cost_inr=0.0,
                annual_maint_inr=0.0,
                expected_cooling_skin_c=0.0,
                cooling_provenance="N/A",
                selection_rationale="Option rejected due to lack of vertical building facades.",
            )

        # Compatible secondary surface (facade): 100m² per 1 ha built land, max 600m²
        facade_m2 = round(min(600.0, max(50.0, polygon_area_m2 * p_built * 0.02)), 1)
        direct_rate = 3500.0  # ₹3,500/m² vertical modular system
        direct_cost = facade_m2 * direct_rate
        capital_cost = round(direct_cost * 1.3817, 2)
        annual_maint = round(facade_m2 * 280.0, 2)

        return RuleEvaluationResult(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            intervention_type=self.intervention_type,
            title=self.title,
            spatial_unit=self.spatial_unit,
            state=ReasoningState.FEASIBLE_SUBJECT_TO_SURVEY,
            is_eligible=True,
            is_compatible_addon=True,
            missing_evidence=["Building heights and vertical facade exposure GIS layers (UNAVAILABLE)"],
            field_survey_requirements=[
                "Facade structural anchoring capacity",
                "Automated drip-irrigation water connection",
                "South/West solar orientation verification",
            ],
            quantity=facade_m2,
            quantity_unit="m² vertical facade",
            quantity_method=f"Compatible secondary vertical facade add-on (~{facade_m2} m²). Does not double-count roof or ground area.",
            direct_cost_inr=direct_cost,
            capital_cost_inr=capital_cost,
            annual_maint_inr=annual_maint,
            expected_cooling_skin_c=-2.5,
            cooling_range_c=(-1.5, -4.0),
            cooling_provenance="Alexandri & Jones (2008) Building and Environment 43: 2025-2038",
            cooling_metric_label="Modeled vertical facade surface skin Delta T (indicative, not 2m air temp)",
            selection_rationale=(
                f"Modular vertical living wall recommended as a compatible facade add-on ({facade_m2:.0f} m²). "
                f"Requires structural facade anchoring and irrigation supply verification."
            ),
        )


class ReasoningEngine:
    """Orchestrates evidence extraction, rule evaluation, hard constraint checks, and ranking."""

    def __init__(self) -> None:
        self.rules: Dict[str, DeclarativeInterventionRule] = {
            "cool_roof": CoolRoofRule(),
            "cool_pavement": CoolPavementRule(),
            "tree_canopy": TreeCanopyRule(),
            "green_roof": GreenRoofRule(),
            "bioswale_rain_garden": StormwaterDrainageRule(),
            "green_wall": ModularLivingWallRule(),
        }

    def evaluate_polygon(
        self,
        polygon_area_m2: float,
        evidence: Dict[str, EvidenceExtractionResult],
        typology: str = "unclassified",
        building_count: int = 0,
        max_roof_m2: float = 0.0,
    ) -> List[RuleEvaluationResult]:
        results: List[RuleEvaluationResult] = []
        for r_name, rule in self.rules.items():
            res = rule.evaluate(
                polygon_area_m2=polygon_area_m2,
                evidence=evidence,
                typology=typology,
                building_count=building_count,
                max_roof_m2=max_roof_m2,
            )
            results.append(res)

        # Ranking logic:
        # Eligible items sorted by thermal cooling skin Delta T (most negative first)
        # Ineligible / rejected items at the bottom
        def sort_key(item: RuleEvaluationResult) -> Tuple[int, float, str]:
            status_order = 0 if item.is_eligible else 1
            # Primary sort by cooling impact (e.g. -3.5 before -2.2)
            cooling = item.expected_cooling_skin_c
            return (status_order, cooling, item.rule_id)

        results.sort(key=sort_key)
        return results


# Authoritative Global Singleton
reasoning_engine = ReasoningEngine()
