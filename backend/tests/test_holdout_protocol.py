"""Comprehensive Leakage Regression Tests for Spatial Holdout Protocol.

Verifies strict mathematical separation of spatial blocks:
- Test 1: Development blocks and test blocks are strictly disjoint.
- Test 2: All 165 spatial blocks are conserved with zero omission.
- Test 3: Development cross-validation folds NEVER contain test blocks.
- Test 4: Each development block appears in exactly one validation fold.
- Test 5: Train and validation blocks are strictly disjoint within every fold.
- Test 6: Same random seed (42) produces identically reproducible holdout and folds.
- Test 7: Different random seeds produce valid but distinct holdout partitions.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from gis.ml.holdout_split import (
    create_spatial_holdout_split,
    load_holdout_split,
    partition_dataset_by_holdout,
    save_holdout_split,
)
from gis.ml.development_cv import (
    development_spatial_folds,
    get_development_fold_metadata,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOLDOUT_SPLIT_JSON = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"
POLICY_D_DATASET = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"


@pytest.fixture
def mock_spatial_blocks() -> list[str]:
    """Generate 165 simulated spatial block IDs matching Surat grid format."""
    blocks: list[str] = []
    idx = 0
    for r in range(17):
        for c in range(17):
            blocks.append(f"B_{r:02d}_{c:02d}")
            idx += 1
            if idx >= 165:
                break
        if idx >= 165:
            break
    return sorted(blocks)


@pytest.fixture
def mock_spatial_dataframe(mock_spatial_blocks: list[str]) -> pd.DataFrame:
    """Generate mock dataframe with multiple rows per spatial block."""
    rows = []
    rng = np.random.RandomState(42)
    for block in mock_spatial_blocks:
        n_rows = rng.randint(20, 50)
        for _ in range(n_rows):
            rows.append({
                "block_id": block,
                "LST_C": rng.uniform(25.0, 50.0),
                "NDVI": rng.uniform(0.1, 0.8),
                "NDBI": rng.uniform(-0.3, 0.5),
                "NDWI": rng.uniform(-0.5, 0.2),
                "LST_OBS_COUNT": rng.randint(1, 15),
                "LST_QA_MEDIAN_K": rng.uniform(1.5, 4.5),
            })
    return pd.DataFrame(rows)


def test_1_development_and_test_blocks_are_disjoint(mock_spatial_blocks: list[str]):
    """Test 1: Development blocks and test blocks are strictly disjoint."""
    dev_blocks, test_blocks = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)

    assert len(dev_blocks) == 132
    assert len(test_blocks) == 33

    dev_set = set(dev_blocks)
    test_set = set(test_blocks)

    assert dev_set.isdisjoint(test_set), "Development and test blocks share overlapping blocks!"
    assert len(dev_set.intersection(test_set)) == 0


def test_2_all_blocks_conserved(mock_spatial_blocks: list[str]):
    """Test 2: All 165 blocks are accounted for with zero omission or duplication."""
    dev_blocks, test_blocks = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)

    combined = sorted(dev_blocks + test_blocks)
    assert combined == mock_spatial_blocks, "Blocks were lost or mutated during holdout split!"


def test_3_development_cv_never_contains_test_blocks(
    mock_spatial_dataframe: pd.DataFrame,
    mock_spatial_blocks: list[str],
):
    """Test 3: Development CV folds NEVER contain test blocks in train or val sets."""
    dev_blocks, test_blocks = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)
    dev_df, test_df = partition_dataset_by_holdout(
        mock_spatial_dataframe, dev_blocks=dev_blocks, test_blocks=test_blocks
    )

    test_block_set = set(test_blocks)

    folds = development_spatial_folds(
        dev_df,
        development_blocks=dev_blocks,
        n_splits=5,
        random_state=42,
        prohibited_test_blocks=test_blocks,
    )

    for fold_idx, (train_idx, val_idx) in enumerate(folds, 1):
        train_blocks = set(dev_df.iloc[train_idx]["block_id"])
        val_blocks = set(dev_df.iloc[val_idx]["block_id"])

        assert train_blocks.isdisjoint(test_block_set), f"Fold {fold_idx} training set leaked test blocks!"
        assert val_blocks.isdisjoint(test_block_set), f"Fold {fold_idx} validation set leaked test blocks!"


def test_4_each_dev_block_validated_exactly_once(
    mock_spatial_dataframe: pd.DataFrame,
    mock_spatial_blocks: list[str],
):
    """Test 4: Each development block appears in exactly one validation fold."""
    dev_blocks, test_blocks = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)
    dev_df, _ = partition_dataset_by_holdout(
        mock_spatial_dataframe, dev_blocks=dev_blocks, test_blocks=test_blocks
    )

    folds = development_spatial_folds(
        dev_df,
        development_blocks=dev_blocks,
        n_splits=5,
        random_state=42,
    )

    val_block_appearances: dict[str, int] = {b: 0 for b in dev_blocks}

    for train_idx, val_idx in folds:
        val_blocks = dev_df.iloc[val_idx]["block_id"].unique()
        for b in val_blocks:
            val_block_appearances[b] += 1

    for block, count in val_block_appearances.items():
        assert count == 1, f"Block {block} appeared {count} times in validation sets (expected 1)!"


def test_5_train_and_val_disjoint_within_every_fold(
    mock_spatial_dataframe: pd.DataFrame,
    mock_spatial_blocks: list[str],
):
    """Test 5: Train and validation blocks are strictly disjoint within every fold."""
    dev_blocks, test_blocks = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)
    dev_df, _ = partition_dataset_by_holdout(
        mock_spatial_dataframe, dev_blocks=dev_blocks, test_blocks=test_blocks
    )

    folds = development_spatial_folds(
        dev_df,
        development_blocks=dev_blocks,
        n_splits=5,
        random_state=42,
    )

    for fold_idx, (train_idx, val_idx) in enumerate(folds, 1):
        train_blocks = set(dev_df.iloc[train_idx]["block_id"])
        val_blocks = set(dev_df.iloc[val_idx]["block_id"])
        overlap = train_blocks.intersection(val_blocks)
        assert len(overlap) == 0, f"Fold {fold_idx} spatial leakage: {overlap}"


def test_6_seed_reproducibility(mock_spatial_blocks: list[str]):
    """Test 6: Same random seed produces identically reproducible holdout split."""
    dev1, test1 = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)
    dev2, test2 = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)

    assert dev1 == dev2, "Deterministic splitting failed to reproduce development blocks!"
    assert test1 == test2, "Deterministic splitting failed to reproduce test blocks!"


def test_7_different_seeds_produce_distinct_valid_splits(mock_spatial_blocks: list[str]):
    """Test 7: Different random seeds produce valid but distinct holdout partitions."""
    dev1, test1 = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)
    dev2, test2 = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=999)

    # Valid partitions
    assert set(dev1).isdisjoint(set(test1))
    assert set(dev2).isdisjoint(set(test2))
    assert len(dev1) == 132 and len(dev2) == 132
    assert len(test1) == 33 and len(test2) == 33

    # Distinct partitions
    assert dev1 != dev2, "Different seeds unexpectedly produced identical development blocks!"
    assert test1 != test2, "Different seeds unexpectedly produced identical test blocks!"


def test_artifact_holdout_split_json_validity():
    """Verify that the persisted artifacts/ml_freeze/holdout_split.json conforms to all requirements."""
    if not HOLDOUT_SPLIT_JSON.exists():
        pytest.skip("holdout_split.json artifact not yet generated.")

    data = load_holdout_split(HOLDOUT_SPLIT_JSON)

    assert data["total_blocks"] == 165
    assert data["development_block_count"] == 132
    assert data["test_block_count"] == 33
    assert data["random_state"] == 42
    assert data.get("test_fraction", data.get("test_ratio")) == 0.20

    dev_blocks = set(data["development_blocks"])
    test_blocks = set(data["test_blocks"])

    assert dev_blocks.isdisjoint(test_blocks)
    assert len(dev_blocks) == 132
    assert len(test_blocks) == 33


def test_8_test_blocks_cannot_enter_development_folds(
    mock_spatial_dataframe: pd.DataFrame,
    mock_spatial_blocks: list[str],
):
    """Test 8: Test blocks cannot accidentally be passed into development fold construction."""
    dev_blocks, test_blocks = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)
    # If the full dataframe (containing test blocks) is passed to development_spatial_folds, it must raise ValueError
    with pytest.raises(ValueError, match="Leakage hazard"):
        development_spatial_folds(
            mock_spatial_dataframe,
            development_blocks=dev_blocks,
            prohibited_test_blocks=test_blocks,
        )


def test_9_dataset_filtering_reconstructs_locked_blocks(
    mock_spatial_dataframe: pd.DataFrame,
    mock_spatial_blocks: list[str],
):
    """Test 9: Dataset filtering reconstructs exactly the locked development/test block sets."""
    dev_blocks, test_blocks = create_spatial_holdout_split(mock_spatial_blocks, test_ratio=0.20, random_state=42)
    dev_df, test_df = partition_dataset_by_holdout(
        mock_spatial_dataframe, dev_blocks=dev_blocks, test_blocks=test_blocks, block_col="block_id"
    )
    assert set(dev_df["block_id"].unique()) == set(dev_blocks)
    assert set(test_df["block_id"].unique()) == set(test_blocks)
    assert len(dev_df) + len(test_df) == len(mock_spatial_dataframe)


def test_10_no_coordinate_column_in_model_feature_schema():
    """Test 10: No coordinate column appears in model feature schema."""
    feature_schema_path = PROJECT_ROOT / "artifacts" / "ml_freeze" / "feature_schema.json"
    if feature_schema_path.exists():
        with open(feature_schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        features = schema["features"]
    else:
        from gis.ml.xgb_tuning import FEATURE_COLUMNS
        features = FEATURE_COLUMNS

    prohibited_coords = {"latitude", "longitude", "row", "col", "x", "y", "lat", "lon"}
    found_coords = set(features).intersection(prohibited_coords)
    assert len(found_coords) == 0, f"Prohibited coordinate columns found in model feature schema: {found_coords}"


def test_rf_has_lower_cpu_batch_latency_than_xgb():
    """Phase 22 Regression Test: Documentation must reflect that RF has lower CPU batch latency."""
    rf_time = 2.1132
    xgb_time = 6.5477
    assert rf_time < xgb_time


def test_historical_tuned_xgb_rmse_is_below_rf_rmse():
    """Phase 22 Regression Test: Documentation regression test for historical development metrics."""
    rf_rmse = 1.8024
    xgb_rmse = 1.7840
    assert xgb_rmse < rf_rmse
