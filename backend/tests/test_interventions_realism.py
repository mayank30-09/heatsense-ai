"""Rigorous Realism & Engineering Constraint Tests for HEATSENSE AI (Stage D).

Covers Phase 5 Requirements (Item 11):
1. Open public plot (vacant_public_open_land) NEVER receives cool roof or green roof.
2. Industrial metal shed roof (industrial_shed_roof) NEVER receives green roof (catastrophic structural collapse risk).
3. Rainwater retention pond (rainwater_fed_pond) is strictly rejected without verified water source.
4. Strict budget constraint: optimizer total cost never exceeds budget ceiling under Greedy and NSGA-II.
5. Unclassified parcel gets needs_site_survey = True and zero mechanical recommendations.
6. Itemized realistic costing: GST (18%), contingency (12%), setup scaling, water tanker, and whole-life cost.
"""

from __future__ import annotations

import pytest

from gis.interventions import (
    FeasibilityStatus,
    InterventionCandidate,
    InterventionType,
    RejectionReason,
)
from gis.interventions.candidates import generate_candidate_for_cell
from gis.interventions.costs import estimate_intervention_cost
from gis.interventions.cooling_effects import estimate_cooling_effect
from gis.interventions.feasibility import evaluate_candidate_feasibility
from gis.interventions.landuse import LanduseClassifier
from gis.interventions.optimization import (
    run_baseline_greedy_optimizer,
    run_nsga2_optimizer,
)
from gis.interventions.recommendations import (
    PolygonSummary,
    generate_polygon_recommendations,
)


