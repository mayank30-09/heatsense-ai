"""FastAPI Integration Tests for Stage D Interventions and Optimization Endpoints.

Verifies:
1. Candidate listing endpoint with viewport bounding box and type filters.
2. Candidate detail endpoint with cost breakdowns and evidence status.
3. Constrained optimization endpoint for both Greedy Knapsack and NSGA-II Pareto algorithms.
4. Input validation: rejection of invalid bounding boxes and unsupported algorithms.
5. Reference planning scenarios listing.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from backend.app.core.auth import DEV_USERS_DB, User, require_planner_or_admin
from backend.app.main import app

client = TestClient(app)


def test_candidates_endpoint_basic():
    """Verify candidate listing returns valid JSON and expected schema."""
    resp = client.get("/api/v1/interventions/candidates?limit=10")
    assert resp.status_code == 200
    data = resp.json()

    assert "total_count" in data
    assert "items" in data
    assert len(data["items"]) <= 10

    if data["items"]:
        cand = data["items"][0]
        assert "candidate_id" in cand
        assert "cost_inr" in cand
        assert cand["cost_inr"] > 0
        assert "expected_cooling_c" in cand
        assert cand["expected_cooling_c"] > 0
        assert cand["evidence_status"] == "CALIBRATED_EMPIRICAL_MICROCLIMATE"
        assert cand["geometry"]["type"] == "Polygon"


def test_candidates_endpoint_type_and_bbox_filtering():
    """Verify filtering by intervention type and bounding box extent."""
    # Filter by tree_canopy
    resp = client.get("/api/v1/interventions/candidates?intervention_type=tree_canopy&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["intervention_type"] == "tree_canopy"

    # Filter with valid bounding box
    resp_bbox = client.get("/api/v1/interventions/candidates?bbox=72.75,21.10,72.90,21.25&limit=5")
    assert resp_bbox.status_code == 200

    # Malformed bounding box returns 400
    resp_bad = client.get("/api/v1/interventions/candidates?bbox=72.75,21.10")
    assert resp_bad.status_code == 400


def test_candidate_detail_endpoint():
    """Verify single candidate detail retrieval with breakdown."""
    valid_id = "CAND_TREE_CANOPY_R120_C150"
    resp = client.get(f"/api/v1/interventions/candidates/{valid_id}")
    assert resp.status_code == 200
    cand = resp.json()
    assert cand["candidate_id"] == valid_id
    assert cand["intervention_type"] == "tree_canopy"
    assert cand["tree_count"] == 50
    assert cand["cost_inr"] == 175000.0  # 50 trees * 3500 INR

    # Malformed candidate ID returns 400
    resp_bad = client.get("/api/v1/interventions/candidates/INVALID_ID_FORMAT")
    assert resp_bad.status_code == 400


def test_optimize_endpoint_greedy():
    """Verify greedy knapsack optimizer via API complies with budget constraint."""
    budget = 10000000.0  # 1 Crore INR
    payload = {
        "budget_inr": budget,
        "algorithm": "greedy",
        "max_candidates": 30,
    }
    resp = client.post("/api/v1/interventions/optimize", json=payload)
    assert resp.status_code == 200
    res = resp.json()

    assert res["algorithm"] == "GREEDY"
    assert res["solutions_count"] == 1
    sol = res["solutions"][0]
    assert sol["is_feasible"] is True
    assert sol["total_cost_inr"] <= budget
    assert sol["interventions_count"] > 0
    assert sol["total_expected_cooling_c"] > 0


def test_optimize_endpoint_nsga2():
    """Verify NSGA-II multi-objective genetic algorithm via API returns Pareto solutions."""
    budget = 15000000.0  # 1.5 Crore INR
    payload = {
        "budget_inr": budget,
        "algorithm": "nsga2",
        "max_candidates": 25,
        "generations": 8,
    }
    resp = client.post("/api/v1/interventions/optimize", json=payload)
    assert resp.status_code == 200
    res = resp.json()

    assert res["algorithm"] == "NSGA2"
    assert res["solutions_count"] >= 1
    for sol in res["solutions"]:
        assert sol["pareto_rank"] == 1
        assert sol["is_feasible"] is True
        assert sol["total_cost_inr"] <= budget


def test_optimize_endpoint_unsupported_algorithm():
    """Verify API rejects invalid optimization algorithm."""
    resp = client.post("/api/v1/interventions/optimize", json={"algorithm": "unsupported_algo"})
    assert resp.status_code == 400


def test_reference_scenarios_endpoint():
    """Verify standard municipal scenarios listing."""
    resp = client.get("/api/v1/interventions/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert isinstance(scenarios, list)
    assert len(scenarios) >= 2
    for sc in scenarios:
        assert "scenario_name" in sc
        assert sc["budget_inr"] > 0


def test_optimize_endpoint_auth_and_dev_token_removal():
    """Verify dev-token returns 404 and optimize enforces 401, 403, and 200."""
    # 1. Deprecated unauthenticated endpoint removed -> 404
    resp_dev_token = client.post("/api/v1/auth/dev-token")
    assert resp_dev_token.status_code == 404

    # Remove Stage D autouse override to test true endpoint authorization
    app.dependency_overrides.pop(require_planner_or_admin, None)
    try:
        payload = {
            "budget_inr": 1000000.0,
            "algorithm": "greedy",
            "max_candidates": 10,
        }
        # 2. No token -> 401 Unauthorized
        resp_no_token = client.post("/api/v1/interventions/optimize", json=payload)
        assert resp_no_token.status_code == 401

        # 3. Public-role token -> 403 Forbidden
        test_pw = os.environ.get("DEV_USER_PASSWORD", "test_throwaway_mock_password_2026")
        login_pub = client.post(
            "/api/v1/auth/login",
            json={"username": "public_user", "password": test_pw},
        )
        assert login_pub.status_code == 200
        pub_token = login_pub.json()["access_token"]
        resp_pub = client.post(
            "/api/v1/interventions/optimize",
            json=payload,
            headers={"Authorization": f"Bearer {pub_token}"},
        )
        assert resp_pub.status_code == 403

        # 4. Planner token via /auth/login -> 200 OK
        login_pln = client.post(
            "/api/v1/auth/login",
            json={"username": "planner_officer", "password": test_pw},
        )
        assert login_pln.status_code == 200
        pln_token = login_pln.json()["access_token"]
        resp_pln = client.post(
            "/api/v1/interventions/optimize",
            json=payload,
            headers={"Authorization": f"Bearer {pln_token}"},
        )
        assert resp_pln.status_code == 200
        assert resp_pln.json()["algorithm"] == "GREEDY"
    finally:
        planner = DEV_USERS_DB["planner_officer"]
        app.dependency_overrides[require_planner_or_admin] = lambda: User(**planner.model_dump())


def test_candidates_filtering_sorting_and_caching():
    """Verify server-side sorting, locality filter, and Cache-Control headers."""
    resp = client.get("/api/v1/interventions/candidates?sort_by=cost_asc&limit=15")
    assert resp.status_code == 200
    assert "cache-control" in resp.headers
    assert "public" in resp.headers["cache-control"]
    data = resp.json()
    items = data["items"]
    assert len(items) > 1
    # Check cost ascending
    costs = [i["cost_inr"] for i in items]
    assert costs == sorted(costs)

    # Test filtering by locality substring
    resp_loc = client.get("/api/v1/interventions/candidates?locality=Surat&limit=5")
    assert resp_loc.status_code == 200


def test_diminishing_returns_endpoint():
    """Verify real diminishing returns curve calculation across budget tiers."""
    payload = {
        "budgets_inr": [5000000.0, 25000000.0, 100000000.0],
        "max_candidates": 20,
    }
    resp = client.post("/api/v1/interventions/diminishing-returns", json=payload)
    assert resp.status_code == 200
    res = resp.json()
    assert res["algorithm"] == "GREEDY_KNAPSACK"
    points = res["curve_points"]
    assert len(points) == 3

    # Check diminishing returns properties: higher budget yields >= treated cells and higher cost
    assert points[0]["budget_inr"] == 5000000.0
    assert points[1]["budget_inr"] == 25000000.0
    assert points[2]["budget_inr"] == 100000000.0
    assert points[0]["total_cost_inr"] <= 5000000.0
    assert points[1]["total_cost_inr"] <= 25000000.0
    assert points[2]["total_cost_inr"] <= 100000000.0
    assert points[0]["treated_cells_count"] <= points[1]["treated_cells_count"]
    assert points[1]["treated_cells_count"] <= points[2]["treated_cells_count"]
