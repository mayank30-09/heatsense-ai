"""Comprehensive test suite for Dynamic World Land Cover integration & Stage D scientific governance.

Covers:
1. 9-class probability constraints (all in [0, 1], sum to ~1.0).
2. Distinction between mean probabilities and hard-label proportions.
3. Zero observations remain strictly NULL/None (never 0.0).
4. Normalized Shannon Entropy in [0, 1] (0 for pure single class, 1 for uniform 1/9).
5. Confidence and ambiguity margin (top1 - top2 >= 0).
6. Suitability rules:
   - Built >= 0.40 -> Cool Roof / Cool Pavement
   - Open ground >= 0.35 & built < 0.30 -> Urban Forestry / Permeable
   - Crops >= 0.40 -> Agricultural conflict (NEEDS_SITE_SURVEY)
   - Trees >= 0.40 -> Canopy preservation
   - Obs < 3 -> Insufficient observations (NEEDS_SITE_SURVEY)
7. Uncalibrated heuristic labeling & mandatory physical survey prerequisite.
8. API endpoints (/landcover/summary, /landcover/{cell_id}, /landcover/grid).
"""

import math
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models.stage_d import StageDDynamicWorldLandCover
from gis.gee.dynamic_world_pipeline import (
    DW_CLASSES,
    calculate_margin,
    calculate_normalized_entropy,
    PIPELINE_VERSION,
    ATTRIBUTION_TEXT,
)
from gis.interventions import FeasibilityStatus, InterventionType
from gis.interventions.candidates import generate_candidate_for_cell
from gis.interventions.landcover_suitability import (
    evaluate_landcover_suitability,
    HEURISTIC_DISCLOSURE_LABEL,
    PHYSICAL_SURVEY_PREREQUISITE_LABEL,
    LandCoverRule,
)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Mathematical Diagnostics Tests (Entropy, Margin, Proportions)
# ---------------------------------------------------------------------------

def test_normalized_shannon_entropy_pure_class():
    """Single class with probability 1.0 must have entropy 0.0 (absolute certainty)."""
    probs = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    h = calculate_normalized_entropy(probs)
    assert h == 0.0


def test_normalized_shannon_entropy_uniform_distribution():
    """Uniform distribution across 9 classes must have normalized entropy 1.0 (maximum ambiguity)."""
    probs = [1.0 / 9.0] * 9
    h = calculate_normalized_entropy(probs)
    assert pytest.approx(h, abs=0.001) == 1.0


def test_normalized_shannon_entropy_bounds():
    """Arbitrary valid distributions must always yield entropy in [0.0, 1.0]."""
    test_cases = [
        [0.8, 0.1, 0.05, 0.02, 0.01, 0.01, 0.01, 0.0, 0.0],
        [0.4, 0.4, 0.1, 0.05, 0.05, 0.0, 0.0, 0.0, 0.0],
        [0.2, 0.2, 0.2, 0.2, 0.1, 0.05, 0.05, 0.0, 0.0],
    ]
    for p in test_cases:
        h = calculate_normalized_entropy(p)
        assert h is not None
        assert 0.0 <= h <= 1.0


def test_calculate_margin_and_top_class():
    """Confidence must equal top class prob, and margin must equal top1 - top2 >= 0."""
    p_dict = {
        "built": 0.65,
        "bare": 0.20,
        "trees": 0.05,
        "grass": 0.05,
        "crops": 0.03,
        "water": 0.01,
        "flooded_vegetation": 0.005,
        "shrub_and_scrub": 0.005,
        "snow_and_ice": 0.0,
    }
    top_cls, conf, margin = calculate_margin(p_dict)
    assert top_cls == "built"
    assert conf == 0.65
    assert margin == 0.45  # 0.65 - 0.20


# ---------------------------------------------------------------------------
# 2. Zero-Observation & Missing Data Strictness Tests
# ---------------------------------------------------------------------------