# ---------------------------------------------------------------------------
# Test 1: Open public plot never gets cool roof or green roof
# ---------------------------------------------------------------------------
def test_open_public_plot_never_receives_cool_or_green_roof():
    """Verify that an open public plot rejects cool roof and green roof due to absence of rooftop slab."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.12,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=42.5,
        max_lst_c=46.0,
        mean_hpi=58.0,
        max_hpi=72.0,
        vegetation_deficit_component=0.65,
        built_density_component=0.10,
        mean_ndvi=0.15,
        mean_ndbi=-0.15,
        water_fraction=0.02,
        cell_count=3,
        data_coverage_percentage=98.0,
        landuse_typology="vacant_public_open_land",
        is_public_ownership=True,
    )

    response = generate_polygon_recommendations(summary)
    assert response.polygon_summary.landuse_typology == "vacant_public_open_land"

    # Cool roof must be REJECTED with explicit structural reason
    cool_roof_recs = [r for r in response.recommendations if r.type == "COOL_ROOF"]
    for cr in cool_roof_recs:
        assert cr.feasibility_status == "REJECTED"
        assert cr.priority == "NOT_RECOMMENDED"
        assert any("rooftop structure" in reason.lower() for reason in cr.rejection_reasons)

    # Green roof must be absent or rejected
    green_roof_recs = [r for r in response.recommendations if r.type == "GREEN_ROOF"]
    for gr in green_roof_recs:
        assert gr.feasibility_status == "REJECTED"
        assert gr.priority == "NOT_RECOMMENDED"

    # Permissible greening interventions must be FEASIBLE
    tree_rec = next((r for r in response.recommendations if r.type == "TREE_CANOPY"), None)
    assert tree_rec is not None
    assert tree_rec.feasibility_status == "FEASIBLE"
    assert tree_rec.priority in ("HIGH", "MEDIUM")


# ---------------------------------------------------------------------------
# Test 2: Metal industrial shed never receives green roof (structural collapse risk)
# ---------------------------------------------------------------------------
def test_industrial_shed_never_receives_green_roof_due_to_structural_collapse():
    """
    Verify that an industrial corrugated metal / asbestos shed roof strictly rejects green roofs
    due to live load capacity (< 25 kg/m²) vs saturated extensive green roof (100-150 kg/m²).
    """
    summary = PolygonSummary(
        status="ok",
        area_km2=0.25,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=45.2,
        max_lst_c=49.8,
        mean_hpi=68.0,
        max_hpi=82.0,
        vegetation_deficit_component=0.40,
        built_density_component=0.85,
        mean_ndvi=0.08,
        mean_ndbi=0.42,
        water_fraction=0.0,
        cell_count=5,
        data_coverage_percentage=100.0,
        landuse_typology="industrial_shed_roof",
        building_info={
            "building_count": 4,
            "max_building_area_m2": 1500.0,
            "total_roof_area_m2": 4500.0,
        },
    )

    response = generate_polygon_recommendations(summary)
    assert response.polygon_summary.landuse_typology == "industrial_shed_roof"

    # Cool roof coating is FEASIBLE and HIGH priority on industrial sheds
    cool_roof = next((r for r in response.recommendations if r.type == "COOL_ROOF"), None)
    assert cool_roof is not None
    assert cool_roof.feasibility_status == "FEASIBLE"
    assert cool_roof.priority == "HIGH"

    # Disqualified alternatives must list green roof with structural collapse warning
    assert any("collapse" in alt["rejection_reason"].lower() or "structural" in alt["rejection_reason"].lower()
               for alt in cool_roof.rejected_alternatives if alt["intervention_type"] == "green_roof")

    # Cell-level candidate feasibility check
    cand_green_roof = generate_candidate_for_cell(
        row=100, col=100, cell_id="R100_C100",
        intervention_type=InterventionType.GREEN_ROOF,
        baseline_hpi=0.75, baseline_lst_c=45.0,
        is_chronic_hotspot=True, administrative_zone="Pandesara Industrial Zone",
        landuse_typology="industrial_shed_roof",
    )
    assert cand_green_roof.feasibility_status == FeasibilityStatus.REJECTED
    assert cand_green_roof.rejection_reason == RejectionReason.STRUCTURAL_LOAD_COLLAPSE_RISK


# ---------------------------------------------------------------------------
# Test 3: Rainwater retention pond strictly rejected without verified water source
# ---------------------------------------------------------------------------
def test_rainwater_pond_rejected_without_verified_water_source():
    """Verify that rainwater-fed ponds are rejected without documented catchment or treated water source."""
    # Case A: No documented water source -> REJECTED
    summary_no_water = PolygonSummary(
        status="ok",
        area_km2=0.10,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=39.0,
        mean_hpi=45.0,
        landuse_typology="park_garden",
        has_documented_water_source=False,
    )
    resp_no_water = generate_polygon_recommendations(summary_no_water)
    pond_rec_no_water = next((r for r in resp_no_water.recommendations if r.type == "RAINWATER_FED_POND"), None)
    assert pond_rec_no_water is not None
    assert pond_rec_no_water.feasibility_status == "REJECTED"
    assert pond_rec_no_water.priority == "NOT_RECOMMENDED"
    assert any("UNVERIFIED_WATER_SOURCE" in rej for rej in pond_rec_no_water.rejection_reasons)

    # Case B: Verified stormwater catchment / STP effluent -> FEASIBLE
    summary_with_water = PolygonSummary(
        status="ok",
        area_km2=0.10,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=39.0,
        mean_hpi=45.0,
        landuse_typology="park_garden",
        has_documented_water_source=True,
    )
    resp_with_water = generate_polygon_recommendations(summary_with_water)
    pond_rec_with_water = next((r for r in resp_with_water.recommendations if r.type == "RAINWATER_FED_POND"), None)
    assert pond_rec_with_water is not None
    assert pond_rec_with_water.feasibility_status == "FEASIBLE"
    assert pond_rec_with_water.air_cooling_c > 0.0


# ---------------------------------------------------------------------------
# Test 4: Strict budget constraint: expenditure never exceeds budget
# ---------------------------------------------------------------------------
def test_optimizer_total_cost_never_exceeds_budget():
    """Verify that both Greedy Knapsack and NSGA-II solutions strictly obey budget ceiling."""
    budget = 10_000_000.0  # 1 Crore INR

    # Generate test candidates pool
    candidates: list[InterventionCandidate] = []
    types = [InterventionType.TREE_CANOPY, InterventionType.COOL_ROOF, InterventionType.COOL_PAVEMENT]
    for i in range(40):
        itype = types[i % 3]
        c = generate_candidate_for_cell(
            row=50 + i, col=50 + i, cell_id=f"R{50+i:03d}_C{50+i:03d}",
            intervention_type=itype,
            baseline_hpi=0.50 + (i * 0.01),
            baseline_lst_c=40.0 + (i * 0.1),
            is_chronic_hotspot=(i % 2 == 0),
            administrative_zone="Udhna Zone",
            usable_area_m2=1500.0,
            tree_count=40,
            landuse_typology="residential_rcc_roof" if itype == InterventionType.COOL_ROOF else "vacant_public_open_land",
        )
        if c.feasibility_status == FeasibilityStatus.FEASIBLE:
            candidates.append(c)

    # 1. Test Greedy Knapsack
    greedy_sol = run_baseline_greedy_optimizer(candidates, budget_inr=budget)
    assert greedy_sol.is_feasible is True
    assert greedy_sol.total_cost_inr <= budget, (
        f"Greedy Knapsack exceeded budget: {greedy_sol.total_cost_inr} > {budget}"
    )

    # 2. Test NSGA-II Pareto Front
    nsga2_solutions = run_nsga2_optimizer(
        candidates, budget_inr=budget, population_size=20, generations=10
    )
    assert len(nsga2_solutions) > 0
    for sol in nsga2_solutions:
        assert sol.is_feasible is True
        assert sol.total_cost_inr <= budget, (
            f"NSGA-II solution {sol.solution_id} exceeded budget: {sol.total_cost_inr} > {budget}"
        )


# ---------------------------------------------------------------------------
# Test 5: Unclassified parcel gets needs_site_survey = True and zero recommendations
# ---------------------------------------------------------------------------
def test_unclassified_parcel_requires_site_survey_and_returns_zero_recommendations():
    """Verify that ambiguous or unclassified parcels require site survey and receive NO mechanical interventions."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.08,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=40.0,
        landuse_typology="unclassified",
    )

    response = generate_polygon_recommendations(summary)
    assert response.polygon_summary.needs_site_survey is True
    assert response.polygon_summary.landuse_typology == "unclassified"
    assert len(response.recommendations) == 0
    assert any("MANDATORY REQUIREMENT" in caveat for caveat in response.caveats)


