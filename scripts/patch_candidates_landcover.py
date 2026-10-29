"""Patch script for integrating Dynamic World Land Cover across candidates, clustering, and optimization."""

import re
from pathlib import Path

# ---------------------------------------------------------
# 1. Patch gis/interventions/candidates.py
# ---------------------------------------------------------
candidates_path = Path("gis/interventions/candidates.py")
with open(candidates_path, "r", encoding="utf-8") as f:
    cand_code = f.read()

# Add import if missing
if "evaluate_landcover_suitability" not in cand_code:
    cand_code = cand_code.replace(
        "from gis.interventions.feasibility import evaluate_candidate_feasibility, get_survey_prerequisites\n",
        "from gis.interventions.feasibility import evaluate_candidate_feasibility, get_survey_prerequisites\nfrom gis.interventions.landcover_suitability import evaluate_landcover_suitability, LandCoverSuitabilityAssessment\n",
    )

# Add dw_record argument to generate_candidate_for_cell
if "dw_record: dict[str, Any] | None = None" not in cand_code:
    cand_code = cand_code.replace(
        "    has_documented_water_source: bool = False,\n    selection_rationale: str = \"\",\n    rejected_alternatives: list[dict[str, str]] | None = None,\n) -> InterventionCandidate:",
        "    has_documented_water_source: bool = False,\n    selection_rationale: str = \"\",\n    rejected_alternatives: list[dict[str, str]] | None = None,\n    dw_record: dict[str, Any] | None = None,\n) -> InterventionCandidate:",
    )

# In generate_candidate_for_cell, evaluate landcover suitability and attach
old_assign = """    candidate.cooling_metric = "modelled surface (skin) temperature reduction on treated area"
    candidate.cell_scope_note = "Treated area within 100m grid cell footprint; skin surface temperature reduction, not air temperature."
    candidate.price_date_note = "indicative, not a tender price"
    candidate.schedule_alignment_note = "rates not verified against CPWD/SMC schedule"
    candidate.unit_rate = BASE_UNIT_RATES.get(intervention_type, 0.0)
    candidate.unit_rate_unit = BASE_UNIT_STRS.get(intervention_type, "INR per unit")"""

new_assign = """    candidate.cooling_metric = "modelled surface (skin) temperature reduction on treated area"
    candidate.cell_scope_note = "Treated area within 100m grid cell footprint; skin surface temperature reduction, not air temperature."
    candidate.price_date_note = "indicative, not a tender price"
    candidate.schedule_alignment_note = "rates not verified against CPWD/SMC schedule"
    candidate.unit_rate = BASE_UNIT_RATES.get(intervention_type, 0.0)
    candidate.unit_rate_unit = BASE_UNIT_STRS.get(intervention_type, "INR per unit")

    # Dynamic World land-cover integration & scientific disclosures
    if dw_record is not None:
        lc_eval = evaluate_landcover_suitability(dw_record, cell_id=cell_id, baseline_hpi=baseline_hpi or 0.50)
        candidate.landcover_assessment = lc_eval.to_dict()
        candidate.landcover_rule_fired = lc_eval.rule_fired
        candidate.landcover_disclosure = lc_eval.scientific_notice
        candidate.landcover_version = lc_eval.pipeline_version
        candidate.landcover_top_class = lc_eval.dw_top_class
        candidate.landcover_confidence = lc_eval.dw_confidence
        candidate.landcover_entropy = lc_eval.dw_entropy

        # Check if intervention is screened out by satellite land cover
        if intervention_type in lc_eval.screened_out_interventions:
            candidate.feasibility_status = FeasibilityStatus.REJECTED
            candidate.rejection_reason = RejectionReason.INCOMPATIBLE_LANDUSE_TYPOLOGY
            candidate.screening_status = "NOT_APPLICABLE"
            candidate.screening_reason_code = lc_eval.rule_fired
            candidate.selection_rationale = f"Screened out by Dynamic World ({lc_eval.rule_fired}): {lc_eval.screening_reason}"
        elif lc_eval.screening_status == "NEEDS_SITE_SURVEY":
            candidate.needs_site_survey = True

    # Satellite data never resolves field survey prerequisites (mandatory rule)
    candidate.prerequisites_status = "FEASIBLE_SUBJECT_TO_SURVEY" if candidate.feasibility_status == FeasibilityStatus.FEASIBLE else "REJECTED" """

if old_assign in cand_code:
    cand_code = cand_code.replace(old_assign, new_assign)

with open(candidates_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(cand_code)

print("Patched gis/interventions/candidates.py")

