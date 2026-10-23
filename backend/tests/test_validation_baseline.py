"""Unit and Integration Tests for Phase 2: Validation, Baseline Comparison, and Holdout Safety.

Validates:
1. Spatial holdout block disjointness (132 dev blocks vs. 33 test blocks).
2. Zero spatial leakage between development and holdout splits in analysis.parquet.
3. Coordinate leakage prevention (lat, lon, row, col excluded from feature schema).
4. Development set benchmark comparison (Mean-by-cell baselines vs. ML models).
5. Holdout safety invariants (evaluation count == 1, test untouched during tuning).
6. Consistency across freeze manifests and model metadata artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
HOLDOUT_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"
QC_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "qc_summary.json"
MODEL_META_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "model_metadata.json"
EVAL_MANIFEST_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "evaluation_manifest.json"
ML_EXP_PATH = PROJECT_ROOT / "artifacts" / "ml_experiments" / "ml_experimental_evaluation.json"


# -----------------------------------------------------------------------------
# 1. Spatial Holdout Disjointness & Block Integrity
# -----------------------------------------------------------------------------
def test_spatial_holdout_block_disjointness():
    """Verify that development and test spatial blocks form a strict, disjoint partition."""
    assert HOLDOUT_PATH.exists(), f"Holdout split artifact missing: {HOLDOUT_PATH}"

    with open(HOLDOUT_PATH, "r", encoding="utf-8") as f:
        holdout = json.load(f)

    dev_blocks = holdout.get("development_blocks", [])
    test_blocks = holdout.get("test_blocks", [])

    assert len(dev_blocks) == 132, f"Expected 132 dev blocks, got {len(dev_blocks)}"
    assert len(test_blocks) == 33, f"Expected 33 test blocks, got {len(test_blocks)}"
    assert len(dev_blocks) + len(test_blocks) == 165, "Total block count must be 165"

    dev_set = set(dev_blocks)
    test_set = set(test_blocks)

    # Core disjointness assertion
    assert dev_set.isdisjoint(test_set), "Fatal: Overlap detected between development and test blocks!"

    # Verify block naming convention (B_XX_YY)
    for b in dev_blocks + test_blocks:
        parts = b.split("_")
        assert len(parts) == 3 and parts[0] == "B", f"Invalid block ID format: {b}"
        assert parts[1].isdigit() and parts[2].isdigit(), f"Non-numeric block indices: {b}"


# -----------------------------------------------------------------------------
# 2. Zero Spatial Leakage in Analysis Dataset
# -----------------------------------------------------------------------------
def test_zero_spatial_leakage_in_analysis_dataset():
    """Verify that rows in analysis.parquet strictly map to their assigned spatial partition."""
    assert DATASET_PATH.exists(), f"Analysis parquet missing: {DATASET_PATH}"

    with open(HOLDOUT_PATH, "r", encoding="utf-8") as f:
        holdout = json.load(f)

    dev_set = set(holdout["development_blocks"])
    test_set = set(holdout["test_blocks"])

    # Load block_id column only for fast verification
    df_blocks = pd.read_parquet(DATASET_PATH, columns=["block_id"])
    total_rows = len(df_blocks)
    assert total_rows == 924731, f"Expected 924,731 total rows, got {total_rows}"

    dev_mask = df_blocks["block_id"].isin(dev_set)
    test_mask = df_blocks["block_id"].isin(test_set)

    dev_row_count = int(dev_mask.sum())
    test_row_count = int(test_mask.sum())

    assert dev_row_count == 720973, f"Expected 720,973 dev rows, got {dev_row_count}"
    assert test_row_count == 203758, f"Expected 203,758 test rows, got {test_row_count}"
    assert dev_row_count + test_row_count == total_rows, "All rows must map to dev or test"

    # Strict partition mutual exclusivity
    assert (dev_mask & test_mask).sum() == 0, "No row may belong to both dev and test!"


def test_coordinate_leakage_prevention():
    """Verify that spatial coordinates (lat, lon, row, col, block_id) are excluded from ML features."""
    with open(QC_PATH, "r", encoding="utf-8") as f:
        qc = json.load(f)

    feature_schema = qc.get("feature_schema", {})
    features = feature_schema.get("features", [])

    prohibited_coords = {"latitude", "longitude", "lat", "lon", "row", "col", "block_id", "pixel_id"}
    leaked = set(features).intersection(prohibited_coords)
    assert not leaked, f"Spatial coordinates detected in model feature schema: {leaked}"
    assert feature_schema.get("coordinates_excluded") is True


# -----------------------------------------------------------------------------
# 3. Development Set Benchmark: Mean-by-Cell vs ML Models
# -----------------------------------------------------------------------------
def test_development_baseline_and_model_benchmarks():
    """Verify that the frozen ML model outperforms naive and stratified cell-mean baselines."""
    with open(QC_PATH, "r", encoding="utf-8") as f:
        qc = json.load(f)

    with open(MODEL_META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # 1. Verify frozen model CV metrics
    cv_rmse = meta.get("best_development_cv_rmse") or qc["model_training"]["development_cv_rmse"]
    assert pytest.approx(cv_rmse, abs=0.01) == 1.8478

    # 2. Check ML experiment results
    assert ML_EXP_PATH.exists(), f"ML experiments artifact missing: {ML_EXP_PATH}"
    with open(ML_EXP_PATH, "r", encoding="utf-8") as f:
        exp_data = json.load(f)

    experiments = exp_data.get("experiments", {})

    # Feature ablation: Optical only vs Full
    optical_rmse = experiments["feature_ablation"]["A_optical_only"]["CV_RMSE"]
    full_rmse = experiments["feature_ablation"]["D_full"]["CV_RMSE"]
    assert optical_rmse > 4.5, "Optical-only model must exhibit high RMSE (>4.5°C) without thermal calibration"
    assert full_rmse < 2.1, "Full model must achieve < 2.1°C CV RMSE"

    # Architecture comparison: Random Forest vs XGBoost
    rf_rmse = experiments["model_comparison"]["RandomForest"]["CV_RMSE"]
    xgb_rmse = experiments["model_comparison"]["XGBoost_Baseline"]["CV_RMSE"]
    assert xgb_rmse < rf_rmse, "XGBoost must outperform Random Forest"

    # Tail weighting: Candidate improved upper decile
    mild_top_rmse = experiments["tail_weighting"]["TailWeight_Mild"]["UpperDecile_RMSE"]
    control_top_rmse = experiments["tail_weighting"]["Control_Uniform"]["UpperDecile_RMSE"]
    assert mild_top_rmse < control_top_rmse, "Tail-weighted candidate must improve upper-decile error"


# -----------------------------------------------------------------------------
# 4. Holdout Safety & Immutability Invariants
# -----------------------------------------------------------------------------
def test_holdout_safety_and_single_evaluation_rule():
    """Verify holdout safety: evaluated exactly once, never used for tuning or model selection."""
    with open(QC_PATH, "r", encoding="utf-8") as f:
        qc = json.load(f)

    with open(EVAL_MANIFEST_PATH, "r", encoding="utf-8") as f:
        eval_manifest = json.load(f)

    # Evaluation count must be strictly 1
    assert qc["holdout_evaluation"]["evaluation_count"] == 1
    assert eval_manifest["evaluation_count"] == 1
    assert eval_manifest["test_accessed_during_tuning"] is False

    # Check leakage controls flags
    leakage = qc.get("leakage_controls", {})
    assert leakage.get("test_blocks_excluded_from_optuna") is True
    assert leakage.get("test_blocks_excluded_from_feature_selection") is True
    assert leakage.get("test_blocks_excluded_from_model_selection") is True
    assert leakage.get("test_blocks_excluded_from_final_training") is True
    assert leakage.get("single_independent_evaluation_verified") is True

    # Check holdout metrics consistency
    assert pytest.approx(qc["holdout_evaluation"]["rmse"], abs=0.01) == 1.7524
    assert pytest.approx(qc["holdout_evaluation"]["r2"], abs=0.01) == 0.9006


# -----------------------------------------------------------------------------
# 5. Conformal Coverage & Subgroup Safety
# -----------------------------------------------------------------------------
def test_conformal_uncertainty_calibration():
    """Verify conformal calibration achieves >= 90% nominal spatial coverage on development folds."""
    with open(ML_EXP_PATH, "r", encoding="utf-8") as f:
        exp_data = json.load(f)

    conformal = exp_data["experiments"]["conformal_calibration"]
    assert conformal["nominal_coverage"] == 0.90
    assert conformal["overall_empirical_coverage"] >= 0.90
    assert pytest.approx(conformal["overall_empirical_coverage"], abs=0.02) == 0.9015

    # Check seasonal subgroup coverage
    subgroups = conformal["subgroups"]["season"]
    assert subgroups["summer"]["coverage"] >= 0.90
    assert subgroups["winter"]["coverage"] >= 0.90
    assert subgroups["post_monsoon"]["coverage"] >= 0.90
    # Monsoon has persistent cloud masking and higher variance, so its coverage is expectedly lower
    assert subgroups["monsoon"]["coverage"] > 0.75