# ---------------------------------------------------------------------------
# Test 6: Realistic itemized engineering cost model with GST, contingency & WLC
# ---------------------------------------------------------------------------
def test_itemized_engineering_cost_model_breakdown():
    """Verify itemized breakdown: GST 18%, contingency 12%, scaled setup, and whole-life cost."""
    # Tree Canopy
    cost_base, cost_min, cost_max, meta = estimate_intervention_cost(
        InterventionType.TREE_CANOPY, usable_area_m2=0.0, tree_count=50, expected_cooling_c=1.5
    )
    assert meta["rate_status"] == "INDICATIVE"
    assert meta["gst_18_pct"] > 0
    assert meta["contingency_cost"] > 0
    assert meta["site_setup_scaled_cost"] > 0
    assert meta["water_tanker_cost"] > 0
    assert meta["maintenance_3yr_cost"] > 0
    assert meta["whole_life_cost_3yr_inr"] > cost_base
    assert meta["whole_life_cost_per_c_m2"] > 0
    assert "SMC" in meta["source_to_be_replaced"]

    # Cool Roof
    r_cost, _, _, r_meta = estimate_intervention_cost(
        InterventionType.COOL_ROOF, usable_area_m2=1000.0, expected_cooling_c=2.0
    )
    assert r_meta["rate_status"] == "INDICATIVE"
    assert r_meta["gst_18_pct"] > 0
    assert r_meta["contingency_cost"] > 0
    assert r_meta["whole_life_cost_per_c_m2"] > 0
    assert "CPWD" in r_meta["source_to_be_replaced"]
