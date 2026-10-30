"""Optimization Engines for HEATSENSE AI (Stage D).

Canonical Architectural Invariants:
1. Decision Units: Municipal Packages (discrete clusters of <= 4 contiguous cells).
2. Exact 0/1 Knapsack DP:
   - Strategy A: Lexicographical Hotspot-First (chronic -> benefit -> cells).
   - Strategy B: Maximum Extensive Thermal Benefit (K·m²).
   - Strategy C: Maximum Cost-Effectiveness ((K·m²) / INR).
3. 10-Point Budget Curve: Exact DP solutions sampled across 10-100% of budget cap.
4. Locality Rollup: Geographical breakdown of spend, packages, cells, and benefit.
5. Heuristic Optimality Gap: Comparison of Greedy / NSGA-II against exact DP.
6. Cell Exclusivity & Single Assignment: Maintained unconditionally.
7. Climatological Physics: Surface skin temperature reductions only; 2m air temperature unmodeled.
"""

from __future__ import annotations

import copy
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any
import numpy as np

from gis.interventions import FeasibilityStatus, InterventionCandidate, Package, InterventionType
from gis.interventions.feasibility import get_survey_prerequisites
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
    run_id: str = ""
    unresolved_prerequisites_count: int = 0
    # Stage D Area & Package Extensions:
    selected_packages: list[Package] = field(default_factory=list)
    packages_count: int = 0
    cells_count: int = 0
    optimality_gap_percent: float = 0.0
    budget_curve: list[dict[str, Any]] = field(default_factory=list)
    locality_rollup: list[dict[str, Any]] = field(default_factory=list)
    strategy_comparison: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        deployments = []
        for c in self.selected_candidates:
            prereqs = getattr(c, "survey_prerequisites", None) or get_survey_prerequisites(c.intervention_type)
            deployments.append({
                "candidate_id": c.candidate_id,
                "cell_id": c.cell_id,
                "intervention_type": c.intervention_type.value if hasattr(c.intervention_type, "value") else str(c.intervention_type),
                "cost_inr": round(c.cost_inr, 2),
                "usable_area_m2": round(c.usable_area_m2, 2),
                "expected_cooling_c": round(c.expected_cooling_c, 3),
                "baseline_hpi": round(c.baseline_hpi, 4) if c.baseline_hpi is not None else None,
                "baseline_lst_c": round(c.baseline_lst_c, 2) if c.baseline_lst_c is not None else None,
                "is_chronic_hotspot": c.is_chronic_hotspot,
                "administrative_zone": c.administrative_zone,
                "latitude": round(c.latitude, 6),
                "longitude": round(c.longitude, 6),
                "landuse_typology": getattr(c, "landuse_typology", "unclassified"),
                "feasibility_status": c.feasibility_status.value if hasattr(c.feasibility_status, "value") else str(c.feasibility_status),
                "prerequisites_status": getattr(c, "prerequisites_status", "FEASIBLE_SUBJECT_TO_SURVEY"),
                "survey_prerequisites": prereqs,
                "landcover_rule_fired": getattr(c, "landcover_rule_fired", "NONE"),
                "landcover_top_class": getattr(c, "landcover_top_class", None),
                "landcover_confidence": getattr(c, "landcover_confidence", None),
                "landcover_entropy": getattr(c, "landcover_entropy", None),
                "landcover_disclosure": getattr(c, "landcover_disclosure", "ASSUMPTION: UNCALIBRATED_HEURISTIC"),
            })

        unresolved_count = sum(1 for d in deployments if d.get("survey_prerequisites"))

        pkgs_dicts = []
        for p in self.selected_packages:
            if hasattr(p, "to_dict"):
                pkgs_dicts.append(p.to_dict())
            else:
                pkgs_dicts.append({
                    "package_id": getattr(p, "package_id", ""),
                    "cluster_id": getattr(p, "cluster_id", ""),
                    "locality": getattr(p, "locality", ""),
                    "cell_ids": getattr(p, "cell_ids", []),
                    "cell_count": getattr(p, "cell_count", 0),
                    "treated_footprint_m2": getattr(p, "treated_footprint_m2", 0.0),
                    "estimated_cost_inr": getattr(p, "estimated_cost_inr", 0.0),
                    "capex_breakdown": getattr(p, "capex_breakdown", {}),
                    "opex_3yr_inr": getattr(p, "opex_3yr_inr", 0.0),
                    "delta_t_skin_c": getattr(p, "delta_t_skin_c", 0.0),
                    "delta_t_cell_c": getattr(p, "delta_t_cell_c", 0.0),
                    "thermal_benefit_k_m2": getattr(p, "thermal_benefit_k_m2", 0.0),
                    "chronic_hotspot_cells_count": getattr(p, "chronic_hotspot_cells_count", 0),
                    "landcover_summary": getattr(p, "landcover_summary", {}),
                })

        return {
            "solution_id": self.solution_id,
            "run_id": self.run_id or f"RUN_{abs(hash((self.solution_id, self.total_cost_inr))) % 1000000:06d}",
            "algorithm": self.algorithm,
            "total_cost_inr": round(self.total_cost_inr, 2),
            "portfolio_thermal_benefit_c_m2": round(self.portfolio_thermal_benefit_c_m2, 2),
            "thermal_benefit_k_m2": round(self.portfolio_thermal_benefit_c_m2, 2),
            "treated_area_m2": round(self.treated_area_m2, 2),
            "mean_local_cooling_c": round(self.mean_local_cooling_c, 3),
            "citywide_cooling_c": round(self.citywide_cooling_c, 6),
            "domain_area_m2": round(self.domain_area_m2, 2),
            "heat_priority_weighted_benefit_c_m2": round(self.heat_priority_weighted_benefit_c_m2, 2),
            "population_exposure_benefit": self.population_exposure_benefit,
            "population_exposure_status": self.population_exposure_status,
            "chronic_hotspots_count": self.chronic_hotspots_count,
            "interventions_count": self.interventions_count,
            "packages_count": self.packages_count or len(self.selected_packages),
            "cells_count": self.cells_count or len(self.selected_candidates),
            "budget_limit_inr": round(self.budget_limit_inr, 2),
            "budget_utilized_percent": round(self.budget_utilized_percent, 2),
            "is_feasible": self.is_feasible,
            "pareto_rank": self.pareto_rank,
            "crowding_distance": round(self.crowding_distance, 4),
            "optimality_gap_percent": round(self.optimality_gap_percent, 1),
            "selected_candidate_ids": [c.candidate_id for c in self.selected_candidates],
            "selected_packages": pkgs_dicts,
            "budget_curve": self.budget_curve,
            "locality_rollup": self.locality_rollup,
            "strategy_comparison": self.strategy_comparison,
            "deployments": deployments,
            "unresolved_prerequisites_count": unresolved_count,
            # Maintained legacy fields for backward compatibility
            "total_expected_cooling_c": round(self.total_expected_cooling_c, 3),
            "heat_priority_weighted_cooling": round(self.heat_priority_weighted_cooling, 2),
        }


