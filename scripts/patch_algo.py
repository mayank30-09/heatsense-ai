with open('backend/app/api/v1/interventions.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    else:  # 'exact' or strategy name default
        sol = run_exact_knapsack_optimizer(
            packages=packages,
            budget_inr=payload.budget_inr,
            strategy=payload.strategy or "hotspot_first",
        )
        sol.strategy_comparison = strat_comp
        solutions = [sol]
        rec_sol = sol"""

replacement = """    elif algo in ("exact", "knapsack", "integer_dp", "hotspot_first", "max_benefit", "cost_effective"):
        sol = run_exact_knapsack_optimizer(
            packages=packages,
            budget_inr=payload.budget_inr,
            strategy=payload.strategy or "hotspot_first",
        )
        sol.strategy_comparison = strat_comp
        solutions = [sol]
        rec_sol = sol
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported optimization algorithm '{payload.algorithm}'. Supported algorithms: 'greedy', 'nsga2', 'exact'.",
        )"""

if target in content:
    new_content = content.replace(target, replacement, 1)
    with open('backend/app/api/v1/interventions.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("PATCHED_SUCCESSFULLY")
else:
    print("TARGET_NOT_FOUND")