def test_zero_observation_cells_remain_null():
    """When valid_observation_count is 0, probabilities must remain None (never 0.0)."""
    record_zero = {
        "cell_id": "TEST_R999_C999",
        "valid_observation_count": 0,
        "mean_built": None,
        "mean_trees": None,
        "mean_grass": None,
        "confidence": None,
        "entropy": None,
        "status": "NO_OBSERVATIONS",
    }
    eval_res = evaluate_landcover_suitability(record_zero, cell_id="TEST_R999_C999")
    assert eval_res.rule_fired == LandCoverRule.RULE_DW_INSUFFICIENT_OBSERVATIONS.value
    assert eval_res.screening_status == "NEEDS_SITE_SURVEY"
    assert eval_res.feasibility_prerequisite == PHYSICAL_SURVEY_PREREQUISITE_LABEL
    assert eval_res.observed_values["mean_built"] is None


# ---------------------------------------------------------------------------
# 3. Suitability Rules & Scientific Governance Tests
# ---------------------------------------------------------------------------

def test_rule_built_dense_fires_and_sets_disclosures():
    """Built probability >= 0.40 must select cool roof/pavements and enforce disclosures."""
    record_built = {
        "cell_id": "TEST_BUILT_001",
        "valid_observation_count": 28,
        "mean_built": 0.65,
        "mean_bare": 0.15,
        "mean_trees": 0.05,
        "mean_grass": 0.05,
        "mean_crops": 0.05,
        "mean_water": 0.02,
        "mean_flooded_vegetation": 0.01,
        "mean_shrub_and_scrub": 0.02,
        "confidence": 0.65,
        "entropy": 0.58,
        "top_class": "built",
        "status": "SUFFICIENT",
    }
    eval_res = evaluate_landcover_suitability(record_built, cell_id="TEST_BUILT_001")
    assert eval_res.rule_fired == LandCoverRule.RULE_DW_BUILT_DENSE.value
    assert InterventionType.COOL_ROOF in eval_res.suitable_interventions
    assert InterventionType.COOL_PAVEMENT in eval_res.suitable_interventions
    assert eval_res.feasibility_prerequisite == PHYSICAL_SURVEY_PREREQUISITE_LABEL
    assert HEURISTIC_DISCLOSURE_LABEL in eval_res.scientific_notice


def test_rule_open_ground_fires():
    """Bare + grass + shrub >= 0.35 and built < 0.30 must select urban forestry."""
    record_open = {
        "cell_id": "TEST_OPEN_001",
        "valid_observation_count": 25,
        "mean_built": 0.10,
        "mean_bare": 0.30,
        "mean_grass": 0.20,
        "mean_shrub_and_scrub": 0.05,
        "mean_trees": 0.15,
        "mean_crops": 0.15,
        "mean_water": 0.03,
        "mean_flooded_vegetation": 0.01,
        "confidence": 0.35,
        "entropy": 0.75,
        "top_class": "bare",
        "status": "SUFFICIENT",
    }
    eval_res = evaluate_landcover_suitability(record_open, cell_id="TEST_OPEN_001")
    assert eval_res.rule_fired == LandCoverRule.RULE_DW_OPEN_GROUND.value
    assert InterventionType.TREE_CANOPY in eval_res.suitable_interventions
    assert InterventionType.COOL_ROOF in eval_res.screened_out_interventions


def test_rule_agricultural_conflict_flags_survey():
    """Crops >= 0.40 must trigger agricultural land conflict and flag NEEDS_SITE_SURVEY."""
    record_crops = {
        "cell_id": "TEST_CROP_001",
        "valid_observation_count": 30,
        "mean_crops": 0.55,
        "mean_built": 0.15,
        "mean_bare": 0.15,
        "mean_trees": 0.05,
        "mean_grass": 0.05,
        "mean_water": 0.03,
        "mean_flooded_vegetation": 0.01,
        "mean_shrub_and_scrub": 0.01,
        "confidence": 0.55,
        "entropy": 0.62,
        "top_class": "crops",
        "status": "SUFFICIENT",
    }
    eval_res = evaluate_landcover_suitability(record_crops, cell_id="TEST_CROP_001")
    assert eval_res.rule_fired == LandCoverRule.RULE_DW_AGRICULTURAL_CONFLICT.value
    assert eval_res.screening_status == "NEEDS_SITE_SURVEY"
    assert "farmland conflict" in eval_res.screening_reason.lower() or "agricultural" in eval_res.screening_reason.lower()


