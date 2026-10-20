"""Automated Tests for Dataset Quality and Scientific Correctness (Phase 1).

Covers:
- Schema integrity, dtypes, and finite values.
- Key uniqueness on (year, season, row, col).
- Optical sentinels handling, bounds, and partition isolation.
- LST_QA_MEDIAN_K radiometric uncertainty behavior.
- Temperature extremes classification (VALID, FLAGGED, INVALID).
- Reproducible dataset quality JSON report verification.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gis.quality.imputation import is_optical_invalid
from scripts.validate_analysis_dataset import (
    MANDATORY_COLUMNS,
    OBSERVATION_KEY,
    OPTICAL_FEATURES,
    SENTINEL_THRESHOLD,
    classify_temperature_observation,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
AUDIT_JSON_PATH = PROJECT_ROOT / "artifacts" / "dataset_quality_audit.json"
HOLDOUT_SPLIT_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"


@pytest.fixture(scope="module")
def analysis_df() -> pd.DataFrame:
    if not DATASET_PATH.exists():
        pytest.skip(f"Analysis dataset not found at {DATASET_PATH}")
    return pd.read_parquet(DATASET_PATH)


@pytest.fixture(scope="module")
def holdout_split() -> dict:
    if not HOLDOUT_SPLIT_PATH.exists():
        pytest.skip(f"Holdout split not found at {HOLDOUT_SPLIT_PATH}")
    with open(HOLDOUT_SPLIT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_schema_integrity_and_columns(analysis_df: pd.DataFrame):
    """Verify that all mandatory columns are present with finite target and feature values."""
    for col in MANDATORY_COLUMNS:
        assert col in analysis_df.columns, f"Mandatory column '{col}' missing."

    core_numerical = ["LST_C", "NDVI", "NDBI", "NDWI", "LST_OBS_COUNT", "LST_QA_MEDIAN_K"]
    for col in core_numerical:
        arr = analysis_df[col].to_numpy()
        assert np.all(np.isfinite(arr)), f"Core column '{col}' has non-finite values."


def test_observation_key_uniqueness(analysis_df: pd.DataFrame):
    """Verify no duplicate records exist for the spatio-temporal observation key."""
    duplicates = analysis_df.duplicated(subset=OBSERVATION_KEY, keep=False).sum()
    assert duplicates == 0, f"Found {duplicates} duplicate records on {OBSERVATION_KEY}."


def test_optical_sentinel_policy_and_isolation(analysis_df: pd.DataFrame, holdout_split: dict):
    """Verify optical sentinels (-9999) are accurately flagged and strictly isolated in development blocks."""
    dev_blocks = set(holdout_split["development_blocks"])
    test_blocks = set(holdout_split["test_blocks"])

    sentinel_mask = (
        (analysis_df["NDVI"] <= SENTINEL_THRESHOLD)
        | (analysis_df["NDBI"] <= SENTINEL_THRESHOLD)
        | (analysis_df["NDWI"] <= SENTINEL_THRESHOLD)
    )
    sentinel_rows = analysis_df[sentinel_mask]

    # Verify sentinel count is non-zero (8 known rows) and none exist in test split
    assert len(sentinel_rows) == 8, f"Expected 8 sentinel rows, found {len(sentinel_rows)}."
    for _, row in sentinel_rows.iterrows():
        b_id = row["block_id"]
        assert b_id in dev_blocks, f"Sentinel row {b_id} leaked into non-dev split!"
        assert b_id not in test_blocks, f"Sentinel row {b_id} found in locked test split!"

    # Verify is_optical_invalid detects all sentinels and out-of-bound values
    assert bool(is_optical_invalid(-9999.0)) is True
    assert bool(is_optical_invalid(np.nan)) is True
    assert bool(is_optical_invalid(1.5)) is True
    assert bool(is_optical_invalid(-1.2)) is True
    assert bool(is_optical_invalid(0.35)) is False


def test_lst_qa_median_k_behavior(analysis_df: pd.DataFrame):
    """Verify LST_QA_MEDIAN_K units, bounds, and tail characteristics."""
    qa = analysis_df["LST_QA_MEDIAN_K"]
    assert qa.min() >= 0.0, "Radiometric uncertainty in Kelvin cannot be negative."
    assert qa.median() > 1.0, "Median QA uncertainty should be > 1.0 K."

    # Exactly 1,005 records have QA > 10.0 K reflecting high atmospheric uncertainty
    high_qa_count = (qa > 10.0).sum()
    assert high_qa_count == 1005, f"Expected 1,005 high QA records, found {high_qa_count}."
    assert qa.max() <= 100.0, f"QA maximum {qa.max()} exceeds physical sanity bound 100 K."


def test_temperature_extreme_classification():
    """Verify deterministic categorization of temperature observations into VALID, FLAGGED, and INVALID."""
    # 70.23°C single observation with high QA -> FLAGGED
    status_hot = classify_temperature_observation(lst_c=70.2328, obs_count=1, qa_k=84.99, delta_neigh=8.92)
    assert status_hot == "FLAGGED"

    # Extreme cold anomaly with large negative neighborhood discrepancy -> INVALID
    status_cold_artifact = classify_temperature_observation(lst_c=6.47, obs_count=1, qa_k=3.5, delta_neigh=-15.39)
    assert status_cold_artifact == "INVALID"

    # Normal physical observation with multi-pass support -> VALID
    status_normal = classify_temperature_observation(lst_c=36.5, obs_count=10, qa_k=2.3, delta_neigh=0.5)
    assert status_normal == "VALID"


def test_reproducible_audit_report_artifact():
    """Verify the reproducibility and integrity of dataset_quality_audit.json."""
    assert AUDIT_JSON_PATH.exists(), f"Audit report not found at {AUDIT_JSON_PATH}"
    with open(AUDIT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["audit_name"] == "HEATSENSE_AI_DATASET_QUALITY_AUDIT"
    assert data["total_records"] == 924731
    assert data["validation_passed"] is True
    assert data["duplicate_records"]["duplicate_count"] == 0
    assert data["optical_sentinels"]["total_sentinel_rows"] == 8
    assert data["optical_sentinels"]["all_sentinels_in_development_partition"] is True
    assert data["radiometric_uncertainty_qa"]["records_above_10_kelvin"] == 1005
    assert data["extreme_temperature_investigation"]["hot_extreme"]["classification"] == "FLAGGED"
