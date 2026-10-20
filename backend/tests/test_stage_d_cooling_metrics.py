"""Comprehensive Acceptance and Scientific Regression Tests for Stage D Cooling Metrics and Spatial Area Reconciliation.

Covers all 9 Phase 5 Verification Requirements:
1. Two equal-area cells with 2°C local reductions do not produce a regional reduction of 4°C.
2. Unequal-area cells are weighted correctly by footprint area.
3. Untreated area is handled according to the documented municipal domain definition (A_domain = 461.63 km²).
4. Duplicating a candidate or counting overlapping areas cannot inflate optimizer benefit (cell exclusivity).
5. Splitting one uniform-area candidate into smaller equivalent pieces strictly preserves the aggregate extensive metric (°C·m²).
6. Greedy Knapsack and NSGA-II engines use consistent, documented benefit semantics.
7. Budget limits, feasibility rules, and site exclusivity hold strictly.
8. API responses and persisted database scenario records use corrected units, field meanings, and explicit population status.
9. Grid coverage and area conservation tests match actual geometry semantics (resolving 497.47 km² vs 459.55 km²).
"""

from __future__ import annotations

from pathlib import Path
import geopandas as gpd
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models.stage_d import (
    StageDInterventionCandidate as DBInterventionCandidate,
    StageDScenarioResult as DBScenarioResult,
)
from backend.app.db.session import SessionLocal
from backend.app.main import app
from gis.interventions import (
    FeasibilityStatus,
    InterventionCandidate,
    InterventionType,
    RejectionReason,
)
from gis.interventions.candidates import generate_candidate_for_cell
from gis.interventions.cooling_effects import (
    DEFAULT_SMC_DOMAIN_AREA_M2,
    calculate_portfolio_cooling_metrics,
)
from gis.interventions.optimization import (
    ScenarioSolution,
    run_baseline_greedy_optimizer,
    run_nsga2_optimizer,
)
from gis.spatial.grid import (
    AUTHORITATIVE_SMC_AREA_KM2,
    CANONICAL_SMC_CELL_COUNT,
    CANONICAL_SMC_CLIPPED_AREA_KM2,
    INTERSECTING_SMC_CELL_COUNT,
    METRIC_CRS,
    PERIMETER_SLIVER_CELL_COUNT,
    PERIMETER_SLIVER_CLIPPED_AREA_KM2,
    get_cell_polygon,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOUNDARY_GEOJSON = PROJECT_ROOT / "data" / "raw" / "boundaries" / "surat_smc_boundary.geojson"

client = TestClient(app)


# ---------------------------------------------------------------------------
# Requirement 1: Equal-Area Regional Cooling Non-Additivity
# ---------------------------------------------------------------------------
def test_two_equal_area_cells_do_not_sum_temperatures():
    """Requirement 1: Two equal-area cells with 2°C local reductions do not produce a regional reduction of 4°C."""
    cell1 = {
        "usable_area_m2": 1500.0,
        "expected_cooling_c": 2.0,
        "baseline_hpi": 0.60,
    }
    cell2 = {
        "usable_area_m2": 1500.0,
        "expected_cooling_c": 2.0,
        "baseline_hpi": 0.60,
    }

    metrics = calculate_portfolio_cooling_metrics([cell1, cell2])

    # 1. Total treated area
    assert metrics["treated_area_m2"] == 3000.0

    # 2. Area-weighted mean local reduction across treated footprint is 2.0°C, NEVER 4.0°C
    assert metrics["mean_local_cooling_c"] == 2.0
    assert metrics["mean_local_cooling_c"] != 4.0, "Portfolio cooling must NEVER sum intensive temperature reductions!"

    # 3. Extensive thermal benefit is 6,000 °C·m²
    assert metrics["portfolio_thermal_benefit_c_m2"] == 6000.0

    # 4. Citywide cooling across municipal domain (461.63 km²) is 6,000 / 461,630,791 ≈ 0.000013 °C
    expected_citywide = 6000.0 / DEFAULT_SMC_DOMAIN_AREA_M2
    assert metrics["citywide_cooling_c"] == pytest.approx(expected_citywide, rel=1e-5)


# ---------------------------------------------------------------------------
# Requirement 2: Unequal-Area Weighting Correctness
# ---------------------------------------------------------------------------
def test_unequal_area_cells_weighted_correctly():
    """Requirement 2: Unequal-area cells are weighted correctly by their respective areas."""
    # Site A: 1,000 m² with 3.0°C cooling -> 3,000 °C·m²
    # Site B: 3,000 m² with 1.0°C cooling -> 3,000 °C·m²
    # Total benefit: 6,000 °C·m² over 4,000 m² -> Mean: 1.50°C
    site_a = {"usable_area_m2": 1000.0, "expected_cooling_c": 3.0, "baseline_hpi": 0.5}
    site_b = {"usable_area_m2": 3000.0, "expected_cooling_c": 1.0, "baseline_hpi": 0.5}

    metrics = calculate_portfolio_cooling_metrics([site_a, site_b])

    assert metrics["treated_area_m2"] == 4000.0
    assert metrics["portfolio_thermal_benefit_c_m2"] == 6000.0
    assert metrics["mean_local_cooling_c"] == 1.50
    # Must NOT equal unweighted mean (3.0 + 1.0) / 2 = 2.0°C
    assert metrics["mean_local_cooling_c"] != 2.0
    # Must NOT equal scalar sum 4.0°C
    assert metrics["mean_local_cooling_c"] != 4.0


# ---------------------------------------------------------------------------
# Requirement 3: Untreated Area Handling Under Documented Domain
# ---------------------------------------------------------------------------
def test_untreated_area_handled_according_to_documented_domain():
    """Requirement 3: Untreated area is handled according to documented domain definition (A_domain = 461.63 km²)."""
    treated_area = 20000.0  # 20,000 m² (0.02 km²)
    local_cooling = 2.50   # 2.5°C
    cand = {"usable_area_m2": treated_area, "expected_cooling_c": local_cooling, "baseline_hpi": 0.7}

    domain_area = DEFAULT_SMC_DOMAIN_AREA_M2  # 461,630,791.0 m²
    metrics = calculate_portfolio_cooling_metrics([cand], domain_area_m2=domain_area)

    # Extensive benefit
    extensive_benefit = treated_area * local_cooling  # 50,000 °C·m²
    assert metrics["portfolio_thermal_benefit_c_m2"] == extensive_benefit

    # Untreated area (461,630,791 - 20,000 = 461,610,791 m²) contributes 0.0°C
    # Citywide reduction = (treated_area * 2.5 + untreated_area * 0.0) / domain_area
    expected_citywide = extensive_benefit / domain_area
    assert metrics["citywide_cooling_c"] == pytest.approx(expected_citywide, rel=1e-6)
    assert metrics["citywide_cooling_c"] < 0.001, "Citywide cooling for 0.02 km² treated out of 461.63 km² must be modest"


# ---------------------------------------------------------------------------
# Requirement 4: Candidate Duplication Immunity
# ---------------------------------------------------------------------------
def test_duplicate_candidate_cannot_inflate_benefit():
    """Requirement 4: Duplicating a candidate or counting overlapping areas cannot inflate optimizer benefit."""
    cand1 = generate_candidate_for_cell(
        row=100, col=100, cell_id="R100_C100",
        intervention_type=InterventionType.COOL_ROOF,
        baseline_hpi=0.8, baseline_lst_c=41.0, is_chronic_hotspot=True,
        administrative_zone="Central Zone", usable_area_m2=2000.0,
    )
    # Exact duplicate in same cell with clone candidate ID
    cand1_dup = generate_candidate_for_cell(
        row=100, col=100, cell_id="R100_C100",
        intervention_type=InterventionType.COOL_ROOF,
        baseline_hpi=0.8, baseline_lst_c=41.0, is_chronic_hotspot=True,
        administrative_zone="Central Zone", usable_area_m2=2000.0,
    )
    cand1_dup.candidate_id = "CAND_COOL_ROOF_R100_C100_CLONE"

    # Distinct cell candidate
    cand2 = generate_candidate_for_cell(
        row=101, col=101, cell_id="R101_C101",
        intervention_type=InterventionType.TREE_CANOPY,
        baseline_hpi=0.7, baseline_lst_c=40.0, is_chronic_hotspot=False,
        administrative_zone="Central Zone", usable_area_m2=1500.0,
    )

    pool_with_dups = [cand1, cand1_dup, cand2]

    # Run optimizer with ample budget
    sol = run_baseline_greedy_optimizer(pool_with_dups, budget_inr=50000000.0, enforce_cell_exclusivity=True)

    # Must select at most 1 candidate from cell R100_C100
    selected_cells = [c.cell_id for c in sol.selected_candidates]
    assert selected_cells.count("R100_C100") == 1, "Duplicate candidate in same cell was counted more than once!"
    assert len(sol.selected_candidates) == 2


# ---------------------------------------------------------------------------
# Requirement 5: Partition Invariance (Splitting Preserves Aggregate Metric)
# ---------------------------------------------------------------------------
def test_splitting_candidate_preserves_aggregate_benefit():
    """Requirement 5: Splitting one uniform-area candidate into smaller equivalent pieces preserves aggregate metric."""
    # Parent candidate: 2,000 m² with 2.4°C cooling
    parent_cand = {"usable_area_m2": 2000.0, "expected_cooling_c": 2.40, "baseline_hpi": 0.65}

    # Split into 4 smaller sub-parcels of 500 m² each with identical cooling intensity
    sub_cands = [
        {"usable_area_m2": 500.0, "expected_cooling_c": 2.40, "baseline_hpi": 0.65}
        for _ in range(4)
    ]

    metrics_parent = calculate_portfolio_cooling_metrics([parent_cand])
    metrics_split = calculate_portfolio_cooling_metrics(sub_cands)

    # Extensive thermal benefit must be IDENTICAL (4,800 °C·m²)
    assert metrics_parent["portfolio_thermal_benefit_c_m2"] == pytest.approx(
        metrics_split["portfolio_thermal_benefit_c_m2"], rel=1e-5
    )
    assert metrics_parent["portfolio_thermal_benefit_c_m2"] == 4800.0

    # Treated-area-weighted mean local cooling must be IDENTICAL (2.40°C)
    assert metrics_parent["mean_local_cooling_c"] == pytest.approx(
        metrics_split["mean_local_cooling_c"], rel=1e-5
    )
    assert metrics_parent["mean_local_cooling_c"] == 2.40

    # Citywide cooling must be IDENTICAL
    assert metrics_parent["citywide_cooling_c"] == pytest.approx(
        metrics_split["citywide_cooling_c"], rel=1e-5
    )

    # In contrast, naive temperature summation would have quadrupled to 9.60°C!
    naive_sum_split = sum(c["expected_cooling_c"] for c in sub_cands)
    assert naive_sum_split == 9.60
    assert metrics_split["mean_local_cooling_c"] != naive_sum_split


# ---------------------------------------------------------------------------
# Requirement 6: Greedy and NSGA-II Consistency
# ---------------------------------------------------------------------------
def test_greedy_and_nsga2_consistent_benefit_semantics():
    """Requirement 6: Greedy and NSGA-II engines use consistent, documented extensive benefit semantics."""
    cands = []
    for i in range(10):
        cands.append(
            generate_candidate_for_cell(
                row=120 + i, col=130 + i, cell_id=f"R{120+i:03d}_C{130+i:03d}",
                intervention_type=InterventionType.COOL_ROOF,
                baseline_hpi=0.55 + i * 0.03, baseline_lst_c=39.0 + i * 0.2,
                is_chronic_hotspot=(i % 2 == 0), administrative_zone="Central Zone",
                usable_area_m2=1200.0 + i * 100.0,
            )
        )

    budget = 1000000.0  # 10 Lakh INR

    sol_greedy = run_baseline_greedy_optimizer(cands, budget_inr=budget)
    solutions_nsga2 = run_nsga2_optimizer(cands, budget_inr=budget, population_size=16, generations=10, random_seed=42)

    assert len(solutions_nsga2) > 0
    all_sols = [sol_greedy] + solutions_nsga2

    assert any(s.interventions_count > 0 for s in solutions_nsga2), "NSGA-II should produce active intervention solutions"

    for sol in all_sols:
        assert sol.domain_area_m2 == DEFAULT_SMC_DOMAIN_AREA_M2
        assert sol.population_exposure_benefit is None
        assert sol.population_exposure_status == "POPULATION_DATA_UNAVAILABLE"

        if sol.interventions_count > 0:
            assert sol.portfolio_thermal_benefit_c_m2 > 0.0
            assert sol.treated_area_m2 > 0.0
            assert sol.mean_local_cooling_c > 0.0
            assert sol.citywide_cooling_c > 0.0

            # Verify mathematical identity: portfolio_thermal_benefit = treated_area * mean_local_cooling
            calculated_product = sol.treated_area_m2 * sol.mean_local_cooling_c
            assert sol.portfolio_thermal_benefit_c_m2 == pytest.approx(calculated_product, rel=1e-3)

            # Verify citywide identity: citywide_cooling = portfolio_thermal_benefit / domain_area
            calculated_citywide = sol.portfolio_thermal_benefit_c_m2 / sol.domain_area_m2
            assert sol.citywide_cooling_c == pytest.approx(calculated_citywide, rel=1e-3)

            # Verify legacy backward compatibility fields
            assert sol.total_expected_cooling_c == pytest.approx(sol.mean_local_cooling_c, rel=1e-3)
        else:
            assert sol.portfolio_thermal_benefit_c_m2 == 0.0
            assert sol.treated_area_m2 == 0.0
            assert sol.mean_local_cooling_c == 0.0
            assert sol.citywide_cooling_c == 0.0
            assert sol.total_expected_cooling_c == 0.0



# ---------------------------------------------------------------------------
# Requirement 7: Budget Limits, Feasibility, and Site Exclusivity
# ---------------------------------------------------------------------------
def test_budget_limits_feasibility_and_site_exclusivity():
    """Requirement 7: Budget limits, feasibility rules, and site exclusivity still work."""
    cands = []
    # 5 feasible candidates in distinct cells
    for i in range(5):
        cands.append(
            generate_candidate_for_cell(
                row=140 + i, col=140 + i, cell_id=f"R{140+i:03d}_C{140+i:03d}",
                intervention_type=InterventionType.TREE_CANOPY,
                baseline_hpi=0.75, baseline_lst_c=41.0, is_chronic_hotspot=True,
                administrative_zone="Central Zone", tree_count=40,
            )
        )
    # 1 candidate outside SMC boundary (REJECTED)
    cand_rejected = generate_candidate_for_cell(
        row=5, col=5, cell_id="R005_C005",
        intervention_type=InterventionType.TREE_CANOPY,
        baseline_hpi=0.8, baseline_lst_c=40.0, is_chronic_hotspot=False,
        administrative_zone="Outside", is_inside_smc=False,
    )
    assert cand_rejected.feasibility_status == FeasibilityStatus.REJECTED
    cands.append(cand_rejected)

    # 1 candidate with water body conflict (REJECTED)
    cand_water = generate_candidate_for_cell(
        row=140, col=141, cell_id="R140_C141",
        intervention_type=InterventionType.COOL_PAVEMENT,
        baseline_hpi=0.8, baseline_lst_c=40.0, is_chronic_hotspot=False,
        administrative_zone="Central Zone", ndwi=0.25,
    )
    assert cand_water.feasibility_status == FeasibilityStatus.REJECTED
    cands.append(cand_water)

    tight_budget = 300000.0  # 3 Lakh INR

    sol = run_baseline_greedy_optimizer(cands, budget_inr=tight_budget, enforce_cell_exclusivity=True)

    # 1. Budget strictly respected
    assert sol.total_cost_inr <= tight_budget
    assert sol.is_feasible is True

    # 2. No rejected candidates selected
    selected_ids = [c.candidate_id for c in sol.selected_candidates]
    assert cand_rejected.candidate_id not in selected_ids
    assert cand_water.candidate_id not in selected_ids

    # 3. Site exclusivity strictly respected
    selected_cells = [c.cell_id for c in sol.selected_candidates]
    assert len(selected_cells) == len(set(selected_cells))


# ---------------------------------------------------------------------------
# Requirement 8: API and Persistence Compatibility
# ---------------------------------------------------------------------------
def test_api_responses_and_persisted_scenarios():
    """Requirement 8: API responses and persisted scenarios use corrected units and field meanings."""
    # 1. Test POST /api/v1/interventions/optimize
    resp = client.post(
        "/api/v1/interventions/optimize",
        json={"budget_inr": 10000000.0, "algorithm": "greedy", "max_candidates": 20},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["solutions_count"] >= 1
    sol = data["solutions"][0]

    # Verify all corrected scientific fields are present in response JSON
    assert "portfolio_thermal_benefit_c_m2" in sol
    assert "treated_area_m2" in sol
    assert "mean_local_cooling_c" in sol
    assert "citywide_cooling_c" in sol
    assert "domain_area_m2" in sol
    assert "heat_priority_weighted_benefit_c_m2" in sol
    assert "population_exposure_benefit" in sol
    assert sol["population_exposure_benefit"] is None
    assert sol["population_exposure_status"] == "POPULATION_DATA_UNAVAILABLE"

    # Verify legacy fields present and coherent
    assert "total_expected_cooling_c" in sol
    assert sol["total_expected_cooling_c"] == sol["mean_local_cooling_c"]
    assert "heat_priority_weighted_cooling" in sol

    # 2. Test database model roundtrip persistence in PostgreSQL
    session: Session = SessionLocal()
    try:
        test_scenario_id = "SCENARIO_SCIENTIFIC_TEST_01"
        # Clean any prior test row
        session.query(DBScenarioResult).filter_by(scenario_id=test_scenario_id).delete()
        session.commit()

        db_record = DBScenarioResult(
            scenario_id=test_scenario_id,
            algorithm="BASELINE_GREEDY_KNAPSACK",
            budget_inr=10000000.0,
            total_cost_inr=9500000.0,
            portfolio_thermal_benefit_c_m2=15000.0,
            treated_area_m2=7500.0,
            mean_local_cooling_c=2.0,
            citywide_cooling_c=15000.0 / DEFAULT_SMC_DOMAIN_AREA_M2,
            domain_area_m2=DEFAULT_SMC_DOMAIN_AREA_M2,
            heat_priority_weighted_benefit_c_m2=10500.0,
            population_exposure_benefit=None,
            population_exposure_status="POPULATION_DATA_UNAVAILABLE",
            total_cooling_c=2.0,
            heat_weighted_cooling=10500.0,
            chronic_hotspots_count=5,
            interventions_count=6,
            is_feasible=True,
            pareto_rank=1,
            selected_candidates_json={"test": True},
        )
        session.add(db_record)
        session.commit()

        # Query back and verify all columns persist correctly
        fetched = session.scalar(
            select(DBScenarioResult).where(DBScenarioResult.scenario_id == test_scenario_id)
        )
        assert fetched is not None
        assert fetched.portfolio_thermal_benefit_c_m2 == 15000.0
        assert fetched.treated_area_m2 == 7500.0
        assert fetched.mean_local_cooling_c == 2.0
        assert fetched.domain_area_m2 == DEFAULT_SMC_DOMAIN_AREA_M2
        assert fetched.population_exposure_benefit is None
        assert fetched.population_exposure_status == "POPULATION_DATA_UNAVAILABLE"
        assert fetched.total_cooling_c == 2.0

        # Clean up
        session.delete(fetched)
        session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Requirement 9: Grid Coverage and Area Conservation Reconciliation
# ---------------------------------------------------------------------------
def test_grid_coverage_and_area_conservation_reconciliation():
    """Requirement 9: Reconcile 497.47 km² nominal vs 459.55 km² operational clipped area."""
    # 1. Authoritative municipal boundary area in EPSG:32643
    gdf = gpd.read_file(BOUNDARY_GEOJSON)
    gdf_utm = gdf.to_crs(METRIC_CRS)
    measured_boundary_km2 = float(gdf_utm.geometry.iloc[0].area / 1e6)
    assert measured_boundary_km2 == pytest.approx(AUTHORITATIVE_SMC_AREA_KM2, abs=0.001)
    assert measured_boundary_km2 == pytest.approx(461.630791, abs=0.001)

    # 2. Individual cell nominal area in EPSG:32643 is ~9,282 m², NOT 10,000 m²
    p0 = get_cell_polygon(160, 160)
    p0_utm = gpd.GeoSeries([p0], crs="EPSG:4326").to_crs(METRIC_CRS).iloc[0]
    cell_nominal_m2 = p0_utm.area
    assert 9270.0 < cell_nominal_m2 < 9295.0, (
        f"Cell area {cell_nominal_m2} m² deviates from expected ~9,282 m² (due to latitude compression at 21.2°N)"
    )

    # 3. 49,747 nominal cells * ~9,282 m² = ~461.78 km², NOT 497.47 km²
    nominal_49747_km2 = (49747 * cell_nominal_m2) / 1e6
    assert nominal_49747_km2 == pytest.approx(461.77, abs=0.5)
    assert nominal_49747_km2 != pytest.approx(497.47, abs=5.0), (
        "497.47 km² is a naive 10,000 m² assumption that ignores latitude compression in EPSG:4326!"
    )

    # 4. Operational clipped area = 459.550165 km² (99.55% of municipal territory)
    # The remaining 2.080626 km² (0.45%) resides in 1,124 perimeter boundary slivers
    assert CANONICAL_SMC_CLIPPED_AREA_KM2 == pytest.approx(459.550165, abs=0.001)
    assert PERIMETER_SLIVER_CLIPPED_AREA_KM2 == pytest.approx(2.080626, abs=0.001)
    assert CANONICAL_SMC_CLIPPED_AREA_KM2 + PERIMETER_SLIVER_CLIPPED_AREA_KM2 == pytest.approx(
        AUTHORITATIVE_SMC_AREA_KM2, abs=0.001
    )

    # 5. Cell count identities
    assert CANONICAL_SMC_CELL_COUNT == 49747
    assert PERIMETER_SLIVER_CELL_COUNT == 1124
    assert INTERSECTING_SMC_CELL_COUNT == 50871
    assert CANONICAL_SMC_CELL_COUNT + PERIMETER_SLIVER_CELL_COUNT == INTERSECTING_SMC_CELL_COUNT
