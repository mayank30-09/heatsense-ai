"""Heat Priority Scoring Engine for HEATSENSE AI.

Provides transparent, defensible prioritization of urban thermal risk zones
grounded in observed satellite LST as primary evidence, multi-season persistence,
vegetation canopy deficits, built-up density, and calibrated confidence context.

Scientific Architectural Invariants:
1. OBSERVED LST is PRIMARY THERMAL EVIDENCE (never substituted by model predictions).
2. MODEL PREDICTION is SUPPLEMENTARY MODEL EVIDENCE (for spatial/hypothetical interpolation).
3. SHAP is MODEL INTERPRETATION (not physical causal proof).
4. Component layers (severity, persistence, deficit, density, confidence) are preserved separately.
"""

from __future__ import annotations

from gis.heat_priority.lst_priority import (
    DEFAULT_NDBI_MAX,
    DEFAULT_NDBI_MIN,
    DEFAULT_NDVI_MIN,
    DEFAULT_NDVI_TARGET,
    DEFAULT_T_MAX,
    DEFAULT_T_MIN,
    compute_builtup_density,
    compute_lst_severity,
    compute_vegetation_deficit,
    normalize_lst_severity,
)
from gis.heat_priority.persistence import (
    classify_chronic_hotspots,
    compute_heat_persistence,
)
from gis.heat_priority.quality import (
    classify_confidence_tier,
    compute_calibrated_confidence_index,
    compute_obs_multiplier,
    compute_qa_multiplier,
    compute_quality_confidence,
    compute_season_multiplier,
)
from gis.heat_priority.scoring import (
    DEFAULT_PERSISTENCE_WEIGHT,
    DEFAULT_SEVERITY_WEIGHT,
    DEFAULT_WEIGHT_BUILTUP,
    DEFAULT_WEIGHT_PERSISTENCE,
    DEFAULT_WEIGHT_THERMAL,
    DEFAULT_WEIGHT_VEGETATION,
    HeatPriorityLayers,
    compute_heat_priority_composite,
    compute_heat_priority_layers,
    compute_heat_priority_score,
)

__all__ = [
    "normalize_lst_severity",
    "compute_vegetation_deficit",
    "compute_builtup_density",
    "compute_lst_severity",
    "compute_heat_persistence",
    "classify_chronic_hotspots",
    "compute_calibrated_confidence_index",
    "classify_confidence_tier",
    "compute_obs_multiplier",
    "compute_qa_multiplier",
    "compute_season_multiplier",
    "compute_quality_confidence",
    "compute_heat_priority_composite",
    "compute_heat_priority_layers",
    "compute_heat_priority_score",
    "HeatPriorityLayers",
    "DEFAULT_WEIGHT_THERMAL",
    "DEFAULT_WEIGHT_PERSISTENCE",
    "DEFAULT_WEIGHT_VEGETATION",
    "DEFAULT_WEIGHT_BUILTUP",
    "DEFAULT_SEVERITY_WEIGHT",
    "DEFAULT_PERSISTENCE_WEIGHT",
    "DEFAULT_T_MIN",
    "DEFAULT_T_MAX",
    "DEFAULT_NDVI_MIN",
    "DEFAULT_NDVI_TARGET",
    "DEFAULT_NDBI_MIN",
    "DEFAULT_NDBI_MAX",
]