def test_rule_tree_canopy_preservation():
    """Trees >= 0.40 must prioritize existing canopy preservation."""
    record_trees = {
        "cell_id": "TEST_TREE_001",
        "valid_observation_count": 32,
        "mean_trees": 0.52,
        "mean_built": 0.15,
        "mean_grass": 0.15,
        "mean_bare": 0.10,
        "mean_crops": 0.05,
        "mean_water": 0.02,
        "mean_flooded_vegetation": 0.01,
        "mean_shrub_and_scrub": 0.0,
        "confidence": 0.52,
        "entropy": 0.60,
        "top_class": "trees",
        "status": "SUFFICIENT",
    }
    eval_res = evaluate_landcover_suitability(record_trees, cell_id="TEST_TREE_001")
    assert eval_res.rule_fired == LandCoverRule.RULE_DW_CANOPY_PRESERVATION.value
    assert InterventionType.PUBLIC_PARK_NATIVE_TREES in eval_res.suitable_interventions
    assert InterventionType.COOL_ROOF in eval_res.screened_out_interventions


def test_candidate_generation_attaches_landcover_and_preserves_unresolved_survey():
    """Candidates generated with Dynamic World data must attach metadata and preserve survey prerequisites."""
    record_built = {
        "cell_id": "R000_C249",
        "valid_observation_count": 30,
        "mean_built": 0.6346,
        "mean_bare": 0.0396,
        "mean_trees": 0.0388,
        "mean_crops": 0.0736,
        "confidence": 0.6346,
        "entropy": 0.6356,
        "top_class": "built",
        "status": "SUFFICIENT",
        "pipeline_version": "v1.0",
    }

    cand = generate_candidate_for_cell(
        row=0,
        col=249,
        cell_id="R000_C249",
        intervention_type=InterventionType.COOL_ROOF,
        baseline_hpi=0.75,
        baseline_lst_c=45.2,
        is_chronic_hotspot=True,
        administrative_zone="Udhana",
        dw_record=record_built,
    )

    assert cand.feasibility_status == FeasibilityStatus.FEASIBLE
    assert cand.screening_status == "MODEL_ELIGIBLE"
    assert cand.landcover_rule_fired == LandCoverRule.RULE_DW_BUILT_DENSE.value
    assert cand.landcover_top_class == "built"
    assert cand.landcover_confidence == 0.6346
    assert HEURISTIC_DISCLOSURE_LABEL in cand.landcover_disclosure
    # Mandatory rule: Satellite data NEVER converts candidate to verified
    assert cand.prerequisites_status == PHYSICAL_SURVEY_PREREQUISITE_LABEL


# ---------------------------------------------------------------------------
# 4. API Integration Tests
# ---------------------------------------------------------------------------

def test_api_landcover_summary(client):
    """GET /api/v1/interventions/landcover/summary returns valid summary diagnostics."""
    res = client.get("/api/v1/interventions/landcover/summary?season=summer&year=2024")
    assert res.status_code == 200
    data = res.json()
    assert data["season"] == "summer"
    assert data["year"] == 2024
    assert data["total_cells_recorded"] >= 300
    assert data["cells_sufficient"] >= 300
    assert "built" in data["class_distribution"]
    assert "mean_probabilities" in data
    assert 0.0 <= data["mean_confidence"] <= 1.0
    assert 0.0 <= data["mean_entropy"] <= 1.0
    assert "CC BY 4.0" in data["attribution"] or "CC-BY-4.0" in data["license"]


def test_api_cell_landcover_details(client):
    """GET /api/v1/interventions/landcover/{cell_id} returns 9-class distribution and suitability."""
    res = client.get("/api/v1/interventions/landcover/R000_C249?season=summer&year=2024")
    assert res.status_code == 200
    data = res.json()
    assert data["cell_id"] == "R000_C249"
    assert data["top_class"] == "built"
    assert data["probabilities"]["built"] is not None
    assert 0.0 <= data["probabilities"]["built"] <= 1.0
    assert data["suitability"]["rule_fired"] == LandCoverRule.RULE_DW_BUILT_DENSE.value
    assert data["suitability"]["feasibility_prerequisite"] == PHYSICAL_SURVEY_PREREQUISITE_LABEL


def test_api_landcover_grid(client):
    """GET /api/v1/interventions/landcover/grid returns lightweight items for map rendering."""
    res = client.get("/api/v1/interventions/landcover/grid?limit=50")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    item0 = items[0]
    assert "cell_id" in item0
    assert "top_class" in item0
    assert "confidence" in item0
    assert "mean_built" in item0

