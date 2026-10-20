"""Acceptance Tests for Stage C Heat Priority API Endpoints.

Verifies:
- GET /api/v1/heat-priority/summary
- GET /api/v1/heat-priority/cells
- GET /api/v1/heat-priority/cell/{pixel_id}
- Error handling (404, 422) for invalid parameters and IDs
- Unavailable scores and SQL NULL handling in responses
- Pagination bounds and out-of-range behavior
- Strict non-finite JSON float compliance (no NaNs or Infs).
"""

from __future__ import annotations

import json
import math
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.api.v1.heat_priority import safe_float
from backend.app.db.models.stage_c import (
    StageCGridCell,
    StageCHeatPriorityScore,
)
from backend.app.db.session import SessionLocal
from backend.app.main import app

client = TestClient(app)


def test_safe_float_utility() -> None:
    """Verify that safe_float safely handles non-finite floats, None, and valid numbers."""
    assert safe_float(None) is None
    assert safe_float(float("nan")) is None
    assert safe_float(float("inf")) is None
    assert safe_float(float("-inf")) is None
    assert safe_float("not_a_number") is None
    assert safe_float(42.12345, 2) == 42.12
    assert safe_float(0.0) == 0.0
    assert safe_float(100.0, 1) == 100.0


def test_heat_priority_summary_endpoint() -> None:
    """Test retrieving summary statistics for operational HPI dataset."""
    response = client.get("/api/v1/heat-priority/summary")
    assert response.status_code == 200, response.text
    
    # Strict JSON validation: must not contain invalid tokens like NaN
    data = json.loads(response.text)

    assert data["scoring_period"] == "2026_summer_operational"
    assert data["spec_version"] == "v2.0"
    assert data["total_grid_cells"] == 49747
    assert data["scored_cells"] == 49747
    assert data["chronic_hotspots_count"] == 223
    assert data["mean_hpi"] is not None
    assert isinstance(data["mean_hpi"], float)
    assert math.isfinite(data["mean_hpi"])
    assert data["confidence_tier_counts"]["HIGH"] > 49000


def test_heat_priority_cells_endpoint() -> None:
    """Test paginated cells query and filtering."""
    # Query default first page
    response = client.get("/api/v1/heat-priority/cells?limit=10&offset=0")
    assert response.status_code == 200
    data = json.loads(response.text)

    assert data["total"] == 49747
    assert len(data["items"]) == 10
    first_item = data["items"][0]
    assert "pixel_id" in first_item
    assert "heat_priority_score" in first_item
    assert "confidence_tier" in first_item
    assert "is_chronic_hotspot" in first_item

    # Query filtered by chronic hotspots
    chronic_response = client.get("/api/v1/heat-priority/cells?is_chronic_hotspot=true&limit=50")
    assert chronic_response.status_code == 200
    chronic_data = json.loads(chronic_response.text)
    assert chronic_data["total"] == 223
    assert len(chronic_data["items"]) == 50
    for item in chronic_data["items"]:
        assert item["is_chronic_hotspot"] is True

    # Query filtered by persistence tier
    pers_response = client.get("/api/v1/heat-priority/cells?persistence_tier=chronic_hotspot&limit=25")
    assert pers_response.status_code == 200
    pers_data = json.loads(pers_response.text)
    assert pers_data["total"] == 223
    for item in pers_data["items"]:
        assert item["persistence_tier"] == "chronic_hotspot"


def test_heat_priority_cells_pagination_validation() -> None:
    """Test pagination bounds, limits, and out-of-range offset behavior."""
    # Limit < 1 -> 422
    resp_zero_limit = client.get("/api/v1/heat-priority/cells?limit=0")
    assert resp_zero_limit.status_code == 422

    # Limit > 500 -> 422
    resp_over_limit = client.get("/api/v1/heat-priority/cells?limit=501")
    assert resp_over_limit.status_code == 422

    # Offset < 0 -> 422
    resp_neg_offset = client.get("/api/v1/heat-priority/cells?offset=-1")
    assert resp_neg_offset.status_code == 422

    # Offset exceeding total rows -> 200 with empty items list, total preserved
    resp_large_offset = client.get("/api/v1/heat-priority/cells?limit=50&offset=100000")
    assert resp_large_offset.status_code == 200
    data = json.loads(resp_large_offset.text)
    assert data["total"] == 49747
    assert data["offset"] == 100000
    assert data["limit"] == 50
    assert len(data["items"]) == 0


def test_heat_priority_cells_query_filter_errors() -> None:
    """Test API error responses for invalid query filter parameters."""
    # min_hpi < 0.0 -> 422
    resp_min_low = client.get("/api/v1/heat-priority/cells?min_hpi=-1.0")
    assert resp_min_low.status_code == 422

    # min_hpi > 100.0 -> 422
    resp_min_high = client.get("/api/v1/heat-priority/cells?min_hpi=100.5")
    assert resp_min_high.status_code == 422

    # Invalid confidence tier pattern -> 422
    resp_invalid_conf = client.get("/api/v1/heat-priority/cells?confidence_tier=INVALID_TIER")
    assert resp_invalid_conf.status_code == 422

    # Invalid persistence tier pattern -> 422
    resp_invalid_pers = client.get("/api/v1/heat-priority/cells?persistence_tier=INVALID_TIER")
    assert resp_invalid_pers.status_code == 422


