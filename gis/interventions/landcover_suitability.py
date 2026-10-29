"""Dynamic World Land-Cover Suitability and Evidence Engine for Stage D Interventions.

Attribution & Scientific Governance:
- Google Dynamic World V1 (10m Near Real-Time Global LULC)
  Brown et al. (2022) Sci Data 9, 251. https://doi.org/10.1038/s41597-022-01307-4
  License: CC BY 4.0

Governance Rules:
1. Dynamic World outputs are deep learning model predictions on Sentinel-2 reflectance,
   NOT empirical ground truth.
2. Satellite data cannot establish ownership, tenancy, structural capacity of roofs,
   or presence of underground utilities.
3. Every heuristic suitability rule is explicitly labeled:
   "ASSUMPTION: UNCALIBRATED_HEURISTIC"
4. Candidates screened through satellite land cover remain:
   "FEASIBLE_SUBJECT_TO_SURVEY"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import sqlalchemy as sa
from sqlalchemy.orm import Session

from gis.interventions import FeasibilityStatus, InterventionType, RejectionReason


# Configurable suitability thresholds (ASSUMPTION: UNCALIBRATED_HEURISTIC)
THRESHOLD_BUILT_HIGH: float = 0.40
THRESHOLD_VEG_OPEN: float = 0.35
THRESHOLD_BUILT_LOW: float = 0.30
THRESHOLD_TREES_CANOPY: float = 0.40
THRESHOLD_CROPS_CONFLICT: float = 0.40
THRESHOLD_WATER_PRESERVATION: float = 0.30
THRESHOLD_CONFIDENCE_MIN: float = 0.40
THRESHOLD_MIN_OBSERVATIONS: int = 3
THRESHOLD_ENTROPY_MAX: float = 0.85
THRESHOLD_MARGIN_MIN: float = 0.10

HEURISTIC_DISCLOSURE_LABEL: str = "ASSUMPTION: UNCALIBRATED_HEURISTIC"
PHYSICAL_SURVEY_PREREQUISITE_LABEL: str = "FEASIBLE_SUBJECT_TO_SURVEY"


class LandCoverRule(str, Enum):
    RULE_DW_BUILT_DENSE = "RULE_DW_BUILT_DENSE"
    RULE_DW_OPEN_GROUND = "RULE_DW_OPEN_GROUND"
    RULE_DW_CANOPY_PRESERVATION = "RULE_DW_CANOPY_PRESERVATION"
    RULE_DW_AGRICULTURAL_CONFLICT = "RULE_DW_AGRICULTURAL_CONFLICT"
    RULE_DW_AQUATIC_PRESERVATION = "RULE_DW_AQUATIC_PRESERVATION"
    RULE_DW_LOW_CONFIDENCE = "RULE_DW_LOW_CONFIDENCE"
    RULE_DW_INSUFFICIENT_OBSERVATIONS = "RULE_DW_INSUFFICIENT_OBSERVATIONS"
    RULE_DW_AMBIGUOUS_SPECTRUM = "RULE_DW_AMBIGUOUS_SPECTRUM"
    RULE_DW_UNCLASSIFIED = "RULE_DW_UNCLASSIFIED"


@dataclass
class LandCoverSuitabilityAssessment:
    cell_id: str
    rule_fired: str
    suitable_interventions: list[InterventionType]
    screened_out_interventions: list[InterventionType]
    screening_status: str  # "MODEL_ELIGIBLE", "NOT_APPLICABLE", "NEEDS_SITE_SURVEY"
    screening_reason: str
    feasibility_prerequisite: str  # Always "FEASIBLE_SUBJECT_TO_SURVEY"
    scientific_notice: str
    data_confidence: str  # "HIGH", "MEDIUM", "LOW"
    dw_confidence: float | None
    dw_entropy: float | None
    dw_top_class: str | None
    dw_observation_count: int
    thresholds_applied: dict[str, float]
    observed_values: dict[str, Any]
    source_dataset: str
    pipeline_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "rule_fired": self.rule_fired,
            "suitable_interventions": [i.value for i in self.suitable_interventions],
            "screened_out_interventions": [i.value for i in self.screened_out_interventions],
            "screening_status": self.screening_status,
            "screening_reason": self.screening_reason,
            "feasibility_prerequisite": self.feasibility_prerequisite,
            "scientific_notice": self.scientific_notice,
            "data_confidence": self.data_confidence,
            "dw_confidence": self.dw_confidence,
            "dw_entropy": self.dw_entropy,
            "dw_top_class": self.dw_top_class,
            "dw_observation_count": self.dw_observation_count,
            "thresholds_applied": self.thresholds_applied,
            "observed_values": self.observed_values,
            "source_dataset": self.source_dataset,
            "pipeline_version": self.pipeline_version,
        }


def fetch_cell_landcover(
    cell_id: str,
    season: str = "summer",
    year: int = 2024,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """
    Fetch seasonal Dynamic World record for a cell from the database.
    """
    from backend.app.db.models.stage_d import StageDDynamicWorldLandCover

    close_session = False
    if db is None:
        from backend.app.db.session import SessionLocal
        db = SessionLocal()
        close_session = True

    try:
        row = (
            db.query(StageDDynamicWorldLandCover)
            .filter(
                StageDDynamicWorldLandCover.cell_id == cell_id,
                StageDDynamicWorldLandCover.season == season,
                StageDDynamicWorldLandCover.year == year,
            )
            .first()
        )
        if not row:
            return None

        return {
            "cell_id": row.cell_id,
            "season": row.season,
            "year": row.year,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "mean_water": row.mean_water,
            "mean_trees": row.mean_trees,
            "mean_grass": row.mean_grass,
            "mean_flooded_vegetation": row.mean_flooded_vegetation,
            "mean_crops": row.mean_crops,
            "mean_shrub_and_scrub": row.mean_shrub_and_scrub,
            "mean_built": row.mean_built,
            "mean_bare": row.mean_bare,
            "mean_snow_and_ice": row.mean_snow_and_ice,
            "prop_water": row.prop_water,
            "prop_trees": row.prop_trees,
            "prop_grass": row.prop_grass,
            "prop_flooded_vegetation": row.prop_flooded_vegetation,
            "prop_crops": row.prop_crops,
            "prop_shrub_and_scrub": row.prop_shrub_and_scrub,
            "prop_built": row.prop_built,
            "prop_bare": row.prop_bare,
            "prop_snow_and_ice": row.prop_snow_and_ice,
            "valid_observation_count": row.valid_observation_count,
            "top_class": row.top_class,
            "confidence": row.confidence,
            "margin": row.margin,
            "entropy": row.entropy,
            "status": row.status,
            "source_dataset": row.source_dataset,
            "class_schema": row.class_schema,
            "pipeline_version": row.pipeline_version,
            "run_id": row.run_id,
        }
    finally:
        if close_session:
            db.close()


def evaluate_landcover_suitability(
    dw_record: dict[str, Any] | None,
    cell_id: str,
    baseline_hpi: float = 0.50,
) -> LandCoverSuitabilityAssessment:
    """
    Evaluate land-cover suitability for Stage D intervention types using Dynamic World observations.
    All evaluations enforce uncalibrated heuristic labeling and mandatory field survey prerequisites.
    """
    thresholds = {
        "built_high": THRESHOLD_BUILT_HIGH,
        "veg_open": THRESHOLD_VEG_OPEN,
        "built_low": THRESHOLD_BUILT_LOW,
        "trees_canopy": THRESHOLD_TREES_CANOPY,
        "crops_conflict": THRESHOLD_CROPS_CONFLICT,
        "water_preservation": THRESHOLD_WATER_PRESERVATION,
        "confidence_min": THRESHOLD_CONFIDENCE_MIN,
        "min_observations": THRESHOLD_MIN_OBSERVATIONS,
    }

    # Case 1: Missing or insufficient observations
    if dw_record is None or dw_record.get("valid_observation_count", 0) < THRESHOLD_MIN_OBSERVATIONS:
        obs_cnt = dw_record.get("valid_observation_count", 0) if dw_record else 0
        return LandCoverSuitabilityAssessment(
            cell_id=cell_id,
            rule_fired=LandCoverRule.RULE_DW_INSUFFICIENT_OBSERVATIONS.value,
            suitable_interventions=[],
            screened_out_interventions=list(InterventionType),
            screening_status="NEEDS_SITE_SURVEY",
            screening_reason=f"Insufficient satellite observations (count={obs_cnt} < {THRESHOLD_MIN_OBSERVATIONS}). Cannot verify ground surface without site inspection.",
            feasibility_prerequisite=PHYSICAL_SURVEY_PREREQUISITE_LABEL,
            scientific_notice=f"{HEURISTIC_DISCLOSURE_LABEL} - Missing or cloud-masked satellite observation; mandatory ground verification required.",
            data_confidence="LOW",
            dw_confidence=dw_record.get("confidence") if dw_record else None,
            dw_entropy=dw_record.get("entropy") if dw_record else None,
            dw_top_class=dw_record.get("top_class") if dw_record else None,
            dw_observation_count=obs_cnt,
            thresholds_applied=thresholds,
            observed_values=dw_record or {},
            source_dataset=dw_record.get("source_dataset", "DATA_UNAVAILABLE") if dw_record else "DATA_UNAVAILABLE",
            pipeline_version=dw_record.get("pipeline_version", "none") if dw_record else "none",
        )

    p_built = dw_record.get("mean_built") or 0.0
    p_bare = dw_record.get("mean_bare") or 0.0
    p_grass = dw_record.get("mean_grass") or 0.0
    p_trees = dw_record.get("mean_trees") or 0.0
    p_crops = dw_record.get("mean_crops") or 0.0
    p_water = dw_record.get("mean_water") or 0.0
    p_flooded = dw_record.get("mean_flooded_vegetation") or 0.0
    p_shrub = dw_record.get("mean_shrub_and_scrub") or 0.0
    conf = dw_record.get("confidence") or 0.0
    entropy = dw_record.get("entropy") or 0.0
    top_cls = dw_record.get("top_class") or "unclassified"
    obs_cnt = dw_record.get("valid_observation_count", 0)

    observed_summary = {
        "built": p_built,
        "bare": p_bare,
        "grass": p_grass,
        "trees": p_trees,
        "crops": p_crops,
        "water": p_water,
        "flooded": p_flooded,
        "shrub": p_shrub,
        "top_class": top_cls,
        "confidence": conf,
        "entropy": entropy,
        "observations": obs_cnt,
    }

    # Case 2: Water / wetland preservation priority
    if (p_water + p_flooded) >= THRESHOLD_WATER_PRESERVATION:
        return LandCoverSuitabilityAssessment(
            cell_id=cell_id,
            rule_fired=LandCoverRule.RULE_DW_AQUATIC_PRESERVATION.value,
            suitable_interventions=[InterventionType.RAINWATER_FED_POND, InterventionType.BIOSWALE_RAIN_GARDEN],
            screened_out_interventions=[
                InterventionType.COOL_ROOF,
                InterventionType.GREEN_ROOF,
                InterventionType.COOL_PAVEMENT,
                InterventionType.SHADED_PARKING_STRUCTURE,
            ],
            screening_status="MODEL_ELIGIBLE",
            screening_reason=f"Surface dominated by water or wetland ({round((p_water+p_flooded)*100, 1)}% >= {int(THRESHOLD_WATER_PRESERVATION*100)}%). Wetland buffer preservation applies.",
            feasibility_prerequisite=PHYSICAL_SURVEY_PREREQUISITE_LABEL,
            scientific_notice=f"{HEURISTIC_DISCLOSURE_LABEL} - Satellite-detected surface water requires seasonal hydrological and drainage survey.",
            data_confidence="HIGH" if conf >= 0.50 else "MEDIUM",
            dw_confidence=conf,
            dw_entropy=entropy,
            dw_top_class=top_cls,
            dw_observation_count=obs_cnt,
            thresholds_applied=thresholds,
            observed_values=observed_summary,
            source_dataset=dw_record.get("source_dataset", "GOOGLE/DYNAMICWORLD/V1"),
            pipeline_version=dw_record.get("pipeline_version", "v1.0"),
        )

    # Case 3: Agricultural conflict (crops >= 40%)
    if p_crops >= THRESHOLD_CROPS_CONFLICT:
        return LandCoverSuitabilityAssessment(
            cell_id=cell_id,
            rule_fired=LandCoverRule.RULE_DW_AGRICULTURAL_CONFLICT.value,
            suitable_interventions=[],
            screened_out_interventions=[
                InterventionType.COOL_ROOF,
                InterventionType.GREEN_ROOF,
                InterventionType.COOL_PAVEMENT,
                InterventionType.SHADED_PARKING_STRUCTURE,
            ],
            screening_status="NEEDS_SITE_SURVEY",
            screening_reason=f"High agricultural crop probability ({round(p_crops*100, 1)}% >= {int(THRESHOLD_CROPS_CONFLICT*100)}%). Potential farmland conflict; verify municipal zoning and land tenure.",
            feasibility_prerequisite=PHYSICAL_SURVEY_PREREQUISITE_LABEL,
            scientific_notice=f"{HEURISTIC_DISCLOSURE_LABEL} - Agricultural crop probability may represent private farming. Legal boundary and zoning survey required before intervention planning.",
            data_confidence="MEDIUM",
            dw_confidence=conf,
            dw_entropy=entropy,
            dw_top_class=top_cls,
            dw_observation_count=obs_cnt,
            thresholds_applied=thresholds,
            observed_values=observed_summary,
            source_dataset=dw_record.get("source_dataset", "GOOGLE/DYNAMICWORLD/V1"),
            pipeline_version=dw_record.get("pipeline_version", "v1.0"),
        )

    # Case 4: Existing dense tree canopy (trees >= 40%)
    if p_trees >= THRESHOLD_TREES_CANOPY:
        return LandCoverSuitabilityAssessment(
            cell_id=cell_id,
            rule_fired=LandCoverRule.RULE_DW_CANOPY_PRESERVATION.value,
            suitable_interventions=[InterventionType.PUBLIC_PARK_NATIVE_TREES],
            screened_out_interventions=[
                InterventionType.COOL_ROOF,
                InterventionType.COOL_PAVEMENT,
            ],
            screening_status="MODEL_ELIGIBLE",
            screening_reason=f"Existing tree canopy coverage ({round(p_trees*100, 1)}% >= {int(THRESHOLD_TREES_CANOPY*100)}%). Canopy preservation and health monitoring recommended over new hard surface interventions.",
            feasibility_prerequisite=PHYSICAL_SURVEY_PREREQUISITE_LABEL,
            scientific_notice=f"{HEURISTIC_DISCLOSURE_LABEL} - Existing vegetation detected by satellite. Pruning, species diversity, and soil moisture assessment required.",
            data_confidence="HIGH" if conf >= 0.50 else "MEDIUM",
            dw_confidence=conf,
            dw_entropy=entropy,
            dw_top_class=top_cls,
            dw_observation_count=obs_cnt,
            thresholds_applied=thresholds,
            observed_values=observed_summary,
            source_dataset=dw_record.get("source_dataset", "GOOGLE/DYNAMICWORLD/V1"),
            pipeline_version=dw_record.get("pipeline_version", "v1.0"),
        )

    # Case 5: Built-dominant surface (built >= 40%)
    if p_built >= THRESHOLD_BUILT_HIGH:
        return LandCoverSuitabilityAssessment(
            cell_id=cell_id,
            rule_fired=LandCoverRule.RULE_DW_BUILT_DENSE.value,
            suitable_interventions=[
                InterventionType.COOL_ROOF,
                InterventionType.GREEN_ROOF,
                InterventionType.COOL_PAVEMENT,
                InterventionType.SHADED_PARKING_STRUCTURE,
                InterventionType.GREEN_WALL,
            ],
            screened_out_interventions=[
                InterventionType.DENSE_MIYAWAKI_PLANTATION,
                InterventionType.RAINWATER_FED_POND,
            ],
            screening_status="MODEL_ELIGIBLE",
            screening_reason=f"Built-up surface probability ({round(p_built*100, 1)}% >= {int(THRESHOLD_BUILT_HIGH*100)}%). Highly suitable for rooftop coating and cool pavements.",
            feasibility_prerequisite=PHYSICAL_SURVEY_PREREQUISITE_LABEL,
            scientific_notice=f"{HEURISTIC_DISCLOSURE_LABEL} - Satellite detects built fabric. Structural load capacity, roof waterproofing, and ownership require physical survey.",
            data_confidence="HIGH" if conf >= 0.50 else "MEDIUM",
            dw_confidence=conf,
            dw_entropy=entropy,
            dw_top_class=top_cls,
            dw_observation_count=obs_cnt,
            thresholds_applied=thresholds,
            observed_values=observed_summary,
            source_dataset=dw_record.get("source_dataset", "GOOGLE/DYNAMICWORLD/V1"),
            pipeline_version=dw_record.get("pipeline_version", "v1.0"),
        )

    # Case 6: Open ground / vegetation / bare land (bare + grass + shrub >= 35% AND built < 30%)
    open_prob = p_bare + p_grass + p_shrub
    if open_prob >= THRESHOLD_VEG_OPEN and p_built < THRESHOLD_BUILT_LOW:
        return LandCoverSuitabilityAssessment(
            cell_id=cell_id,
            rule_fired=LandCoverRule.RULE_DW_OPEN_GROUND.value,
            suitable_interventions=[
                InterventionType.TREE_CANOPY,
                InterventionType.PUBLIC_PARK_NATIVE_TREES,
                InterventionType.DENSE_MIYAWAKI_PLANTATION,
                InterventionType.BIOSWALE_RAIN_GARDEN,
                InterventionType.PERMEABLE_GROUND_COVER,
            ],
            screened_out_interventions=[
                InterventionType.COOL_ROOF,
                InterventionType.GREEN_ROOF,
            ],
            screening_status="MODEL_ELIGIBLE",
            screening_reason=f"Open ground probability ({round(open_prob*100, 1)}% >= {int(THRESHOLD_VEG_OPEN*100)}%, built={round(p_built*100, 1)}% < {int(THRESHOLD_BUILT_LOW*100)}%). Highly suitable for urban forestry and ground permeability.",
            feasibility_prerequisite=PHYSICAL_SURVEY_PREREQUISITE_LABEL,
            scientific_notice=f"{HEURISTIC_DISCLOSURE_LABEL} - Satellite detects open soil/grass. Soil depth, underground utilities, and water access require physical survey.",
            data_confidence="HIGH" if conf >= 0.45 else "MEDIUM",
            dw_confidence=conf,
            dw_entropy=entropy,
            dw_top_class=top_cls,
            dw_observation_count=obs_cnt,
            thresholds_applied=thresholds,
            observed_values=observed_summary,
            source_dataset=dw_record.get("source_dataset", "GOOGLE/DYNAMICWORLD/V1"),
            pipeline_version=dw_record.get("pipeline_version", "v1.0"),
        )

    # Case 7: High ambiguity / mixed surface / low confidence
    return LandCoverSuitabilityAssessment(
        cell_id=cell_id,
        rule_fired=LandCoverRule.RULE_DW_LOW_CONFIDENCE.value,
        suitable_interventions=[
            InterventionType.TREE_CANOPY,
            InterventionType.COOL_ROOF,
            InterventionType.COOL_PAVEMENT,
        ],
        screened_out_interventions=[],
        screening_status="NEEDS_SITE_SURVEY",
        screening_reason=f"Mixed heterogeneous land cover (top={top_cls}, built={round(p_built*100, 1)}%, open={round(open_prob*100, 1)}%, entropy={round(entropy, 2)}). Detailed on-ground site survey required.",
        feasibility_prerequisite=PHYSICAL_SURVEY_PREREQUISITE_LABEL,
        scientific_notice=f"{HEURISTIC_DISCLOSURE_LABEL} - Satellite classification ambiguity is elevated (entropy={round(entropy, 2)}). On-site land-use verification recommended.",
        data_confidence="MEDIUM" if conf >= 0.40 else "LOW",
        dw_confidence=conf,
        dw_entropy=entropy,
        dw_top_class=top_cls,
        dw_observation_count=obs_cnt,
        thresholds_applied=thresholds,
        observed_values=observed_summary,
        source_dataset=dw_record.get("source_dataset", "GOOGLE/DYNAMICWORLD/V1"),
        pipeline_version=dw_record.get("pipeline_version", "v1.0"),
    )

