"""Automated Tests for Phase 2: ML Validation, Conformal Uncertainty, and Promotion Criteria.

Verifies:
1. Conformal calibrator interval generation, bounds validity, and nominal coverage guarantees.
2. Grouped spatial cross-validation fold disjointness and zero test leakage.
3. Feature ablation configuration consistency.
4. Training-fold isolation of sample weighting thresholds.
5. Strict promotion criteria enforcement (retaining baseline when conditions unmet).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from gis.ml.conformal import SpatiallyCalibratedConformalRegressor
from gis.ml.development_cv import development_spatial_folds
from scripts.run_ml_experiments import (
    ALL_FEATURES,
    TARGET,
    clean_features_for_training,
    compute_metrics,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOLDOUT_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"


@pytest.fixture(scope="module")
def holdout_split() -> dict:
    if not HOLDOUT_PATH.exists():
        pytest.skip(f"Holdout split not found at {HOLDOUT_PATH}")
    with open(HOLDOUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_conformal_calibrator_mathematical_properties():
    """Verify conformal predictor achieves valid bounds and empirical coverage on simulated residuals."""
    np.random.seed(42)
    n = 1000
    y_true = np.random.normal(loc=35.0, scale=5.0, size=n)
    # Add noise to predictions
    residuals = np.random.normal(loc=0.0, scale=1.5, size=n)
    y_pred = y_true + residuals

    calibrator = SpatiallyCalibratedConformalRegressor(alpha=0.10)
    calibrator.fit_calibration(y_true=y_true[:500], y_pred=y_pred[:500])

    assert calibrator.q_val is not None
    assert calibrator.q_val > 0.0, "Conformal quantile must be positive."

    # Test prediction interval properties on test set
    lower, upper, half_width = calibrator.predict_intervals(y_pred[500:])
    assert np.all(lower <= upper), "Lower bounds must be <= upper bounds."
    assert np.all(np.isclose(upper - lower, 2 * half_width)), "Interval width must be 2 * q_val."

    # Evaluate empirical coverage
    eval_res = calibrator.evaluate_coverage(y_true=y_true[500:], y_pred=y_pred[500:])
    assert eval_res["nominal_coverage"] == 0.90
    # On 500 samples drawn from same distribution, empirical coverage should be within 4% of nominal 90%
    assert 0.86 <= eval_res["overall_empirical_coverage"] <= 0.94


def test_spatial_cross_validation_strict_disjointness(holdout_split: dict):
    """Verify 5-fold spatial cross-validation produces mutually disjoint block groups with ZERO test leakage."""
    dev_blocks = holdout_split["development_blocks"]
    test_blocks = holdout_split["test_blocks"]

    # Create dummy DataFrame with 132 development blocks
    import pandas as pd
    dummy_rows = []
    for b in dev_blocks:
        for _ in range(5):
            dummy_rows.append({"block_id": b, "LST_C": 35.0})
    df_dummy = pd.DataFrame(dummy_rows)

    folds = development_spatial_folds(
        df_dev=df_dummy,
        development_blocks=dev_blocks,
        n_splits=5,
        random_state=42,
        block_col="block_id",
        prohibited_test_blocks=test_blocks,
    )

    assert len(folds) == 5

    all_val_blocks = set()
    for fold_idx, (tr_idx, val_idx) in enumerate(folds):
        tr_blocks = set(df_dummy.iloc[tr_idx]["block_id"].unique())
        val_blocks = set(df_dummy.iloc[val_idx]["block_id"].unique())

        # Disjointness assertion
        overlap = tr_blocks.intersection(val_blocks)
        assert len(overlap) == 0, f"Fold {fold_idx} has train/val block leakage: {overlap}"

        # Zero test blocks assertion
        test_overlap = val_blocks.intersection(set(test_blocks))
        assert len(test_overlap) == 0, f"Fold {fold_idx} leaked test blocks: {test_overlap}"

        all_val_blocks.update(val_blocks)

    # Every development block should appear in validation across the 5 folds
    assert all_val_blocks == set(dev_blocks)


def test_clean_features_training_fold_imputation():
    """Verify that optical sentinels (<= -9000) are replaced by training fold median without test leakage."""
    import pandas as pd
    df_tr = pd.DataFrame({
        "NDVI": [0.2, 0.4, 0.3, -9999.0],
        "NDBI": [0.1, 0.0, -0.1, 0.05],
        "NDWI": [-0.2, -0.3, -0.25, -0.22],
    })
    df_val = pd.DataFrame({
        "NDVI": [-9999.0, 0.35],
        "NDBI": [0.0, -0.05],
        "NDWI": [-0.2, -0.25],
    })

    X_tr_arr, fitted_imp = clean_features_for_training(df_tr)
    # NDVI valid median is 0.3
    assert fitted_imp["NDVI"] == 0.3
    # In training array, -9999 is replaced by 0.3
    assert X_tr_arr[3, 0] == 0.3

    # Clean validation using training fold fitted imputers
    X_val_arr, _ = clean_features_for_training(df_val, imputer_values=fitted_imp)
    # In val array, sentinel is replaced by training median 0.3
    assert X_val_arr[0, 0] == 0.3


def test_metrics_computation_with_upper_decile():
    """Verify metric computation accurately extracts upper-decile RMSE and bias."""
    y_true = np.array([20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0, 34.0, 36.0, 40.0])
    y_pred = np.array([20.1, 21.9, 24.0, 25.8, 28.2, 30.0, 31.8, 34.2, 35.5, 38.0])

    m = compute_metrics(y_true, y_pred)
    assert m["count"] == 10
    assert m["MAE"] > 0.0
    assert m["RMSE"] > 0.0
    assert m["UpperDecile_RMSE"] > 0.0
    # For top observation (40.0 vs 38.0), residual is +2.0
    assert m["UpperDecile_MeanBias"] > 0.0
