"""Heat Priority Scoring Engine for HEATSENSE AI.

Provides transparent, defensible prioritization of urban thermal risk zones
grounded in observed satellite LST as primary evidence, multi-season persistence,
observation quality context, and supplementary ML uncertainty context.

Scientific Architectural Invariants:
1. OBSERVED LST is PRIMARY THERMAL EVIDENCE (never substituted by model predictions).
2. MODEL PREDICTION is SUPPLEMENTARY MODEL EVIDENCE (for spatial/hypothetical interpolation).
3. SHAP is MODEL INTERPRETATION (not physical causal proof).
4. Component layers (severity, persistence, quality, uncertainty) are preserved separately.
"""

from __future__ import annotations

from gis.heat_priority.lst_priority import compute_lst_severity
from gis.heat_priority.persistence import compute_heat_persistence
from gis.heat_priority.quality import compute_quality_confidence
from gis.heat_priority.scoring import (
    DEFAULT_PERSISTENCE_WEIGHT,
    DEFAULT_SEVERITY_WEIGHT,
    HeatPriorityLayers,
    compute_heat_priority_layers,
    compute_heat_priority_score,
)

__all__ = [
    "compute_lst_severity",
    "compute_heat_persistence",
    "compute_quality_confidence",
    "compute_heat_priority_score",
    "compute_heat_priority_layers",
    "HeatPriorityLayers",
    "DEFAULT_SEVERITY_WEIGHT",
    "DEFAULT_PERSISTENCE_WEIGHT",
]
