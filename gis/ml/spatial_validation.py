"""Deterministic Spatial Block Cross-Validation for HEATSENSE AI.

Ensures zero spatial leakage by partitioning spatial blocks (not individual pixels)
into disjoint cross-validation folds. Guarantees identical spatial fold assignments
across different policy datasets.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def spatial_block_folds(
    df: pd.DataFrame,
    n_splits: int = 5,
    random_state: int = 42,
    block_col: str = "block_id",
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Generate deterministic spatial block cross-validation splits.

    Blocks, not individual pixels, are partitioned into folds to prevent
    spatial autocorrelation leakage between training and validation sets.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the spatial block column (e.g. 'block_id').
    n_splits : int
        Number of spatial folds (default: 5).
    random_state : int
        Seed for deterministic block shuffling (default: 42).
    block_col : str
        Name of the block identifier column (default: 'block_id').

    Returns
    -------
    list[tuple[np.ndarray, np.ndarray]]
        List of (train_indices, validation_indices) index arrays.
    """
    if block_col not in df.columns:
        raise ValueError(f"Block column '{block_col}' not found in DataFrame.")

    unique_blocks = np.sort(df[block_col].unique())
    n_blocks = len(unique_blocks)
    if n_blocks < n_splits:
        raise ValueError(f"Number of unique blocks ({n_blocks}) is less than n_splits ({n_splits}).")

    # Deterministic permutation of unique blocks
    rng = np.random.RandomState(random_state)
    shuffled_blocks = rng.permutation(unique_blocks)

    # Assign blocks to folds
    block_folds = np.array_split(shuffled_blocks, n_splits)

    splits: list[tuple[np.ndarray, np.ndarray]] = []
    df_indices = np.arange(len(df))

    for fold_idx in range(n_splits):
        val_blocks = set(block_folds[fold_idx])
        val_mask = df[block_col].isin(val_blocks).to_numpy()
        train_mask = ~val_mask

        train_idx = df_indices[train_mask]
        val_idx = df_indices[val_mask]

        splits.append((train_idx, val_idx))

    return splits


def validate_fold_separation(
    df: pd.DataFrame,
    folds: list[tuple[np.ndarray, np.ndarray]],
    block_col: str = "block_id",
) -> bool:
    """
    Verify that training blocks and validation blocks are strictly disjoint
    in every fold (zero spatial leakage).

    Raises AssertionError if any spatial overlap is detected.
    """
    for fold_idx, (train_idx, val_idx) in enumerate(folds):
        train_blocks = set(df.iloc[train_idx][block_col].unique())
        val_blocks = set(df.iloc[val_idx][block_col].unique())

        intersection = train_blocks.intersection(val_blocks)
        if len(intersection) > 0:
            raise AssertionError(
                f"Spatial leakage detected in Fold {fold_idx + 1}! "
                f"Overlapping blocks: {intersection}"
            )

    return True


def get_fold_metadata(
    df: pd.DataFrame,
    folds: list[tuple[np.ndarray, np.ndarray]],
    block_col: str = "block_id",
) -> list[dict[str, Any]]:
    """Return summary metadata for each spatial fold."""
    meta = []
    for fold_idx, (train_idx, val_idx) in enumerate(folds):
        n_train = len(train_idx)
        n_val = len(val_idx)
        n_val_blocks = df.iloc[val_idx][block_col].nunique()
        n_train_blocks = df.iloc[train_idx][block_col].nunique()

        meta.append({
            "fold": fold_idx + 1,
            "train_samples": n_train,
            "val_samples": n_val,
            "train_blocks": n_train_blocks,
            "val_blocks": n_val_blocks,
        })
    return meta