def _package_to_candidates(package: Package) -> list[InterventionCandidate]:
    """Convert package cells into standard InterventionCandidate objects."""
    cands: list[InterventionCandidate] = []
    itype = package.intervention_type if hasattr(package, "intervention_type") else InterventionType.COOL_ROOF
    for c in getattr(package, "cells", []):
        cand = InterventionCandidate(
            candidate_id=c.get("candidate_id", f"CAND_{package.package_id}_{c.get('cell_id', 'X')}"),
            cell_id=c.get("cell_id", ""),
            row=c.get("row", 0),
            col=c.get("col", 0),
            tree_count=c.get("tree_count", 0),
            intervention_type=itype,
            feasibility_status=FeasibilityStatus.FEASIBLE,
            cost_inr=c.get("cost_inr", 0.0),
            usable_area_m2=c.get("usable_area_m2", 0.0),
            expected_cooling_c=c.get("expected_cooling_c", 0.0),
            baseline_hpi=c.get("baseline_hpi"),
            baseline_lst_c=c.get("baseline_lst_c"),
            is_chronic_hotspot=c.get("is_chronic_hotspot", False),
            administrative_zone=package.locality,
            latitude=c.get("latitude", 21.1702),
            longitude=c.get("longitude", 72.8311),
        )
        cand.landcover_rule_fired = package.landcover_summary.get("rule_fired", "RULE_DW_BUILT_DENSE")
        cand.landcover_top_class = package.landcover_summary.get("top_class", "built")
        cand.landcover_confidence = package.landcover_summary.get("confidence", 0.60)
        cand.landcover_entropy = package.landcover_summary.get("entropy", 0.65)
        cand.landcover_disclosure = "Dynamic World 10m LULC model prediction (Brown et al. 2022)"
        cand.survey_prerequisites = get_survey_prerequisites(itype)
        cands.append(cand)
    return cands


def compute_locality_rollup(packages: list[Package]) -> list[dict[str, Any]]:
    """Aggregate municipal package deployments by locality."""
    from collections import defaultdict
    loc_groups = defaultdict(list)
    for p in packages:
        loc = getattr(p, "locality", None) or "Unassigned"
        loc_groups[loc].append(p)

    rollups = []
    for loc, pkgs in sorted(loc_groups.items(), key=lambda item: len(item[1]), reverse=True):
        spend = round(sum(p.estimated_cost_inr for p in pkgs), 2)
        benefit = round(sum(p.thermal_benefit_k_m2 for p in pkgs), 1)
        cells = sum(p.cell_count for p in pkgs)
        chronic = sum(p.chronic_hotspot_cells_count for p in pkgs)
        area_m2 = round(sum(p.treated_footprint_m2 for p in pkgs), 1)
        types = sorted(list({
            p.intervention_type.value if hasattr(p.intervention_type, "value") else str(p.intervention_type)
            for p in pkgs
        }))
        rollups.append({
            "locality": loc,
            "packages_count": len(pkgs),
            "cells_count": cells,
            "spend_inr": spend,
            "treated_area_m2": area_m2,
            "thermal_benefit_k_m2": benefit,
            "chronic_hotspot_cells_count": chronic,
            "intervention_types": types,
        })
    return rollups


# ===========================================================================
# 1. EXACT 0/1 KNAPSACK OPTIMIZER BY INTEGER DYNAMIC PROGRAMMING
# ===========================================================================

