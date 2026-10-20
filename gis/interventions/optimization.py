"""Optimization Engines for HEATSENSE AI (Stage D).

Implements:
1. Baseline Constrained Optimizer (Greedy Priority-Ranked Knapsack).
2. NSGA-II Multi-Objective Evolutionary Optimizer (Pareto Front Extraction).

Objectives:
- Minimize Total Implementation Cost (INR ₹)
- Maximize Heat Priority-Weighted Cooling Impact (sum of delta_T * HPI)
- Maximize Chronic Hotspot Interventions

Constraints:
- Total Budget B (INR ₹)
- Cell Exclusivity (at most 1 intervention per grid cell)
- Feasibility Guarantee (only FEASIBLE candidates considered)
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Any
import numpy as np

from gis.interventions import FeasibilityStatus, InterventionCandidate
from gis.interventions.cooling_effects import (
    DEFAULT_SMC_DOMAIN_AREA_M2,
    calculate_portfolio_cooling_metrics,
)


@dataclass
class ScenarioSolution:
    solution_id: str
    algorithm: str
    selected_candidates: list[InterventionCandidate]
    total_cost_inr: float
    portfolio_thermal_benefit_c_m2: float
    treated_area_m2: float
    mean_local_cooling_c: float
    citywide_cooling_c: float
    domain_area_m2: float
    heat_priority_weighted_benefit_c_m2: float
    chronic_hotspots_count: int
    interventions_count: int
    budget_limit_inr: float
    budget_utilized_percent: float
    is_feasible: bool
    pareto_rank: int = 1
    crowding_distance: float = 0.0
    population_exposure_benefit: float | None = None
    population_exposure_status: str = "POPULATION_DATA_UNAVAILABLE"
    # Backward compatibility legacy fields:
    total_expected_cooling_c: float = 0.0  # Equals mean_local_cooling_c in °C
    heat_priority_weighted_cooling: float = 0.0  # Equals heat_priority_weighted_benefit_c_m2 in °C·m²

    def to_dict(self) -> dict[str, Any]:
        return {
            "solution_id": self.solution_id,
            "algorithm": self.algorithm,
            "total_cost_inr": round(self.total_cost_inr, 2),
            "portfolio_thermal_benefit_c_m2": round(self.portfolio_thermal_benefit_c_m2, 2),
            "treated_area_m2": round(self.treated_area_m2, 2),
            "mean_local_cooling_c": round(self.mean_local_cooling_c, 3),
            "citywide_cooling_c": round(self.citywide_cooling_c, 6),
            "domain_area_m2": round(self.domain_area_m2, 2),
            "heat_priority_weighted_benefit_c_m2": round(self.heat_priority_weighted_benefit_c_m2, 2),
            "population_exposure_benefit": self.population_exposure_benefit,
            "population_exposure_status": self.population_exposure_status,
            "chronic_hotspots_count": self.chronic_hotspots_count,
            "interventions_count": self.interventions_count,
            "budget_limit_inr": round(self.budget_limit_inr, 2),
            "budget_utilized_percent": round(self.budget_utilized_percent, 2),
            "is_feasible": self.is_feasible,
            "pareto_rank": self.pareto_rank,
            "crowding_distance": round(self.crowding_distance, 4),
            "selected_candidate_ids": [c.candidate_id for c in self.selected_candidates],
            # Maintained legacy fields for backward compatibility
            "total_expected_cooling_c": round(self.total_expected_cooling_c, 3),
            "heat_priority_weighted_cooling": round(self.heat_priority_weighted_cooling, 2),
        }


# ===========================================================================
# 1. BASELINE CONSTRAINED OPTIMIZER (GREEDY KNAPSACK)
# ===========================================================================

def run_baseline_greedy_optimizer(
    candidates: list[InterventionCandidate],
    budget_inr: float = 50000000.0,  # Default 5 Crore INR (50M INR)
    enforce_cell_exclusivity: bool = True,
    domain_area_m2: float = DEFAULT_SMC_DOMAIN_AREA_M2,
) -> ScenarioSolution:
    """
    Greedy priority-ranked baseline optimizer.

    Ranks candidates by extensive thermal cost-effectiveness ratio:
        Ratio = (usable_area_m2 * expected_cooling_c * baseline_hpi * (1.5 if chronic else 1.0)) / cost_inr
    Units: (°C·m²) / INR

    Greedily selects top candidates without violating budget or cell exclusivity.
    """
    feasible_cands = [c for c in candidates if c.feasibility_status == FeasibilityStatus.FEASIBLE]

    def score_candidate(c: InterventionCandidate) -> float:
        cost = max(100.0, c.cost_inr)
        hpi = c.baseline_hpi if c.baseline_hpi is not None else 0.5
        chronic_mult = 1.5 if c.is_chronic_hotspot else 1.0
        extensive_benefit_c_m2 = c.usable_area_m2 * c.expected_cooling_c
        return (extensive_benefit_c_m2 * hpi * chronic_mult) / cost

    # Sort descending by priority ratio
    ranked = sorted(feasible_cands, key=score_candidate, reverse=True)

    selected: list[InterventionCandidate] = []
    used_cells: set[str] = set()
    current_cost = 0.0

    for cand in ranked:
        if enforce_cell_exclusivity and cand.cell_id in used_cells:
            continue
        if current_cost + cand.cost_inr <= budget_inr:
            selected.append(cand)
            current_cost += cand.cost_inr
            used_cells.add(cand.cell_id)

    metrics = calculate_portfolio_cooling_metrics(selected, domain_area_m2=domain_area_m2)
    chronic_count = sum(1 for c in selected if c.is_chronic_hotspot)
    utilized_pct = (current_cost / budget_inr * 100.0) if budget_inr > 0 else 0.0

    return ScenarioSolution(
        solution_id="BASELINE_GREEDY_SOL",
        algorithm="BASELINE_GREEDY_KNAPSACK",
        selected_candidates=selected,
        total_cost_inr=current_cost,
        portfolio_thermal_benefit_c_m2=metrics["portfolio_thermal_benefit_c_m2"],
        treated_area_m2=metrics["treated_area_m2"],
        mean_local_cooling_c=metrics["mean_local_cooling_c"],
        citywide_cooling_c=metrics["citywide_cooling_c"],
        domain_area_m2=metrics["domain_area_m2"],
        heat_priority_weighted_benefit_c_m2=metrics["heat_priority_weighted_benefit_c_m2"],
        chronic_hotspots_count=chronic_count,
        interventions_count=len(selected),
        budget_limit_inr=budget_inr,
        budget_utilized_percent=utilized_pct,
        is_feasible=current_cost <= budget_inr,
        pareto_rank=1,
        population_exposure_benefit=None,
        population_exposure_status="POPULATION_DATA_UNAVAILABLE",
        total_expected_cooling_c=metrics["mean_local_cooling_c"],
        heat_priority_weighted_cooling=metrics["heat_priority_weighted_benefit_c_m2"],
    )


# ===========================================================================
# 2. NSGA-II MULTI-OBJECTIVE EVOLUTIONARY OPTIMIZER
# ===========================================================================

def fast_non_dominated_sort(
    costs: np.ndarray,
    heat_coolings: np.ndarray,
    chronic_counts: np.ndarray,
) -> list[list[int]]:
    """
    Fast non-dominated sorting for 3 objectives:
    - Min Cost (costs)
    - Max Heat-Weighted Cooling (heat_coolings)
    - Max Chronic Hotspots (chronic_counts)
    """
    n = len(costs)
    domination_sets: list[list[int]] = [[] for _ in range(n)]
    dominated_counts = np.zeros(n, dtype=int)
    fronts: list[list[int]] = [[]]

    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            # p dominates q if p is <= q on cost, and >= q on cooling and chronic, with at least one strict
            p_better_or_equal = (
                costs[p] <= costs[q]
                and heat_coolings[p] >= heat_coolings[q]
                and chronic_counts[p] >= chronic_counts[q]
            )
            p_strictly_better = (
                costs[p] < costs[q]
                or heat_coolings[p] > heat_coolings[q]
                or chronic_counts[p] > chronic_counts[q]
            )
            if p_better_or_equal and p_strictly_better:
                domination_sets[p].append(q)
            elif (
                costs[q] <= costs[p]
                and heat_coolings[q] >= heat_coolings[p]
                and chronic_counts[q] >= chronic_counts[p]
                and (costs[q] < costs[p] or heat_coolings[q] > heat_coolings[p] or chronic_counts[q] > chronic_counts[p])
            ):
                dominated_counts[p] += 1

        if dominated_counts[p] == 0:
            fronts[0].append(p)

    curr_front = 0
    while curr_front < len(fronts) and len(fronts[curr_front]) > 0:
        next_front: list[int] = []
        for p in fronts[curr_front]:
            for q in domination_sets[p]:
                dominated_counts[q] -= 1
                if dominated_counts[q] == 0:
                    next_front.append(q)
        curr_front += 1
        if next_front:
            fronts.append(next_front)

    return fronts


def compute_crowding_distances(
    front: list[int],
    costs: np.ndarray,
    heat_coolings: np.ndarray,
    chronic_counts: np.ndarray,
) -> dict[int, float]:
    """Compute crowding distances along front to maintain diversity."""
    distances = {idx: 0.0 for idx in front}
    if len(front) <= 2:
        for idx in front:
            distances[idx] = float("inf")
        return distances

    objectives = [costs, heat_coolings, chronic_counts]
    for obj in objectives:
        sorted_indices = sorted(front, key=lambda i: obj[i])
        distances[sorted_indices[0]] = float("inf")
        distances[sorted_indices[-1]] = float("inf")
        obj_range = obj[sorted_indices[-1]] - obj[sorted_indices[0]]
        if obj_range == 0:
            continue
        for k in range(1, len(sorted_indices) - 1):
            distances[sorted_indices[k]] += (
                obj[sorted_indices[k + 1]] - obj[sorted_indices[k - 1]]
            ) / obj_range

    return distances


def run_nsga2_optimizer(
    candidates: list[InterventionCandidate],
    budget_inr: float = 50000000.0,
    population_size: int = 40,
    generations: int = 30,
    crossover_prob: float = 0.85,
    mutation_prob: float = 0.05,
    random_seed: int = 42,
    domain_area_m2: float = DEFAULT_SMC_DOMAIN_AREA_M2,
) -> list[ScenarioSolution]:
    """
    NSGA-II Multi-Objective Optimizer for Pareto front generation.

    Objectives:
    1. Minimize Total Cost (INR ₹)
    2. Maximize Extensive Heat Priority-Weighted Thermal Benefit (°C·m²)
    3. Maximize Chronic Hotspots Intervened (count)

    Returns
    -------
    list[ScenarioSolution]
        Non-dominated Pareto-optimal solutions.
    """
    random.seed(random_seed)
    np.random.seed(random_seed)

    feasible_cands = [c for c in candidates if c.feasibility_status == FeasibilityStatus.FEASIBLE]
    m = len(feasible_cands)
    if m == 0:
        return []

    # Map candidate attributes to fast numpy arrays
    cand_costs = np.array([c.cost_inr for c in feasible_cands], dtype=np.float64)
    # Extensive priority-weighted thermal cooling benefit (°C·m²)
    cand_weighted_benefits = np.array([
        c.usable_area_m2 * c.expected_cooling_c * (c.baseline_hpi or 0.5)
        for c in feasible_cands
    ], dtype=np.float64)
    cand_is_chronic = np.array([1 if c.is_chronic_hotspot else 0 for c in feasible_cands], dtype=int)
    cand_cells = [c.cell_id for c in feasible_cands]

    # Pre-map cell collisions
    cell_to_cand_indices: dict[str, list[int]] = {}
    for idx, c_id in enumerate(cand_cells):
        cell_to_cand_indices.setdefault(c_id, []).append(idx)

    def repair_chromosome(chrom: np.ndarray) -> np.ndarray:
        """Enforce cell exclusivity and budget constraint."""
        fixed = chrom.copy()
        # Enforce cell exclusivity: if multiple selected in same cell, keep the one with higher extensive benefit/cost ratio
        for c_id, idxs in cell_to_cand_indices.items():
            active_in_cell = [i for i in idxs if fixed[i] == 1]
            if len(active_in_cell) > 1:
                # Keep best
                best_i = max(active_in_cell, key=lambda i: cand_weighted_benefits[i] / max(1.0, cand_costs[i]))
                for i in active_in_cell:
                    if i != best_i:
                        fixed[i] = 0

        # Enforce budget: if over budget, randomly drop candidates until under budget
        tot_cost = np.sum(cand_costs[fixed == 1])
        if tot_cost > budget_inr:
            active = np.where(fixed == 1)[0]
            # Drop least cost-effective first
            active_sorted = sorted(active, key=lambda i: cand_weighted_benefits[i] / max(1.0, cand_costs[i]))
            for i in active_sorted:
                fixed[i] = 0
                tot_cost -= cand_costs[i]
                if tot_cost <= budget_inr:
                    break
        return fixed

    # Initialize Population
    population = []
    # Seed 1: greedy baseline solution
    greedy_sol = run_baseline_greedy_optimizer(feasible_cands, budget_inr=budget_inr, domain_area_m2=domain_area_m2)
    greedy_chrom = np.zeros(m, dtype=int)
    for c in greedy_sol.selected_candidates:
        if c in feasible_cands:
            greedy_chrom[feasible_cands.index(c)] = 1
    population.append(greedy_chrom)

    # Seed remaining randomly
    for _ in range(population_size - 1):
        raw = np.random.binomial(1, 0.15, size=m)
        repaired = repair_chromosome(raw)
        population.append(repaired)

    population = np.array(population)

    # Evolution Loop
    for gen in range(generations):
        # Evaluate objectives
        costs = np.array([np.sum(cand_costs[p == 1]) for p in population])
        heat_benefits = np.array([np.sum(cand_weighted_benefits[p == 1]) for p in population])
        chronic_counts = np.array([np.sum(cand_is_chronic[p == 1]) for p in population])

        # Non-dominated sort
        fronts = fast_non_dominated_sort(costs, heat_benefits, chronic_counts)

        # Offspring generation
        offspring = []
        for _ in range(population_size // 2):
            # Tournament selection
            parent1_idx = random.randint(0, population_size - 1)
            parent2_idx = random.randint(0, population_size - 1)
            p1 = population[parent1_idx].copy()
            p2 = population[parent2_idx].copy()

            # Single-point crossover
            if random.random() < crossover_prob:
                cx_pt = random.randint(1, m - 1) if m > 1 else 0
                c1 = np.concatenate([p1[:cx_pt], p2[cx_pt:]])
                c2 = np.concatenate([p2[:cx_pt], p1[cx_pt:]])
            else:
                c1, c2 = p1.copy(), p2.copy()

            # Bit-flip mutation
            for child in (c1, c2):
                if random.random() < 0.5:
                    mut_idx = random.randint(0, m - 1)
                    child[mut_idx] = 1 - child[mut_idx]
                offspring.append(repair_chromosome(child))

        # Combine parent + offspring
        combined_pop = np.vstack([population, np.array(offspring)])
        comb_costs = np.array([np.sum(cand_costs[p == 1]) for p in combined_pop])
        comb_benefits = np.array([np.sum(cand_weighted_benefits[p == 1]) for p in combined_pop])
        comb_chronic = np.array([np.sum(cand_is_chronic[p == 1]) for p in combined_pop])

        comb_fronts = fast_non_dominated_sort(comb_costs, comb_benefits, comb_chronic)

        # Select next generation
        new_pop = []
        for front in comb_fronts:
            if len(new_pop) + len(front) <= population_size:
                new_pop.extend([combined_pop[i] for i in front])
            else:
                # Sort remaining by crowding distance
                distances = compute_crowding_distances(front, comb_costs, comb_benefits, comb_chronic)
                sorted_front = sorted(front, key=lambda i: distances[i], reverse=True)
                needed = population_size - len(new_pop)
                new_pop.extend([combined_pop[i] for i in sorted_front[:needed]])
                break

        population = np.array(new_pop)

    # Final Evaluation & Extract Rank 1 Pareto Front
    final_costs = np.array([np.sum(cand_costs[p == 1]) for p in population])
    final_benefits = np.array([np.sum(cand_weighted_benefits[p == 1]) for p in population])
    final_chronic = np.array([np.sum(cand_is_chronic[p == 1]) for p in population])
    final_fronts = fast_non_dominated_sort(final_costs, final_benefits, final_chronic)
    rank1_indices = final_fronts[0]

    crowding = compute_crowding_distances(rank1_indices, final_costs, final_benefits, final_chronic)

    pareto_solutions: list[ScenarioSolution] = []
    seen_hashes = set()

    for sol_rank, p_idx in enumerate(sorted(rank1_indices, key=lambda i: final_benefits[i], reverse=True)):
        chrom = population[p_idx]
        sel_cands = [feasible_cands[i] for i in range(m) if chrom[i] == 1]
        c_ids_tuple = tuple(sorted(c.candidate_id for c in sel_cands))
        if c_ids_tuple in seen_hashes:
            continue
        seen_hashes.add(c_ids_tuple)

        tot_cost = float(final_costs[p_idx])
        chr_cnt = int(final_chronic[p_idx])
        util_pct = (tot_cost / budget_inr * 100.0) if budget_inr > 0 else 0.0

        metrics = calculate_portfolio_cooling_metrics(sel_cands, domain_area_m2=domain_area_m2)

        sol = ScenarioSolution(
            solution_id=f"PARETO_NSGA2_SOL_{len(pareto_solutions) + 1:02d}",
            algorithm="NSGA_II_PARETO",
            selected_candidates=sel_cands,
            total_cost_inr=tot_cost,
            portfolio_thermal_benefit_c_m2=metrics["portfolio_thermal_benefit_c_m2"],
            treated_area_m2=metrics["treated_area_m2"],
            mean_local_cooling_c=metrics["mean_local_cooling_c"],
            citywide_cooling_c=metrics["citywide_cooling_c"],
            domain_area_m2=metrics["domain_area_m2"],
            heat_priority_weighted_benefit_c_m2=metrics["heat_priority_weighted_benefit_c_m2"],
            chronic_hotspots_count=chr_cnt,
            interventions_count=len(sel_cands),
            budget_limit_inr=budget_inr,
            budget_utilized_percent=util_pct,
            is_feasible=tot_cost <= budget_inr,
            pareto_rank=1,
            crowding_distance=crowding.get(p_idx, 0.0),
            population_exposure_benefit=None,
            population_exposure_status="POPULATION_DATA_UNAVAILABLE",
            total_expected_cooling_c=metrics["mean_local_cooling_c"],
            heat_priority_weighted_cooling=metrics["heat_priority_weighted_benefit_c_m2"],
        )
        pareto_solutions.append(sol)

    return pareto_solutions
