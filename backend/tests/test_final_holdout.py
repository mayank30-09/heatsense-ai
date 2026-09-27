"""Unit tests for independent spatial holdout module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gis.ml.final_holdout import create_spatial_holdout_split


def test_spatial_holdout_split_disjointness_and_coverage():
    # Synthetic dataframe with 20 blocks
    blocks = [f"B_{i:02d}" for i in range(20)]
    rows = []
    for b in blocks:
        for _ in range(50):
            rows.append({"block_id": b, "val": np.random.randn()})
    df = pd.DataFrame(rows)

    dev_idx, test_idx, dev_blocks, test_blocks = create_spatial_holdout_split(
        df, test_ratio=0.20, random_state=42, block_col="block_id"
    )

    # 1. Total block counts: 20 blocks -> 4 test blocks (20%), 16 dev blocks (80%)
    assert len(test_blocks) == 4
    assert len(dev_blocks) == 16
    assert set(test_blocks).isdisjoint(set(dev_blocks))

    # 2. Total row counts
    assert len(dev_idx) + len(test_idx) == len(df)
    assert set(dev_idx).isdisjoint(set(test_idx))

    # 3. Spatial integrity: all test rows belong to test_blocks
    test_block_set = set(test_blocks)
    assert df.iloc[test_idx]["block_id"].isin(test_block_set).all()

    dev_block_set = set(dev_blocks)
    assert df.iloc[dev_idx]["block_id"].isin(dev_block_set).all()


def test_spatial_holdout_reproducibility():
    blocks = [f"B_{i:02d}" for i in range(15)]
    df = pd.DataFrame([{"block_id": b} for b in blocks for _ in range(10)])

    d1, t1, db1, tb1 = create_spatial_holdout_split(df, test_ratio=0.20, random_state=42)
    d2, t2, db2, tb2 = create_spatial_holdout_split(df, test_ratio=0.20, random_state=42)

    assert tb1 == tb2
    assert db1 == db2
    np.testing.assert_array_equal(d1, d2)
    np.testing.assert_array_equal(t1, t2)


def test_spatial_holdout_missing_column_raises():
    df = pd.DataFrame({"colA": [1, 2, 3]})
    with pytest.raises(ValueError, match="Block column 'block_id' missing"):
        create_spatial_holdout_split(df, block_col="block_id")
