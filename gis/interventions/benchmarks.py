"""Stage D Reproducible Benchmark Execution Engine.

Executes canonical optimization benchmarks on the materialized candidate catalog:
1. Baseline Constrained Greedy Knapsack Optimizer (1.0 Cr Budget).
2. NSGA-II Multi-Objective Evolutionary Optimizer (1.5 Cr Budget) with Pareto front extraction:
   - Solution 1: Max Extensive Cooling
   - Solution 2: Balanced Trade-Off
   - Solution 3: Low-Budget Entry

Persists all benchmark scenario records and candidate provenance into `stage_d_scenario_results`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any
import psycopg
from psycopg.rows import dict_row

from gis.interventions import (
    FeasibilityStatus,
    InterventionCandidate,
    InterventionType,
    RejectionReason,
)
from gis.interventions.cooling_effects import DEFAULT_SMC_DOMAIN_AREA_M2
from gis.interventions.optimization import (
    ScenarioSolution,
    run_baseline_greedy_optimizer,
    run_nsga2_optimizer,
)

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "stage_d"
load_dotenv(PROJECT_ROOT / ".env")


def get_db_connection() -> psycopg.Connection:
    """Connect to heatsense database using environment or .env configuration."""
    port = int(os.environ.get("POSTGRES_PORT", 5433))
    dbname = os.environ.get("POSTGRES_DB", "heatsense")
    user = os.environ.get("POSTGRES_USER", "heatsense")
    password = os.environ.get("POSTGRES_PASSWORD")
    host = os.environ.get("POSTGRES_HOST", "localhost")

    if not password:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            return psycopg.connect(
                db_url.replace("postgresql+psycopg://", "postgresql://"),
                autocommit=False,
            )
        raise ValueError("Database credentials not configured: POSTGRES_PASSWORD or DATABASE_URL required in .env.")

    return psycopg.connect(
        f"host={host} port={port} dbname={dbname} user={user} password={password}",
        autocommit=False,
    )


def load_feasible_candidates_from_db(
    conn: psycopg.Connection,
    min_hpi: float = 0.30,
    limit: int | None = None,
) -> list[InterventionCandidate]:
    """
    Load materialized feasible candidates from stage_d_intervention_candidates.
    """
    query = """
        SELECT
            candidate_id,
            cell_id,
            intervention_type,
            usable_area_m2,
            tree_count,
            cost_inr,
            cost_inr_min,
            cost_inr_max,
            expected_cooling_c,
            expected_cooling_c_min,
            expected_cooling_c_max,
            feasibility_status,
            rejection_reason,
            baseline_hpi,
            baseline_lst_c,
            is_chronic_hotspot,
            administrative_zone,
            evidence_status,
            ST_X(ST_Centroid(geometry)) as longitude,
            ST_Y(ST_Centroid(geometry)) as latitude
        FROM stage_d_intervention_candidates
        WHERE feasibility_status = 'FEASIBLE'
    """
    params: list[Any] = []
    if min_hpi > 0:
        query += " AND (baseline_hpi >= %s OR is_chronic_hotspot = TRUE)"
        params.append(min_hpi)

    query += " ORDER BY is_chronic_hotspot DESC, baseline_hpi DESC NULLS LAST"
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    candidates: list[InterventionCandidate] = []
    for r in rows:
        cand_id = r["candidate_id"]
        # Parse row/col from candidate_id (format CAND_TYPE_Rxxx_Cyyy)
        parts = cand_id.split("_")
        row_idx = int(parts[-2].replace("R", ""))
        col_idx = int(parts[-1].replace("C", ""))

        cand = InterventionCandidate(
            candidate_id=cand_id,
            cell_id=r["cell_id"],
            row=row_idx,
            col=col_idx,
            longitude=float(r["longitude"]) if r["longitude"] is not None else 72.83,
            latitude=float(r["latitude"]) if r["latitude"] is not None else 21.17,
            intervention_type=InterventionType(r["intervention_type"]),
            usable_area_m2=float(r["usable_area_m2"]),
            tree_count=int(r["tree_count"]),
            baseline_hpi=float(r["baseline_hpi"]) if r["baseline_hpi"] is not None else 0.5,
            baseline_lst_c=float(r["baseline_lst_c"]) if r["baseline_lst_c"] is not None else 38.0,
            is_chronic_hotspot=bool(r["is_chronic_hotspot"]),
            administrative_zone=r["administrative_zone"],
            feasibility_status=FeasibilityStatus(r["feasibility_status"]),
            rejection_reason=RejectionReason(r["rejection_reason"]),
            cost_inr=float(r["cost_inr"]),
            cost_inr_min=float(r["cost_inr_min"]),
            cost_inr_max=float(r["cost_inr_max"]),
            expected_cooling_c=float(r["expected_cooling_c"]),
            expected_cooling_c_min=float(r["expected_cooling_c_min"]),
            expected_cooling_c_max=float(r["expected_cooling_c_max"]),
            evidence_status=r["evidence_status"],
        )
        candidates.append(cand)

    return candidates


def persist_scenario_result(
    conn: psycopg.Connection,
    solution: ScenarioSolution,
    scenario_id: str,
    catalog_fingerprint: str = "CANONICAL_V1",
    scenario_description: str = "",
) -> None:
    """
    Persist an optimization scenario into stage_d_scenario_results with provenance.
    """
    selected_summary = [
        {
            "candidate_id": c.candidate_id,
            "cell_id": c.cell_id,
            "intervention_type": c.intervention_type.value,
            "usable_area_m2": c.usable_area_m2,
            "cost_inr": c.cost_inr,
            "expected_cooling_c": c.expected_cooling_c,
            "baseline_hpi": c.baseline_hpi,
            "is_chronic_hotspot": c.is_chronic_hotspot,
            "administrative_zone": c.administrative_zone,
        }
        for c in solution.selected_candidates
    ]

    payload_json = {
        "scenario_id": scenario_id,
        "scenario_description": scenario_description,
        "catalog_fingerprint": catalog_fingerprint,
        "algorithm": solution.algorithm,
        "budget_limit_inr": solution.budget_limit_inr,
        "budget_utilized_percent": solution.budget_utilized_percent,
        "crowding_distance": solution.crowding_distance,
        "execution_status": "COMPLETED",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "selected_candidate_ids": [c.candidate_id for c in solution.selected_candidates],
        "selected_candidates_summary": selected_summary,
    }

    insert_sql = """
        INSERT INTO stage_d_scenario_results (
            scenario_id, algorithm, budget_inr, total_cost_inr,
            portfolio_thermal_benefit_c_m2, treated_area_m2, mean_local_cooling_c,
            citywide_cooling_c, domain_area_m2, heat_priority_weighted_benefit_c_m2,
            population_exposure_benefit, population_exposure_status,
            total_cooling_c, heat_weighted_cooling, chronic_hotspots_count,
            interventions_count, is_feasible, pareto_rank, selected_candidates_json,
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP
        ) ON CONFLICT (scenario_id) DO UPDATE SET
            algorithm = EXCLUDED.algorithm,
            budget_inr = EXCLUDED.budget_inr,
            total_cost_inr = EXCLUDED.total_cost_inr,
            portfolio_thermal_benefit_c_m2 = EXCLUDED.portfolio_thermal_benefit_c_m2,
            treated_area_m2 = EXCLUDED.treated_area_m2,
            mean_local_cooling_c = EXCLUDED.mean_local_cooling_c,
            citywide_cooling_c = EXCLUDED.citywide_cooling_c,
            domain_area_m2 = EXCLUDED.domain_area_m2,
            heat_priority_weighted_benefit_c_m2 = EXCLUDED.heat_priority_weighted_benefit_c_m2,
            population_exposure_benefit = EXCLUDED.population_exposure_benefit,
            population_exposure_status = EXCLUDED.population_exposure_status,
            total_cooling_c = EXCLUDED.total_cooling_c,
            heat_weighted_cooling = EXCLUDED.heat_weighted_cooling,
            chronic_hotspots_count = EXCLUDED.chronic_hotspots_count,
            interventions_count = EXCLUDED.interventions_count,
            is_feasible = EXCLUDED.is_feasible,
            pareto_rank = EXCLUDED.pareto_rank,
            selected_candidates_json = EXCLUDED.selected_candidates_json,
            created_at = CURRENT_TIMESTAMP;
    """

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                insert_sql,
                (
                    scenario_id,
                    solution.algorithm,
                    round(solution.budget_limit_inr, 2),
                    round(solution.total_cost_inr, 2),
                    round(solution.portfolio_thermal_benefit_c_m2, 2),
                    round(solution.treated_area_m2, 2),
                    round(solution.mean_local_cooling_c, 3),
                    round(solution.citywide_cooling_c, 6),
                    round(solution.domain_area_m2, 2),
                    round(solution.heat_priority_weighted_benefit_c_m2, 2),
                    solution.population_exposure_benefit,
                    solution.population_exposure_status,
                    round(solution.mean_local_cooling_c, 3),  # legacy alias
                    round(solution.heat_priority_weighted_benefit_c_m2, 2),  # legacy alias
                    solution.chronic_hotspots_count,
                    solution.interventions_count,
                    solution.is_feasible,
                    solution.pareto_rank,
                    json.dumps(payload_json),
                ),
            )


def run_stage_d_reproducible_benchmark(
    conn: psycopg.Connection | None = None,
) -> dict[str, Any]:
    """
    Run and persist the canonical Stage D benchmarks for Surat Municipal Corporation.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    t0 = time.time()
    try:
        # 1. Load catalog fingerprint if manifest exists
        catalog_manifest_path = ARTIFACTS_DIR / "stage_d_candidate_catalog_manifest.json"
        catalog_fingerprint = "UNKNOWN"
        if catalog_manifest_path.exists():
            with open(catalog_manifest_path, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
                catalog_fingerprint = cat_data.get("catalog_fingerprint", "UNKNOWN")

        # 2. Load all feasible candidates for Greedy Knapsack (evaluated across full catalog)
        print("Loading feasible candidates for Greedy Knapsack...")
        greedy_pool = load_feasible_candidates_from_db(conn, min_hpi=0.30)
        if not greedy_pool:
            raise RuntimeError("No feasible candidates found in stage_d_intervention_candidates! Run materialization first.")

        print(f"Loaded {len(greedy_pool)} feasible candidates for greedy optimization.")

        # Execute Greedy Baseline (₹10M Budget / 1 Crore INR)
        greedy_budget = 10_000_000.0
        greedy_sol = run_baseline_greedy_optimizer(
            candidates=greedy_pool,
            budget_inr=greedy_budget,
            enforce_cell_exclusivity=True,
            domain_area_m2=DEFAULT_SMC_DOMAIN_AREA_M2,
        )
        greedy_scenario_id = "SCENARIO_BASELINE_GREEDY_10M"
        persist_scenario_result(
            conn=conn,
            solution=greedy_sol,
            scenario_id=greedy_scenario_id,
            catalog_fingerprint=catalog_fingerprint,
            scenario_description="Baseline priority-ranked knapsack optimizer for 1 Crore INR budget with cell exclusivity.",
        )
        print(f"Greedy Knapsack Persisted: {greedy_sol.interventions_count} interventions, INR {greedy_sol.total_cost_inr:,.2f}")

        # 3. Load top priority candidates for NSGA-II multi-objective genetic algorithm (₹15M Budget)
        # Select all chronic hotspots + top thermal priority cells (total ~2,000 candidates)
        print("Loading high-priority candidate pool for NSGA-II multi-objective search...")
        nsga2_pool = load_feasible_candidates_from_db(conn, min_hpi=0.55, limit=2000)
        print(f"Loaded {len(nsga2_pool)} priority candidates for NSGA-II.")

        nsga2_budget = 15_000_000.0
        pareto_front = run_nsga2_optimizer(
            candidates=nsga2_pool,
            budget_inr=nsga2_budget,
            population_size=40,
            generations=25,
            random_seed=42,
            domain_area_m2=DEFAULT_SMC_DOMAIN_AREA_M2,
        )

        if not pareto_front:
            raise RuntimeError("NSGA-II failed to generate Pareto solutions.")

        print(f"NSGA-II generated {len(pareto_front)} non-dominated Rank 1 Pareto solutions.")

        # Extract 3 canonical benchmark solutions along the front:
        # Sol 1: Max Cooling (first in list sorted by extensive benefit)
        sol_max_cooling = pareto_front[0]
        # Sol 2: Balanced Trade-Off (~70-80% budget utilization)
        balanced_candidates = [
            s for s in pareto_front if 65.0 <= s.budget_utilized_percent <= 85.0 and s.interventions_count > 0
        ]
        sol_balanced = balanced_candidates[0] if balanced_candidates else pareto_front[len(pareto_front) // 2]
        # Sol 3: Low-Budget Entry (~40-55% budget utilization)
        low_budget_candidates = [
            s for s in pareto_front if 30.0 <= s.budget_utilized_percent <= 60.0 and s.interventions_count > 0
        ]
        sol_low_budget = low_budget_candidates[-1] if low_budget_candidates else pareto_front[-1]

        scenarios_to_persist = [
            (sol_max_cooling, "SCENARIO_NSGA2_MAX_COOLING_15M", "NSGA-II Pareto Solution 1: Maximum extensive thermal cooling benefit under 1.5 Cr budget."),
            (sol_balanced, "SCENARIO_NSGA2_BALANCED_15M", "NSGA-II Pareto Solution 2: Balanced trade-off between capital investment and thermal impact."),
            (sol_low_budget, "SCENARIO_NSGA2_LOW_BUDGET_15M", "NSGA-II Pareto Solution 3: Cost-conservative entry-level mitigation deployment."),
        ]

        for sol, sc_id, desc in scenarios_to_persist:
            persist_scenario_result(
                conn=conn,
                solution=sol,
                scenario_id=sc_id,
                catalog_fingerprint=catalog_fingerprint,
                scenario_description=desc,
            )
            print(f"NSGA-II Solution Persisted ({sc_id}): {sol.interventions_count} interventions, INR {sol.total_cost_inr:,.2f}")

        duration = round(time.time() - t0, 2)
        benchmark_results = {
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "catalog_fingerprint": catalog_fingerprint,
            "execution_duration_seconds": duration,
            "scenarios": {
                "greedy_knapsack": greedy_sol.to_dict(),
                "nsga2_max_cooling": sol_max_cooling.to_dict(),
                "nsga2_balanced": sol_balanced.to_dict(),
                "nsga2_low_budget": sol_low_budget.to_dict(),
            },
        }

        # Export manifest to artifacts/stage_d/
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = ARTIFACTS_DIR / "stage_d_benchmark_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_results, f, indent=2)

        return benchmark_results

    finally:
        if should_close:
            conn.close()
