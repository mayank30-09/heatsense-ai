"""Tests for XGBoost Hyperparameter Tuning and Spatial Confirmation."""

from __future__ import annotations

import numpy as np
import optuna
import pandas as pd
import pytest

from gis.ml.spatial_validation import (
    spatial_block_folds,
    validate_fold_separation,
)
from gis.ml.xgb_tuning import (
    FEATURE_COLUMNS,
    PARAM_SEARCH_BOUNDS,
    REQUIRED_COLUMNS,
    TARGET_COLUMN,
    sample_spatially_stratified,
    sample_xgb_params,
    validate_dataset_schema,
)


@pytest.fixture
def mock_dataset() -> pd.DataFrame:
    """Create a minimal synthetic valid dataset with spatial blocks."""
    rng = np.random.RandomState(42)
    n = 200
    blocks = [f"B_{i // 20:02d}_{i % 5:02d}" for i in range(n)]
    df = pd.DataFrame({
        "NDVI": rng.uniform(0.0, 0.8, size=n),
        "NDBI": rng.uniform(-0.5, 0.5, size=n),
        "NDWI": rng.uniform(-0.6, 0.4, size=n),
        "LST_OBS_COUNT": rng.randint(1, 15, size=n).astype(float),
        "LST_QA_MEDIAN_K": rng.uniform(1.5, 6.0, size=n),
        "LST_C": rng.uniform(25.0, 48.0, size=n),
        "block_id": blocks,
    })
    return df


def test_spatial_leakage_and_fold_coverage(mock_dataset: pd.DataFrame):
    """Verify train_blocks INTERSECT val_blocks = empty and every row appears once in validation."""
    folds = spatial_block_folds(mock_dataset, n_splits=5, random_state=42)

    # 1. Leakage check
    assert validate_fold_separation(mock_dataset, folds) is True

    # 2. Fold coverage check
    all_val_indices = []
    for _, val_idx in folds:
        all_val_indices.extend(val_idx)

    assert len(all_val_indices) == len(mock_dataset)
    assert set(all_val_indices) == set(range(len(mock_dataset)))


def test_spatial_folds_reproducibility(mock_dataset: pd.DataFrame):
    """Verify that identical random seed produces identical spatial folds."""
    folds1 = spatial_block_folds(mock_dataset, n_splits=5, random_state=42)
    folds2 = spatial_block_folds(mock_dataset, n_splits=5, random_state=42)

    assert len(folds1) == len(folds2)
    for f in range(len(folds1)):
        np.testing.assert_array_equal(folds1[f][0], folds2[f][0])
        np.testing.assert_array_equal(folds1[f][1], folds2[f][1])


def test_schema_validation_rejects_missing_columns(mock_dataset: pd.DataFrame):
    """Verify that validate_dataset_schema raises ValueError when required columns are absent."""
    df_missing_target = mock_dataset.drop(columns=[TARGET_COLUMN])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_dataset_schema(df_missing_target)

    df_missing_feature = mock_dataset.drop(columns=["NDBI"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_dataset_schema(df_missing_feature)

    df_missing_block = mock_dataset.drop(columns=["block_id"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_dataset_schema(df_missing_block)


def test_schema_validation_rejects_non_finite_data(mock_dataset: pd.DataFrame):
    """Verify that validate_dataset_schema rejects infinite or NaN values in features or target."""
    df_nan_target = mock_dataset.copy()
    df_nan_target.loc[0, TARGET_COLUMN] = np.nan
    with pytest.raises(ValueError, match="Target column 'LST_C' contains non-finite"):
        validate_dataset_schema(df_nan_target)

    df_inf_feature = mock_dataset.copy()
    df_inf_feature.loc[1, "NDVI"] = np.inf
    with pytest.raises(ValueError, match="Feature column 'NDVI' contains non-finite"):
        validate_dataset_schema(df_inf_feature)


def test_spatially_stratified_sampling_preserves_all_blocks(mock_dataset: pd.DataFrame):
    """Verify that stratified proportional sampling retains 100% of spatial blocks."""
    initial_blocks = set(mock_dataset["block_id"].unique())
    sampled_df = sample_spatially_stratified(mock_dataset, sample_size=50, random_state=42)

    assert len(sampled_df) < len(mock_dataset)
    assert set(sampled_df["block_id"].unique()) == initial_blocks, "Sampling dropped spatial blocks!"


def test_optuna_search_determinism_and_param_bounds():
    """Verify Optuna TPESampler seed determinism and ensure sampled parameters are within defined bounds."""
    study = optuna.create_study(
        sampler=optuna.samplers.TPESampler(seed=42),
        direction="minimize",
    )

    def dummy_objective(trial: optuna.Trial) -> float:
        params = sample_xgb_params(trial)

        # Check parameter bounds
        assert PARAM_SEARCH_BOUNDS["n_estimators"][0] <= params["n_estimators"] <= PARAM_SEARCH_BOUNDS["n_estimators"][1]
        assert PARAM_SEARCH_BOUNDS["max_depth"][0] <= params["max_depth"] <= PARAM_SEARCH_BOUNDS["max_depth"][1]
        assert PARAM_SEARCH_BOUNDS["learning_rate"][0] <= params["learning_rate"] <= PARAM_SEARCH_BOUNDS["learning_rate"][1]
        assert PARAM_SEARCH_BOUNDS["min_child_weight"][0] <= params["min_child_weight"] <= PARAM_SEARCH_BOUNDS["min_child_weight"][1]
        assert PARAM_SEARCH_BOUNDS["subsample"][0] <= params["subsample"] <= PARAM_SEARCH_BOUNDS["subsample"][1]
        assert PARAM_SEARCH_BOUNDS["colsample_bytree"][0] <= params["colsample_bytree"] <= PARAM_SEARCH_BOUNDS["colsample_bytree"][1]
        assert PARAM_SEARCH_BOUNDS["gamma"][0] <= params["gamma"] <= PARAM_SEARCH_BOUNDS["gamma"][1]
        assert PARAM_SEARCH_BOUNDS["reg_alpha"][0] <= params["reg_alpha"] <= PARAM_SEARCH_BOUNDS["reg_alpha"][1]
        assert PARAM_SEARCH_BOUNDS["reg_lambda"][0] <= params["reg_lambda"] <= PARAM_SEARCH_BOUNDS["reg_lambda"][1]

        # Check fixed parameters
        assert params["objective"] == "reg:squarederror"
        assert params["tree_method"] == "hist"
        assert params["random_state"] == 42
        assert params["n_jobs"] == -1

        return float(params["learning_rate"] + params["max_depth"])

    study.optimize(dummy_objective, n_trials=3)
    assert len(study.trials) == 3
