"""HEATSENSE AI — Stage D Intervention Candidate Types and Models.

Defines schemas and constants for urban heat mitigation candidates:
- Tree Canopy Planting
- Cool Roof Coating
- Extensive Green Roofs
- Cool Permeable Pavement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InterventionType(str, Enum):
    TREE_CANOPY = "tree_canopy"
    COOL_ROOF = "cool_roof"
    GREEN_ROOF = "green_roof"
    COOL_PAVEMENT = "cool_pavement"


class FeasibilityStatus(str, Enum):
    FEASIBLE = "FEASIBLE"
    REJECTED = "REJECTED"


class RejectionReason(str, Enum):
    NONE = "NONE"
    OUTSIDE_STUDY_BOUNDARY = "OUTSIDE_STUDY_BOUNDARY"
    INSUFFICIENT_USABLE_AREA = "INSUFFICIENT_USABLE_AREA"
    WATER_BODY_CONFLICT = "WATER_BODY_CONFLICT"
    INSUFFICIENT_THERMAL_PRIORITY = "INSUFFICIENT_THERMAL_PRIORITY"
    LOW_BUILT_DENSITY_FOR_ROOF = "LOW_BUILT_DENSITY_FOR_ROOF"
    HIGH_VEGETATION_CONFLICT_FOR_ROOF = "HIGH_VEGETATION_CONFLICT_FOR_ROOF"
    MISSING_HPI_EVIDENCE = "MISSING_HPI_EVIDENCE"


@dataclass
class InterventionCandidate:
    candidate_id: str
    cell_id: str
    row: int
    col: int
    longitude: float
    latitude: float
    intervention_type: InterventionType
    usable_area_m2: float
    tree_count: int
    baseline_hpi: float
    baseline_lst_c: float
    is_chronic_hotspot: bool
    administrative_zone: str
    feasibility_status: FeasibilityStatus = FeasibilityStatus.FEASIBLE
    rejection_reason: RejectionReason = RejectionReason.NONE
    cost_inr: float = 0.0
    cost_inr_min: float = 0.0
    cost_inr_max: float = 0.0
    expected_cooling_c: float = 0.0
    expected_cooling_c_min: float = 0.0
    expected_cooling_c_max: float = 0.0
    evidence_status: str = "CALIBRATED_EMPIRICAL_MICROCLIMATE"
    geometry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "cell_id": self.cell_id,
            "row": self.row,
            "col": self.col,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "intervention_type": self.intervention_type.value,
            "usable_area_m2": round(self.usable_area_m2, 2),
            "tree_count": self.tree_count,
            "baseline_hpi": round(self.baseline_hpi, 4) if self.baseline_hpi is not None else None,
            "baseline_lst_c": round(self.baseline_lst_c, 2) if self.baseline_lst_c is not None else None,
            "is_chronic_hotspot": self.is_chronic_hotspot,
            "administrative_zone": self.administrative_zone,
            "feasibility_status": self.feasibility_status.value,
            "rejection_reason": self.rejection_reason.value,
            "cost_inr": round(self.cost_inr, 2),
            "cost_inr_range": [round(self.cost_inr_min, 2), round(self.cost_inr_max, 2)],
            "expected_cooling_c": round(self.expected_cooling_c, 2),
            "expected_cooling_c_range": [round(self.expected_cooling_c_min, 2), round(self.expected_cooling_c_max, 2)],
            "evidence_status": self.evidence_status,
            "geometry": self.geometry,
        }
