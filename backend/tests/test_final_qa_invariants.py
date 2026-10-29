"""Final QA Invariants and Acceptance Tests for HEATSENSE AI Submission.

Verifies:
1. Exact public-works cost markup chain arithmetic reconstruction (direct + design + GST + contingency + site setup).
2. Portfolio cooling metric sign, units, and thermodynamic bounds.
3. Zero cell duplication across selected intervention candidates and packages.
4. Negative API inputs (malformed geometry, invalid algorithms, unauthenticated optimization).
5. Strict location-independence: zero hardcoded ward/locality names in recommendation logic.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from gis.interventions import InterventionType
from gis.interventions.candidates import generate_candidate_for_cell
from gis.interventions.costs import estimate_intervention_cost
from gis.interventions.cooling_effects import (
    calculate_portfolio_cooling_metrics,
    MAX_COMBINED_CELL_COOLING_C,
)
from gis.interventions.optimization import (
    Package,
    run_baseline_greedy_optimizer,
    run_exact_knapsack_optimizer,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Invariant 1: Exact Public-Works Cost Markup Chain
# ---------------------------------------------------------------------------
def test_cost_markup_chain_reconstruction():
    """Verify that Total Cost = Direct + Design + GST + Contingency + Site Setup for all typologies."""
    for itype in [
        InterventionType.COOL_ROOF,
        InterventionType.COOL_PAVEMENT,
        InterventionType.TREE_CANOPY,
        InterventionType.GREEN_ROOF,
    ]:
        base_cost, min_cost, max_cost, breakdown = estimate_intervention_cost(
            itype,
            usable_area_m2=2000.0,
            tree_count=50,
        )
        direct = breakdown["direct_cost"]
        design = breakdown["design_and_supervision_cost"]
        gst = breakdown["gst_18_pct"]
        contingency = breakdown["contingency_cost"]
        site_setup = breakdown.get("site_setup_scaled_cost", 0.0)

        # 1. Statutory GST is strictly 18% of (direct + design)
        subtotal_before_tax = direct + design
        assert gst == pytest.approx(subtotal_before_tax * 0.18, rel=1e-3)

        # 2. Total reconstruction check: Base capex strictly equals the sum of its itemized parts
        reconstructed_total = direct + design + gst + contingency + site_setup
        assert base_cost == pytest.approx(reconstructed_total, rel=1e-3)
        assert breakdown["capital_cost_inr"] == pytest.approx(reconstructed_total, rel=1e-3)

        # 3. Overall markup multiplier is between 1.35x and 1.50x
        multiplier = base_cost / direct
        assert 1.35 <= multiplier <= 1.50


# ---------------------------------------------------------------------------
# Invariant 2: Cooling Metric Signs, Units, and Thermodynamic Bounds
# ---------------------------------------------------------------------------
def test_portfolio_cooling_metric_signs_and_bounds():
    """Verify extensive and intensive cooling metrics have strictly positive magnitude."""
    cells = [
        {"usable_area_m2": 2500.0, "expected_cooling_c": 1.80, "baseline_hpi": 65.0},
        {"usable_area_m2": 3200.0, "expected_cooling_c": 2.10, "baseline_hpi": 72.0},
        {"usable_area_m2": 1800.0, "expected_cooling_c": 1.40, "baseline_hpi": 55.0},
    ]
    metrics = calculate_portfolio_cooling_metrics(cells)

    # Treated area is strictly positive m²
    assert metrics["treated_area_m2"] == 7500.0
    # Extensive benefit (°C·m²) is strictly positive
    expected_thermal = (2500.0 * 1.80) + (3200.0 * 2.10) + (1800.0 * 1.40)
    assert metrics["portfolio_thermal_benefit_c_m2"] == pytest.approx(expected_thermal, rel=1e-4)

    # Area-weighted intensive local cooling is strictly positive °C
    expected_mean = expected_thermal / 7500.0
    assert metrics["mean_local_cooling_c"] == pytest.approx(expected_mean, rel=1e-4)
    assert 0.0 < metrics["mean_local_cooling_c"] <= MAX_COMBINED_CELL_COOLING_C

    # Citywide cooling is strictly positive °C
    assert 0.0 < metrics["citywide_cooling_c"] < 1.0


# ---------------------------------------------------------------------------
# Invariant 3: Zero Cell Duplication Across Selected Candidates & Packages
# ---------------------------------------------------------------------------
def test_zero_cell_duplication_in_optimizers():
    """Verify that neither Greedy nor Exact knapsack selects overlapping or duplicate cells."""
    # 1. Candidate-level Greedy selection
    cands = []
    for i in range(1, 9):
        c1 = generate_candidate_for_cell(
            row=100 + i, col=100 + i, cell_id=f"R{100+i}_C{100+i}",
            intervention_type=InterventionType.COOL_ROOF,
            baseline_hpi=0.75, baseline_lst_c=42.0, is_chronic_hotspot=True,
            administrative_zone="Central Zone", usable_area_m2=2000.0,
        )
        c2 = generate_candidate_for_cell(
            row=100 + i, col=100 + i, cell_id=f"R{100+i}_C{100+i}",
            intervention_type=InterventionType.TREE_CANOPY,
            baseline_hpi=0.75, baseline_lst_c=42.0, is_chronic_hotspot=True,
            administrative_zone="Central Zone", usable_area_m2=1500.0,
        )
        cands.extend([c1, c2])

    greedy_sol = run_baseline_greedy_optimizer(cands, budget_inr=5000000.0)
    assert len(greedy_sol.selected_candidates) > 0
    greedy_cells = [c.cell_id for c in greedy_sol.selected_candidates]
    assert len(greedy_cells) == len(set(greedy_cells)), "Greedy must have ZERO duplicate cells"

    # 2. Package-level Exact DP selection
    pkgs = []
    for i in range(1, 6):
        p = Package(
            package_id=f"PKG_{i}",
            cluster_id=f"CLUST_{i}",
            locality="Area Alpha",
            intervention_type=InterventionType.COOL_ROOF,
            cell_ids=[f"CELL_A_{i}", f"CELL_B_{i}"],
            cell_count=2,
            cells=[],
            geographic_coverage_ha=0.185,
            treated_footprint_m2=3000.0,
            estimated_cost_inr=800000.0 * i,
            capex_breakdown={},
            opex_3yr_inr=80000.0,
            expected_cooling_c=1.8,
            delta_t_skin_c=8.59,
            delta_t_cell_c=1.8,
            thermal_benefit_k_m2=5400.0 * i,
            indicative_diluted_cooling_c=1.8,
            chronic_hotspot_cells_count=2,
            mean_hpi=70.0,
            max_hpi=75.0,
            landcover_summary={},
            confidence_rating="HIGH",
            unresolved_prerequisites=[],
        )
        pkgs.append(p)

    exact_sol = run_exact_knapsack_optimizer(pkgs, budget_inr=3000000.0)
    assert len(exact_sol.selected_packages) > 0
    exact_cells: list[str] = []
    for pkg in exact_sol.selected_packages:
        for cid in pkg.cell_ids:
            assert cid not in exact_cells, f"Exact DP duplicate cell found: {cid}"
            exact_cells.append(cid)


# ---------------------------------------------------------------------------
# Invariant 4: Negative API Inputs & Security Guardrails
# ---------------------------------------------------------------------------
def test_api_negative_inputs():
    """Verify proper HTTP error codes for invalid inputs."""
    # 1. Degenerate polygon (< 3 points) -> 400 Bad Request
    resp = client.post(
        "/api/v1/analysis/recommendations",
        json={"geometry": {"type": "Polygon", "coordinates": [[[72.8, 21.2], [72.81, 21.21]]]}},
    )
    assert resp.status_code == 400

    # 2. Polygon outside SMC study area -> handled cleanly (inside_smc_fraction == 0.0)
    resp = client.post(
        "/api/v1/analysis/recommendations",
        json={"geometry": {"type": "Polygon", "coordinates": [[[77.2, 28.6], [77.21, 28.6], [77.21, 28.61], [77.2, 28.6]]]}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["polygon_summary"]["inside_smc_fraction"] == 0.0
    assert data["polygon_summary"]["cell_count"] == 0

    # 3. Invalid optimization algorithm -> 400 or 401/403/422
    resp = client.post(
        "/api/v1/interventions/optimize",
        json={"budget_inr": 25000000.0, "algorithm": "quantum_annealing"},
    )
    assert resp.status_code in [400, 401, 403, 422]


# ---------------------------------------------------------------------------
# Invariant 5: Strict Location Independence
# ---------------------------------------------------------------------------
def test_zero_locality_names_in_recommendation_logic():
    """Verify that recommendation rules contain ZERO hardcoded ward/locality names."""
    known_localities = [
        "udhana", "katargam", "athwa", "varachha", "limbayat",
        "rander", "adajan", "vesu", "piplod", "pal", "pandesara",
        "amroli", "begumpura", "nanpura", "gopipura", "sagrampura",
    ]
    files_to_scan = [
        Path("gis/interventions/rules.py"),
        Path("gis/interventions/recommendations.py"),
        Path("gis/interventions/cooling_effects.py"),
        Path("gis/interventions/costs.py"),
    ]

    for p in files_to_scan:
        assert p.exists(), f"File {p} must exist"
        text = p.read_text(encoding="utf-8").lower()
        for loc in known_localities:
            # Match word boundary
            matches = re.findall(rf"\b{loc}\b", text)
            assert len(matches) == 0, f"Found hardcoded locality '{loc}' in {p}"
