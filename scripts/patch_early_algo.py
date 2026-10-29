with open('backend/app/api/v1/interventions.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    algo = payload.algorithm.lower().replace("-", "_")
    scope = payload.scope or "all"

    # 1. Fetch candidate packages for scope"""

replacement = """    algo = payload.algorithm.lower().replace("-", "_")
    supported_algos = ("greedy", "baseline_greedy", "nsga2", "nsga_ii", "pareto", "exact", "knapsack", "integer_dp", "hotspot_first", "max_benefit", "cost_effective")
    if algo not in supported_algos:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported optimization algorithm '{payload.algorithm}'. Supported algorithms: 'greedy', 'nsga2', 'exact'.",
        )
    scope = payload.scope or "all"

    # 1. Fetch candidate packages for scope"""

if target in content:
    content = content.replace(target, replacement, 1)
    with open('backend/app/api/v1/interventions.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("EARLY_ALGO_CHECK_INSERTED")
else:
    print("TARGET_NOT_FOUND")
