"""Unit tests for scripts/analyze_hotspot_persistence.py."""

import pandas as pd
import numpy as np
import pytest

from scripts.analyze_hotspot_persistence import (
    compute_hotspot_persistence,
    classify_persistence_tier,
)


def test_classify_persistence_tier():
    assert classify_persistence_tier(1.0) == "chronic_hotspot"
    assert classify_persistence_tier(0.50) == "chronic_hotspot"
    assert classify_persistence_tier(0.40) == "frequent_hotspot"
    assert classify_persistence_tier(0.25) == "frequent_hotspot"
    assert classify_persistence_tier(0.15) == "occasional_hotspot"
    assert classify_persistence_tier(0.05) == "transient_extreme"


def test_compute_hotspot_persistence_synthetic():
    """
    Test persistence calculation with:
    - Loc 1: Multi-season persistent hotspot (hot in 4 seasons out of 4)
    - Loc 2: One-season transient hotspot (hot in 1 season out of 4)
    - Loc 3: Cold extreme (should not be in hot persistence)
    """
    records = [
        # Loc 1 (R100_C100): hot in 2022 winter, 2022 summer, 2023 winter, 2023 summer
        {"year": 2022, "season": "winter", "extreme_type": "hot_top_1pct,hot_top_20", "row": 100, "col": 100, "longitude": 72.8, "latitude": 21.1, "lst_c": 40.0, "obs_count": 10, "qa_k": 2.5, "ndvi": 0.2, "ndbi": 0.1, "ndwi": -0.2, "neighborhood_median": 35.0, "valid_neighbor_count": 8},
        {"year": 2022, "season": "summer", "extreme_type": "hot_top_1pct,hot_top_20", "row": 100, "col": 100, "longitude": 72.8, "latitude": 21.1, "lst_c": 55.0, "obs_count": 10, "qa_k": 2.5, "ndvi": 0.2, "ndbi": 0.1, "ndwi": -0.2, "neighborhood_median": 48.0, "valid_neighbor_count": 8},
        {"year": 2023, "season": "winter", "extreme_type": "hot_top_1pct", "row": 100, "col": 100, "longitude": 72.8, "latitude": 21.1, "lst_c": 41.0, "obs_count": 10, "qa_k": 2.5, "ndvi": 0.2, "ndbi": 0.1, "ndwi": -0.2, "neighborhood_median": 36.0, "valid_neighbor_count": 8},
        {"year": 2023, "season": "summer", "extreme_type": "hot_top_1pct,hot_top_20", "row": 100, "col": 100, "longitude": 72.8, "latitude": 21.1, "lst_c": 56.0, "obs_count": 10, "qa_k": 2.5, "ndvi": 0.2, "ndbi": 0.1, "ndwi": -0.2, "neighborhood_median": 49.0, "valid_neighbor_count": 8},

        # Loc 2 (R200_C200): hot only in 2022 summer
        {"year": 2022, "season": "summer", "extreme_type": "hot_top_1pct", "row": 200, "col": 200, "longitude": 72.9, "latitude": 21.2, "lst_c": 50.0, "obs_count": 1, "qa_k": 50.0, "ndvi": 0.1, "ndbi": 0.2, "ndwi": -0.1, "neighborhood_median": 45.0, "valid_neighbor_count": 8},

        # Loc 3 (R300_C300): cold extreme (should be excluded from hot analysis)
        {"year": 2022, "season": "monsoon", "extreme_type": "cold_bottom_1pct", "row": 300, "col": 300, "longitude": 72.7, "latitude": 21.0, "lst_c": 15.0, "obs_count": 1, "qa_k": 3.0, "ndvi": 0.1, "ndbi": -0.1, "ndwi": -0.1, "neighborhood_median": 25.0, "valid_neighbor_count": 8},
    ]
    df_raw = pd.DataFrame(records)

    df_instances, df_summary = compute_hotspot_persistence(
        df_raw,
        total_seasons_count=4,
        persistence_thresh=0.25,
    )

    # Loc 3 is cold, should not be in summary
    assert "R300_C300" not in df_summary["location"].values

    # Loc 1 summary check
    s1 = df_summary[df_summary["location"] == "R100_C100"].iloc[0]
    assert s1["hot_seasons_count"] == 4
    assert s1["valid_seasons_count"] == 4
    assert np.isclose(s1["hotspot_frequency"], 1.0)
    assert s1["is_persistent_hotspot"] == True
    assert s1["persistence_tier"] == "chronic_hotspot"

    # Loc 2 summary check
    s2 = df_summary[df_summary["location"] == "R200_C200"].iloc[0]
    assert s2["hot_seasons_count"] == 1
    assert s2["valid_seasons_count"] == 4
    assert np.isclose(s2["hotspot_frequency"], 0.25)
    assert s2["persistence_tier"] == "frequent_hotspot"


def test_compute_hotspot_persistence_duplicate_records():
    """Ensure duplicate records in the same season do not double count."""
    records = [
        {"year": 2022, "season": "summer", "extreme_type": "hot_top_1pct", "row": 50, "col": 50, "longitude": 72.8, "latitude": 21.1, "lst_c": 50.0, "obs_count": 10, "qa_k": 2.5, "ndvi": 0.2, "ndbi": 0.1, "ndwi": -0.2, "neighborhood_median": 45.0, "valid_neighbor_count": 8},
        {"year": 2022, "season": "summer", "extreme_type": "hot_top_20", "row": 50, "col": 50, "longitude": 72.8, "latitude": 21.1, "lst_c": 50.0, "obs_count": 10, "qa_k": 2.5, "ndvi": 0.2, "ndbi": 0.1, "ndwi": -0.2, "neighborhood_median": 45.0, "valid_neighbor_count": 8},
    ]
    df_raw = pd.DataFrame(records)
    df_inst, df_sum = compute_hotspot_persistence(df_raw, total_seasons_count=4)
    s = df_sum[df_sum["location"] == "R050_C050"].iloc[0]
    # Distinct seasons hot should be 1
    assert s["hot_seasons_count"] == 1
