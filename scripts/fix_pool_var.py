from pathlib import Path

p = Path("backend/app/api/v1/interventions.py")
content = p.read_text(encoding="utf-8")

old_part = """    # Determine if in-memory candidate pool was exhausted by the highest budget
    pool_exhausted = len(candidates) > 0 and len(sol.selected_candidates) >= len(candidates)

    return DiminishingReturnsResponse(
        algorithm="GREEDY_KNAPSACK",
        curve_points=curve_points,
        parameters={
            "max_candidates": payload.max_candidates,
            "effective_candidate_limit": effective_candidate_limit,
            "candidate_pool_size": len(candidates),
            "candidate_pool_exhausted": pool_exhausted,"""

new_part = """    # Determine if in-memory candidate pool was exhausted by the highest budget
    pool_exhausted = len(pool) > 0 and len(sol.selected_candidates) >= len(pool)

    return DiminishingReturnsResponse(
        algorithm="GREEDY_KNAPSACK",
        curve_points=curve_points,
        parameters={
            "max_candidates": payload.max_candidates,
            "effective_candidate_limit": effective_candidate_limit,
            "candidate_pool_size": len(pool),
            "candidate_pool_exhausted": pool_exhausted,"""

assert old_part in content, "old_part not found"
p.write_text(content.replace(old_part, new_part, 1), encoding="utf-8", newline="\n")
print("Fixed candidates -> pool in diminishing returns")

