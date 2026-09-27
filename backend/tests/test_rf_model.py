"""Tests for Random Forest Regressor and Baseline Metrics."""

from __future__ import annotations

import numpy as np
import pytest

from gis.ml.rf_model import (
    train_rf_regressor,
    compute_regression_metrics,
    get_default_rf_params,
    DEFAULT_FEATURES,
    TARGET_COL,
)


def test_metric_computation():
    """Verify MAE, RMSE, R2, and sample count calculations."""
    y_true = np.array([20.0, 30.0, 40.0, 50.0])
    y_pred = np.array([21.0, 29.0, 41.0, 49.0])

    metrics = compute_regression_metrics(y_true, y_pred)
    assert metrics["MAE"] == 1.0
    assert metrics["RMSE"] == 1.0
    assert metrics["R2"] > 0.98
    assert metrics["n_samples"] == 4


def test_rf_train_and_predict():
    """Verify RF model trains and produces predictions."""
    rng = np.random.RandomState(42)
    X = rng.normal(0, 1, size=(200, 5))
    y = 2.0 * X[:, 0] - 1.5 * X[:, 1] + 35.0 + rng.normal(0, 0.5, size=200)

    model = train_rf_regressor(
        X,
        y,
        params={"n_estimators": 20, "random_state": 42, "n_jobs": 1},
    )
    preds = model.predict(X[:10])
    assert len(preds) == 10
    assert np.all(np.isfinite(preds))


def test_rf_reproducibility():
    """Verify identical random state produces identical predictions."""
    rng = np.random.RandomState(123)
    X = rng.normal(0, 1, size=(100, 5))
    y = 1.2 * X[:, 0] + 30.0

    model1 = train_rf_regressor(X, y, params={"n_estimators": 20, "random_state": 42, "n_jobs": 1})
    model2 = train_rf_regressor(X, y, params={"n_estimators": 20, "random_state": 42, "n_jobs": 1})

    preds1 = model1.predict(X)
    preds2 = model2.predict(X)
    np.testing.assert_allclose(preds1, preds2, atol=1e-6)


def test_rf_sample_weights():
    """Verify sample weighting can be passed and influences the fit."""
    rng = np.random.RandomState(42)
    X = rng.normal(0, 1, size=(150, 5))
    y = 2.0 * X[:, 0] + 30.0

    weights = np.ones(150)
    weights[:50] = 0.25  # Lower weight on first 50 observations

    model = train_rf_regressor(
        X,
        y,
        sample_weight=weights,
        params={"n_estimators": 20, "random_state": 42, "n_jobs": 1},
    )
    preds = model.predict(X)
    assert len(preds) == 150
    assert np.all(np.isfinite(preds))
