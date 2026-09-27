"""Tests for XGBoost Regressor and SHAP Explainability."""

from __future__ import annotations

import numpy as np
import pytest

from gis.ml.xgb_model import train_xgb_regressor
from gis.ml.explainability import compute_tree_shap_values, compare_shap_stability
from gis.ml.rf_model import DEFAULT_FEATURES


def test_xgb_train_and_predict():
    """Verify XGBoost regressor trains and produces predictions."""
    rng = np.random.RandomState(42)
    X = rng.normal(0, 1, size=(200, 5))
    y = 2.5 * X[:, 0] - 1.2 * X[:, 1] + 32.0 + rng.normal(0, 0.3, size=200)

    model = train_xgb_regressor(
        X,
        y,
        params={"n_estimators": 25, "random_state": 42, "n_jobs": 1},
    )
    preds = model.predict(X[:10])
    assert len(preds) == 10
    assert np.all(np.isfinite(preds))


def test_xgb_reproducibility():
    """Verify identical random state produces identical XGBoost predictions."""
    rng = np.random.RandomState(99)
    X = rng.normal(0, 1, size=(100, 5))
    y = 1.8 * X[:, 0] + 28.0

    model1 = train_xgb_regressor(X, y, params={"n_estimators": 20, "random_state": 42, "n_jobs": 1})
    model2 = train_xgb_regressor(X, y, params={"n_estimators": 20, "random_state": 42, "n_jobs": 1})

    preds1 = model1.predict(X)
    preds2 = model2.predict(X)
    np.testing.assert_allclose(preds1, preds2, atol=1e-5)


def test_shap_attribution_computation():
    """Verify SHAP TreeExplainer outputs correct shapes and values."""
    rng = np.random.RandomState(42)
    X = rng.normal(0, 1, size=(150, 5))
    y = 3.0 * X[:, 0] + 0.1 * X[:, 1] + 30.0

    model = train_xgb_regressor(X, y, params={"n_estimators": 20, "random_state": 42, "n_jobs": 1})
    shap_res = compute_tree_shap_values(model, X[:30], DEFAULT_FEATURES)

    assert "shap_values" in shap_res
    assert shap_res["shap_values"].shape == (30, 5)
    assert "mean_abs_shap" in shap_res
    assert len(shap_res["mean_abs_shap"]) == 5
    assert "feature_ranking" in shap_res
    # X[:, 0] should have highest attribution
    assert shap_res["feature_ranking"][0] == DEFAULT_FEATURES[0]


def test_shap_stability_analysis():
    """Verify across-fold attribution stability summarizer."""
    mock_fold_results = [
        {"mean_abs_shap": {f: 1.0 + (i * 0.1) for f in DEFAULT_FEATURES}}
        for i in range(3)
    ]
    df_stability = compare_shap_stability(mock_fold_results, DEFAULT_FEATURES)
    assert len(df_stability) == len(DEFAULT_FEATURES)
    assert "mean_shap" in df_stability.columns
    assert "std_shap" in df_stability.columns
    assert "cov_percent" in df_stability.columns
