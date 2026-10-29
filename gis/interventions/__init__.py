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
    PUBLIC_PARK_NATIVE_TREES = "public_park_native_trees"
    DENSE_MIYAWAKI_PLANTATION = "dense_miyawaki_plantation"
    BIOSWALE_RAIN_GARDEN = "bioswale_rain_garden"
    RAINWATER_FED_POND = "rainwater_fed_pond"
    SHADED_PARKING_STRUCTURE = "shaded_parking_structure"
    GREEN_WALL = "green_wall"
    PERMEABLE_GROUND_COVER = "permeable_ground_cover"


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
    STRUCTURAL_LOAD_COLLAPSE_RISK = "STRUCTURAL_LOAD_COLLAPSE_RISK"
    NO_ROOF_STRUCTURE_ON_OPEN_LAND = "NO_ROOF_STRUCTURE_ON_OPEN_LAND"
    UNVERIFIED_WATER_SOURCE_FOR_POND = "UNVERIFIED_WATER_SOURCE_FOR_POND"
    INCOMPATIBLE_LANDUSE_TYPOLOGY = "INCOMPATIBLE_LANDUSE_TYPOLOGY"
    SITE_SURVEY_REQUIRED = "SITE_SURVEY_REQUIRED"


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
    air_cooling_c: float = 0.0
    evidence_status: str = "CALIBRATED_EMPIRICAL_MICROCLIMATE"
    geometry: dict[str, Any] = field(default_factory=dict)
    landuse_typology: str = "unclassified"
    needs_site_survey: bool = False
    selection_rationale: str = ""
    rejected_alternatives: list[dict[str, str]] = field(default_factory=list)
    water_need_description: str = ""
    maintenance_burden: str = ""
    construction_time: str = ""
    prerequisites_status: str = "FEASIBLE_SUBJECT_TO_SURVEY"
    survey_prerequisites: list[str] = field(default_factory=list)
    screening_status: str = "MODEL_ELIGIBLE"
    screening_reason_code: str = "NONE"
    site_suitability: str = "UNKNOWN - survey required"
    ownership_legal: str = "UNVERIFIED"
    engineering_clearance: str = "NOT ASSESSED"
    procurement_status: str = "NOT STARTED"
    benefit_evidence: str = "MODELLED"
    data_confidence: str = "MEDIUM"
    cooling_metric: str = "modelled surface (skin) temperature reduction on treated area"
    cell_scope_note: str = "Treated area within 100m grid cell footprint; skin surface temperature reduction, not air temperature."
    price_date_note: str = "indicative, not a tender price"
    schedule_alignment_note: str = "rates not verified against CPWD/SMC schedule"
    unit_rate: float = 0.0
    unit_rate_unit: str = ""
    markups_description: str = "Includes 18% GST, 12% contingency, 6% design & supervision, and scaled site setup"
    landcover_assessment: dict[str, Any] | None = None
    landcover_rule_fired: str = "NONE"
    landcover_disclosure: str = "ASSUMPTION: UNCALIBRATED_HEURISTIC"
    landcover_version: str = "v1.0"
    landcover_top_class: str | None = None
    landcover_confidence: float | None = None
    landcover_entropy: float | None = None

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
            "screening_status": self.screening_status,
            "screening_reason_code": self.screening_reason_code,
            "site_suitability": self.site_suitability,
            "ownership_legal": self.ownership_legal,
            "engineering_clearance": self.engineering_clearance,
            "procurement_status": self.procurement_status,
            "benefit_evidence": self.benefit_evidence,
            "data_confidence": self.data_confidence,
            "cooling_metric": self.cooling_metric,
            "cell_scope_note": self.cell_scope_note,
            "price_date_note": self.price_date_note,
            "schedule_alignment_note": self.schedule_alignment_note,
            "unit_rate": round(self.unit_rate, 2),
            "unit_rate_unit": self.unit_rate_unit,
            "markups_description": self.markups_description,
            "cost_inr": round(self.cost_inr, 2),
            "cost_inr_range": [round(self.cost_inr_min, 2), round(self.cost_inr_max, 2)],
            "expected_cooling_c": round(self.expected_cooling_c, 2),
            "expected_cooling_c_range": [round(self.expected_cooling_c_min, 2), round(self.expected_cooling_c_max, 2)],
            "air_cooling_c": round(self.air_cooling_c, 2),
            "evidence_status": self.evidence_status,
            "geometry": self.geometry,
            "landuse_typology": self.landuse_typology,
            "needs_site_survey": self.needs_site_survey,
            "selection_rationale": self.selection_rationale,
            "rejected_alternatives": self.rejected_alternatives,
            "water_need_description": self.water_need_description,
            "maintenance_burden": self.maintenance_burden,
            "construction_time": self.construction_time,
            "prerequisites_status": self.prerequisites_status,
            "survey_prerequisites": self.survey_prerequisites,
            "landcover_assessment": self.landcover_assessment,
            "landcover_rule_fired": self.landcover_rule_fired,
            "landcover_disclosure": self.landcover_disclosure,
            "landcover_version": self.landcover_version,
            "landcover_top_class": self.landcover_top_class,
            "landcover_confidence": self.landcover_confidence,
            "landcover_entropy": self.landcover_entropy,
        }


