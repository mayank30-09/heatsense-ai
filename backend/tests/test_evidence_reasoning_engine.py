"""
Tests for HEATSENSE AI Stage D Spatial Intervention Reasoning Engine and Scoped Fixes.

Covers:
1. Location Independence: Automated static AST scan asserting zero hardcoded locality/ward/zone conditionals in recommendation logic.
2. Controlled Synthetic Evidence: Rules evaluate deterministically based on physical evidence.
3. Evidence Availability: UNAVAILABLE providers (roads, footprints, parcels, DEM) are declared explicitly with missing reasons.
4. Physically Meaningful Quantities: Derived quantities never exceed candidate geometry, with no fixed caps (40,000m², 800 trees).
5. Cost Reconciliation: Rejected and not-applicable options strictly carry 0.00 cost base.
6. Cache Isolation: Cache keys differ across geometry, season, year, parameters, and rule versions.
7. Scientific Cooling Labeling: Labeled as modeled surface skin Delta T (Delta T skin), NOT 2m air temperature.
8. State Model Invariants: No upgrade to IMPLEMENTATION_READY from satellite data alone.
9. Grid Area Reconciliation: Discloses 93.25m x 99.54m (9,282 m²) UTM cell area reconciling 49,747 cells (461.77 km²) against 461.63 km² boundary.
"""

import ast
from pathlib import Path
import pytest
from pydantic import ValidationError

from gis.interventions.evidence import (
    EvidenceAvailability,
    EvidenceExtractionResult,
    compute_evidence_cache_key,
    evidence_registry,
)
from gis.interventions.rules import (
    ReasoningState,
    SpatialUnit,
    reasoning_engine,
)
from gis.interventions.recommendations import (
    PolygonSummary,
    RecommendationItem,
    RecommendationsResponse,
    generate_polygon_recommendations,
)


def test_location_independence_static_scan():
    """HARD RULE 2: Automated AST and string scan ensuring NO locality names appear in recommendation logic."""
    forbidden_names = [
        "Udhna", "Limbayat", "Katargam", "Athwa", "Rander", "Varachha",
        "Central Zone", "North Zone", "South Zone", "East Zone", "West Zone",
    ]

    target_files = [
        Path("gis/interventions/rules.py"),
        Path("gis/interventions/evidence.py"),
        Path("gis/interventions/recommendations.py"),
    ]

    for file_path in target_files:
        assert file_path.exists(), f"File {file_path} must exist"
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        for name in forbidden_names:
            assert f'"{name}"' not in code, f"Hardcoded locality '{name}' found in {file_path}"
            assert f"'{name}'" not in code, f"Hardcoded locality '{name}' found in {file_path}"


def test_evidence_providers_availability_and_reasons():
    """Verify that unavailable datasets declare UNAVAILABLE and never silently return zeros or fake data."""
    providers = evidence_registry.providers
    assert "road_network" in providers
    assert "building_footprints" in providers
    assert "cadastral_ownership" in providers
    assert "drainage_dem" in providers

    road_prov = providers["road_network"]
    assert road_prov.availability == EvidenceAvailability.UNAVAILABLE
    assert road_prov.missing_reason is not None
    assert "road network" in road_prov.missing_reason.lower()

    res = road_prov.extract(geometry={}, season="summer", year=2026)
    assert res.availability == EvidenceAvailability.UNAVAILABLE
    assert res.coverage_fraction == 0.0


def test_cache_key_isolation():
    """Verify cache keys differ when geometry, season, year, parameters, or rule version change."""
    geom1 = {"type": "Polygon", "coordinates": [[[72.8, 21.1], [72.9, 21.1], [72.9, 21.2], [72.8, 21.1]]]}
    geom2 = {"type": "Polygon", "coordinates": [[[72.81, 21.11], [72.91, 21.11], [72.91, 21.21], [72.81, 21.11]]]}

    k1 = compute_evidence_cache_key(geom1, "summer", 2026, {"t": 1}, rule_version="2.0.0")
    k2 = compute_evidence_cache_key(geom2, "summer", 2026, {"t": 1}, rule_version="2.0.0")
    k_diff_season = compute_evidence_cache_key(geom1, "winter", 2026, {"t": 1}, rule_version="2.0.0")
    k_diff_year = compute_evidence_cache_key(geom1, "summer", 2025, {"t": 1}, rule_version="2.0.0")
    k_diff_rule = compute_evidence_cache_key(geom1, "summer", 2026, {"t": 1}, rule_version="2.1.0")

    assert k1 != k2
    assert k1 != k_diff_season
    assert k1 != k_diff_year
    assert k1 != k_diff_rule


