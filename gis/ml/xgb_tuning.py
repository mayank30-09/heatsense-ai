"""XGBoost Hyperparameter Tuning Module for HEATSENSE AI.

Provides:
- Dataset loading and strict schema validation
- Spatially stratified proportional sampling by block_id
- Deterministic 5-fold spatial cross-validation integration
- Optuna search space definition and TPE study orchestration
- Reproducibility metadata extraction and parameter serialization
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import pandas as pd
import sklearn
import xgboost as xgb

from gis.ml.rf_model import compute_regression_metrics, DEFAULT_FEATURES, TARGET_COL
from gis.ml.spatial_validation import (
    get_fold_metadata,
    spatial_block_folds,
    validate_fold_separation,
)

FEATURE_COLUMNS = DEFAULT_FEATURES
TARGET_COLUMN = TARGET_COL
REQUIRED_COLUMNS = FEATURE_COLUMNS + [TARGET_COLUMN, "block_id"]

PARAM_SEARCH_BOUNDS = {
    "n_estimators": (300, 1500),
    "max_depth": (3, 10),
    "learning_rate": (0.01, 0.20),
    "min_child_weight": (1.0, 20.0),
    "subsample": (0.6, 1.0),
    "colsample_bytree": (0.6, 1.0),
    "gamma": (0.0, 5.0),
    "reg_alpha": (1e-8, 10.0),
    "reg_lambda": (1e-3, 20.0),
}


def validate_dataset_schema(df: pd.DataFrame) -> None:
    """Verify that required predictors, target, and block_id exist and are finite."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    # Check finite values in target
    y_vals = df[TARGET_COLUMN].to_numpy()
    if not np.all(np.isfinite(y_vals)):
        raise ValueError(f"Target column '{TARGET_COLUMN}' contains non-finite values.")

    # Check finite values in features
    for col in FEATURE_COLUMNS:
        f_vals = df[col].to_numpy()
        if not np.all(np.isfinite(f_vals)):
            raise ValueError(f"Feature column '{col}' contains non-finite values.")


def sample_spatially_stratified(
    df: pd.DataFrame,
    sample_size: int = 250000,
    random_state: int = 42,
    block_col: str = "block_id",
) -> pd.DataFrame:
    """Sample approximately proportional rows grouped by spatial block.

    Guarantees that 100% of spatial blocks remain represented in the search sample,
    preventing geographical bias while reducing tuning computation time.
    If sample_size <= 0 or sample_size >= len(df), returns df unmodified.
    """
    if sample_size <= 0 or sample_size >= len(df):
        return df

    frac = sample_size / len(df)
    rng = np.random.RandomState(random_state)

    sampled_indices = []
    # Group by block_id to draw proportional samples
    for _, group in df.groupby(block_col):
        n_block = len(group)
        n_draw = max(1, int(round(n_block * frac)))
        n_draw = min(n_draw, n_block)
        chosen = rng.choice(group.index.to_numpy(), size=n_draw, replace=False)
        sampled_indices.extend(chosen)

    df_sampled = df.loc[sampled_indices].copy().reset_index(drop=True)
    return df_sampled


def sample_xgb_params(trial: optuna.Trial) -> dict[str, Any]:
    """Sample hyperparameters within the defined scientific search space."""
    return {
        "n_estimators": trial.suggest_int("n_estimators", 300, 1500, step=50),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.20, log=True),
        "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 20.0),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "gamma": trial.suggest_float("gamma", 0.0, 5.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 20.0, log=True),
        "objective": "reg:squarederror",
        "tree_method": "hist",
        "random_state": 42,
        "n_jobs": -1,
    }