@dataclass
class Package:
    package_id: str
    cluster_id: str
    locality: str
    intervention_type: InterventionType
    cell_ids: list[str]
    cell_count: int
    cells: list[dict[str, Any]]
    geographic_coverage_ha: float
    treated_footprint_m2: float
    estimated_cost_inr: float          # Capex
    capex_breakdown: dict[str, float]
    opex_3yr_inr: float                # Separate 3-year opex
    expected_cooling_c: float          # Local skin cooling on treated footprint
    delta_t_skin_c: float              # <= 0
    delta_t_cell_c: float              # <= 0 (cell-diluted)
    thermal_benefit_k_m2: float        # Conserved extensive benefit |delta_t_cell_c| * A_cell
    indicative_diluted_cooling_c: float
    chronic_hotspot_cells_count: int
    mean_hpi: float
    max_hpi: float
    landcover_summary: dict[str, Any]
    confidence_rating: str
    unresolved_prerequisites: list[str]
    feasibility_status: str = "FEASIBLE_SUBJECT_TO_SURVEY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "cluster_id": self.cluster_id,
            "locality": self.locality,
            "intervention_type": self.intervention_type.value if hasattr(self.intervention_type, "value") else str(self.intervention_type),
            "cell_ids": self.cell_ids,
            "cell_count": self.cell_count,
            "cells": self.cells,
            "geographic_coverage_ha": round(self.geographic_coverage_ha, 2),
            "treated_footprint_m2": round(self.treated_footprint_m2, 1),
            "estimated_cost_inr": round(self.estimated_cost_inr, 2),
            "capex_breakdown": self.capex_breakdown,
            "opex_3yr_inr": round(self.opex_3yr_inr, 2),
            "expected_cooling_c": round(self.expected_cooling_c, 3),
            "delta_t_skin_c": round(self.delta_t_skin_c, 3),
            "delta_t_cell_c": round(self.delta_t_cell_c, 3),
            "thermal_benefit_k_m2": round(self.thermal_benefit_k_m2, 2),
            "indicative_diluted_cooling_c": round(self.indicative_diluted_cooling_c, 3),
            "chronic_hotspot_cells_count": self.chronic_hotspot_cells_count,
            "mean_hpi": round(self.mean_hpi, 2),
            "max_hpi": round(self.max_hpi, 2),
            "landcover_summary": self.landcover_summary,
            "confidence_rating": self.confidence_rating,
            "unresolved_prerequisites": self.unresolved_prerequisites,
            "feasibility_status": self.feasibility_status,
        }
