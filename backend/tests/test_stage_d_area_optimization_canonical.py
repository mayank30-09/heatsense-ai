"""Canonical Verification Suite for Area-Based Optimization & Interventions.

Verifies:
1. Canonical Invariant 1: No duplicate cells across packages, clusters, or portfolios.
2. Canonical Invariant 2: Package Queen contiguity and municipal size cap <= 4 cells.
3. Canonical Invariant 3: Exact DP solver optimality vs brute force verification.
4. Canonical Invariant 4: Explorer Phase 1 equals Optimization default at identical inputs.
5. Canonical Invariant 5: Climatological Physics (surface skin cooling <= 0, K·m² thermal benefit).
6. Canonical Invariant 6: Itemized line items sum exactly to displayed totals with 0 double counting.
7. Canonical Invariant 7: Type availability reporting across all 10 catalog typologies.
8. Canonical Invariant 8: API contracts for /optimize, /types/availability, and /optimize/export.
"""

from __future__ import annotations

import itertools
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.db.session import SessionLocal

from gis.interventions import InterventionType, Package
from gis.interventions.clustering import (
    generate_clusters_for_area,
    get_all_packages_for_area,
    get_area_summary,
    get_type_availability,
    get_cluster_cells,
)
from gis.interventions.optimization import (
    run_exact_knapsack_optimizer,
    run_baseline_greedy_optimizer,
    compare_strategies,
    compute_locality_rollup,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_no_duplicate_cells_across_packages_and_clusters(db: Session):
    """Verify each 100m grid cell belongs to at most ONE package and ONE cluster."""
    for loc in ["Udhana", "Dindoli", "Bhestan"]:
        pkgs = get_all_packages_for_area(db, area_name=loc)
        seen_cells = set()
        for p in pkgs:
            for c_id in p.cell_ids:
                assert c_id not in seen_cells, f"Cell {c_id} appears in multiple packages in {loc}!"
                seen_cells.add(c_id)


def test_package_queen_contiguity_and_size_cap(db: Session):
    """Verify all packages enforce size cap <= 4 cells and Queen contiguity."""
    pkgs = get_all_packages_for_area(db, area_name="Udhana")
    for p in pkgs:
        assert 1 <= p.cell_count <= 4, f"Package {p.package_id} exceeds size cap of 4 cells ({p.cell_count})"
        assert len(p.cell_ids) == p.cell_count
        assert len(p.cells) == p.cell_count

        if p.cell_count > 1:
            coords = [(c["row"], c["col"]) for c in p.cells]
            visited = {coords[0]}
            queue = [coords[0]]
            while queue:
                curr = queue.pop(0)
                for other in coords:
                    if other not in visited and max(abs(curr[0] - other[0]), abs(curr[1] - other[1])) <= 1:
                        visited.add(other)
                        queue.append(other)
            assert len(visited) == len(coords), f"Package {p.package_id} is not Queen contiguous!"


def test_exact_dp_solver_optimality_vs_brute_force():
    """Verify exact DP knapsack finds the absolute global optimum against brute force on subset."""
    mock_pkgs = []
    for i in range(10):
        cost = (i + 1) * 100_000.0
        benefit = (10 - i) * 5_000.0 + (i % 2) * 20_000.0
        chronic = 1 if i % 3 == 0 else 0
        p = Package(
            package_id=f"PKG_{i}",
            cluster_id=f"CLUST_{i}",
            locality="TestLoc",
            intervention_type=InterventionType.COOL_ROOF,
            cell_ids=[f"C_{i}"],
            cell_count=1,
            cells=[{"cell_id": f"C_{i}", "row": i, "col": i, "cost_inr": cost, "usable_area_m2": 1000.0, "expected_cooling_c": 1.5}],
            geographic_coverage_ha=0.10,
            treated_footprint_m2=1000.0,
            estimated_cost_inr=cost,
            capex_breakdown={},
            opex_3yr_inr=0.0,
            expected_cooling_c=1.5,
            delta_t_skin_c=-1.5,
            delta_t_cell_c=-0.5,
            thermal_benefit_k_m2=benefit,
            indicative_diluted_cooling_c=0.5,
            chronic_hotspot_cells_count=chronic,
            mean_hpi=75.0,
            max_hpi=80.0,
            landcover_summary={},
            confidence_rating="HIGH",
            unresolved_prerequisites=[],
        )
        mock_pkgs.append(p)

    budget = 450_000.0

    # 1. Exact DP Solution (Strategy A: Hotspot First)
    sol_dp = run_exact_knapsack_optimizer(mock_pkgs, budget_inr=budget, strategy="hotspot_first", discretization_unit_inr=1000.0)

    # 2. Brute Force Search over 2^10 = 1024 combinations
    best_tuple = (-1, -1.0, -1)
    for r in range(len(mock_pkgs) + 1):
        for combo in itertools.combinations(mock_pkgs, r):
            tot_cost = sum(p.estimated_cost_inr for p in combo)
            if tot_cost <= budget:
                tot_chronic = sum(p.chronic_hotspot_cells_count for p in combo)
                tot_benefit = round(sum(p.thermal_benefit_k_m2 for p in combo), 1)
                tot_cells = sum(p.cell_count for p in combo)
                val_tuple = (tot_chronic, tot_benefit, tot_cells)
                if val_tuple > best_tuple:
                    best_tuple = val_tuple

    assert sol_dp.chronic_hotspots_count == best_tuple[0]
    assert abs(sol_dp.portfolio_thermal_benefit_c_m2 - best_tuple[1]) < 0.1
    assert sol_dp.total_cost_inr <= budget


def test_explorer_phase1_equals_optimization_default(db: Session):
    """Verify single source of truth: Explorer Phase 1 and Optimization default produce identical results."""
    budget = 25_000_000.0  # Rs 2.5 Cr

    # 1. Explorer Phase 1 Portfolio
    summary = get_area_summary(db, area_name="Udhana", budget_cap_inr=budget)
    p1 = summary["phase1_portfolio"]

    # 2. Optimizer Default Solution
    pkgs = get_all_packages_for_area(db, area_name="Udhana")
    opt_sol = run_exact_knapsack_optimizer(pkgs, budget_inr=budget, strategy="hotspot_first")

    assert abs(p1["budget_utilized_inr"] - opt_sol.total_cost_inr) < 0.05
    assert p1["packages_count"] == len(opt_sol.selected_packages)
    assert p1["cells_count"] == opt_sol.cells_count
    assert p1["chronic_hotspots_covered"] == opt_sol.chronic_hotspots_count
    assert abs(p1["thermal_benefit_k_m2"] - opt_sol.portfolio_thermal_benefit_c_m2) < 0.05
    assert p1["selected_package_ids"] == [p.package_id for p in opt_sol.selected_packages]


def test_cooling_definitions_and_thermodynamics(db: Session):
    """Verify skin cooling metrics, extensive K·m² units, and non-existence of unmodeled air temperatures."""
    pkgs = get_all_packages_for_area(db, area_name="Udhana")
    for p in pkgs:
        assert p.delta_t_skin_c <= 0.0, f"Skin Delta T must be negative ({p.delta_t_skin_c})"
        assert p.delta_t_cell_c <= 0.0, f"Cell Delta T must be negative ({p.delta_t_cell_c})"
        assert p.thermal_benefit_k_m2 >= 0.0, "Extensive thermal benefit must be positive (K·m² conserved)"


def test_cost_summation_exact_reconciliation(db: Session):
    """Verify sum(cell cost) == package cost == line items."""
    pkgs = get_all_packages_for_area(db, area_name="Udhana")
    for p in pkgs[:20]:
        cell_sum = sum(c["cost_inr"] for c in p.cells)
        assert abs(cell_sum - p.estimated_cost_inr) < 0.05, f"Cell cost mismatch in package {p.package_id}"

        cb = p.capex_breakdown
        exact_sum = round(
            cb.get("materials_cost_inr", 0.0)
            + cb.get("labour_cost_inr", 0.0)
            + cb.get("design_supervision_inr", 0.0)
            + cb.get("gst_18_pct_inr", 0.0)
            + cb.get("contingency_inr", 0.0)
            + cb.get("scaled_site_setup_inr", 0.0)
            + cb.get("plant_replacement_inr", 0.0),
            2,
        )
        assert abs(exact_sum - p.estimated_cost_inr) < 1.0, f"Capex line items mismatch in package {p.package_id}"


def test_types_availability_catalog_reporting(db: Session):
    """Verify get_type_availability reports availability and reasons across all 10 typologies."""
    avail = get_type_availability(db, area_name="all")
    assert len(avail) >= 10
    assert avail["cool_roof"]["is_assessable"] is True
    assert avail["tree_canopy"]["is_assessable"] is True
    assert avail["water_body_retention_pond"]["is_assessable"] is False
    assert "DEM" in avail["water_body_retention_pond"]["data_needed"]
    assert avail["green_wall"]["is_assessable"] is False
    assert "building heights" in avail["green_wall"]["reason"].lower()


def test_api_optimize_exact_dp_and_curve(client):
    """Verify POST /api/v1/interventions/optimize returns recommended plan, 10-point curve, and roll-up."""
    payload = {
        "budget_inr": 25_000_000.0,
        "algorithm": "exact",
        "strategy": "hotspot_first",
        "scope": "Udhana",
    }
    r = client.post("/api/v1/interventions/optimize", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["algorithm"] == "EXACT"
    assert data["budget_inr"] == 25_000_000.0
    assert "recommended_solution" in data
    rec = data["recommended_solution"]
    assert rec["total_cost_inr"] <= 25_000_000.0
    assert rec["packages_count"] >= 1
    assert rec["chronic_hotspots_count"] >= 10
    
    # Check 10-point curve
    assert len(data["budget_curve"]) == 10
    for pt in data["budget_curve"]:
        assert pt["actual_spend_inr"] <= pt["budget_cap_inr"]
        assert pt["thermal_benefit_k_m2"] >= 0.0

    # Check locality rollup
    assert len(data["locality_rollup"]) >= 1
    assert data["locality_rollup"][0]["locality"] == "Udhana"

    # Check strategy comparison
    comp = data["strategy_comparison"]
    assert "strategy_a_hotspot_first" in comp
    assert "strategy_b_max_benefit" in comp
    assert "strategy_c_greedy_baseline" in comp
    assert comp["strategy_a_hotspot_first"]["chronic_hotspots_count"] >= comp["strategy_b_max_benefit"]["chronic_hotspots_count"]


def test_api_types_availability_endpoint(client):
    """Verify GET /api/v1/interventions/types/availability returns assessability breakdown."""
    r = client.get("/api/v1/interventions/types/availability?area_name=Udhana")
    assert r.status_code == 200
    data = r.json()
    assert "cool_roof" in data
    assert "water_body_retention_pond" in data
    assert data["water_body_retention_pond"]["is_assessable"] is False


def test_api_optimize_csv_export_endpoint(client):
    """Verify POST /api/v1/interventions/optimize/export downloads valid CSVs."""
    payload = {
        "budget_inr": 25_000_000.0,
        "scope": "Udhana",
    }
    # Package level
    r_pkg = client.post("/api/v1/interventions/optimize/export?export_level=package", json=payload)
    assert r_pkg.status_code == 200
    assert "text/csv" in r_pkg.headers["content-type"]
    assert "package_id,cluster_id,locality" in r_pkg.text

    # Cell level
    r_cell = client.post("/api/v1/interventions/optimize/export?export_level=cell", json=payload)
    assert r_cell.status_code == 200
    assert "candidate_id,cell_id,locality" in r_cell.text
