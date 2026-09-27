"""Deterministic Spatial Holdout Splitting for HEATSENSE AI.

Strictly partitions spatial blocks (not individual rows/pixels) into disjoint
development blocks (80%) and untouched test blocks (20%).

Invariants:
1. development_blocks INTERSECT test_blocks == empty set.
2. len(development_blocks) + len(test_blocks) == len(total_blocks).
3. Test blocks are completely isolated from hyperparameter tuning,
   model selection, feature selection, and CV fold generation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd


def create_spatial_holdout_split(
    block_ids: list[str] | np.ndarray | pd.Series,
    test_ratio: float = 0.20,
    random_state: int = 42,
) -> tuple[list[str], list[str]]:
    """
    Deterministically split unique spatial block IDs into development and test partitions.

    Parameters
    ----------
    block_ids : list[str] | np.ndarray | pd.Series
        Collection of all unique or raw block identifiers.
    test_ratio : float
        Fraction of blocks reserved for test partition (default: 0.20).
    random_state : int
        RNG seed for deterministic permutation (default: 42).

    Returns
    -------
    tuple[list[str], list[str]]
        (development_blocks, test_blocks) sorted lexicographically.
    """
    if isinstance(block_ids, pd.Series):
        unique_blocks = np.sort(block_ids.dropna().unique().astype(str))
    elif isinstance(block_ids, np.ndarray):
        unique_blocks = np.sort(np.unique(block_ids).astype(str))
    else:
        unique_blocks = np.sort(np.array(list(set(str(b) for b in block_ids))))

    n_total = len(unique_blocks)
    if n_total == 0:
        raise ValueError("Cannot create holdout split from empty block collection.")

    n_test = int(np.round(n_total * test_ratio))
    if n_test < 1 or n_test >= n_total:
        raise ValueError(
            f"Invalid test block count {n_test} for total blocks {n_total} (test_ratio={test_ratio})."
        )

    # Deterministic permutation of sorted block list
    rng = np.random.RandomState(random_state)
    shuffled = rng.permutation(unique_blocks)

    test_blocks = sorted(list(shuffled[:n_test]))
    dev_blocks = sorted(list(shuffled[n_test:]))

    # Assert spatial disjointness
    dev_set = set(dev_blocks)
    test_set = set(test_blocks)
    assert dev_set.isdisjoint(test_set), "Spatial overlap detected between dev and test blocks!"
    assert len(dev_blocks) + len(test_blocks) == n_total, "Block conservation mismatch!"

    return dev_blocks, test_blocks


def save_holdout_split(
    dev_blocks: list[str],
    test_blocks: list[str],
    output_path: Path,
    random_state: int = 42,
    test_ratio: float = 0.20,
    metadata_extra: dict[str, Any] | None = None,
) -> Path:
    """Save the holdout split definition to JSON with schema validation."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dev_set = set(dev_blocks)
    test_set = set(test_blocks)
    assert dev_set.isdisjoint(test_set), "Cannot save split: dev and test blocks overlap!"

    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "random_state": random_state,
        "test_fraction": test_ratio,
        "total_blocks": len(dev_blocks) + len(test_blocks),
        "development_block_count": len(dev_blocks),
        "test_block_count": len(test_blocks),
        "development_blocks": sorted(dev_blocks),
        "test_blocks": sorted(test_blocks),
    }

    if metadata_extra:
        payload["metadata_extra"] = metadata_extra

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return output_path


def load_holdout_split(split_path: Path) -> dict[str, Any]:
    """Load and validate an existing holdout split JSON artifact."""
    split_path = Path(split_path)
    if not split_path.exists():
        raise FileNotFoundError(f"Holdout split file not found: {split_path}")

    with open(split_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate schema
    required_keys = [
        "random_state",
        "test_fraction",
        "total_blocks",
        "development_blocks",
        "test_blocks",
    ]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Holdout split artifact missing required key: '{key}'")

    dev_blocks = data["development_blocks"]
    test_blocks = data["test_blocks"]

    dev_set = set(dev_blocks)
    test_set = set(test_blocks)
    if not dev_set.isdisjoint(test_set):
        raise ValueError("Corrupt holdout split: development and test blocks overlap!")

    if len(dev_blocks) + len(test_blocks) != data["total_blocks"]:
        raise ValueError("Corrupt holdout split: total_blocks count mismatch!")

    return data


def partition_dataset_by_holdout(
    df: pd.DataFrame,
    dev_blocks: list[str],
    test_blocks: list[str],
    block_col: str = "block_id",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Partition DataFrame into development and test slices using locked block IDs.

    Guarantees that test_df contains only test_blocks and dev_df contains only dev_blocks.
    """
    if block_col not in df.columns:
        raise ValueError(f"Block column '{block_col}' missing from DataFrame.")

    dev_set = set(dev_blocks)
    test_set = set(test_blocks)
    assert dev_set.isdisjoint(test_set), "Dev and test block sets overlap!"

    df_block_str = df[block_col].astype(str)
    dev_mask = df_block_str.isin(dev_set).to_numpy()
    test_mask = df_block_str.isin(test_set).to_numpy()

    dev_df = df[dev_mask].copy()
    test_df = df[test_mask].copy()

    assert len(dev_df) + len(test_df) == len(df), (
        f"Row count mismatch: dev ({len(dev_df):,}) + test ({len(test_df):,}) "
        f"!= total ({len(df):,}). Some rows have unassigned block IDs!"
    )
    assert set(dev_df[block_col].astype(str)).isdisjoint(set(test_df[block_col].astype(str)))

    return dev_df, test_df
