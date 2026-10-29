path_opt = 'gis/interventions/optimization.py'
with open(path_opt, 'r', encoding='utf-8') as f:
    opt_content = f.read()

target_opt = '''    # Discretization: use ceil so sum(weights)*unit >= sum(actual_cost), strictly guaranteeing spend <= budget
    unit = max(100.0, discretization_unit_inr)
    W = int(budget_inr / unit)
    n = len(eligible)
    weights = [max(1, int(math.ceil(p.estimated_cost_inr / unit))) for p in eligible]'''

replacement_opt = '''    # Discretization: use adaptive unit so W <= 1000, preventing exponential state space and memory spikes
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
    weights = [max(1, int(math.ceil(p.estimated_cost_inr / unit))) for p in eligible]'''

if target_opt in opt_content:
    opt_content = opt_content.replace(target_opt, replacement_opt, 1)
elif target_opt.replace('\n', '\r\n') in opt_content:
    opt_content = opt_content.replace(target_opt.replace('\n', '\r\n'), replacement_opt.replace('\n', '\r\n'), 1)
else:
    print('ERROR: target_opt not found in optimization.py')

with open(path_opt, 'w', encoding='utf-8') as f:
    f.write(opt_content)

print('Updated optimization.py')


# Now update backend/app/api/v1/interventions.py
path_api = 'backend/app/api/v1/interventions.py'
with open(path_api, 'r', encoding='utf-8') as f:
    api_content = f.read()

target_api = '''    # Common exact 10-point budget curve and locality rollup
    exact_a = run_exact_knapsack_optimizer(packages, budget_inr=payload.budget_inr, strategy="hotspot_first")
    budget_curve = exact_a.budget_curve
    locality_rollup = rec_sol.locality_rollup or compute_locality_rollup(rec_sol.selected_packages)'''

replacement_api = '''    # Common budget curve and locality rollup
    if algo in ("exact", "knapsack") and (payload.strategy or "hotspot_first") == "hotspot_first":
        budget_curve = rec_sol.budget_curve
    elif algo in ("greedy", "baseline_greedy"):
        # Build 10-point budget curve from greedy cumulative packages
        budget_curve = []
        sorted_pkgs = sorted(
            packages,
            key=lambda p: (
                p.chronic_hotspot_cells_count / max(100.0, p.estimated_cost_inr),
                p.thermal_benefit_k_m2 / max(100.0, p.estimated_cost_inr),
            ),
            reverse=True,
        )
        from gis.interventions.cooling_effects import DEFAULT_SMC_DOMAIN_AREA_M2
        for step in range(1, 11):
            target_b = payload.budget_inr * (step / 10.0)
            step_cost = 0.0
            step_benefit = 0.0
            step_cells = 0
            step_hotspots = 0
            for p in sorted_pkgs:
                if step_cost + p.estimated_cost_inr <= target_b:
                    step_cost += p.estimated_cost_inr
                    step_benefit += p.thermal_benefit_k_m2
                    step_cells += p.cell_count
                    step_hotspots += p.chronic_hotspot_cells_count
            budget_curve.append({
                "step": step,
                "target_budget_inr": round(target_b, 2),
                "actual_spend_inr": round(step_cost, 2),
                "thermal_benefit_k_m2": round(step_benefit, 1),
                "cells_count": step_cells,
                "chronic_hotspots_count": step_hotspots,
                "citywide_cooling_c": round(step_benefit / DEFAULT_SMC_DOMAIN_AREA_M2, 4),
            })
    else:
        exact_a = run_exact_knapsack_optimizer(
            packages,
            budget_inr=payload.budget_inr,
            strategy="hotspot_first",
            discretization_unit_inr=max(25000.0, payload.budget_inr / 1000.0),
        )
        budget_curve = exact_a.budget_curve

    locality_rollup = rec_sol.locality_rollup or compute_locality_rollup(rec_sol.selected_packages)'''

if target_api in api_content:
    api_content = api_content.replace(target_api, replacement_api, 1)
elif target_api.replace('\n', '\r\n') in api_content:
    api_content = api_content.replace(target_api.replace('\n', '\r\n'), replacement_api.replace('\n', '\r\n'), 1)
else:
    print('ERROR: target_api not found in interventions.py')

with open(path_api, 'w', encoding='utf-8') as f:
    f.write(api_content)

print('Updated interventions.py')
