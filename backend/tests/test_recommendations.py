"""Unit and API tests for Area Analysis Recommendations Engine (Task G3).

Verifies:
1. Deterministic rule evaluation for Tree Canopy, Cool Roof, and Cool Pavement.
2. Hard constraint enforcement (water bodies, canopy saturation, boundary containment).
3. Explicit missing-data annotations ('not available - field survey required').
4. Cost and cooling interval calculations.
5. Public rate-limited API endpoint: POST /api/v1/analysis/recommendations.
"""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box, mapping

from backend.app.main import app
from backend.app.api.v1.analysis import recommendations_rate_limiter
from gis.interventions.recommendations import (
    PolygonSummary,
    generate_polygon_recommendations,
    ASSUMPTION_HIGH_HPI_THRESHOLD,
    ASSUMPTION_MAX_HPI_CRITICAL_THRESHOLD,
    ASSUMPTION_HIGH_VEG_DEFICIT,
    ASSUMPTION_HIGH_BUILT_DENSITY,
    ASSUMPTION_CANOPY_SATURATION_NDVI,
    MISSING_DATA_NOTE,
)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Deterministic Rule Engine Tests
# ---------------------------------------------------------------------------

def test_tree_canopy_high_priority_on_vegetation_deficit():
    """Verify that high HPI + high vegetation deficit triggers HIGH priority Tree Canopy."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.08,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=43.5,
        max_lst_c=47.2,
        min_lst_c=39.1,
        p90_lst_c=45.8,
        mean_hpi=62.4,
        max_hpi=74.1,
        vegetation_deficit_component=0.72,
        built_density_component=0.45,
        mean_ndvi=0.12,
        mean_ndbi=0.08,
        mean_ndwi=-0.18,
        water_fraction=0.01,
        water_warning=False,
        cell_count=2,
        chronic_cell_count=1,
        chronic_cell_share=0.50,
        frequent_cell_share=0.50,
        data_coverage_percentage=98.5,
        confidence_score=0.85,
        confidence_tier="HIGH",
    )

    response = generate_polygon_recommendations(summary)
    assert len(response.recommendations) > 0

    tree_rec = next(r for r in response.recommendations if r.type == "TREE_CANOPY")
    assert tree_rec.priority == "HIGH"
    assert tree_rec.feasibility_status == "FEASIBLE"
    assert "43.5°C" in tree_rec.rationale
    assert "0.72" in tree_rec.rationale
    assert tree_rec.cost_range_inr.base > 0
    assert tree_rec.cooling_range_c.expected > 0
    assert tree_rec.evidence_label == "MODELLED"
    assert "3-year" in tree_rec.maintenance_note

    # Missing data checks
    assert any(MISSING_DATA_NOTE in req for req in tree_rec.missing_data_survey_requirements)


def test_cool_roof_high_priority_on_built_density():
    """Verify that high thermal severity + high built density triggers HIGH priority Cool Roof."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.10,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=44.1,
        max_lst_c=48.5,
        min_lst_c=40.0,
        p90_lst_c=46.9,
        mean_hpi=65.0,
        max_hpi=78.0,
        vegetation_deficit_component=0.35,
        built_density_component=0.78,
        mean_ndvi=0.22,
        mean_ndbi=0.28,
        mean_ndwi=-0.22,
        water_fraction=0.0,
        water_warning=False,
        cell_count=3,
        chronic_cell_count=2,
        chronic_cell_share=0.67,
        frequent_cell_share=0.67,
        data_coverage_percentage=100.0,
        confidence_score=0.90,
        confidence_tier="HIGH",
    )

    response = generate_polygon_recommendations(summary)
    roof_rec = next(r for r in response.recommendations if r.type == "COOL_ROOF")
    assert roof_rec.priority == "HIGH"
    assert roof_rec.feasibility_status == "FEASIBLE"
    assert "0.78" in roof_rec.rationale
    assert roof_rec.cost_range_inr.base > 0
    assert roof_rec.cooling_range_c.expected > 0
    assert "CPWD" in roof_rec.maintenance_note or "Cool Roofs" in roof_rec.maintenance_note

    # Missing data checks
    assert any(MISSING_DATA_NOTE in req for req in roof_rec.missing_data_survey_requirements)


