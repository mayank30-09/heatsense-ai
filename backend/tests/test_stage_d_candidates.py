"""Unit and Scientific Tests for Stage D Candidate Generation, Costs, and Cooling Effects.

Verifies:
1. Candidate creation for all 4 intervention types with stable identifiers and geometry.
2. Evidence-backed INR cost calculation and non-negative components.
3. Calibrated empirical microclimate cooling (rejection of SHAP-as-multiplier fallacy).
4. Sub-additive combined cooling and physical saturation caps.
5. Hard feasibility constraints and structured rejection logging.
"""

from __future__ import annotations

import pytest

from gis.interventions import (
    FeasibilityStatus,
    InterventionType,
    RejectionReason,
)
from gis.interventions.candidates import (
    generate_candidate_for_cell,
    generate_intervention_candidates,
)
from gis.interventions.cooling_effects import (
    compute_combined_cooling,
    estimate_cooling_effect,
)
from gis.interventions.costs import estimate_intervention_cost
from gis.interventions.feasibility import evaluate_candidate_feasibility


def test_candidate_generation_all_types():
    """Verify that candidates can be generated with valid costs, cooling, and geometries."""
    types = [
        InterventionType.TREE_CANOPY,
        InterventionType.COOL_ROOF,
        InterventionType.GREEN_ROOF,
        InterventionType.COOL_PAVEMENT,
    ]

    for itype in types:
        cand = generate_candidate_for_cell(
            row=150,
            col=160,
            cell_id="R150_C160",
            intervention_type=itype,
            baseline_hpi=0.72,
            baseline_lst_c=42.5,
            is_chronic_hotspot=True,
            administrative_zone="Central Zone",
            ndvi=0.20,
            ndbi=0.15,
            ndwi=-0.25,
            usable_area_m2=1800.0,
            tree_count=50,
            is_inside_smc=True,
        )

        assert cand.candidate_id.startswith(f"CAND_{itype.value.upper()}_")
        assert cand.feasibility_status == FeasibilityStatus.FEASIBLE
        assert cand.rejection_reason == RejectionReason.NONE
        assert cand.cost_inr > 0.0
        assert cand.cost_inr_min < cand.cost_inr < cand.cost_inr_max
        assert 0.0 < cand.expected_cooling_c <= 3.5
        assert cand.geometry["type"] == "Polygon"


def test_scientific_cooling_models_and_fallacy_prevention():
    """Verify cooling estimates obey physical saturation and do not scale linearly to infinity."""
    # Tree canopy with 10 trees vs 100 trees
    cool_10, _, _, meta10 = estimate_cooling_effect(InterventionType.TREE_CANOPY, usable_area_m2=1000, tree_count=10)
    cool_100, _, _, meta100 = estimate_cooling_effect(InterventionType.TREE_CANOPY, usable_area_m2=1000, tree_count=100)

    assert cool_10 > 0.0
    assert cool_100 > cool_10
    # Must saturate below physical maximum (3.5°C), never unbounded linear scaling
    assert cool_100 <= 3.50
    assert "SHAP" not in meta100["model"]
    assert "Bowler" in meta100["model"]

    # Cool roof treated area
    cool_roof, _, _, meta_roof = estimate_cooling_effect(InterventionType.COOL_ROOF, usable_area_m2=5000)
    assert cool_roof <= 2.50
    assert "Santamouris" in meta_roof["model"]


def test_combined_cooling_sub_additivity():
    """Verify multiple overlapping interventions attenuate and never exceed saturation ceiling 4.5°C."""
    single = [2.0]
    double = [2.0, 1.5]
    triple = [2.0, 1.5, 1.2]
    extreme = [3.5, 2.5, 2.0]

    comb_single = compute_combined_cooling(single)
    comb_double = compute_combined_cooling(double)
    comb_triple = compute_combined_cooling(triple)
    comb_extreme = compute_combined_cooling(extreme)

    assert comb_double < 2.0 + 1.5, "Combined cooling must be sub-additive."
    assert comb_triple < 2.0 + 1.5 + 1.2
    assert comb_extreme <= 4.50, "Combined cooling must not exceed 4.5°C physical ceiling."


def test_cost_models_positive_and_detailed():
    """Verify INR cost models produce positive values and structured breakdowns."""
    cost, c_min, c_max, meta = estimate_intervention_cost(InterventionType.TREE_CANOPY, usable_area_m2=1000, tree_count=40)
    # Itemized realistic engineering cost: materials, labour, design (6%), GST (18%), contingency (12%), setup, tanker
    assert cost == 115254.98
    assert c_min == 92203.98  # -20%
    assert c_max == 138305.98  # +20%
    assert "maintenance_3yr_cost" in meta
    assert meta["maintenance_3yr_cost"] == 60000.0


def test_hard_feasibility_boundary_and_water_rejection():
    """Verify hard feasibility constraints reject invalid candidates with structured reasons."""
    # 1. Outside SMC boundary
    cand_outside = generate_candidate_for_cell(
        row=10, col=10, cell_id="R010_C010",
        intervention_type=InterventionType.TREE_CANOPY,
        baseline_hpi=0.8, baseline_lst_c=40.0, is_chronic_hotspot=False,
        administrative_zone="Outside", is_inside_smc=False,
    )
    assert cand_outside.feasibility_status == FeasibilityStatus.REJECTED
    assert cand_outside.rejection_reason == RejectionReason.OUTSIDE_STUDY_BOUNDARY

    # 2. Water body conflict (NDWI > 0.05)
    cand_water = generate_candidate_for_cell(
        row=100, col=100, cell_id="R100_C100",
        intervention_type=InterventionType.COOL_PAVEMENT,
        baseline_hpi=0.8, baseline_lst_c=40.0, is_chronic_hotspot=False,
        administrative_zone="Central Zone", ndwi=0.25, is_inside_smc=True,
    )
    assert cand_water.feasibility_status == FeasibilityStatus.REJECTED
    assert cand_water.rejection_reason == RejectionReason.WATER_BODY_CONFLICT

    # 3. Insufficient usable area (< 100 m²)
    cand_tiny = generate_candidate_for_cell(
        row=120, col=120, cell_id="R120_C120",
        intervention_type=InterventionType.COOL_ROOF,
        baseline_hpi=0.8, baseline_lst_c=40.0, is_chronic_hotspot=False,
        administrative_zone="Central Zone", usable_area_m2=50.0, is_inside_smc=True,
    )
    assert cand_tiny.feasibility_status == FeasibilityStatus.REJECTED
    assert cand_tiny.rejection_reason == RejectionReason.INSUFFICIENT_USABLE_AREA
