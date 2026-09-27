"""Development-Only Spatial Cross-Validation for HEATSENSE AI.

Ensures that spatial cross-validation is generated STRICTLY within the locked
development partition (132 blocks). Test blocks are structurally prohibited
from entering fold generation or CV evaluation.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def development_spatial_folds(
    df_dev: pd.DataFrame,
    development_blocks: list[str] | set[str],
    n_splits: int = 5,
    random_state: int = 42,
    block_col: str = "block_id",
    prohibited_test_blocks: list[str] | set[str] | None = None,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Generate deterministic spatial cross-validation folds strictly within development blocks.

    Parameters
    ----------
    df_dev : pd.DataFrame
        Development DataFrame containing `block_col`.
    development_blocks : list[str] | set[str]
        The authoritative locked list/set of development block IDs.
    n_splits : int
        Number of cross-validation folds (default: 5).
    random_state : int
        RNG seed for deterministic block fold assignment (default: 42).
    block_col : str
        Column name identifying the spatial block.
    prohibited_test_blocks : list[str] | set[str] | None
        Optional set of test blocks to explicitly assert complete absence.

    Returns
    -------
    list[tuple[np.ndarray, np.ndarray]]
        List of 5 (train_indices, validation_indices) index arrays relative to df_dev.
    """
    if block_col not in df_dev.columns:
        raise ValueError(f"Block column '{block_col}' missing from development DataFrame.")

    dev_block_set = set(str(b) for b in development_blocks)
    df_blocks = set(df_dev[block_col].astype(str).unique())

    # Strict isolation assertion: df_dev must only contain development blocks
    extra_blocks = df_blocks - dev_block_set
    if extra_blocks:
        raise ValueError(
            f"Leakage hazard: df_dev contains {len(extra_blocks)} blocks not in development_blocks: {extra_blocks}"
        )

    if prohibited_test_blocks is not None:
        prohibited_set = set(str(b) for b in prohibited_test_blocks)
        overlap = df_blocks.intersection(prohibited_set)
        if overlap:
            raise ValueError(
                f"FATAL LEAKAGE: df_dev contains {len(overlap)} prohibited test blocks: {overlap}"
            )

    unique_dev_blocks = np.sort(np.array(list(dev_block_set)))
    n_dev_blocks = len(unique_dev_blocks)
    if n_dev_blocks < n_splits:
        raise ValueError(
            f"Cannot create {n_splits} folds with only {n_dev_blocks} development blocks."
        )

    # Deterministic permutation of development blocks
    rng = np.random.RandomState(random_state)
    shuffled_dev_blocks = rng.permutation(unique_dev_blocks)

    # Partition blocks into n_splits roughly equal groups
    block_folds = np.array_split(shuffled_dev_blocks, n_splits)

    splits: list[tuple[np.ndarray, np.ndarray]] = []
    df_indices = np.arange(len(df_dev))

    seen_val_blocks: set[str] = set()

    for fold_idx in range(n_splits):
        val_blocks = set(block_folds[fold_idx])
        val_mask = df_dev[block_col].astype(str).isin(val_blocks).to_numpy()
        train_mask = ~val_mask

        train_idx = df_indices[train_mask]
        val_idx = df_indices[val_mask]

        # Verify disjointness
        train_block_set = set(df_dev.iloc[train_idx][block_col].astype(str))
        val_block_set = set(df_dev.iloc[val_idx][block_col].astype(str))

        assert train_block_set.isdisjoint(val_block_set), (
            f"Fold {fold_idx + 1} leakage: train and validation blocks overlap!"
        )

        if prohibited_test_blocks is not None:
            assert train_block_set.isdisjoint(prohibited_set), (
                f"Fold {fold_idx + 1} leakage: train contains test blocks!"
            )
            assert val_block_set.isdisjoint(prohibited_set), (
                f"Fold {fold_idx + 1} leakage: validation contains test blocks!"
            )

        seen_val_blocks.update(val_block_set)
        splits.append((train_idx, val_idx))

    # Verify that every development block appeared in exactly one validation fold
    assert seen_val_blocks == df_blocks, (
        "Not all development blocks were validated across the folds!"
    )

    return splits


def get_development_fold_metadata(
    df_dev: pd.DataFrame,
    folds: list[tuple[np.ndarray, np.ndarray]],
    block_col: str = "block_id",
) -> list[dict[str, Any]]:
    """Extract summary metrics and block counts for each development fold."""
    meta: list[dict[str, Any]] = []
    for fold_idx, (train_idx, val_idx) in enumerate(folds, 1):
        train_blocks = df_dev.iloc[train_idx][block_col].nunique()
        val_blocks = df_dev.iloc[val_idx][block_col].nunique()
        meta.append(
            {
                "fold": fold_idx,
                "train_samples": int(len(train_idx)),
                "val_samples": int(len(val_idx)),
                "train_blocks": int(train_blocks),
                "val_blocks": int(val_blocks),
            }
        )
    return meta