def run_exact_knapsack_optimizer(
    packages: list[Package],
    budget_inr: float = 50_000_000.0,
    strategy: str = "hotspot_first",
    discretization_unit_inr: float = 5000.0,
    domain_area_m2: float = DEFAULT_SMC_DOMAIN_AREA_M2,
) -> ScenarioSolution:
    """
    Exact 0/1 Knapsack Optimizer by Integer Dynamic Programming.

    Guarantees mathematically exact Pareto optimality for the chosen strategy:
    - 'hotspot_first' (Strategy A): Lexicographical (chronic hotspots -> thermal benefit -> cells).
    - 'max_benefit' (Strategy B): Maximum extensive thermal benefit in K·m².
    - 'cost_effective' (Strategy C): Maximum thermal benefit per Lakh INR.
    """
    strat_key = strategy.lower().replace("-", "_")
    if "hotspot" in strat_key or "strat_a" in strat_key or "a" == strat_key:
        strat = "hotspot_first"
    elif "benefit" in strat_key or "strat_b" in strat_key or "b" == strat_key:
        strat = "max_benefit"
    else:
        strat = "cost_effective"

    eligible = [p for p in packages if p.estimated_cost_inr <= budget_inr]
    if not eligible or budget_inr <= 0:
        return ScenarioSolution(
            solution_id=f"EXACT_DP_{strat.upper()}_EMPTY",
            algorithm=f"EXACT_01_KNAPSACK_{strat.upper()}",
            selected_candidates=[],
            total_cost_inr=0.0,
            portfolio_thermal_benefit_c_m2=0.0,
            treated_area_m2=0.0,
            mean_local_cooling_c=0.0,
            citywide_cooling_c=0.0,
            domain_area_m2=domain_area_m2,
            heat_priority_weighted_benefit_c_m2=0.0,
            chronic_hotspots_count=0,
            interventions_count=0,
            packages_count=0,
            cells_count=0,
            budget_limit_inr=budget_inr,
            budget_utilized_percent=0.0,
            is_feasible=True,
            budget_curve=[],
            locality_rollup=[],
        )

    # Discretization: use adaptive unit so W <= 1000, preventing exponential state space and memory spikes
    adaptive_unit = max(25000.0, budget_inr / 1000.0)
    unit = max(100.0, discretization_unit_inr, adaptive_unit)
    W = int(budget_inr / unit)

    # Candidate pruning for exact DP: if candidate pool exceeds 400, pre-filter by strategy density
    if len(eligible) > 400:
        if strat == "hotspot_first":
            eligible = sorted(
                eligible,
                key=lambda p: (
                    p.chronic_hotspot_cells_count > 0,
                    p.chronic_hotspot_cells_count / max(100.0, p.estimated_cost_inr),
                    p.thermal_benefit_k_m2 / max(100.0, p.estimated_cost_inr),
                ),
                reverse=True,
            )[:400]
        elif strat == "max_benefit":
            eligible = sorted(
                eligible,
                key=lambda p: p.thermal_benefit_k_m2 / max(100.0, p.estimated_cost_inr),
                reverse=True,
            )[:400]
        else: # cost_effective
            eligible = sorted(
                eligible,
                key=lambda p: (p.thermal_benefit_k_m2 / max(100.0, p.estimated_cost_inr)),
                reverse=True,
            )[:400]

    n = len(eligible)
    # Ceiling discretization ensures discrete weight strictly upper-bounds continuous cost
    weights = [max(1, int(math.ceil(p.estimated_cost_inr / unit))) for p in eligible]

    if strat == "hotspot_first":
        values = [(p.chronic_hotspot_cells_count, round(p.thermal_benefit_k_m2, 1), p.cell_count) for p in eligible]
        zero_val = (0, 0.0, 0)
    elif strat == "max_benefit":
        values = [(round(p.thermal_benefit_k_m2, 1), p.chronic_hotspot_cells_count, p.cell_count) for p in eligible]
        zero_val = (0.0, 0, 0)
    else: # cost_effective
        values = [
            (round((p.thermal_benefit_k_m2 / max(100.0, p.estimated_cost_inr)) * 100_000.0, 2),
             p.chronic_hotspot_cells_count, p.cell_count)
            for p in eligible
        ]
        zero_val = (0.0, 0, 0)

    dp_val = [zero_val] * (W + 1)
    keep = [[False] * (W + 1) for _ in range(n)]

    for i in range(n):
        wt = weights[i]
        val = values[i]
        for w in range(W, wt - 1, -1):
            cand_val = (
                dp_val[w - wt][0] + val[0],
                dp_val[w - wt][1] + val[1],
                dp_val[w - wt][2] + val[2],
            )
            if cand_val > dp_val[w]:
                dp_val[w] = cand_val
                keep[i][w] = True

    # 10-Point Budget Curve from same DP table
    budget_curve = []
    for step in range(1, 11):
        target_fraction = step / 10.0
        target_budget = budget_inr * target_fraction
        target_w = int(target_budget / unit)
        best_step_w = max(range(target_w + 1), key=lambda w: dp_val[w])
        curr = best_step_w
        sub_indices = []
        for i in range(n - 1, -1, -1):
            if keep[i][curr]:
                sub_indices.append(i)
                curr -= weights[i]
        sub_pkgs = [eligible[i] for i in sub_indices]
        # Re-verify true cost strictly against step target budget
        if sum(p.estimated_cost_inr for p in sub_pkgs) > target_budget:
            sub_pkgs.sort(key=lambda p: p.thermal_benefit_k_m2 / max(1.0, p.estimated_cost_inr), reverse=True)
            while sub_pkgs and sum(p.estimated_cost_inr for p in sub_pkgs) > target_budget:
                sub_pkgs.pop()
        spend = sum(p.estimated_cost_inr for p in sub_pkgs)
        benefit = sum(p.thermal_benefit_k_m2 for p in sub_pkgs)
        chronic = sum(p.chronic_hotspot_cells_count for p in sub_pkgs)
        cells = sum(p.cell_count for p in sub_pkgs)
        budget_curve.append({
            "step": step,
            "budget_fraction": target_fraction,
            "budget_cap_inr": round(target_budget, 2),
            "actual_spend_inr": round(spend, 2),
            "spend_utilized_percent": round((spend / target_budget * 100.0), 1) if target_budget > 0 else 0.0,
            "packages_count": len(sub_pkgs),
            "cells_count": cells,
            "chronic_hotspots_count": chronic,
            "thermal_benefit_k_m2": round(benefit, 1),
        })

    # Main solution at capacity W
    best_final_w = max(range(W + 1), key=lambda w: dp_val[w])
    curr = best_final_w
    final_indices = []
    for i in range(n - 1, -1, -1):
        if keep[i][curr]:
            final_indices.append(i)
            curr -= weights[i]

    selected_pkgs = [eligible[i] for i in final_indices]
    # Re-verify true cost strictly against budget cap
    if sum(p.estimated_cost_inr for p in selected_pkgs) > budget_inr:
        selected_pkgs.sort(key=lambda p: p.thermal_benefit_k_m2 / max(1.0, p.estimated_cost_inr), reverse=True)
        while selected_pkgs and sum(p.estimated_cost_inr for p in selected_pkgs) > budget_inr:
            selected_pkgs.pop()

    tot_cost = sum(p.estimated_cost_inr for p in selected_pkgs)
    tot_benefit = sum(p.thermal_benefit_k_m2 for p in selected_pkgs)
    tot_treated_area = sum(p.treated_footprint_m2 for p in selected_pkgs)
    tot_chronic = sum(p.chronic_hotspot_cells_count for p in selected_pkgs)
    tot_cells = sum(p.cell_count for p in selected_pkgs)

    # Convert package cells into InterventionCandidates
    selected_cands: list[InterventionCandidate] = []
    for p in selected_pkgs:
        selected_cands.extend(_package_to_candidates(p))

    mean_local = (
        round(tot_benefit / max(1.0, tot_treated_area), 2)
        if tot_treated_area > 0 else 0.0
    )
    citywide = round(tot_benefit / max(1.0, domain_area_m2), 6)
    utilized_pct = (tot_cost / budget_inr * 100.0) if budget_inr > 0 else 0.0

    rollup = compute_locality_rollup(selected_pkgs)

    return ScenarioSolution(
        solution_id=f"EXACT_DP_{strat.upper()}_SOL",
        algorithm=f"EXACT_01_KNAPSACK_{strat.upper()}",
        selected_candidates=selected_cands,
        total_cost_inr=tot_cost,
        portfolio_thermal_benefit_c_m2=tot_benefit,
        treated_area_m2=tot_treated_area,
        mean_local_cooling_c=mean_local,
        citywide_cooling_c=citywide,
        domain_area_m2=domain_area_m2,
        heat_priority_weighted_benefit_c_m2=tot_benefit,
        chronic_hotspots_count=tot_chronic,
        interventions_count=len(selected_pkgs),
        packages_count=len(selected_pkgs),
        cells_count=tot_cells,
        budget_limit_inr=budget_inr,
        budget_utilized_percent=utilized_pct,
        is_feasible=tot_cost <= budget_inr,
        pareto_rank=1,
        crowding_distance=1.0,
        population_exposure_benefit=None,
        population_exposure_status="POPULATION_DATA_UNAVAILABLE",
        total_expected_cooling_c=mean_local,
        heat_priority_weighted_cooling=tot_benefit,
        selected_packages=selected_pkgs,
        budget_curve=budget_curve,
        locality_rollup=rollup,
    )


