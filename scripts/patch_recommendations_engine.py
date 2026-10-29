"""
Patch script for gis/interventions/recommendations.py
Integrates EvidenceRegistry and ReasoningEngine, eliminates fixed caps (40,000m², 800 trees, 20,000m²),
sets proposed cost and quantity to 0 for rejected/not-applicable options, and populates the 7 required sections.
"""

import re

file_path = "gis/interventions/recommendations.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add imports if not present
if "from gis.interventions.evidence import" not in content:
    import_target = "from gis.interventions.landuse import LanduseClassifier"
    import_replacement = """from gis.interventions.landuse import LanduseClassifier
from gis.interventions.evidence import (
    evidence_registry,
    compute_evidence_cache_key,
    EvidenceAvailability,
    EvidenceExtractionResult,
)
from gis.interventions.rules import (
    reasoning_engine,
    ReasoningState,
    SpatialUnit,
    RuleEvaluationResult,
)"""
    content = content.replace(import_target, import_replacement, 1)

# 2. Add additive fields to RecommendationItem
if "rule_id: str =" not in content:
    rec_target = '    markups_description: str = Field(\n        default="Includes 18% GST, 12% contingency, 6% design & supervision, and scaled site setup",\n        description="Cost markup items included in total cost"\n    )'
    rec_replacement = """    markups_description: str = Field(
        default="Includes 18% GST, 12% contingency, 6% design & supervision, and scaled site setup",
        description="Cost markup items included in total cost"
    )
    rule_id: str = Field(default="RULE-ROOF-01", description="Authoritative rule identifier")
    rule_version: str = Field(default="2.0.0", description="Rule configuration version")
    spatial_unit: str = Field(default="BUILDING_ROOF_POLYGON", description="Physical spatial unit")
    reasoning_state: str = Field(default="FEASIBLE_SUBJECT_TO_SURVEY", description="Explicit reasoning engine state")
    is_compatible_addon: bool = Field(default=False, description="Whether this is a compatible secondary surface add-on")
    direct_cost_inr: float = Field(default=0.0, description="Direct material + labour cost in INR")
    capital_cost_inr: float = Field(default=0.0, description="All-inclusive capital cost in INR (Cost Base)")
    cost_base_multiplier: float = Field(default=1.3817, description="Direct to capital cost multiplier")
    quantity_derivation_method: str = Field(default="", description="Derivation formula narrative")
    missing_evidence: List[str] = Field(default_factory=list, description="Explicitly missing evidence layers")
    screening_caveats: List[str] = Field(default_factory=list, description="Screening caveats and limitations")"""
    content = content.replace(rec_target, rec_replacement, 1)

# 3. Add additive fields to RecommendationsResponse
if "quantity_cost_rollup: Dict[str, Any]" not in content:
    resp_target = """class RecommendationsResponse(BaseModel):
    polygon_summary: PolygonSummary
    recommendations: List[RecommendationItem]
    caveats: List[str]
    assumptions_applied: List[str]
    evidence_label: str = "MODELLED\""""

    resp_replacement = """class RecommendationsResponse(BaseModel):
    polygon_summary: PolygonSummary
    recommendations: List[RecommendationItem]
    caveats: List[str]
    assumptions_applied: List[str]
    evidence_label: str = "MODELLED"
    heat_conditions: Dict[str, Any] = Field(default_factory=dict, description="Section 1: Observed and modeled thermal conditions")
    physical_features: Dict[str, Any] = Field(default_factory=dict, description="Section 2: Physical features and opportunities")
    candidate_sites: List[Dict[str, Any]] = Field(default_factory=list, description="Section 3: Candidate sites with spatial geometry")
    quantity_cost_rollup: Dict[str, Any] = Field(default_factory=dict, description="Section 4: Portfolio quantity and cost roll-up")
    evidence_gaps: List[str] = Field(default_factory=list, description="Section 5: Missing datasets and required field checks")
    rejected_candidates: List[Dict[str, Any]] = Field(default_factory=list, description="Section 6: Excluded candidates with failed rule IDs")
    evidence_availability_panel: List[Dict[str, Any]] = Field(default_factory=list, description="Section 7: Evidence layers availability status")
    cache_key: Optional[str] = Field(default=None, description="Deterministic spatial-temporal-rule cache key")"""
    content = content.replace(resp_target, resp_replacement, 1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCH_PART1_APPLIED")
