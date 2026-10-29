import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

import time
from app.db.session import SessionLocal
from app.api.v1.interventions import get_all_packages_for_area
from gis.interventions.optimization import run_exact_knapsack_optimizer, run_baseline_greedy_optimizer

db = SessionLocal()
packages = get_all_packages_for_area(db, area_name='all')
print(f'Total packages loaded from DB: {len(packages)}')

budget = 25_000_000.0 # 2.5 Cr

# 1. Greedy
t0 = time.time()
sol_greedy = run_baseline_greedy_optimizer(packages, budget_inr=budget, enforce_cell_exclusivity=True)
t_greedy = time.time() - t0
print(f'Greedy time: {t_greedy:.4f}s, pkgs: {sol_greedy.packages_count}, cost: {sol_greedy.total_cost_inr}')

# 2. Adaptive Unit Exact DP with candidate pruning if > 400
t0 = time.time()
unit = max(25000.0, budget / 1000.0)
eligible = [p for p in packages if p.estimated_cost_inr <= budget]
if len(eligible) > 400:
    eligible = sorted(
        eligible,
        key=lambda p: (
            p.chronic_hotspot_cells_count > 0,
            p.chronic_hotspot_cells_count / max(100.0, p.estimated_cost_inr),
            p.thermal_benefit_k_m2 / max(100.0, p.estimated_cost_inr)
        ),
        reverse=True
    )[:400]
sol_exact = run_exact_knapsack_optimizer(eligible, budget_inr=budget, discretization_unit_inr=unit)
t_exact = time.time() - t0
print(f'Exact DP (W={int(budget/unit)}, N={len(eligible)}) time: {t_exact:.4f}s, pkgs: {sol_exact.packages_count}, cost: {sol_exact.total_cost_inr}')
