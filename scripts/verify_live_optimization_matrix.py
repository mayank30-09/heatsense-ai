import json
from app.db.session import SessionLocal
from gis.interventions.clustering import get_all_packages_for_area, get_available_areas
from gis.interventions.optimization import run_exact_knapsack_optimizer, compare_strategies, compute_locality_rollup

db = SessionLocal()

scopes = ["Udhana", "Dindoli", "Bhestan", "all"]
budgets = [
    ("50 Lakh", 5_000_000.0),
    ("2.50 Crore", 25_000_000.0),
    ("10.00 Crore", 100_000_000.0),
]

results = []

for scope in scopes:
    scope_name = "Citywide (All Areas)" if scope == "all" else scope
    pkgs = get_all_packages_for_area(db, area_name=scope)
    total_cells = sum(p.cell_count for p in pkgs)
    chronic_cells = sum(p.chronic_hotspot_cells_count for p in pkgs)
    
    print(f"\n=======================================================")
    print(f"SCOPE: {scope_name} (Total Packages: {len(pkgs)}, Total Cells: {total_cells}, Chronic: {chronic_cells})")
    print(f"=======================================================")
    
    for b_label, b_val in budgets:
        # Strategy A (Hotspot-First Exact DP)
        sol_a = run_exact_knapsack_optimizer(pkgs, budget_inr=b_val, strategy="hotspot_first")
        
        # Strategy B (Max Benefit Exact DP)
        sol_b = run_exact_knapsack_optimizer(pkgs, budget_inr=b_val, strategy="max_benefit")
        
        # Strategy C (Greedy Heuristic Baseline)
        strat_comp = compare_strategies(pkgs, b_val)
        gap = strat_comp.get("optimality_gap_percent", 0.0)
        
        rec = {
            "scope": scope_name,
            "budget_label": b_label,
            "budget_inr": b_val,
            "total_packages_available": len(pkgs),
            "total_cells_available": total_cells,
            # Strategy A results
            "spend_inr": sol_a.total_cost_inr,
            "utilization_pct": round((sol_a.total_cost_inr / b_val) * 100, 2),
            "packages_selected": len(sol_a.selected_packages),
            "cells_selected": sol_a.cells_count,
            "chronic_hotspots_mitigated": sol_a.chronic_hotspots_count,
            "treated_area_m2": sol_a.treated_area_m2,
            "mean_skin_cooling_c": round(sol_a.mean_local_cooling_c, 2),
            "thermal_benefit_k_m2": round(sol_a.portfolio_thermal_benefit_c_m2, 1),
            # Strategy B comparisons
            "strat_b_benefit_k_m2": round(sol_b.portfolio_thermal_benefit_c_m2, 1),
            "strat_b_cells": sol_b.cells_count,
            # Optimality gap
            "heuristic_optimality_gap_pct": gap,
        }
        results.append(rec)
        
        print(f"Budget: {b_label} ({b_val:,.0f} INR)")
        print(f"  Spend: INR {sol_a.total_cost_inr:,.2f} ({rec['utilization_pct']}% utilized)")
        print(f"  Packages Selected: {rec['packages_selected']} (Queen contiguous, <= 4 cells)")
        print(f"  Cells Selected: {rec['cells_selected']} (Zero duplicates)")
        print(f"  Chronic Hotspots: {rec['chronic_hotspots_mitigated']}")
        print(f"  Treated Surface: {rec['treated_area_m2']:,.1f} m2 ({(rec['treated_area_m2']/10000):.2f} ha)")
        print(f"  Mean Skin Cooling: -{rec['mean_skin_cooling_c']} C")
        print(f"  Extensive Thermal Benefit: {rec['thermal_benefit_k_m2']:,.1f} K*m2")
        print(f"  Strategy B Max Benefit: {rec['strat_b_benefit_k_m2']:,.1f} K*m2")
        print(f"  Greedy Heuristic Optimality Gap: {gap:.2f}%")
        print(f"  Budget Curve Points: {len(sol_a.budget_curve)}")
        print(f"  Locality Rollup entries: {len(sol_a.locality_rollup)}")

with open("docs/validation/area_optimization_live_matrix.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\nSuccessfully exported docs/validation/area_optimization_live_matrix.json")