def evaluate_spatial_cv(
    model_params: dict[str, Any],
    df: pd.DataFrame,
    folds: list[tuple[np.ndarray, np.ndarray]],
    trial: optuna.Trial | None = None,
) -> dict[str, Any]:
    """Train and evaluate an XGBoost model across spatial folds.

    Returns summary metrics (mean/std for MAE, RMSE, R2) and fold-level records.
    """
    X = df[FEATURE_COLUMNS].to_numpy()
    y = df[TARGET_COLUMN].to_numpy()

    fold_maes = []
    fold_rmses = []
    fold_r2s = []
    fold_details = []

    for fold_idx, (train_idx, val_idx) in enumerate(folds):
        model = xgb.XGBRegressor(**model_params)
        model.fit(X[train_idx], y[train_idx])

        y_pred = model.predict(X[val_idx])
        metrics = compute_regression_metrics(y[val_idx], y_pred)

        fold_maes.append(metrics["MAE"])
        fold_rmses.append(metrics["RMSE"])
        fold_r2s.append(metrics["R2"])

        fold_details.append({
            "fold": fold_idx + 1,
            "MAE": metrics["MAE"],
            "RMSE": metrics["RMSE"],
            "R2": metrics["R2"],
            "n_samples": metrics["n_samples"],
        })

        # Optuna intermediate pruning support
        if trial is not None:
            intermediate_mean_rmse = float(np.mean(fold_rmses))
            trial.report(intermediate_mean_rmse, step=fold_idx)
            if trial.should_prune():
                raise optuna.TrialPruned()

    return {
        "mean_rmse": float(np.mean(fold_rmses)),
        "std_rmse": float(np.std(fold_rmses)),
        "min_rmse": float(np.min(fold_rmses)),
        "max_rmse": float(np.max(fold_rmses)),
        "mean_mae": float(np.mean(fold_maes)),
        "std_mae": float(np.std(fold_maes)),
        "mean_r2": float(np.mean(fold_r2s)),
        "std_r2": float(np.std(fold_r2s)),
        "fold_details": fold_details,
    }


class XGBoostSpatialObjective:
    """Optuna objective function minimizing mean spatial cross-validation RMSE."""

    def __init__(
        self,
        df: pd.DataFrame,
        folds: list[tuple[np.ndarray, np.ndarray]],
    ) -> None:
        self.df = df
        self.folds = folds
        self.trial_records: list[dict[str, Any]] = []

    def __call__(self, trial: optuna.Trial) -> float:
        params = sample_xgb_params(trial)
        t0 = time.time()
        try:
            eval_res = evaluate_spatial_cv(params, self.df, self.folds, trial=trial)
            elapsed = time.time() - t0

            record = {
                "trial_number": trial.number,
                "state": "COMPLETE",
                "mean_rmse": eval_res["mean_rmse"],
                "std_rmse": eval_res["std_rmse"],
                "mean_mae": eval_res["mean_mae"],
                "mean_r2": eval_res["mean_r2"],
                "duration_seconds": round(elapsed, 2),
                **{k: trial.params[k] for k in trial.params},
            }
            self.trial_records.append(record)
            return eval_res["mean_rmse"]

        except optuna.TrialPruned:
            elapsed = time.time() - t0
            record = {
                "trial_number": trial.number,
                "state": "PRUNED",
                "mean_rmse": None,
                "std_rmse": None,
                "mean_mae": None,
                "mean_r2": None,
                "duration_seconds": round(elapsed, 2),
                **{k: trial.params[k] for k in trial.params},
            }
            self.trial_records.append(record)
            raise


def run_optuna_study(
    df_search: pd.DataFrame,
    folds: list[tuple[np.ndarray, np.ndarray]],
    n_trials: int = 30,
    random_state: int = 42,
) -> tuple[optuna.Study, list[dict[str, Any]]]:
    """Orchestrate deterministic Optuna TPE optimization study."""
    sampler = optuna.samplers.TPESampler(seed=random_state)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1)

    study = optuna.create_study(
        direction="minimize",
        sampler=sampler,
        pruner=pruner,
        study_name="heatsense_xgb_spatial_tuning",
    )

    objective = XGBoostSpatialObjective(df_search, folds)
    study.optimize(objective, n_trials=n_trials)
    return study, objective.trial_records


def build_tuning_metadata(
    dataset_path: str | Path,
    total_dataset_rows: int,
    search_sample_size: int,
    best_value_rmse: float,
    best_params: dict[str, Any],
    n_trials: int,
    n_folds: int = 5,
    random_state: int = 42,
    git_hash: str | None = None,
) -> dict[str, Any]:
    """Construct reproducible metadata dictionary for the tuning experiment."""
    return {
        "experiment_name": "XGBoost_Spatial_Hyperparameter_Tuning",
        "dataset_path": str(dataset_path),
        "total_dataset_rows": total_dataset_rows,
        "search_sample_size": search_sample_size,
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "spatial_validation_method": "5-Fold Spatial Block Cross-Validation (2km x 2km)",
        "number_of_folds": n_folds,
        "random_seed": random_state,
        "n_trials": n_trials,
        "best_value_rmse": round(float(best_value_rmse), 4),
        "best_params": best_params,
        "fixed_params": {
            "objective": "reg:squarederror",
            "tree_method": "hist",
            "random_state": 42,
            "n_jobs": -1,
        },
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "xgboost_version": xgb.__version__,
            "optuna_version": optuna.__version__,
            "sklearn_version": sklearn.__version__,
        },
        "git_commit": git_hash or "uncommitted",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