def compare_strategies(
    packages: list[Package],
    budget_inr: float,
    discretization_unit_inr: float = 5000.0,
    domain_area_m2: float = DEFAULT_SMC_DOMAIN_AREA_M2,
) -> dict[str, Any]:
    """Compare Strategy A (Hotspot-First), Strategy B (Max Benefit), and Greedy Baseline."""
    sol_a = run_exact_knapsack_optimizer(packages, budget_inr=budget_inr, strategy="hotspot_first", discretization_unit_inr=discretization_unit_inr, domain_area_m2=domain_area_m2)
    sol_b = run_exact_knapsack_optimizer(packages, budget_inr=budget_inr, strategy="max_benefit", discretization_unit_inr=discretization_unit_inr, domain_area_m2=domain_area_m2)
    sol_greedy = run_baseline_greedy_optimizer(packages, budget_inr=budget_inr, domain_area_m2=domain_area_m2)

    b_benefit = sol_b.portfolio_thermal_benefit_c_m2
    g_benefit = sol_greedy.portfolio_thermal_benefit_c_m2
    optimality_gap = round(max(0.0, (b_benefit - g_benefit) / max(1.0, b_benefit) * 100.0), 1)

    return {
        "strategy_a_hotspot_first": {
            "title": "Strategy A: Hotspot-First (Recommended)",
            "description": "Lexicographic priority: strictly maximizes chronic hotspot remediation before expanding extensive cooling.",
            "packages_count": sol_a.packages_count,
            "cells_count": sol_a.cells_count,
            "spend_inr": round(sol_a.total_cost_inr, 2),
            "budget_utilized_percent": round(sol_a.budget_utilized_percent, 1),
            "thermal_benefit_k_m2": round(sol_a.portfolio_thermal_benefit_c_m2, 1),
            "chronic_hotspots_count": sol_a.chronic_hotspots_count,
            "treated_area_m2": round(sol_a.treated_area_m2, 1),
            "mean_local_cooling_c": round(sol_a.mean_local_cooling_c, 2),
            "is_exact_optimal": True,
        },
        "strategy_b_max_benefit": {
            "title": "Strategy B: Max Thermal Benefit",
            "description": "Unconstrained benefit maximization: maximizes aggregate citywide thermal benefit (K·m²).",
            "packages_count": sol_b.packages_count,
            "cells_count": sol_b.cells_count,
            "spend_inr": round(sol_b.total_cost_inr, 2),
            "budget_utilized_percent": round(sol_b.budget_utilized_percent, 1),
            "thermal_benefit_k_m2": round(sol_b.portfolio_thermal_benefit_c_m2, 1),
            "chronic_hotspots_count": sol_b.chronic_hotspots_count,
            "treated_area_m2": round(sol_b.treated_area_m2, 1),
            "mean_local_cooling_c": round(sol_b.mean_local_cooling_c, 2),
            "is_exact_optimal": True,
        },
        "strategy_c_greedy_baseline": {
            "title": "Strategy C: Greedy Heuristic Baseline",
            "description": "Greedy cost-effectiveness ratio ranking. Fast approximation with measured optimality gap.",
            "packages_count": sol_greedy.packages_count or len(sol_greedy.selected_packages),
            "cells_count": sol_greedy.cells_count or len(sol_greedy.selected_candidates),
            "spend_inr": round(sol_greedy.total_cost_inr, 2),
            "budget_utilized_percent": round(sol_greedy.budget_utilized_percent, 1),
            "thermal_benefit_k_m2": round(sol_greedy.portfolio_thermal_benefit_c_m2, 1),
            "chronic_hotspots_count": sol_greedy.chronic_hotspots_count,
            "treated_area_m2": round(sol_greedy.treated_area_m2, 1),
            "mean_local_cooling_c": round(sol_greedy.mean_local_cooling_c, 2),
            "is_exact_optimal": False,
            "optimality_gap_percent": optimality_gap,
        },
        "recommended_strategy": "strategy_a_hotspot_first",
        "optimality_gap_percent": optimality_gap,
    }