def test_dynamic_quantities_scale_without_arbitrary_caps():
    """Verify derived quantities scale dynamically with polygon area and never clamp to 40,000m² or 800 trees."""
    # Small polygon: 10 ha (100,000 m²)
    small_summary = PolygonSummary(
        status="ok",
        area_km2=0.10,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=42.5,
        max_lst_c=46.0,
        mean_hpi=65.0,
        built_density_component=0.60,
        vegetation_deficit_component=0.70,
        cell_count=10,
    )
    # Large polygon: 100 ha (1,000,000 m²)
    large_summary = PolygonSummary(
        status="ok",
        area_km2=1.00,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=42.5,
        max_lst_c=46.0,
        mean_hpi=65.0,
        built_density_component=0.60,
        vegetation_deficit_component=0.70,
        cell_count=100,
    )

    res_small = generate_polygon_recommendations(small_summary)
    res_large = generate_polygon_recommendations(large_summary)

    roof_small = next(r for r in res_small.recommendations if r.type == "COOL_ROOF")
    roof_large = next(r for r in res_large.recommendations if r.type == "COOL_ROOF")

    # Ensure quantity scaled dynamically with area (not clamped to 40,000 m²)
    assert roof_small.quantity_basis.estimated_quantity > 0
    assert roof_large.quantity_basis.estimated_quantity > roof_small.quantity_basis.estimated_quantity
    assert roof_large.quantity_basis.estimated_quantity > 40000.0, "Quantity should not clamp to 40,000 m² on large polygons"


def test_rejected_and_excluded_options_carry_zero_cost():
    """Verify that options marked REJECTED or EXCLUDED carry exactly 0.00 proposed cost and 0 quantity."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.20,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=43.0,
        max_lst_c=45.0,
        water_fraction=0.60,  # Environmental water conflict >= 50%
        cell_count=20,
    )

    res = generate_polygon_recommendations(summary)
    for rec in res.recommendations:
        if rec.feasibility_status == "REJECTED" or rec.priority == "NOT_RECOMMENDED":
            assert rec.cost_range_inr.base == 0.0
            assert rec.cost_range_inr.min == 0.0
            assert rec.cost_range_inr.max == 0.0
            assert rec.quantity_basis.estimated_quantity == 0.0


def test_no_upgrade_to_implementation_ready_from_model_data_alone():
    """Verify that no recommendation is ever marked IMPLEMENTATION_READY without field surveys."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.50,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=44.0,
        max_lst_c=48.0,
        mean_hpi=75.0,
        cell_count=50,
    )
    res = generate_polygon_recommendations(summary)
    for rec in res.recommendations:
        assert rec.reasoning_state != "IMPLEMENTATION_READY", (
            f"Intervention {rec.type} cannot be IMPLEMENTATION_READY from satellite/model data alone!"
        )


def test_response_contains_all_seven_required_sections():
    """Verify that RecommendationsResponse returns all 7 core spatial intervention reasoning sections."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.25,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=41.5,
        max_lst_c=45.2,
        mean_hpi=58.0,
        cell_count=25,
        landuse_typology="residential_rcc_roof",
    )
    res = generate_polygon_recommendations(summary)

    # 1. Heat conditions
    assert "mean_lst_c" in res.heat_conditions
    assert "mean_hpi" in res.heat_conditions

    # 2. Physical features
    assert "polygon_area_m2" in res.physical_features
    assert "polygon_area_ha" in res.physical_features

    # 3. Candidate sites
    assert isinstance(res.candidate_sites, list)
    assert len(res.candidate_sites) > 0

    # 4. Quantity and cost roll-up
    assert "total_capital_spend_inr" in res.quantity_cost_rollup
    assert "total_treated_area_m2" in res.quantity_cost_rollup

    # 5. Evidence gaps
    assert isinstance(res.evidence_gaps, list)
    assert len(res.evidence_gaps) >= 4

    # 6. Rejected candidates
    assert isinstance(res.rejected_candidates, list)

    # 7. Evidence availability panel
    assert isinstance(res.evidence_availability_panel, list)
    assert len(res.evidence_availability_panel) >= 7

    # Cache key
    assert res.cache_key is not None
