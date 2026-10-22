"""Unit and Integration Tests for Stage D Optimization Engines.

Verifies:
1. Baseline constrained greedy knapsack optimizer budget compliance.
2. Cell exclusivity enforcement in optimizer selections.
3. NSGA-II multi-objective genetic algorithm convergence to Rank 1 Pareto front.
4. Determinism of optimization under fixed random seeds.
"""

from __future__ import annotations

import pytest

from gis.interventions import InterventionType
from gis.interventions.candidates import generate_candidate_for_cell
from gis.interventions.optimization import (
    run_baseline_greedy_optimizer,
    run_nsga2_optimizer,
)


@pytest.fixture
def sample_candidates():
    cands = []
    # Create 30 synthetic feasible candidates across 15 distinct cells
    for i in range(15):
        row = 100 + i
        col = 150 + i
        cell_id = f"R{row:03d}_C{col:03d}"
        is_chr = (i % 3 == 0)
        hpi = 0.50 + (i * 0.03)

        # Candidate 1: Tree Canopy
        c_tree = generate_candidate_for_cell(
            row=row, col=col, cell_id=cell_id,
            intervention_type=InterventionType.TREE_CANOPY,
            baseline_hpi=hpi, baseline_lst_c=40.0,
            is_chronic_hotspot=is_chr, administrative_zone="Central Zone",
            tree_count=30 + i * 2, usable_area_m2=1200.0,
        )
        cands.append(c_tree)

        # Candidate 2: Cool Roof
        c_roof = generate_candidate_for_cell(
            row=row, col=col, cell_id=cell_id,
            intervention_type=InterventionType.COOL_ROOF,
            baseline_hpi=hpi, baseline_lst_c=40.0,
            is_chronic_hotspot=is_chr, administrative_zone="Central Zone",
            usable_area_m2=1500.0, ndbi=0.10,
        )
        cands.append(c_roof)

    return cands


def test_baseline_greedy_optimizer_budget_and_exclusivity(sample_candidates):
    """Verify greedy baseline strictly complies with budget and enforces cell exclusivity."""
    budget = 1000000.0  # 10 Lakh INR (1 Million INR)

    sol = run_baseline_greedy_optimizer(
        candidates=sample_candidates,
        budget_inr=budget,
        enforce_cell_exclusivity=True,
    )

    assert sol.is_feasible is True
    assert sol.total_cost_inr <= budget, f"Cost {sol.total_cost_inr} exceeded budget {budget}!"
    assert sol.interventions_count > 0

    # Assert cell exclusivity: no cell is used more than once
    selected_cells = [c.cell_id for c in sol.selected_candidates]
    assert len(selected_cells) == len(set(selected_cells)), "Cell exclusivity violated in greedy solution!"


def test_nsga2_pareto_front_generation(sample_candidates):
    """Verify NSGA-II produces non-dominated Pareto front with budget compliance."""
    budget = 1500000.0  # 15 Lakh INR

    pareto_solutions = run_nsga2_optimizer(
        candidates=sample_candidates,
        budget_inr=budget,
        population_size=20,
        generations=15,
        random_seed=42,
    )

    assert len(pareto_solutions) > 0, "NSGA-II failed to generate any Pareto solutions."

    for sol in pareto_solutions:
        assert sol.pareto_rank == 1
        assert sol.is_feasible is True
        assert sol.total_cost_inr <= budget
        # Assert cell exclusivity
        cells = [c.cell_id for c in sol.selected_candidates]
        assert len(cells) == len(set(cells)), "Cell exclusivity violated in NSGA-II solution!"


def test_optimizer_determinism_under_fixed_seed(sample_candidates):
    """Verify NSGA-II is completely deterministic when run with identical seed."""
    budget = 1000000.0

    run1 = run_nsga2_optimizer(sample_candidates, budget_inr=budget, population_size=16, generations=10, random_seed=99)
    run2 = run_nsga2_optimizer(sample_candidates, budget_inr=budget, population_size=16, generations=10, random_seed=99)

    assert len(run1) == len(run2)
    for s1, s2 in zip(run1, run2):
        assert s1.total_cost_inr == s2.total_cost_inr
        assert s1.total_expected_cooling_c == s2.total_expected_cooling_c


def test_multi_tier_budget_scenarios(sample_candidates):
    """Verify standard low, medium, and high budget scenarios scale properly."""
    low_budget = 500000.0     # ₹5 Lakhs
    med_budget = 2000000.0    # ₹20 Lakhs
    high_budget = 5000000.0   # ₹50 Lakhs

    sol_low = run_baseline_greedy_optimizer(sample_candidates, budget_inr=low_budget)
    sol_med = run_baseline_greedy_optimizer(sample_candidates, budget_inr=med_budget)
    sol_high = run_baseline_greedy_optimizer(sample_candidates, budget_inr=high_budget)

    assert sol_low.total_cost_inr <= low_budget
    assert sol_med.total_cost_inr <= med_budget
    assert sol_high.total_cost_inr <= high_budget
    assert sol_low.interventions_count <= sol_med.interventions_count <= sol_high.interventions_count
    assert sol_low.portfolio_thermal_benefit_c_m2 <= sol_med.portfolio_thermal_benefit_c_m2 <= sol_high.portfolio_thermal_benefit_c_m2
