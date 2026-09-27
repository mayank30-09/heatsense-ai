"""XGBoost Regressor for HEATSENSE AI.

Provides reproducible spatial cross-validation training, prediction,
and metric evaluation using XGBoost's XGBRegressor.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import xgboost as xgb
from gis.ml.rf_model import compute_regression_metrics, DEFAULT_FEATURES, TARGET_COL


def get_default_xgb_params() -> dict[str, Any]:
    """Default baseline XGBoost hyperparameters."""
    return {
        "n_estimators": 500,
        "learning_rate": 0.05,
        "max_depth": 6,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "n_jobs": -1,
        "tree_method": "hist",
    }


def train_xgb_regressor(
    X_train: np.ndarray,
    y_train: np.ndarray,
    sample_weight: np.ndarray | None = None,
    params: dict[str, Any] | None = None,
) -> xgb.XGBRegressor:
    """
    Instantiate and fit an XGBoost Regressor.

    Parameters
    ----------
    X_train : np.ndarray
        Training feature matrix.
    y_train : np.ndarray
        Training target vector.
    sample_weight : np.ndarray | None
        Optional sample weights.
    params : dict[str, Any] | None
        Hyperparameters overriding defaults.

    Returns
    -------
    xgb.XGBRegressor
        Fitted model.
    """
    xgb_params = get_default_xgb_params()
    if params:
        xgb_params.update(params)

    model = xgb.XGBRegressor(**xgb_params)
    model.fit(X_train, y_train, sample_weight=sample_weight)
    return model
