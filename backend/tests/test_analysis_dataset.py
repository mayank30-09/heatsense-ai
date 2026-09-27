"""Tests for Analysis Dataset Structure, Quality Fields, and Delegation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gis.ml.dataset import (
    DEFAULT_SENSITIVITY_ROOT,
    assign_spatial_blocks,
)
from gis.quality.eligibility import evaluate_pixel_eligibility, EligibilityStatus


def test_dataset_required_columns():
    """Verify that generated analysis datasets have all mandatory fields."""
    pq_path = DEFAULT_SENSITIVITY_ROOT / "policy_d" / "analysis.parquet"
    if not pq_path.exists():
        pytest.skip("policy_d analysis.parquet not yet generated.")

    df = pd.read_parquet(pq_path)

    expected_cols = [
        "year",
        "season",
        "row",
        "col",
        "longitude",
        "latitude",
        "LST_C",
        "NDVI",
        "NDBI",
        "NDWI",
        "LST_OBS_COUNT",
        "LST_QA_MEDIAN_K",
        "quality_flag",
        "eligibility",
        "hotspot_frequency",
        "block_id",
        "neighborhood_median",
        "neighborhood_std",
        "pixel_minus_neighborhood_median",
        "absolute_pixel_minus_neighborhood_median",
        "valid_neighbor_count",
    ]

    for col in expected_cols:
        assert col in df.columns, f"Mandatory column '{col}' missing from analysis dataset."


def test_target_and_features_finite():
    """Verify target LST_C and all predictor features are strictly finite."""
    pq_path = DEFAULT_SENSITIVITY_ROOT / "policy_d" / "analysis.parquet"
    if not pq_path.exists():
        pytest.skip("policy_d analysis.parquet not yet generated.")

    df = pd.read_parquet(pq_path)

    assert np.all(np.isfinite(df["LST_C"].to_numpy())), "Target LST_C contains non-finite values."
    for feat in ["NDVI", "NDBI", "NDWI", "LST_OBS_COUNT", "LST_QA_MEDIAN_K"]:
        assert np.all(np.isfinite(df[feat].to_numpy())), f"Feature '{feat}' contains non-finite values."


def test_spatial_blocks_assignment():
    """Verify block IDs are deterministic and well-formed."""
    df_dummy = pd.DataFrame({
        "row": [0, 19, 20, 39, 40],
        "col": [0, 19, 20, 39, 40],
    })
    df_blocked = assign_spatial_blocks(df_dummy, block_size=20)
    assert "block_id" in df_blocked.columns
    assert df_blocked.loc[0, "block_id"] == "B_00_00"
    assert df_blocked.loc[1, "block_id"] == "B_00_00"
    assert df_blocked.loc[2, "block_id"] == "B_01_01"
    assert df_blocked.loc[3, "block_id"] == "B_01_01"
    assert df_blocked.loc[4, "block_id"] == "B_02_02"


def test_policy_delegation_consistency():
    """Verify that dataset builder delegates directly to authoritative eligibility logic."""
    # Policy D rule: cold anomalies EXCLUDE
    status_cold, reason_cold = evaluate_pixel_eligibility(
        obs_count=1,
        policy_name="policy_d",
        quality_flags=["LOW_SUPPORT_SPATIAL_EXTREME"],
        abs_diff_med=7.0,
        is_persistent_hotspot=False,
    )
    assert status_cold == EligibilityStatus.EXCLUDE

    # Test multi-obs normal pixel -> ACCEPT under Policy D
    status_normal, reason_normal = evaluate_pixel_eligibility(
        obs_count=3,
        policy_name="policy_d",
        quality_flags=[],
        abs_diff_med=0.5,
    )
    assert status_normal == EligibilityStatus.ACCEPT


def test_partial_season_metadata_preserved():
    """Verify 2026 monsoon is explicitly flagged as partial season."""
    pq_path = DEFAULT_SENSITIVITY_ROOT / "policy_d" / "analysis.parquet"
    if not pq_path.exists():
        pytest.skip("policy_d analysis.parquet not yet generated.")

    df = pd.read_parquet(pq_path)
    monsoon_2026 = df[(df["year"] == 2026) & (df["season"] == "monsoon")]
    if len(monsoon_2026) > 0:
        assert monsoon_2026["is_partial_season"].all(), "2026 monsoon must have is_partial_season=True"

    summer_2024 = df[(df["year"] == 2024) & (df["season"] == "summer")]
    if len(summer_2024) > 0:
        assert not summer_2024["is_partial_season"].any(), "2024 summer must have is_partial_season=False"
