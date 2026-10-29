import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

import urllib.request, json, time
from app.core.security import create_access_token

token = create_access_token("planner_officer", "planner")

url = "http://127.0.0.1:8000/api/v1/interventions/optimize"
algorithms = ["greedy", "exact", "nsga2"]
results = {}

for algo in algorithms:
    payload = {
        "budget_inr": 25000000.0,
        "algorithm": algo,
        "scope": "all",
        "strategy": "hotspot_first",
        "generations": 10 if algo == "nsga2" else None,
        "target_types": ["cool_roof", "tree_canopy", "cool_pavement"],
    }
    
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
    )
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            dt = time.time() - t0
            results[algo] = {
                "status": resp.status,
                "duration_s": round(dt, 3),
                "solutions_count": data.get("solutions_count"),
                "rec_cost": data.get("recommended_solution", {}).get("total_cost_inr"),
                "rec_pkgs": data.get("recommended_solution", {}).get("packages_count"),
                "budget_curve_pts": len(data.get("budget_curve", [])),
            }
    except Exception as e:
        results[algo] = {"error": str(e), "duration_s": round(time.time() - t0, 3)}

for k, v in results.items():
    print(f"Algorithm: {k:8s} -> {v}")