def test_water_body_conflict_rejects_terrestrial_interventions():
    """Verify that a polygon dominated by water (water_fraction >= 50%) rejects interventions."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.15,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=34.0,
        max_lst_c=36.0,
        min_lst_c=31.0,
        mean_hpi=25.0,
        water_fraction=0.65,
        water_warning=True,
        cell_count=2,
        data_coverage_percentage=95.0,
    )

    response = generate_polygon_recommendations(summary)
    for rec in response.recommendations:
        assert rec.feasibility_status == "REJECTED"
        assert rec.priority == "NOT_RECOMMENDED"
        assert any("Water body conflict" in reason for reason in rec.rejection_reasons)


def test_canopy_saturation_rejects_further_tree_planting():
    """Verify that if existing NDVI >= 0.55, Tree Canopy is rejected due to saturation."""
    summary = PolygonSummary(
        status="ok",
        area_km2=0.05,
        inside_smc_fraction=1.0,
        season="summer",
        effective_year=2026,
        mean_lst_c=35.0,
        max_lst_c=38.0,
        mean_hpi=35.0,
        vegetation_deficit_component=0.05,
        built_density_component=0.10,
        mean_ndvi=0.62,
        mean_ndbi=-0.15,
        water_fraction=0.02,
        cell_count=1,
        data_coverage_percentage=100.0,
    )

    response = generate_polygon_recommendations(summary)
    tree_rec = next(r for r in response.recommendations if r.type == "TREE_CANOPY")
    assert tree_rec.feasibility_status == "REJECTED"
    assert tree_rec.priority == "NOT_RECOMMENDED"
    assert any("Canopy saturation" in reason for reason in tree_rec.rejection_reasons)


def test_outside_study_area_returns_empty_recommendations_with_caveat():
    """Verify that a polygon outside SMC returns no recommendations with explicit boundary notice."""
    summary = PolygonSummary(
        status="outside_study_area",
        area_km2=0.20,
        inside_smc_fraction=0.0,
        season="summer",
        effective_year=2026,
        cell_count=0,
        data_coverage_percentage=0.0,
    )

    response = generate_polygon_recommendations(summary)
    assert len(response.recommendations) == 0
    assert any("entirely outside" in caveat for caveat in response.caveats)


# ---------------------------------------------------------------------------
# 2. API Endpoint Integration Tests (POST /api/v1/analysis/recommendations)
# ---------------------------------------------------------------------------

def test_api_recommendations_valid_polygon(client):
    """Test POST /api/v1/analysis/recommendations returns 200 with full recommendations structure."""
    recommendations_rate_limiter.reset()

    # Surat city center polygon
    b = box(72.82, 21.16, 72.84, 21.18)
    payload = {
        "geometry": mapping(b),
        "season": "summer",
        "year": 2026,
    }

    resp = client.post("/api/v1/analysis/recommendations", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "polygon_summary" in data
    assert "recommendations" in data
    assert "caveats" in data
    assert "assumptions_applied" in data
    assert data["evidence_label"] == "MODELLED"

    summary = data["polygon_summary"]
    assert summary["area_km2"] > 0
    assert summary["cell_count"] > 0
    assert summary["mean_lst_c"] is not None

    recs = data["recommendations"]
    assert len(recs) >= 2
    for r in recs:
        assert "type" in r
        assert "priority" in r
        assert "cost_range_inr" in r
        assert "cooling_range_c" in r
        assert "maintenance_note" in r
        assert "missing_data_survey_requirements" in r


def test_api_recommendations_outside_polygon(client):
    """Test POST /api/v1/analysis/recommendations with a polygon outside Surat."""
    recommendations_rate_limiter.reset()

    # Arabian sea polygon outside SMC
    b = box(72.50, 21.10, 72.52, 21.12)
    payload = {
        "geometry": mapping(b),
        "season": "summer",
        "year": 2026,
    }

    resp = client.post("/api/v1/analysis/recommendations", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    summary = data["polygon_summary"]
    assert summary["status"] == "outside_study_area"
    assert len(data["recommendations"]) == 0


def test_api_recommendations_invalid_geometry(client):
    """Test POST /api/v1/analysis/recommendations with invalid unclosed geometry returns 400."""
    recommendations_rate_limiter.reset()

    # Unclosed ring
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[72.82, 21.16], [72.84, 21.16], [72.84, 21.18]]],
        },
        "season": "summer",
    }

    resp = client.post("/api/v1/analysis/recommendations", json=payload)
    assert resp.status_code == 400
    assert "Linear ring 0 must contain at least 4 coordinate positions" in resp.json()["detail"]


def test_api_recommendations_rate_limiting(client):
    """Test POST /api/v1/analysis/recommendations returns 429 when rate limit is exceeded."""
    recommendations_rate_limiter.reset()

    b = box(72.82, 21.16, 72.84, 21.18)
    payload = {
        "geometry": mapping(b),
        "season": "summer",
    }

    # Exhaust 30 attempts
    for _ in range(30):
        recommendations_rate_limiter.check_and_record("recs_testclient")

    resp = client.post("/api/v1/analysis/recommendations", json=payload)
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.json()["detail"]
    assert "Retry-After" in resp.headers

    # Reset after test
    recommendations_rate_limiter.reset()


def test_compatibility_matrix_and_status_coherence():
    """Verify Q2 compatibility matrix across all typologies and candidates:
    - No ground-only intervention on rooftop typology and vice versa.
    - Rejected/not-applicable items never have positive 'justifies' language.
    - Every rationale mentions its own status.
    - screening_status never implies approval.
    """
    from gis.interventions import InterventionType
    from gis.interventions.candidates import generate_candidate_for_cell

    typologies = [
        "residential_rcc_roof",
        "industrial_shed_roof",
        "informal_settlement_roof",
        "vacant_public_open_land",
        "vacant_private_land",
        "park_garden",
        "road_corridor",
        "parking_paved_yard",
        "institutional_campus",
        "water_adjacent",
    ]

    roof_typologies = {"residential_rcc_roof", "industrial_shed_roof", "informal_settlement_roof"}
    ground_only_types = {
        "TREE_CANOPY",
        "COOL_PAVEMENT",
        "PUBLIC_PARK_NATIVE_TREES",
        "DENSE_MIYAWAKI_PLANTATION",
        "BIOSWALE_RAIN_GARDEN",
        "RAINWATER_FED_POND",
        "SHADED_PARKING_STRUCTURE",
        "PERMEABLE_GROUND_COVER",
    }
    roof_only_types = {"COOL_ROOF", "GREEN_ROOF", "GREEN_WALL"}

    pure_ground_typologies = {
        "vacant_public_open_land",
        "vacant_private_land",
        "park_garden",
        "road_corridor",
        "parking_paved_yard",
        "water_adjacent",
    }

    forbidden_approval_terms = ["APPROVED", "READY", "COMMISSIONED", "PERMITTED"]

    for typo in typologies:
        summary = PolygonSummary(
            status="ok",
            area_km2=0.10,
            inside_smc_fraction=1.0,
            season="summer",
            effective_year=2026,
            mean_lst_c=44.0,
            max_lst_c=48.0,
            min_lst_c=39.0,
            p90_lst_c=46.0,
            mean_hpi=60.0,
            max_hpi=75.0,
            vegetation_deficit_component=0.60,
            built_density_component=0.60,
            mean_ndvi=0.15,
            mean_ndbi=0.20 if typo in roof_typologies else -0.05,
            mean_ndwi=-0.20,
            water_fraction=0.0,
            cell_count=3,
            chronic_cell_count=2,
            chronic_cell_share=0.67,
            frequent_cell_share=0.67,
            data_coverage_percentage=100.0,
            confidence_score=0.90,
            confidence_tier="HIGH",
            landuse_typology=typo,
        )

        resp = generate_polygon_recommendations(summary)

        for rec in resp.recommendations:
            # 1. Status taxonomy validity
            assert rec.screening_status in ("MODEL_ELIGIBLE", "NOT_APPLICABLE", "EXCLUDED")
            for term in forbidden_approval_terms:
                assert term not in rec.screening_status, f"screening_status must never imply approval: {rec.screening_status}"

            # 2. Every rationale mentions its own status
            assert "Screening status:" in rec.rationale, f"Rationale must mention its status: {rec.rationale}"

            # 3. Rejected/not-applicable items NEVER have positive 'justifies' language
            if rec.screening_status in ("NOT_APPLICABLE", "EXCLUDED") or rec.feasibility_status == "REJECTED":
                assert "justifies" not in rec.rationale.lower(), f"Non-eligible item has positive 'justifies' language: {rec.rationale}"

            # 4. Rooftop compatibility: no ground-only intervention is MODEL_ELIGIBLE
            if typo in roof_typologies:
                if rec.type in ground_only_types:
                    assert rec.screening_status != "MODEL_ELIGIBLE", f"Ground-only {rec.type} eligible on roof {typo}"
                    assert rec.feasibility_status == "REJECTED"
                if rec.type == "TREE_CANOPY":
                    assert "not applicable to a rooftop" in rec.rationale
                if rec.type == "COOL_PAVEMENT":
                    assert "not applicable to a rooftop" in rec.rationale
                    assert "ground-level" in rec.rationale

            # 5. Non-roof compatibility: no roof-only intervention is MODEL_ELIGIBLE on pure ground
            if typo in pure_ground_typologies:
                if rec.type in roof_only_types:
                    assert rec.screening_status != "MODEL_ELIGIBLE", f"Roof-only {rec.type} eligible on ground {typo}"
                    assert rec.feasibility_status == "REJECTED"

            # 6. Check required pre-implementation checks on eligible items
            if rec.screening_status == "MODEL_ELIGIBLE":
                if rec.type == "COOL_ROOF":
                    for check in ["roof area verification", "structure", "ownership/permission", "condition", "drainage", "access"]:
                        assert check in rec.rationale, f"Missing {check} in cool roof rationale"
                elif rec.type in ("TREE_CANOPY", "PUBLIC_PARK_NATIVE_TREES"):
                    for check in ["soil/verge", "utilities", "species/site suitability", "water", "survival plan", "maintenance"]:
                        assert check in rec.rationale, f"Missing {check} in tree rationale"
                elif rec.type in ("COOL_PAVEMENT", "PERMEABLE_GROUND_COVER", "BIOSWALE_RAIN_GARDEN"):
                    for check in ["traffic loading", "drainage", "subgrade", "utilities"]:
                        assert check in rec.rationale, f"Missing {check} in pavement/swale rationale"

            # 7. Check cooling and cost metadata
            assert rec.cooling_metric == "modelled surface (skin) temperature reduction on treated area"
            assert "skin" in rec.cell_scope_note.lower() and "not" in rec.cell_scope_note.lower() and "air" in rec.cell_scope_note.lower()
            assert rec.price_date_note == "indicative, not a tender price"
            assert rec.schedule_alignment_note == "rates not verified against CPWD/SMC schedule"
            assert rec.unit_rate > 0
            assert rec.unit_rate_unit != ""

    # Test candidate generation compatibility
    cand_tree = generate_candidate_for_cell(
        row=50, col=50, cell_id="R050_C050",
        intervention_type=InterventionType.TREE_CANOPY,
        baseline_hpi=60.0, baseline_lst_c=44.0, is_chronic_hotspot=True,
        administrative_zone="Central Zone",
        landuse_typology="residential_rcc_roof",
    )
    assert cand_tree.screening_status == "NOT_APPLICABLE"
    assert cand_tree.feasibility_status.value == "REJECTED"
    assert "justifies" not in cand_tree.selection_rationale.lower()
    assert "Screening status:" in cand_tree.selection_rationale

    cand_roof = generate_candidate_for_cell(
        row=50, col=50, cell_id="R050_C050",
        intervention_type=InterventionType.COOL_ROOF,
        baseline_hpi=60.0, baseline_lst_c=44.0, is_chronic_hotspot=True,
        administrative_zone="Central Zone",
        landuse_typology="residential_rcc_roof",
    )
    assert cand_roof.screening_status == "MODEL_ELIGIBLE"
    assert cand_roof.feasibility_status.value == "FEASIBLE"
    assert "Screening status: Model-eligible (survey required)" in cand_roof.selection_rationale
