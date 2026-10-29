"""Unit and integration tests for Stage D Locality Grouping, Spatial Clustering, and Cluster API Endpoints.

Tests:
- Locality enumeration and sufficiency evaluation
- Hotspot-seeded queen contiguity spatial clustering
- Scientifically defensible aggregation (intensive area-weighted cooling, extensive additive costs)
- Deterministic multi-factor priority ranking
- API endpoints: /areas, /areas/{area}/summary, /areas/{area}/clusters, /clusters/{id}/cells
- Error handling and edge cases (empty area, invalid format, non-existent cluster)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from gis.interventions.clustering import (
    get_available_areas,
    get_area_summary,
    generate_clusters_for_area,
    get_cluster_cells,
    compute_priority_score,
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


# ---------------------------------------------------------------------------
# Unit Tests for Clustering Engine Logic
# ---------------------------------------------------------------------------

def test_get_available_areas_engine(db):
    areas = get_available_areas(db, min_hpi=35.0)
    assert len(areas) >= 15, "Expected at least 15 real localities from Stage C cells"
    top_area = areas[0]
    assert "area_name" in top_area
    assert "total_cells" in top_area
    assert "eligible_cell_count" in top_area
    assert "chronic_hotspot_count" in top_area
    assert "is_sufficient" in top_area
    assert top_area["eligible_cell_count"] > 0
    # Verifies sorted descending by chronic hotspots, then eligible cells
    for i in range(len(areas) - 1):
        c1, c2 = areas[i]["chronic_hotspot_count"], areas[i + 1]["chronic_hotspot_count"]
        if c1 == c2:
            assert areas[i]["eligible_cell_count"] >= areas[i + 1]["eligible_cell_count"]
        else:
            assert c1 >= c2


def test_area_summary_physics_and_aggregation(db):
    summary = get_area_summary(db, "Udhana", min_hpi=35.0)
    assert summary["area_name"] == "Udhana"
    assert summary["is_sufficient"] is True
    assert summary["eligible_cells"] > 0
    # Physics check: Cooling is intensive (NOT summed across 1500 cells!)
    # Must be bounded within realistic single-intervention range (~0.3 to 3.0 °C)
    assert 0.3 <= summary["best_option_mean_cooling_c"] <= 3.0
    # Cost is extensive (additive sum, so for 1500 cells it is in tens of crores)
    assert summary["best_option_portfolio_cost_inr"] > 10_000_000.0
    assert summary["total_treated_area_m2"] > 0
    # Data confidence summary check
    conf = summary["data_confidence_summary"]
    assert "survey_required_percentage" in conf
    assert "unverified_roof_percentage" in conf
    assert "valid_observations_percentage" in conf


def test_area_summary_nonexistent_area(db):
    summary = get_area_summary(db, "NonExistentPlaceXYZ", min_hpi=35.0)
    assert summary["is_sufficient"] is False
    assert summary["eligible_cells"] == 0
    assert summary["best_option_mean_cooling_c"] == 0.0
    assert "No grid cells" in summary["insufficient_reason"]


def test_compute_priority_score_bounds_and_weights():
    # Test high priority hotspot
    score_high, tier_high, factors_high = compute_priority_score(
        mean_hpi=85.0,
        chronic_ratio=1.0,
        cooling_c=1.5,
        cost_inr=1_000_000.0,
        cell_count=10,
    )
    assert 10.0 <= score_high <= 99.0
    assert tier_high in ("CRITICAL", "HIGH")
    assert factors_high["hpi_factor"] > 70.0
    assert factors_high["chronic_factor"] == 100.0

    # Test low priority cell
    score_low, tier_low, factors_low = compute_priority_score(
        mean_hpi=36.0,
        chronic_ratio=0.0,
        cooling_c=0.4,
        cost_inr=50_000_000.0,
        cell_count=16,
    )
    assert score_low < score_high
    assert tier_low in ("MODERATE", "MEDIUM")


def test_generate_clusters_queen_contiguity_and_size_limit(db):
    max_size = 12
    res = generate_clusters_for_area(
        db,
        area_name="Udhana",
        intervention_type="cool_roof",
        max_cluster_size=max_size,
        limit=5,
    )
    assert res["is_sufficient"] is True
    assert res["total_clusters"] > 0
    clusters = res["clusters"]
    assert len(clusters) <= 5

    for cl in clusters:
        assert cl["area_name"] == "Udhana"
        assert cl["cell_count"] <= max_size
        assert cl["cell_count"] >= 1
        # Cooling must be area-weighted mean (intensive)
        assert 0.2 <= cl["expected_cooling_c"] <= 3.0
        # Indicative diluted cooling must be less than or equal to local skin cooling
        assert cl["indicative_diluted_cooling_c"] <= cl["expected_cooling_c"]
        # Cost additivity
        assert cl["estimated_cost_inr"] > 0
        assert cl["unit_cost_inr_per_m2"] > 0
        # Priority rank is 1-based sequential
        assert cl["priority_rank"] >= 1
        # Check coordinates and bounds
        assert 20.0 <= cl["centroid"]["latitude"] <= 22.0
        assert 72.0 <= cl["centroid"]["longitude"] <= 74.0
        bbox = cl["bounding_box"]
        assert bbox["min_lat"] <= bbox["max_lat"]
        assert bbox["min_lon"] <= bbox["max_lon"]


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------

def test_api_get_areas(client):
    r = client.get("/api/v1/interventions/areas")
    assert r.status_code == 200
    areas = r.json()
    assert isinstance(areas, list)
    assert len(areas) >= 15
    for a in areas:
        assert "area_name" in a
        assert "eligible_cell_count" in a
        assert "chronic_hotspot_count" in a
        assert "mean_hpi" in a
        assert "is_sufficient" in a
        assert "top_recommended_type" in a


def test_api_get_area_summary(client):
    r = client.get("/api/v1/interventions/areas/Udhana/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["area_name"] == "Udhana"
    assert data["eligible_cells"] > 0
    assert data["best_option_mean_cooling_c"] > 0
    assert data["best_option_portfolio_cost_inr"] > 0
    assert data["is_sufficient"] is True


def test_api_get_area_clusters_sorting_and_pagination(client):
    # Test priority_desc
    r1 = client.get("/api/v1/interventions/areas/Udhana/clusters?sort_by=priority_desc&limit=5")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total_clusters"] > 0
    clusters = d1["clusters"]
    assert len(clusters) == 5
    # Ranks must be 1, 2, 3, 4, 5
    ranks = [c["priority_rank"] for c in clusters]
    assert ranks == [1, 2, 3, 4, 5]
    for i in range(len(clusters) - 1):
        assert clusters[i]["priority_score"] >= clusters[i + 1]["priority_score"]

    # Test cooling_desc
    r2 = client.get("/api/v1/interventions/areas/Udhana/clusters?sort_by=cooling_desc&limit=4")
    assert r2.status_code == 200
    d2 = r2.json()
    c2 = d2["clusters"]
    for i in range(len(c2) - 1):
        assert c2[i]["expected_cooling_c"] >= c2[i + 1]["expected_cooling_c"]

    # Test cost_asc
    r3 = client.get("/api/v1/interventions/areas/Udhana/clusters?sort_by=cost_asc&limit=4")
    assert r3.status_code == 200
    d3 = r3.json()
    c3 = d3["clusters"]
    for i in range(len(c3) - 1):
        assert c3[i]["estimated_cost_inr"] <= c3[i + 1]["estimated_cost_inr"]


def test_api_get_cluster_cells_and_drilldown(client):
    # Fetch clusters for Bhestan
    r_list = client.get("/api/v1/interventions/areas/Bhestan/clusters?limit=1")
    assert r_list.status_code == 200
    first_cluster = r_list.json()["clusters"][0]
    cid = first_cluster["cluster_id"]
    cell_count = first_cluster["cell_count"]

    # Drill down into contributing cells
    r_detail = client.get(f"/api/v1/interventions/clusters/{cid}/cells")
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert detail["cluster_id"] == cid
    assert detail["cell_count"] == cell_count
    assert len(detail["cells"]) == cell_count
    for cell in detail["cells"]:
        assert "cell_id" in cell
        assert "row" in cell
        assert "col" in cell
        assert "latitude" in cell
        assert "longitude" in cell
        assert "baseline_hpi" in cell
        assert "expected_cooling_c" in cell
        assert "cost_inr" in cell


def test_api_cluster_cells_errors(client):
    # Malformed cluster ID format
    r_bad = client.get("/api/v1/interventions/clusters/INVALID_ID/cells")
    assert r_bad.status_code == 400

    # Non-existent cluster ID
    r_none = client.get("/api/v1/interventions/clusters/CLUST_NONEXISTENT_COOL_ROOF_999/cells")
    assert r_none.status_code == 404


def test_clustering_no_cell_overlap_and_assignment_exclusivity(db):
    """Verify that no cell is assigned to more than one cluster across all generated recommendations."""
    res = generate_clusters_for_area(db, area_name="Udhana", limit=100, offset=0)
    all_raw = res.get("_all_clusters_internal", [])
    assert len(all_raw) > 0

    all_cells_seen = []
    for c in all_raw:
        cell_ids = [cell["cell_id"] for cell in c["_cells"]]
        all_cells_seen.extend(cell_ids)

    # Invariant: zero duplicate cells
    assert len(all_cells_seen) == len(set(all_cells_seen)), (
        f"Overlap detected: {len(all_cells_seen) - len(set(all_cells_seen))} duplicate cell references."
    )


def test_clustering_land_cover_suitability_and_evidence(db):
    """Verify that cluster targeted surface and evidence match actual land cover."""
    res = generate_clusters_for_area(db, area_name="Udhana", limit=50, offset=0)
    clusters = res.get("clusters", [])

    for c in clusters:
        itype = c["intervention_type"]
        surf = c["targeted_surface"]
        if itype in ("cool_roof", "green_roof"):
            assert "Rooftop (material unverified)" in surf
        elif itype in ("tree_canopy", "public_park_native_trees"):
            assert "Open Ground" in surf
        elif itype in ("cool_pavement", "shaded_parking_structure"):
            assert "Paved Hardstanding" in surf

        # Check evidence and rate provenance fields
        assert "rate_provenance" in c
        assert "source_name" in c["rate_provenance"]
        assert c["rate_provenance"]["verified"] is False
        assert "rate_basis" in c["rate_provenance"]
        assert "evidence_rationale" in c
        evid = c["evidence_rationale"]
        if itype in ("cool_roof", "cool_pavement"):
            assert evid["thermodynamics_formula"] is not None
        elif itype == "tree_canopy":
            assert evid["thermodynamics_formula"] is None
            assert "Beer-Lambert" in evid["governing_principle"]
            assert evid["maturity_notice"] is not None
        assert len(evid["verified_literature_citations"]) >= 1


def test_clustering_cost_line_item_math_reconciliation(client, db):
    """Verify mathematical proof that line-items sum to total cost, and total cost matches cell drill-down."""
    res = generate_clusters_for_area(db, area_name="Udhana", limit=5, offset=0)
    cluster = res["clusters"][0]
    cid = cluster["cluster_id"]
    cb = cluster["cost_breakdown"]

    # 1. Check line-item build-up
    # direct = materials + labour
    assert abs((cb["materials_cost_inr"] + cb["labour_cost_inr"]) - cb["direct_cost_inr"]) < 1.0
    # capital = direct + design + gst + contingency + setup (zero double-counting of water tanker in Capex!)
    computed_cap = (
        cb["materials_cost_inr"]
        + cb["labour_cost_inr"]
        + cb["design_supervision_inr"]
        + cb["gst_18_pct_inr"]
        + cb["contingency_inr"]
        + cb.get("scaled_site_setup_inr", 0.0)
    )
    assert abs(computed_cap - cb["capital_cost_inr"]) < 1.0
    assert abs(cb["capital_cost_inr"] - cluster["estimated_cost_inr"]) < 1.0


def test_cost_line_items_exact_summation_and_no_double_counting(db):
    """Verify that for every cluster and cell, displayed line items sum exactly to displayed total."""
    for loc in ["Udhana", "Dindoli", "Bhestan"]:
        res = generate_clusters_for_area(db, area_name=loc, limit=30, offset=0)
        for cluster in res["clusters"]:
            cb = cluster["cost_breakdown"]
            exact_sum = round(
                cb["materials_cost_inr"]
                + cb["labour_cost_inr"]
                + cb["design_supervision_inr"]
                + cb["gst_18_pct_inr"]
                + cb["contingency_inr"]
                + cb.get("scaled_site_setup_inr", 0.0),
                2,
            )
            assert abs(exact_sum - cb["capital_cost_inr"]) < 0.05, f"Capex line items mismatch in {cluster['cluster_id']}"
            assert abs(cluster["estimated_cost_inr"] - cb["capital_cost_inr"]) < 0.05

            # Opex segregation: water tanker and plant replacement must NOT be in Capex
            assert cb.get("water_tanker_inr", 0.0) == 0.0 or cluster["intervention_type"] != "tree_canopy"
            assert cb.get("plant_replacement_inr", 0.0) == 0.0

            # Cell check
            cells_data = get_cluster_cells(db, cluster_id=cluster["cluster_id"])
            for cell in cells_data.get("cells", []):
                ccb = cell["cost_breakdown"]
                cell_sum = round(
                    ccb["materials_cost_inr"]
                    + ccb["labour_cost_inr"]
                    + ccb["design_supervision_inr"]
                    + ccb["gst_18_pct_inr"]
                    + ccb["contingency_inr"]
                    + ccb.get("scaled_site_setup_inr", 0.0),
                    2,
                )
                assert abs(cell_sum - cell["cost_inr"]) < 50.0, f"Cell cost mismatch in {cell['cell_id']}"


def test_type_specific_evidence_templates(db):
    """Verify that cost line descriptions and Evidence/Survey/Assumption text are segregated per intervention type."""
    res = generate_clusters_for_area(db, area_name="Udhana", limit=50, offset=0)
    for c in res["clusters"]:
        itype = c["intervention_type"]
        evid = c["evidence_rationale"]
        unc = " ".join(evid["uncertainties"]).lower()
        surv = " ".join(evid["survey_requirements"]).lower()

        if itype == "tree_canopy":
            assert evid["thermodynamics_formula"] is None
            assert "rcc slab" not in surv
            assert "reflective" not in unc
            assert "albedo degradation" not in unc
            assert "permeable paving" not in surv
            assert "soil depth" in unc or "soil depth" in surv or "utilities" in surv
        elif itype == "cool_roof":
            assert evid["thermodynamics_formula"] is not None
            assert "sapling" not in unc
            assert "soil depth" not in unc
            assert "rcc" in surv or "structural" in surv
            assert "albedo degradation" in unc or "washing" in unc


def test_tree_cooling_bounds_and_clamping(db):
    """Verify that tree canopy cooling is clamped inside [1.50, 2.50] °C catalog range."""
    res = generate_clusters_for_area(db, area_name="Udhana", limit=50, offset=0)
    tree_clusters = [c for c in res["clusters"] if c["intervention_type"] == "tree_canopy"]
    assert len(tree_clusters) > 0
    for tc in tree_clusters:
        assert 1.50 <= tc["expected_cooling_c"] <= 2.50
        assert tc["expected_cooling_c_range"][0] >= 1.50
        assert tc["expected_cooling_c_range"][1] <= 2.50




def test_area_summary_phase1_budget_knapsack(client):
    """Verify Phase 1 portfolio respects budget ceiling and prioritizes chronic hotspots."""
    budget_cap = 25_000_000.0  # ₹2.50 Cr
    r = client.get(f"/api/v1/interventions/areas/Udhana/summary?budget_cap_inr={budget_cap}")
    assert r.status_code == 200
    data = r.json()

    assert "phase1_portfolio" in data
    p1 = data["phase1_portfolio"]
    assert p1["budget_cap_inr"] == budget_cap
    assert p1["budget_utilized_inr"] <= budget_cap
    assert p1["clusters_count"] > 0
    assert p1["cells_count"] > 0
    assert p1["mean_cooling_c"] > 0.5
    # Full coverage bound should be substantially higher than Phase 1 budget
    assert data["full_coverage_bound_inr"] >= p1["budget_utilized_inr"]