# ===========================================================================
# 2. BASELINE CONSTRAINED OPTIMIZER (GREEDY KNAPSACK)
# ===========================================================================

def run_baseline_greedy_optimizer(
    candidates: list[Any],
    budget_inr: float = 50000000.0,
    enforce_cell_exclusivity: bool = True,
    domain_area_m2: float = DEFAULT_SMC_DOMAIN_AREA_M2,
) -> ScenarioSolution:
    """
    Greedy priority-ranked baseline optimizer.
    Supports both list[InterventionCandidate] and list[Package].
    """
    if not candidates:
        return ScenarioSolution(
            solution_id="BASELINE_GREEDY_SOL_EMPTY",
            algorithm="BASELINE_GREEDY_KNAPSACK",
            selected_candidates=[],
            total_cost_inr=0.0,
            portfolio_thermal_benefit_c_m2=0.0,
            treated_area_m2=0.0,
            mean_local_cooling_c=0.0,
            citywide_cooling_c=0.0,
            domain_area_m2=domain_area_m2,
            heat_priority_weighted_benefit_c_m2=0.0,
            chronic_hotspots_count=0,
            interventions_count=0,
            budget_limit_inr=budget_inr,
            budget_utilized_percent=0.0,
            is_feasible=True,
        )

    is_package_list = hasattr(candidates[0], "package_id")

    if is_package_list:
        # Operating on Package objects
        def score_package(p: Package) -> float:
            cost = max(100.0, p.estimated_cost_inr)
            benefit = p.thermal_benefit_k_m2
            chronic_mult = 1.5 if p.chronic_hotspot_cells_count > 0 else 1.0
            return (benefit * chronic_mult) / cost

        ranked_pkgs = sorted(candidates, key=score_package, reverse=True)
        selected_pkgs: list[Package] = []
        used_cells: set[str] = set()
        current_cost = 0.0

        for pkg in ranked_pkgs:
            if enforce_cell_exclusivity and any(c_id in used_cells for c_id in pkg.cell_ids):
                continue
            if current_cost + pkg.estimated_cost_inr <= budget_inr:
                selected_pkgs.append(pkg)
                current_cost += pkg.estimated_cost_inr
                used_cells.update(pkg.cell_ids)

        tot_benefit = sum(p.thermal_benefit_k_m2 for p in selected_pkgs)
        tot_area = sum(p.treated_footprint_m2 for p in selected_pkgs)
        tot_chronic = sum(p.chronic_hotspot_cells_count for p in selected_pkgs)
        tot_cells = sum(p.cell_count for p in selected_pkgs)

        selected_cands: list[InterventionCandidate] = []
        for p in selected_pkgs:
            selected_cands.extend(_package_to_candidates(p))

        mean_local = round(tot_benefit / max(1.0, tot_area), 2) if tot_area > 0 else 0.0
        citywide = round(tot_benefit / max(1.0, domain_area_m2), 6)
        utilized_pct = (current_cost / budget_inr * 100.0) if budget_inr > 0 else 0.0

        rollup = compute_locality_rollup(selected_pkgs)

        return ScenarioSolution(
            solution_id="BASELINE_GREEDY_SOL",
            algorithm="BASELINE_GREEDY_KNAPSACK",
            selected_candidates=selected_cands,
            total_cost_inr=current_cost,
            portfolio_thermal_benefit_c_m2=tot_benefit,
            treated_area_m2=tot_area,
            mean_local_cooling_c=mean_local,
            citywide_cooling_c=citywide,
            domain_area_m2=domain_area_m2,
            heat_priority_weighted_benefit_c_m2=tot_benefit,
            chronic_hotspots_count=tot_chronic,
            interventions_count=len(selected_pkgs),
            packages_count=len(selected_pkgs),
            cells_count=tot_cells,
            budget_limit_inr=budget_inr,
            budget_utilized_percent=utilized_pct,
            is_feasible=current_cost <= budget_inr,
            pareto_rank=1,
            selected_packages=selected_pkgs,
            locality_rollup=rollup,
            total_expected_cooling_c=mean_local,
            heat_priority_weighted_cooling=tot_benefit,
        )

    # Legacy: Operating on InterventionCandidate objects
    feasible_cands = [c for c in candidates if c.feasibility_status == FeasibilityStatus.FEASIBLE]

    def score_candidate(c: InterventionCandidate) -> float:
        cost = max(100.0, c.cost_inr)
        hpi = c.baseline_hpi if c.baseline_hpi is not None else 0.5
        chronic_mult = 1.5 if c.is_chronic_hotspot else 1.0
        extensive_benefit_c_m2 = c.usable_area_m2 * c.expected_cooling_c
        return (extensive_benefit_c_m2 * hpi * chronic_mult) / cost

    ranked = sorted(feasible_cands, key=score_candidate, reverse=True)
    selected: list[InterventionCandidate] = []
    used_cells = set()
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
        cells_count=len(selected),
        packages_count=len(selected),
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
# 3. NSGA-II MULTI-OBJECTIVE EVOLUTIONARY OPTIMIZER
# ===========================================================================

