"""Unit tests for gis/quality/pixel_quality.py module."""

import numpy as np
import pytest

from gis.quality.pixel_quality import (
    classify_temporal_support,
    compute_neighborhood_metrics,
    evaluate_boundary_context,
    classify_extreme_status,
    classify_qa_uncertainty,
    assign_quality_flags,
)


def test_classify_temporal_support():
    assert classify_temporal_support(1) == "low"
    assert classify_temporal_support(0) == "low"
    assert classify_temporal_support(2) == "moderate"
    assert classify_temporal_support(3) == "moderate"
    assert classify_temporal_support(4) == "high"
    assert classify_temporal_support(10) == "high"
    assert classify_temporal_support(None) == "unknown"
    assert classify_temporal_support(np.nan) == "unknown"


def test_compute_neighborhood_metrics_non_circular():
    """Verify that center pixel is strictly excluded and does not bias statistics."""
    grid = np.full((5, 5), -9999.0, dtype=np.float32)
    # 3x3 surrounding (2, 2) set to 25.0
    grid[1:4, 1:4] = 25.0
    # Center pixel is 100.0 (extreme spike)
    grid[2, 2] = 100.0

    metrics = compute_neighborhood_metrics(grid, row=2, col=2)
    assert metrics["valid_neighbor_count"] == 8
    assert np.isclose(metrics["neighborhood_median"], 25.0)
    assert np.isclose(metrics["neighborhood_mean"], 25.0)
    assert np.isclose(metrics["neighborhood_std"], 0.0)
    assert np.isclose(metrics["pixel_minus_neighborhood_median"], 75.0)
    assert np.isclose(metrics["absolute_pixel_minus_neighborhood_median"], 75.0)


def test_compute_neighborhood_metrics_nodata_and_edges():
    """Verify edge handling and NoData exclusion."""
    grid = np.full((3, 3), -9999.0, dtype=np.float32)
    grid[0, 0] = 30.0  # Corner
    grid[0, 1] = 32.0  # Neighbor 1
    grid[1, 0] = 28.0  # Neighbor 2
    # All other 6 cells are -9999.0

    metrics = compute_neighborhood_metrics(grid, row=0, col=0)
    # Corner has 2 valid neighbors out of 3 potential neighbors
    assert metrics["valid_neighbor_count"] == 2
    assert np.isclose(metrics["neighborhood_median"], 30.0)
    assert np.isclose(metrics["pixel_minus_neighborhood_median"], 0.0)


def test_evaluate_boundary_context():
    # Corner
    res = evaluate_boundary_context(row=0, col=0, rows=10, cols=10, valid_neighbor_count=3)
    assert res["is_raster_edge"] is True
    assert res["insufficient_neighborhood"] is True
    assert res["is_boundary_context"] is True

    # Center with full neighbors
    res_center = evaluate_boundary_context(row=5, col=5, rows=10, cols=10, valid_neighbor_count=8)
    assert res_center["is_raster_edge"] is False
    assert res_center["insufficient_neighborhood"] is False
    assert res_center["is_boundary_context"] is False


def test_classify_extreme_status():
    tags = classify_extreme_status(
        lst_c=65.0,
        p_low=20.0,
        p_high=55.0,
        rank_hot=1,
        rank_cold=None,
        top_n=20,
        bottom_n=20,
    )
    assert "hot_top_20" in tags
    assert "hot_top_1pct" in tags

    normal_tags = classify_extreme_status(
        lst_c=35.0,
        p_low=20.0,
        p_high=55.0,
        rank_hot=500,
        rank_cold=500,
    )
    assert normal_tags == ["normal"]


def test_classify_qa_uncertainty():
    assert classify_qa_uncertainty(2.5) == "low_uncertainty"
    assert classify_qa_uncertainty(8.0) == "moderate_uncertainty"
    assert classify_qa_uncertainty(75.0) == "high_uncertainty"
    assert classify_qa_uncertainty(None) == "unknown"


def test_assign_quality_flags():
    # Perfect pixel
    flags = assign_quality_flags(
        obs_count=10,
        qa_k=2.5,
        abs_diff_med=1.2,
        valid_neighbor_count=8,
        is_boundary=False,
    )
    assert "SPATIALLY_COHERENT" in flags
    assert "LOW_TEMPORAL_SUPPORT" not in flags

    # Cloud shadow anomaly: OBS=1, severe diff, boundary edge
    flags_anom = assign_quality_flags(
        obs_count=1,
        qa_k=3.5,
        abs_diff_med=15.4,
        valid_neighbor_count=4,
        is_boundary=True,
    )
    assert "LOW_TEMPORAL_SUPPORT" in flags_anom
    assert "SPATIAL_ANOMALY" in flags_anom
    assert "LOW_SUPPORT_SPATIAL_EXTREME" in flags_anom
    assert "BOUNDARY_CONTEXT" in flags_anom