def test_heat_priority_cell_detail_valid_and_invalid_ids() -> None:
    """Test single cell detail lookup by pixel_id with valid and invalid IDs."""
    # Valid cell lookup
    list_resp = client.get("/api/v1/heat-priority/cells?limit=1")
    pixel_id = list_resp.json()["items"][0]["pixel_id"]

    detail_resp = client.get(f"/api/v1/heat-priority/cell/{pixel_id}")
    assert detail_resp.status_code == 200
    detail = json.loads(detail_resp.text)
    assert detail["pixel_id"] == pixel_id
    assert detail["heat_priority_score"] is not None
    assert math.isfinite(detail["heat_priority_score"])

    # Non-existent cell ID -> 404
    missing_resp = client.get("/api/v1/heat-priority/cell/INVALID_CELL_999")
    assert missing_resp.status_code == 404
    assert "not exist" in missing_resp.json()["detail"].lower()

    # Invalid cell ID (exceeding max_length=16) -> 422
    long_resp = client.get("/api/v1/heat-priority/cell/THIS_PIXEL_ID_IS_TOO_LONG_FOR_SPEC")
    assert long_resp.status_code == 422


def test_heat_priority_cell_unavailable_score_handling() -> None:
    """Test retrieving detail for a cell with unavailable/NULL score."""
    session = SessionLocal()
    from backend.app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: session
    savepoint = session.begin_nested()
    try:
        sample_pixel_id = session.scalar(select(StageCGridCell.pixel_id).limit(1))
        assert sample_pixel_id is not None

        test_period = "test_unavailable_period"
        null_score = StageCHeatPriorityScore(
            pixel_id=sample_pixel_id,
            scoring_period=test_period,
            spec_version="v2.0",
            heat_priority_score=None,
            thermal_severity_component=None,
            persistence_component=None,
            vegetation_deficit_component=None,
            built_density_component=None,
            effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
            confidence_index=0.25,
            confidence_tier="INSUFFICIENT",
            persistence_tier="non_hotspot",
            is_chronic_hotspot=False,
            valid_seasons_count=0,
            hot_seasons_count=0,
            hotspot_frequency=0.0,
            distinct_years_count=0,
            eligibility_status="INSUFFICIENT_THERMAL_EVIDENCE",
            provenance_hash="test_null_provenance",
        )
        session.add(null_score)
        session.flush()

        # Query API for this specific scoring period
        resp = client.get(
            f"/api/v1/heat-priority/cell/{sample_pixel_id}?scoring_period={test_period}"
        )
        assert resp.status_code == 200
        data = json.loads(resp.text)

        # JSON response must serialize unavailable scores as null
        assert data["pixel_id"] == sample_pixel_id
        assert data["heat_priority_score"] is None
        assert data["thermal_severity_component"] is None
        assert data["persistence_component"] is None
        assert data["vegetation_deficit_component"] is None
        assert data["built_density_component"] is None
        assert data["confidence_tier"] == "INSUFFICIENT"
        assert data["is_chronic_hotspot"] is False
        assert data["eligibility_status"] == "INSUFFICIENT_THERMAL_EVIDENCE"
    finally:
        savepoint.rollback()
        app.dependency_overrides.pop(get_db, None)
        session.close()


def test_heat_priority_cell_unscored_cell_handling() -> None:
    """Test retrieving detail for a cell with no score record for that scoring period."""
    session = SessionLocal()
    sample_pixel_id = session.scalar(select(StageCGridCell.pixel_id).limit(1))
    session.close()
    assert sample_pixel_id is not None

    unscored_period = "non_existent_scoring_period_2099"
    resp = client.get(
        f"/api/v1/heat-priority/cell/{sample_pixel_id}?scoring_period={unscored_period}"
    )
    assert resp.status_code == 200
    data = json.loads(resp.text)

    # Returns cell info with all score fields as null
    assert data["pixel_id"] == sample_pixel_id
    assert data["heat_priority_score"] is None
    assert data["thermal_severity_component"] is None
    assert data["confidence_tier"] is None
    assert data["is_chronic_hotspot"] is False


def test_heat_priority_cells_bbox_viewport_filtering() -> None:
    """Test bounded viewport requests using bbox parameter."""
    # Surat central bbox
    bbox_str = "72.80,21.15,72.85,21.20"
    resp = client.get(f"/api/v1/heat-priority/cells?bbox={bbox_str}&limit=100")
    assert resp.status_code == 200
    data = json.loads(resp.text)

    # Should find bounded cells within coordinate range
    assert data["total"] > 0
    assert len(data["items"]) <= 100
    for item in data["items"]:
        assert 21.15 <= item["latitude"] <= 21.20
        assert 72.80 <= item["longitude"] <= 72.85
        # Verify observed_lst_c and optical_imputation_flag are provided
        assert "observed_lst_c" in item
        assert "optical_imputation_flag" in item

