"""Regression tests for Issue 1: Optical Sentinel Sensitivity Audit.

Verifies the invariant that the locked independent test population contains
zero optical-feature sentinel observations (-9999.0), that development sentinels
are strictly bounded to 8 flagged monsoon observations, and that sensitivity
audit artifacts confirm resolution.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analyze_optical_sentinel_spatial_proximity import (
    DISTANCE_BINS,
    compute_distance_bin_summary,
)
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
SPLIT_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"
AUDIT_SUMMARY_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "sentinel_sensitivity" / "sentinel_sensitivity_summary.json"
LOCAL_EFFECT_CSV_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "sentinel_sensitivity" / "sentinel_local_effect.csv"
LOCAL_EFFECT_JSON_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "sentinel_sensitivity" / "sentinel_local_effect_summary.json"
PROXIMITY_CSV_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "sentinel_sensitivity" / "sentinel_spatial_proximity.csv"
PROXIMITY_JSON_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "sentinel_sensitivity" / "sentinel_spatial_proximity_summary.json"

SENTINEL_VAL = -9999.0
OPTICAL_FEATURES = ["NDVI", "NDBI", "NDWI"]


@pytest.fixture(scope="module")
def dataset_and_split():
    if not DATASET_PATH.exists():
        pytest.skip(f"Analysis dataset missing: {DATASET_PATH}")
    if not SPLIT_PATH.exists():
        pytest.skip(f"Holdout split missing: {SPLIT_PATH}")

    df = pd.read_parquet(DATASET_PATH)
    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        split = json.load(f)

    return df, split


def test_locked_test_population_has_zero_optical_sentinels(dataset_and_split):
    """Core scientific invariant: locked independent test set contains 0 optical sentinels."""
    df, split = dataset_and_split
    test_blocks = set(split["test_blocks"])
    test_df = df[df["block_id"].isin(test_blocks)]

    assert len(test_df) == 203758, f"Expected 203,758 test rows, found {len(test_df)}"

    test_sentinel_mask = (
        test_df["NDVI"].eq(SENTINEL_VAL)
        | test_df["NDBI"].eq(SENTINEL_VAL)
        | test_df["NDWI"].eq(SENTINEL_VAL)
    )
    sentinel_count = int(test_sentinel_mask.sum())
    assert sentinel_count == 0, (
        f"FATAL: Locked test set contains {sentinel_count} optical sentinel rows! "
        "Test population purity violated."
    )


def test_development_sentinels_strictly_bounded_and_flagged(dataset_and_split):
    """Development set contains exactly 8 sentinel rows, all categorized as Policy D FLAG."""
    df, split = dataset_and_split
    dev_blocks = set(split["development_blocks"])
    dev_df = df[df["block_id"].isin(dev_blocks)]

    assert len(dev_df) == 720973, f"Expected 720,973 dev rows, found {len(dev_df)}"

    dev_sentinel_mask = (
        dev_df["NDVI"].eq(SENTINEL_VAL)
        | dev_df["NDBI"].eq(SENTINEL_VAL)
        | dev_df["NDWI"].eq(SENTINEL_VAL)
    )
    sentinel_rows = dev_df[dev_sentinel_mask]
    assert len(sentinel_rows) == 8, f"Expected exactly 8 development sentinel rows, found {len(sentinel_rows)}"

    # Check block distribution
    sentinel_blocks = set(sentinel_rows["block_id"].unique())
    assert sentinel_blocks == {"B_05_11", "B_10_04"}

    # Check eligibility and quality flag
    assert set(sentinel_rows["eligibility"].unique()) == {"FLAG"}
    assert set(sentinel_rows["quality_flag"].unique()) == {"LOW_TEMPORAL_SUPPORT;SPATIALLY_COHERENT"}


def test_sentinel_sensitivity_audit_artifacts_resolved():
    """Verify that sensitivity audit summary artifact exists and confirms resolution."""
    if not AUDIT_SUMMARY_PATH.exists():
        pytest.skip(f"Audit summary missing: {AUDIT_SUMMARY_PATH}")

    with open(AUDIT_SUMMARY_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)

    assert summary["status"] == "RESOLVED BY SENSITIVITY EVIDENCE"
    assert summary["frozen_model_changed"] is False
    assert summary["authoritative_dataset_changed"] is False
    assert summary["locked_test_modified"] is False
    assert summary["common_non_sentinel_validation_rows"] == 720965

    # Check metric stability
    diffs = summary["metric_differences_abs"]
    assert diffs["delta_MAE"] <= 0.005
    assert diffs["delta_RMSE"] <= 0.005
    assert diffs["delta_R2"] <= 0.005


@pytest.mark.skipif(
    not LOCAL_EFFECT_CSV_PATH.exists(),
    reason="Large untracked sentinel_local_effect.csv not present in checkout",
)
def test_sentinel_local_effect_artifacts_exist():
    """Test A: Verify that local effect CSV and summary JSON artifacts exist."""
    assert LOCAL_EFFECT_CSV_PATH.exists(), f"Missing local effect CSV: {LOCAL_EFFECT_CSV_PATH}"
    assert LOCAL_EFFECT_JSON_PATH.exists(), f"Missing local effect summary JSON: {LOCAL_EFFECT_JSON_PATH}"


def test_sentinel_local_effect_summary_structure():
    """Test B: Verify that local effect summary JSON contains all required fields and sub-keys."""
    if not LOCAL_EFFECT_JSON_PATH.exists():
        pytest.skip(f"Local effect summary missing: {LOCAL_EFFECT_JSON_PATH}")

    with open(LOCAL_EFFECT_JSON_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # Required top-level keys
    required_keys = [
        "analysis",
        "prediction_difference_c",
        "threshold_counts",
        "affected_blocks",
        "season_gt_1C",
        "season_effect",
        "top_effects",
    ]
    for key in required_keys:
        assert key in summary, f"Required key '{key}' missing from summary JSON"

    # Analysis sub-keys
    analysis = summary["analysis"]
    for k in ["original_rows", "sentinel_excluded_rows", "matched_rows"]:
        assert k in analysis, f"Key '{k}' missing from analysis"
    assert analysis["matched_rows"] == analysis["original_rows"] == analysis["sentinel_excluded_rows"] == 720973

    # Prediction difference sub-keys
    pred_diff = summary["prediction_difference_c"]
    for k in ["mean", "mean_absolute", "rmse", "p95_absolute", "p99_absolute", "max_absolute", "min_delta", "max_delta"]:
        assert k in pred_diff, f"Key '{k}' missing from prediction_difference_c"

    # Threshold counts sub-keys
    thresh_counts = summary["threshold_counts"]
    expected_thresholds = [
        "abs_delta_gt_0_1C",
        "abs_delta_gt_0_25C",
        "abs_delta_gt_0_5C",
        "abs_delta_gt_1_0C",
        "abs_delta_gt_2_0C",
        "abs_delta_gt_3_0C",
        "abs_delta_gt_4_0C",
    ]
    for k in expected_thresholds:
        assert k in thresh_counts, f"Key '{k}' missing from threshold_counts"

    # Affected blocks sub-keys
    blocks = summary["affected_blocks"]
    for k in ["total_blocks", "max_abs_delta_gt_1C", "max_abs_delta_gt_2C", "max_abs_delta_gt_4C", "blocks_with_max_delta_gt_1C"]:
        assert k in blocks, f"Key '{k}' missing from affected_blocks"
    assert blocks["total_blocks"] == 132

    # Season gt 1C and season_effect
    assert isinstance(summary["season_gt_1C"], dict)
    assert isinstance(summary["season_effect"], dict)
    for s_name, s_data in summary["season_effect"].items():
        for field in ["rows", "mean_abs_delta_c", "max_abs_delta_c", "p95_abs_delta_c", "p99_abs_delta_c", "obs_gt_1C", "obs_gt_2C", "obs_gt_4C"]:
            assert field in s_data, f"Field '{field}' missing from season_effect[{s_name}]"
            assert math.isfinite(s_data[field]), f"Non-finite value in season_effect[{s_name}][{field}]"

    # Top effects
    assert isinstance(summary["top_effects"], list)
    assert len(summary["top_effects"]) >= 20


def test_sentinel_local_effect_summary_values_finite():
    """Test C: Verify that all prediction-difference summary values are finite numbers."""
    if not LOCAL_EFFECT_JSON_PATH.exists():
        pytest.skip(f"Local effect summary missing: {LOCAL_EFFECT_JSON_PATH}")

    with open(LOCAL_EFFECT_JSON_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)

    pred_diff = summary["prediction_difference_c"]
    for k, val in pred_diff.items():
        assert isinstance(val, (int, float)), f"Value for '{k}' is not numeric: {val}"
        assert math.isfinite(val), f"Value for '{k}' is non-finite: {val}"

    # Also verify threshold counts are valid non-negative integers
    for k, val in summary["threshold_counts"].items():
        assert isinstance(val, int) and val >= 0, f"Invalid threshold count for '{k}': {val}"


def test_sentinel_local_effect_csv_columns_and_mathematical_consistency():
    """Tests D, E, F: Verify CSV columns and mathematical relationships.

    - Test D: CSV contains required columns.
    - Test E: prediction_delta_c == prediction_clean_c - prediction_original_c (within 1e-6).
    - Test F: abs_prediction_delta_c == abs(prediction_delta_c) (within 1e-6).
    """
    if not LOCAL_EFFECT_CSV_PATH.exists():
        pytest.skip(f"Local effect CSV missing: {LOCAL_EFFECT_CSV_PATH}")

    # Read CSV
    df = pd.read_csv(LOCAL_EFFECT_CSV_PATH)

    # Test D: Required columns
    expected_cols = [
        "year",
        "season",
        "row",
        "col",
        "block_id",
        "prediction_original_c",
        "prediction_clean_c",
        "prediction_delta_c",
        "abs_prediction_delta_c",
    ]
    for col in expected_cols:
        assert col in df.columns, f"Expected column '{col}' missing from {LOCAL_EFFECT_CSV_PATH.name}"

    assert len(df) == 720973, f"Expected 720,973 matched rows, found {len(df)}"

    # Test E: prediction_delta_c == prediction_clean_c - prediction_original_c within 1e-6
    delta_computed = df["prediction_clean_c"] - df["prediction_original_c"]
    max_delta_diff = (df["prediction_delta_c"] - delta_computed).abs().max()
    assert max_delta_diff <= 1e-6, f"prediction_delta_c mismatch: max diff = {max_delta_diff}"

    # Test F: abs_prediction_delta_c == abs(prediction_delta_c) within 1e-6
    abs_delta_computed = df["prediction_delta_c"].abs()
    max_abs_diff = (df["abs_prediction_delta_c"] - abs_delta_computed).abs().max()
    assert max_abs_diff <= 1e-6, f"abs_prediction_delta_c mismatch: max diff = {max_abs_diff}"

    # Verify descending sort order
    assert df["abs_prediction_delta_c"].is_monotonic_decreasing, "CSV rows are not sorted descending by abs_prediction_delta_c"


@pytest.mark.skipif(
    not PROXIMITY_CSV_PATH.exists(),
    reason="Large untracked sentinel_spatial_proximity.csv not present in checkout",
)
def test_sentinel_spatial_proximity_artifacts_exist():
    """Verify that spatial proximity CSV and summary JSON artifacts exist."""
    assert PROXIMITY_CSV_PATH.exists(), f"Missing proximity CSV: {PROXIMITY_CSV_PATH}"
    assert PROXIMITY_JSON_PATH.exists(), f"Missing proximity summary JSON: {PROXIMITY_JSON_PATH}"


def test_sentinel_spatial_proximity_summary_structure():
    """Verify spatial proximity summary JSON keys, metrics, and population conservation."""
    if not PROXIMITY_JSON_PATH.exists():
        pytest.skip(f"Proximity summary JSON missing: {PROXIMITY_JSON_PATH}")

    with open(PROXIMITY_JSON_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)

    required_keys = [
        "sentinel_count",
        "effect_rows",
        "same_block_rows",
        "different_block_rows",
        "same_block_mean_abs_delta_c",
        "different_block_mean_abs_delta_c",
        "distance_summary",
        "threshold_profile",
    ]
    for k in required_keys:
        assert k in summary, f"Required key '{k}' missing from proximity summary JSON"

    assert summary["sentinel_count"] == 8
    assert summary["effect_rows"] == 720973
    assert summary["same_block_rows"] + summary["different_block_rows"] == summary["effect_rows"]

    for k in ["same_block_mean_abs_delta_c", "different_block_mean_abs_delta_c"]:
        assert isinstance(summary[k], (int, float))
        assert math.isfinite(summary[k]) and summary[k] >= 0.0

    # Distance summary verification
    assert isinstance(summary["distance_summary"], list)
    assert len(summary["distance_summary"]) == 8
    total_binned_obs = sum(item["observations"] for item in summary["distance_summary"])
    assert total_binned_obs == summary["effect_rows"], f"Distance bins sum to {total_binned_obs} != {summary['effect_rows']}"

    total_observations = summary["effect_rows"]
    for bin_item in summary["distance_summary"]:
        # Verify required keys exist and are finite numbers
        for req_field in [
            "observations",
            "percentage",
            "mean_abs_delta_c",
            "max_abs_delta_c",
            "gt_1C",
            "gt_1C_pct",
            "gt_2C",
            "gt_2C_pct",
            "gt_4C",
            "gt_4C_pct",
        ]:
            assert req_field in bin_item, f"Required field '{req_field}' missing from distance bin {bin_item.get('distance_bin')}"
            val = bin_item[req_field]
            assert isinstance(val, (int, float)), f"Field '{req_field}' must be numeric, got {type(val)}"
            assert math.isfinite(val), f"Field '{req_field}' must be finite, got {val}"

        obs = bin_item["observations"]
        assert obs >= 0
        assert 0 <= bin_item["gt_4C"] <= bin_item["gt_2C"] <= bin_item["gt_1C"] <= obs
        assert 0.0 <= bin_item["gt_4C_pct"] <= bin_item["gt_2C_pct"] <= bin_item["gt_1C_pct"] <= 100.0
        assert 0.0 <= bin_item["percentage"] <= 100.0

        if obs > 0:
            expected_pct = (obs / total_observations) * 100.0
            assert abs(bin_item["percentage"] - expected_pct) <= 1e-4, (
                f"Percentage mismatch for {bin_item['distance_bin']}: {bin_item['percentage']} vs {expected_pct}"
            )

            for thresh_name, pct_name in [("gt_1C", "gt_1C_pct"), ("gt_2C", "gt_2C_pct"), ("gt_4C", "gt_4C_pct")]:
                expected_thresh_pct = (bin_item[thresh_name] / obs) * 100.0
                assert abs(bin_item[pct_name] - expected_thresh_pct) <= 1e-4, (
                    f"{pct_name} mismatch for {bin_item['distance_bin']}: {bin_item[pct_name]} vs {expected_thresh_pct}"
                )
        else:
            assert bin_item["percentage"] == 0.0
            assert bin_item["gt_1C_pct"] == 0.0
            assert bin_item["gt_2C_pct"] == 0.0
            assert bin_item["gt_4C_pct"] == 0.0

    # Threshold profile verification
    assert isinstance(summary["threshold_profile"], dict)
    for t_key in ["gt_1_0C", "gt_2_0C", "gt_4_0C"]:
        assert t_key in summary["threshold_profile"]
        profile = summary["threshold_profile"][t_key]
        assert profile["same_block_count"] + profile["different_block_count"] == profile["observations"]
        assert profile["median_nearest_sentinel_distance_cells"] >= 0.0
        assert profile["max_nearest_sentinel_distance_cells"] >= profile["median_nearest_sentinel_distance_cells"]


def test_sentinel_spatial_proximity_csv_schema_and_integrity():
    """Verify proximity CSV columns, row count preservation, distance formulas, and binning."""
    if not PROXIMITY_CSV_PATH.exists():
        pytest.skip(f"Proximity CSV missing: {PROXIMITY_CSV_PATH}")

    df = pd.read_csv(PROXIMITY_CSV_PATH)

    required_cols = [
        "year",
        "season",
        "row",
        "col",
        "block_id",
        "prediction_delta_c",
        "abs_prediction_delta_c",
        "nearest_sentinel_distance_cells",
        "nearest_sentinel_year",
        "nearest_sentinel_season",
        "nearest_sentinel_row",
        "nearest_sentinel_col",
        "nearest_sentinel_block_id",
        "same_block_as_nearest_sentinel",
        "distance_bin",
    ]
    for col in required_cols:
        assert col in df.columns, f"Required column '{col}' missing from {PROXIMITY_CSV_PATH.name}"

    assert len(df) == 720973, f"Expected 720,973 rows, found {len(df)}"

    # Finiteness
    assert np.all(np.isfinite(df["nearest_sentinel_distance_cells"])), "Non-finite nearest sentinel distances found"
    assert (df["nearest_sentinel_distance_cells"] >= 0.0).all(), "Negative distances found"

    # Verify same_block classification consistency
    expected_same_block = (df["block_id"] == df["nearest_sentinel_block_id"])
    assert (df["same_block_as_nearest_sentinel"] == expected_same_block).all(), "Inconsistent same_block_as_nearest_sentinel flags"

    # Verify mathematical Euclidean distance consistency on sample rows
    sample = df.sample(n=min(500, len(df)), random_state=42)
    dr = sample["row"] - sample["nearest_sentinel_row"]
    dc = sample["col"] - sample["nearest_sentinel_col"]
    expected_dist = np.sqrt(dr ** 2 + dc ** 2)
    diff = (sample["nearest_sentinel_distance_cells"] - expected_dist).abs().max()
    assert diff <= 1e-4, f"Euclidean distance calculation mismatch: max diff = {diff}"

    # Verify distance bin assignment consistency on sample rows
    for _, r in sample.iterrows():
        d = r["nearest_sentinel_distance_cells"]
        b = r["distance_bin"]
        if d <= 1.0:
            assert b == "<=1 cell"
        elif d <= 2.0:
            assert b == "1-2 cells"
        elif d <= 5.0:
            assert b == "2-5 cells"
        elif d <= 10.0:
            assert b == "5-10 cells"
        elif d <= 20.0:
            assert b == "10-20 cells"
        elif d <= 50.0:
            assert b == "20-50 cells"
        elif d <= 100.0:
            assert b == "50-100 cells"
        else:
            assert b == ">100 cells"


# ---------------------------------------------------------------------------
# Stage B Unit Tests: Deterministic Diagnostics & Empty Bin Handling
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_distance_bin_data() -> pd.DataFrame:
    """Deterministic synthetic fixture for distance-bin percentage diagnostics.

    Creates a small dataset with known counts across standard distance bins:
    - '<=1 cell': 10 rows: 4 with delta > 1.0 (2 > 2.0, 1 > 4.0).
    - '1-2 cells': 20 rows: 0 with delta > 1.0.
    - '2-5 cells': 0 rows (empty bin).
    - '5-10 cells': 5 rows: 1 with delta > 1.0.
    """
    records = []
    # <=1 cell (10 rows: deltas 5.0, 3.0, 1.5, 1.2, 0.8, 0.5, 0.2, 0.1, 0.05, 0.01)
    # gt_1C = 4 (40%), gt_2C = 2 (20%), gt_4C = 1 (10%)
    for d in [5.0, 3.0, 1.5, 1.2, 0.8, 0.5, 0.2, 0.1, 0.05, 0.01]:
        records.append({"distance_bin": "<=1 cell", "abs_prediction_delta_c": d})
    # 1-2 cells (20 rows: all delta 0.05)
    for _ in range(20):
        records.append({"distance_bin": "1-2 cells", "abs_prediction_delta_c": 0.05})
    # 5-10 cells (5 rows: one 1.5, four 0.2)
    records.append({"distance_bin": "5-10 cells", "abs_prediction_delta_c": 1.5})
    for _ in range(4):
        records.append({"distance_bin": "5-10 cells", "abs_prediction_delta_c": 0.2})

    return pd.DataFrame(records)


def test_distance_bin_summary_deterministic_rates(synthetic_distance_bin_data):
    """Test rate and percentage calculation logic against exact deterministic targets."""
    df = synthetic_distance_bin_data
    total_matched = 100  # Explicit denominator: 35 rows in df, 100 total
    summary = compute_distance_bin_summary(df, total_matched=total_matched)

    summary_by_bin = {item["distance_bin"]: item for item in summary}

    # Bin <=1 cell
    b1 = summary_by_bin["<=1 cell"]
    assert b1["observations"] == 10
    assert b1["percentage"] == pytest.approx(10.0)  # 10 / 100 * 100
    assert b1["gt_1C"] == 4
    assert b1["gt_1C_pct"] == pytest.approx(40.0)  # 4 / 10 * 100
    assert b1["gt_2C"] == 2
    assert b1["gt_2C_pct"] == pytest.approx(20.0)  # 2 / 10 * 100
    assert b1["gt_4C"] == 1
    assert b1["gt_4C_pct"] == pytest.approx(10.0)  # 1 / 10 * 100
    assert b1["max_abs_delta_c"] == pytest.approx(5.0)

    # Bin 1-2 cells
    b2 = summary_by_bin["1-2 cells"]
    assert b2["observations"] == 20
    assert b2["percentage"] == pytest.approx(20.0)  # 20 / 100 * 100
    assert b2["gt_1C"] == 0
    assert b2["gt_1C_pct"] == pytest.approx(0.0)
    assert b2["gt_2C"] == 0
    assert b2["gt_2C_pct"] == pytest.approx(0.0)
    assert b2["gt_4C"] == 0
    assert b2["gt_4C_pct"] == pytest.approx(0.0)

    # Bin 2-5 cells (empty bin in synthetic data)
    b3 = summary_by_bin["2-5 cells"]
    assert b3["observations"] == 0
    assert b3["percentage"] == pytest.approx(0.0)
    assert b3["gt_1C"] == 0
    assert b3["gt_1C_pct"] == pytest.approx(0.0)
    assert b3["gt_2C"] == 0
    assert b3["gt_2C_pct"] == pytest.approx(0.0)
    assert b3["gt_4C"] == 0
    assert b3["gt_4C_pct"] == pytest.approx(0.0)
    assert b3["mean_abs_delta_c"] == pytest.approx(0.0)
    assert b3["max_abs_delta_c"] == pytest.approx(0.0)


def test_distance_bin_summary_zero_observation_handling():
    """Verify that empty bins and an empty DataFrame handle division safely and produce valid JSON."""
    empty_df = pd.DataFrame(columns=["distance_bin", "abs_prediction_delta_c"])
    summary = compute_distance_bin_summary(empty_df, total_matched=0)

    assert len(summary) == len(DISTANCE_BINS)
    for item in summary:
        assert item["observations"] == 0
        assert item["percentage"] == 0.0
        assert item["mean_abs_delta_c"] == 0.0
        assert item["max_abs_delta_c"] == 0.0
        assert item["gt_1C"] == 0
        assert item["gt_1C_pct"] == 0.0
        assert item["gt_2C"] == 0
        assert item["gt_2C_pct"] == 0.0
        assert item["gt_4C"] == 0
        assert item["gt_4C_pct"] == 0.0

    # Ensure clean JSON serializability (no NaN, Infinity, or serialization errors)
    serialized = json.dumps(summary)
    deserialized = json.loads(serialized)
    assert len(deserialized) == len(DISTANCE_BINS)


def test_distance_bin_summary_bounds_and_invariants(synthetic_distance_bin_data):
    """Verify count bounds: counts are non-negative and cannot exceed their denominators."""
    df = synthetic_distance_bin_data
    summary = compute_distance_bin_summary(df, total_matched=len(df))

    for item in summary:
        obs = item["observations"]
        assert obs >= 0
        assert item["gt_1C"] >= 0
        assert item["gt_2C"] >= 0
        assert item["gt_4C"] >= 0

        # Cannot exceed denominator
        assert item["gt_1C"] <= obs
        assert item["gt_2C"] <= obs
        assert item["gt_4C"] <= obs

        # Monotonicity of threshold exceedances: gt_4C <= gt_2C <= gt_1C
        assert item["gt_4C"] <= item["gt_2C"] <= item["gt_1C"]

        # Rates are within [0.0, 100.0]
        assert 0.0 <= item["percentage"] <= 100.0
        assert 0.0 <= item["gt_1C_pct"] <= 100.0
        assert 0.0 <= item["gt_2C_pct"] <= 100.0
        assert 0.0 <= item["gt_4C_pct"] <= 100.0


def test_distance_bin_summary_json_schema_and_precision():
    """Verify JSON schema preservation, field completeness, and numeric precision."""
    if not PROXIMITY_JSON_PATH.exists():
        pytest.skip(f"Proximity summary JSON missing: {PROXIMITY_JSON_PATH}")

    with open(PROXIMITY_JSON_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # Diagnostic and outcome metadata
    assert summary.get("outcome") == "Outcome B: Observed Distributed Prediction Sensitivity"
    assert "diagnostic" in summary

    expected_bin_keys = [
        "distance_bin",
        "observations",
        "percentage",
        "mean_abs_delta_c",
        "max_abs_delta_c",
        "gt_1C",
        "gt_1C_pct",
        "gt_2C",
        "gt_2C_pct",
        "gt_4C",
        "gt_4C_pct",
    ]

    for bin_record in summary["distance_summary"]:
        for k in expected_bin_keys:
            assert k in bin_record, f"Field '{k}' missing from distance_summary record"
            assert bin_record[k] is not None, f"Field '{k}' is None"

        # Check types
        assert isinstance(bin_record["distance_bin"], str)
        assert isinstance(bin_record["observations"], int)
        assert isinstance(bin_record["gt_1C"], int)
        assert isinstance(bin_record["gt_2C"], int)
        assert isinstance(bin_record["gt_4C"], int)

        for float_key in [
            "percentage",
            "mean_abs_delta_c",
            "max_abs_delta_c",
            "gt_1C_pct",
            "gt_2C_pct",
            "gt_4C_pct",
        ]:
            val = bin_record[float_key]
            assert isinstance(val, (int, float)), f"Expected float for {float_key}, got {type(val)}"
            assert math.isfinite(val), f"Non-finite value for {float_key}"