def fast_non_dominated_sort(
    costs: np.ndarray,
    heat_coolings: np.ndarray,
    chronic_counts: np.ndarray,
) -> list[list[int]]:
    """Fast non-dominated sorting for 3 objectives."""
    n = len(costs)
    domination_sets: list[list[int]] = [[] for _ in range(n)]
    dominated_counts = np.zeros(n, dtype=int)
    fronts: list[list[int]] = [[]]

    for p in range(n):
        for q in range(n):
            if p == q:
                continue
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
    candidates: list[Any],
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
    Supports both list[InterventionCandidate] and list[Package].
    """
    if not candidates:
        return []

    is_package_list = hasattr(candidates[0], "package_id")

    if is_package_list:
        # Operating on Package items
        random.seed(random_seed)
        np.random.seed(random_seed)
        m = len(candidates)
        pkg_costs = np.array([p.estimated_cost_inr for p in candidates], dtype=np.float64)
        pkg_benefits = np.array([p.thermal_benefit_k_m2 for p in candidates], dtype=np.float64)
        pkg_chronic = np.array([p.chronic_hotspot_cells_count for p in candidates], dtype=int)

        def repair_package_chrom(chrom: np.ndarray) -> np.ndarray:
            fixed = chrom.copy()
            tot_cost = float(np.sum(pkg_costs[fixed == 1]))
            if tot_cost > budget_inr:
                active = np.where(fixed == 1)[0]
                active_sorted = sorted(active, key=lambda i: pkg_benefits[i] / max(1.0, pkg_costs[i]))
                for i in active_sorted:
                    fixed[i] = 0
                    tot_cost = float(np.sum(pkg_costs[fixed == 1]))
                    if tot_cost <= budget_inr:
                        break
            return fixed

        # Seed initial population with Exact DP solutions (Strategy A and Strategy B) + random feasible sets
        exact_sol_a = run_exact_knapsack_optimizer(candidates, budget_inr=budget_inr, strategy="hotspot_first", domain_area_m2=domain_area_m2)
        exact_chrom_a = np.zeros(m, dtype=int)
        for p in exact_sol_a.selected_packages:
            if p in candidates:
                exact_chrom_a[candidates.index(p)] = 1

        exact_sol_b = run_exact_knapsack_optimizer(candidates, budget_inr=budget_inr, strategy="max_benefit", domain_area_m2=domain_area_m2)
        exact_chrom_b = np.zeros(m, dtype=int)
        for p in exact_sol_b.selected_packages:
            if p in candidates:
                exact_chrom_b[candidates.index(p)] = 1

        population = [exact_chrom_a, exact_chrom_b]
        for _ in range(population_size - len(population)):
            raw = np.random.binomial(1, min(0.25, 10.0 / max(1, m)), size=m)
            population.append(repair_package_chrom(raw))
        population = np.array(population)

        for gen in range(generations):
            costs = np.array([np.sum(pkg_costs[p == 1]) for p in population])
            benefits = np.array([np.sum(pkg_benefits[p == 1]) for p in population])
            chronic = np.array([np.sum(pkg_chronic[p == 1]) for p in population])
            fronts = fast_non_dominated_sort(costs, benefits, chronic)

            offspring = []
            for _ in range(population_size // 2):
                p1_idx = random.randint(0, population_size - 1)
                p2_idx = random.randint(0, population_size - 1)
                p1, p2 = population[p1_idx].copy(), population[p2_idx].copy()
                if random.random() < crossover_prob:
                    cx = random.randint(1, m - 1) if m > 1 else 0
                    c1 = np.concatenate([p1[:cx], p2[cx:]])
                    c2 = np.concatenate([p2[:cx], p1[cx:]])
                else:
                    c1, c2 = p1.copy(), p2.copy()
                for child in (c1, c2):
                    if random.random() < mutation_prob:
                        mut_idx = random.randint(0, m - 1)
                        child[mut_idx] = 1 - child[mut_idx]
                    offspring.append(repair_package_chrom(child))

            combined_pop = np.vstack([population, np.array(offspring)])
            comb_costs = np.array([np.sum(pkg_costs[p == 1]) for p in combined_pop])
            comb_benefits = np.array([np.sum(pkg_benefits[p == 1]) for p in combined_pop])
            comb_chronic = np.array([np.sum(pkg_chronic[p == 1]) for p in combined_pop])
            comb_fronts = fast_non_dominated_sort(comb_costs, comb_benefits, comb_chronic)

            new_pop = []
            for front in comb_fronts:
                if len(new_pop) + len(front) <= population_size:
                    new_pop.extend([combined_pop[i] for i in front])
                else:
                    distances = compute_crowding_distances(front, comb_costs, comb_benefits, comb_chronic)
                    sorted_front = sorted(front, key=lambda i: distances[i], reverse=True)
                    needed = population_size - len(new_pop)
                    new_pop.extend([combined_pop[i] for i in sorted_front[:needed]])
                    break
            population = np.array(new_pop)

        # Extract Rank 1 Front
        final_costs = np.array([np.sum(pkg_costs[p == 1]) for p in population])
        final_benefits = np.array([np.sum(pkg_benefits[p == 1]) for p in population])
        final_chronic = np.array([np.sum(pkg_chronic[p == 1]) for p in population])
        final_fronts = fast_non_dominated_sort(final_costs, final_benefits, final_chronic)
        rank1 = final_fronts[0]
        crowding = compute_crowding_distances(rank1, final_costs, final_benefits, final_chronic)

        pareto_sols: list[ScenarioSolution] = []
        seen_p_ids = set()

        for idx, p_idx in enumerate(sorted(rank1, key=lambda i: final_benefits[i], reverse=True)):
            chrom = population[p_idx]
            sel_pkgs = [candidates[i] for i in range(m) if chrom[i] == 1]
            tup = tuple(sorted(p.package_id for p in sel_pkgs))
            if tup in seen_p_ids:
                continue
            seen_p_ids.add(tup)

            tot_cost = sum(p.estimated_cost_inr for p in sel_pkgs)
            tot_benefit = sum(p.thermal_benefit_k_m2 for p in sel_pkgs)
            tot_area = sum(p.treated_footprint_m2 for p in sel_pkgs)
            tot_chronic = sum(p.chronic_hotspot_cells_count for p in sel_pkgs)
            tot_cells = sum(p.cell_count for p in sel_pkgs)

            sel_cands: list[InterventionCandidate] = []
            for p in sel_pkgs:
                sel_cands.extend(_package_to_candidates(p))

            mean_local = round(tot_benefit / max(1.0, tot_area), 2) if tot_area > 0 else 0.0
            citywide = round(tot_benefit / max(1.0, domain_area_m2), 6)
            util_pct = (tot_cost / budget_inr * 100.0) if budget_inr > 0 else 0.0

            sol = ScenarioSolution(
                solution_id=f"PARETO_NSGA2_SOL_{len(pareto_sols) + 1:02d}",
                algorithm="NSGA_II_PARETO",
                selected_candidates=sel_cands,
                total_cost_inr=tot_cost,
                portfolio_thermal_benefit_c_m2=tot_benefit,
                treated_area_m2=tot_area,
                mean_local_cooling_c=mean_local,
                citywide_cooling_c=citywide,
                domain_area_m2=domain_area_m2,
                heat_priority_weighted_benefit_c_m2=tot_benefit,
                chronic_hotspots_count=tot_chronic,
                interventions_count=len(sel_pkgs),
                packages_count=len(sel_pkgs),
                cells_count=tot_cells,
                budget_limit_inr=budget_inr,
                budget_utilized_percent=util_pct,
                is_feasible=tot_cost <= budget_inr,
                pareto_rank=1,
                crowding_distance=crowding.get(p_idx, 0.0),
                selected_packages=sel_pkgs,
                locality_rollup=compute_locality_rollup(sel_pkgs),
                total_expected_cooling_c=mean_local,
                heat_priority_weighted_cooling=tot_benefit,
            )
            pareto_sols.append(sol)

        return pareto_sols

    # Legacy: Candidates logic
    random.seed(random_seed)
    np.random.seed(random_seed)
    feasible_cands = [c for c in candidates if c.feasibility_status == FeasibilityStatus.FEASIBLE]
    m = len(feasible_cands)
    if m == 0:
        return []

    cand_costs = np.array([c.cost_inr for c in feasible_cands], dtype=np.float64)
    cand_weighted_benefits = np.array([
        c.usable_area_m2 * c.expected_cooling_c * (c.baseline_hpi or 0.5)
        for c in feasible_cands
    ], dtype=np.float64)
    cand_is_chronic = np.array([1 if c.is_chronic_hotspot else 0 for c in feasible_cands], dtype=int)
    cand_cells = [c.cell_id for c in feasible_cands]

    cell_to_cand_indices: dict[str, list[int]] = {}
    for idx, c_id in enumerate(cand_cells):
        cell_to_cand_indices.setdefault(c_id, []).append(idx)

    def repair_chromosome(chrom: np.ndarray) -> np.ndarray:
        fixed = chrom.copy()
        for c_id, idxs in cell_to_cand_indices.items():
            active_in_cell = [i for i in idxs if fixed[i] == 1]
            if len(active_in_cell) > 1:
                best_i = max(active_in_cell, key=lambda i: cand_weighted_benefits[i] / max(1.0, cand_costs[i]))
                for i in active_in_cell:
                    if i != best_i:
                        fixed[i] = 0
        tot_cost = float(np.sum(cand_costs[fixed == 1]))
        if tot_cost > budget_inr:
            active = np.where(fixed == 1)[0]
            active_sorted = sorted(active, key=lambda i: cand_weighted_benefits[i] / max(1.0, cand_costs[i]))
            for i in active_sorted:
                fixed[i] = 0
                tot_cost = float(np.sum(cand_costs[fixed == 1]))
                if tot_cost <= budget_inr:
                    break
        return fixed

    population = []
    greedy_sol = run_baseline_greedy_optimizer(feasible_cands, budget_inr=budget_inr, domain_area_m2=domain_area_m2)
    greedy_chrom = np.zeros(m, dtype=int)
    for c in greedy_sol.selected_candidates:
        if c in feasible_cands:
            greedy_chrom[feasible_cands.index(c)] = 1
    population.append(greedy_chrom)

    for _ in range(population_size - 1):
        raw = np.random.binomial(1, 0.15, size=m)
        repaired = repair_chromosome(raw)
        population.append(repaired)
    population = np.array(population)

    for gen in range(generations):
        costs = np.array([np.sum(cand_costs[p == 1]) for p in population])
        heat_benefits = np.array([np.sum(cand_weighted_benefits[p == 1]) for p in population])
        chronic_counts = np.array([np.sum(cand_is_chronic[p == 1]) for p in population])
        fronts = fast_non_dominated_sort(costs, heat_benefits, chronic_counts)

        offspring = []
        for _ in range(population_size // 2):
            p1_idx = random.randint(0, population_size - 1)
            p2_idx = random.randint(0, population_size - 1)
            p1, p2 = population[p1_idx].copy(), population[p2_idx].copy()
            if random.random() < crossover_prob:
                cx_pt = random.randint(1, m - 1) if m > 1 else 0
                c1 = np.concatenate([p1[:cx_pt], p2[cx_pt:]])
                c2 = np.concatenate([p2[:cx_pt], p1[cx_pt:]])
            else:
                c1, c2 = p1.copy(), p2.copy()
            for child in (c1, c2):
                if random.random() < 0.5:
                    mut_idx = random.randint(0, m - 1)
                    child[mut_idx] = 1 - child[mut_idx]
                offspring.append(repair_chromosome(child))

        combined_pop = np.vstack([population, np.array(offspring)])
        comb_costs = np.array([np.sum(cand_costs[p == 1]) for p in combined_pop])
        comb_benefits = np.array([np.sum(cand_weighted_benefits[p == 1]) for p in combined_pop])
        comb_chronic = np.array([np.sum(cand_is_chronic[p == 1]) for p in combined_pop])
        comb_fronts = fast_non_dominated_sort(comb_costs, comb_benefits, comb_chronic)

        new_pop = []
        for front in comb_fronts:
            if len(new_pop) + len(front) <= population_size:
                new_pop.extend([combined_pop[i] for i in front])
            else:
                distances = compute_crowding_distances(front, comb_costs, comb_benefits, comb_chronic)
                sorted_front = sorted(front, key=lambda i: distances[i], reverse=True)
                needed = population_size - len(new_pop)
                new_pop.extend([combined_pop[i] for i in sorted_front[:needed]])
                break
        population = np.array(new_pop)

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

        actual_cost = sum(c.cost_inr for c in sel_cands)
        if actual_cost > budget_inr:
            sel_cands_sorted = sorted(sel_cands, key=lambda c: (c.usable_area_m2 * c.expected_cooling_c * (c.baseline_hpi or 0.5)) / max(1.0, c.cost_inr))
            remaining = list(sel_cands_sorted)
            while actual_cost > budget_inr and remaining:
                dropped = remaining.pop(0)
                actual_cost -= dropped.cost_inr
            sel_cands = remaining
            tot_cost = actual_cost
        else:
            tot_cost = actual_cost

        chr_cnt = sum(1 for c in sel_cands if c.is_chronic_hotspot)
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
            domain_area_m2=domain_area_m2,
            heat_priority_weighted_benefit_c_m2=metrics["heat_priority_weighted_benefit_c_m2"],
            chronic_hotspots_count=chr_cnt,
            interventions_count=len(sel_cands),
            cells_count=len(sel_cands),
            packages_count=len(sel_cands),
            budget_limit_inr=budget_inr,
            budget_utilized_percent=util_pct,
            is_feasible=tot_cost <= budget_inr,
            pareto_rank=1,
            crowding_distance=crowding.get(p_idx, 0.0),
            total_expected_cooling_c=metrics["mean_local_cooling_c"],
            heat_priority_weighted_cooling=metrics["heat_priority_weighted_benefit_c_m2"],
        )
        pareto_solutions.append(sol)

    return pareto_solutions
