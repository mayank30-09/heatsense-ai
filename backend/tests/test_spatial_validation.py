"""Tests for Spatial Validation and Leakage Prevention."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gis.ml.dataset import DEFAULT_SENSITIVITY_ROOT
from gis.ml.spatial_validation import (
    spatial_block_folds,
    validate_fold_separation,
    get_fold_metadata,
)


def test_spatial_leakage_rejection():
    """Verify that validate_fold_separation detects and rejects spatial leakage."""
    df_test = pd.DataFrame({
        "block_id": ["B_01", "B_01", "B_02", "B_02", "B_03"],
        "val": [1, 2, 3, 4, 5],
    })

    # Legitimate disjoint folds
    valid_folds = [
        (np.array([0, 1]), np.array([2, 3, 4])),
    ]
    assert validate_fold_separation(df_test, valid_folds) is True

    # Leaking fold where B_01 appears in both train and val
    leaking_folds = [
        (np.array([0, 2]), np.array([1, 3, 4])),
    ]
    with pytest.raises(AssertionError, match="Spatial leakage detected"):
        validate_fold_separation(df_test, leaking_folds)


def test_5fold_spatial_separation_on_policy_datasets():
    """Verify zero spatial leakage across all 5 folds on actual generated dataset."""
    pq_path = DEFAULT_SENSITIVITY_ROOT / "policy_d" / "analysis.parquet"
    if not pq_path.exists():
        pytest.skip("policy_d analysis.parquet not yet generated.")

    df = pd.read_parquet(pq_path)
    folds = spatial_block_folds(df, n_splits=5, random_state=42)

    assert len(folds) == 5
    assert validate_fold_separation(df, folds) is True

    meta = get_fold_metadata(df, folds)
    assert len(meta) == 5
    for m in meta:
        assert m["val_samples"] > 0
        assert m["train_samples"] > 0
        assert m["val_blocks"] > 0
        assert m["train_blocks"] > 0
        assert m["val_blocks"] + m["train_blocks"] == 165


def test_policies_use_identical_spatial_folds():
    """Verify that Policies A, B, C, D share exact identical spatial block partitions per fold."""
    policies = ["policy_a", "policy_b", "policy_c", "policy_d"]
    existing = [p for p in policies if (DEFAULT_SENSITIVITY_ROOT / p / "analysis.parquet").exists()]
    if len(existing) < 2:
        pytest.skip("Need at least two policy datasets to verify equivalence.")

    fold_block_maps: dict[str, list[set[str]]] = {}
    for p in existing:
        df = pd.read_parquet(DEFAULT_SENSITIVITY_ROOT / p / "analysis.parquet")
        folds = spatial_block_folds(df, n_splits=5, random_state=42)
        fold_block_maps[p] = [
            set(df.iloc[val_idx]["block_id"].unique()) for _, val_idx in folds
        ]

    ref_policy = existing[0]
    for other_p in existing[1:]:
        for f_idx in range(5):
            assert (
                fold_block_maps[ref_policy][f_idx] == fold_block_maps[other_p][f_idx]
            ), f"Spatial block mismatch between {ref_policy} and {other_p} on fold {f_idx + 1}."
