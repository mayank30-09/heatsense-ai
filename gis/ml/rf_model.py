"""Random Forest Baseline Regressor for HEATSENSE AI.

Provides reproducible spatial cross-validation training, prediction,
and metric evaluation using scikit-learn's RandomForestRegressor.
"""

from __future__ import annotations

from typing import Any
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score

DEFAULT_FEATURES = ["NDVI", "NDBI", "NDWI", "LST_OBS_COUNT", "LST_QA_MEDIAN_K"]
TARGET_COL = "LST_C"


def get_default_rf_params() -> dict[str, Any]:
    """Default baseline Random Forest hyperparameters."""
    return {
        "n_estimators": 300,
        "min_samples_leaf": 3,
        "random_state": 42,
        "n_jobs": -1,
    }


def compute_regression_metrics(
    y_true: np.ndarray | list[float],
    y_pred: np.ndarray | list[float],
) -> dict[str, float]:
    """
    Compute standard regression accuracy metrics.

    Returns
    -------
    dict[str, float]
        MAE, RMSE, R2, and sample count n_samples.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    # Guard against NaN
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[valid]
    y_pred = y_pred[valid]

    n_samples = len(y_true)
    if n_samples == 0:
        return {"MAE": float("nan"), "RMSE": float("nan"), "R2": float("nan"), "n_samples": 0}

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))

    return {
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "R2": round(r2, 4),
        "n_samples": n_samples,
    }


def train_rf_regressor(
    X_train: np.ndarray,
    y_train: np.ndarray,
    sample_weight: np.ndarray | None = None,
    params: dict[str, Any] | None = None,
) -> RandomForestRegressor:
    """
    Instantiate and fit a Random Forest Regressor.

    Parameters
    ----------
    X_train : np.ndarray
        Training feature matrix.
    y_train : np.ndarray
        Training target vector.
    sample_weight : np.ndarray | None
        Optional sample weights (e.g. for FLAG sensitivity experiments).
    params : dict[str, Any] | None
        Hyperparameters overriding defaults.

    Returns
    -------
    RandomForestRegressor
        Fitted model.
    """
    rf_params = get_default_rf_params()
    if params:
        rf_params.update(params)

    model = RandomForestRegressor(**rf_params)
    model.fit(X_train, y_train, sample_weight=sample_weight)
    return model
