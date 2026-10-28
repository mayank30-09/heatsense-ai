"""EXPERIMENTAL - does not modify frozen artifacts.

Gated, Non-Destructive Model Candidate Retraining for HEATSENSE AI.

Strictly isolated from frozen models and locked holdout partitions:
1. DOES NOT touch or overwrite artifacts/ml_freeze/ or data/.
2. Refuses to run without an explicit --output-dir outside artifacts/ml_freeze and data/.
3. Strictly asserts that the 33 locked test blocks are NEVER loaded into training data.
4. Gated: Never auto-promoted to production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any

EXPERIMENTAL_NOTICE = "EXPERIMENTAL - does not modify frozen artifacts"
print(EXPERIMENTAL_NOTICE)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
import pandas as pd
import xgboost as xgb

from gis.ml.holdout_split import load_holdout_split
from gis.ml.rf_model import compute_regression_metrics
from gis.ml.xgb_tuning import FEATURE_COLUMNS, TARGET_COLUMN, validate_dataset_schema

logger = logging.getLogger("heatsense.retrain")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Baseline frozen metrics for reference
FROZEN_BASELINE = {
    "pooled_r2": 0.9006,
    "pooled_mae": 1.2726,
    "pooled_rmse": 1.7524,
    "summer_r2": 0.7119,
    "dev_blocks": 132,
    "test_blocks": 33,
}

DEFAULT_DATASET = _REPO_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
DEFAULT_HOLDOUT = _REPO_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"
DEFAULT_PARAMS = _REPO_ROOT / "artifacts" / "ml_freeze" / "tuning" / "xgb_best_params.json"


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hexadecimal digest."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def validate_output_directory(output_dir: Path | str | None, repo_root: Path) -> Path:
    """Validate that output_dir is explicitly specified and strictly outside protected directories.
    
    Raises:
        ValueError: If output_dir is None or empty.
        PermissionError: If output_dir is within artifacts/ml_freeze or data/.
    """
    if output_dir is None:
        raise ValueError(
            "CRITICAL GUARDRAIL VIOLATION: Experimental candidate retraining refuses to run "
            "without an explicit --output-dir."
        )

    out_p = Path(output_dir).resolve()
    freeze_dir = (repo_root / "artifacts" / "ml_freeze").resolve()
    data_dir = (repo_root / "data").resolve()

    if out_p == freeze_dir or freeze_dir in out_p.parents:
        raise PermissionError(
            f"CRITICAL GUARDRAIL VIOLATION: Output directory ({out_p}) cannot be inside "
            f"artifacts/ml_freeze ({freeze_dir})."
        )

    if out_p == data_dir or data_dir in out_p.parents:
        raise PermissionError(
            f"CRITICAL GUARDRAIL VIOLATION: Output directory ({out_p}) cannot be inside "
            f"data/ ({data_dir})."
        )

    out_p.mkdir(parents=True, exist_ok=True)
    return out_p


def assert_test_blocks_never_loaded(df: pd.DataFrame, test_blocks: set[str]) -> None:
    """Assert that none of the 33 locked test blocks are present in the dataset."""
    assert len(test_blocks) == 33, f"Expected exactly 33 test blocks, got {len(test_blocks)}"
    leaked = set(df["block_id"].unique()).intersection(test_blocks)
    assert len(leaked) == 0, (
        f"CRITICAL GUARDRAIL VIOLATION: {len(leaked)} locked test blocks detected in loaded data! "
        "The 33 locked test blocks must NEVER be loaded in candidate retraining."
    )


def filter_development_data_only(df: pd.DataFrame, holdout_split_path: Path) -> tuple[pd.DataFrame, set[str]]:
    """Filter dataset to strictly exclude the 33 locked test blocks and assert separation."""
    holdout_data = load_holdout_split(holdout_split_path)
    test_blocks = set(holdout_data.get("test_blocks", []))
    dev_blocks = set(holdout_data.get("development_blocks", []))

    assert len(test_blocks) == 33, f"Expected 33 test blocks, found {len(test_blocks)}"
    assert dev_blocks.isdisjoint(test_blocks), "Development and test blocks must be disjoint!"

    # Strictly filter out any test blocks
    df_dev = df[df["block_id"].isin(dev_blocks)].copy()

    # Enforce guardrail assertion: 33 test blocks are NEVER loaded
    assert_test_blocks_never_loaded(df_dev, test_blocks)
    assert len(df_dev) > 0, "No development rows remaining after excluding test blocks!"

    return df_dev, dev_blocks


def retrain_candidate(
    output_dir: Path | str | None = None,
    dataset_path: Path = DEFAULT_DATASET,
    holdout_split_path: Path = DEFAULT_HOLDOUT,
    params_path: Path = DEFAULT_PARAMS,
    sample_fraction: float | None = None,
) -> dict[str, Any]:
    """Train experimental candidate model strictly on development blocks.
    
    Refuses to run without an explicit output_dir outside artifacts/ml_freeze and data/.
    Asserts that the 33 locked test blocks are never loaded.
    """
    out_dir = validate_output_directory(output_dir, _REPO_ROOT)

    logger.info("=" * 70)
    logger.info(EXPERIMENTAL_NOTICE)
    logger.info("HEATSENSE AI EXPERIMENTAL CANDIDATE RETRAINING")
    logger.info("Target candidate directory: %s", out_dir)
    logger.info("=" * 70)

    # 1. Load dataset and assert 33 test blocks are never loaded
    df = pd.read_parquet(dataset_path)
    validate_dataset_schema(df)

    df_dev, dev_blocks = filter_development_data_only(df, holdout_split_path)

    # Double guardrail check
    test_blocks = set(load_holdout_split(holdout_split_path).get("test_blocks", []))
    assert_test_blocks_never_loaded(df_dev, test_blocks)

    if sample_fraction is not None and 0.0 < sample_fraction < 1.0:
        logger.info("Subsampling dev dataset to %.2f fraction for fast testing...", sample_fraction)
        df_dev = df_dev.sample(frac=sample_fraction, random_state=42).copy()
        assert_test_blocks_never_loaded(df_dev, test_blocks)

    X_train = df_dev[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
    y_train = df_dev[TARGET_COLUMN].to_numpy(dtype=np.float32)

    # 2. Load hyperparameters
    with open(params_path, "r", encoding="utf-8") as f:
        params_meta = json.load(f)
    best_params = params_meta.get("best_params", params_meta)

    # 3. Fit XGBoost model on dev data only
    logger.info("Training candidate XGBoost model on %d development rows...", len(df_dev))
    model = xgb.XGBRegressor(
        **best_params,
        random_state=42,
        tree_method="hist",
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_dev_pred = model.predict(X_train)
    dev_metrics = compute_regression_metrics(y_train, y_dev_pred)

    candidate_metadata = {
        "status": "EXPERIMENTAL",
        "notice": EXPERIMENTAL_NOTICE,
        "output_dir": str(out_dir),
        "dev_blocks_used": len(dev_blocks),
        "test_blocks_loaded": 0,
        "dev_rows": len(df_dev),
        "dev_metrics": {
            "r2": float(dev_metrics["r2"]),
            "mae": float(dev_metrics["mae"]),
            "rmse": float(dev_metrics["rmse"]),
        },
        "promotion_status": "NEVER_AUTO_PROMOTED",
        "guardrails_enforced": [
            "explicit_output_dir_verified",
            "outside_artifacts_ml_freeze_verified",
            "outside_data_verified",
            "33_test_blocks_never_loaded_verified",
        ],
    }

    # 4. Save model and metadata in user-specified output_dir
    model_json_path = out_dir / "xgb_candidate_model.json"
    model.save_model(str(model_json_path))

    metadata_path = out_dir / "candidate_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(candidate_metadata, f, indent=2)

    # 5. Generate candidate-specific checksum manifest
    manifest_lines = []
    for file_p in sorted(out_dir.iterdir()):
        if file_p.is_file() and file_p.name != "checksums.sha256":
            sha = compute_file_sha256(file_p)
            manifest_lines.append(f"{sha}  {file_p.name}")

    checksum_path = out_dir / "checksums.sha256"
    with open(checksum_path, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines) + "\n")

    logger.info("Candidate retraining finished successfully in %s", out_dir)
    return candidate_metadata


def main():
    parser = argparse.ArgumentParser(description="HEATSENSE AI Experimental Candidate Retraining")
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Explicit output directory (MUST be outside artifacts/ml_freeze and data/)",
    )
    parser.add_argument("--dataset", type=str, default=str(DEFAULT_DATASET), help="Path to analysis dataset")
    parser.add_argument("--sample-fraction", type=float, default=None, help="Optional sample fraction for testing")
    args = parser.parse_args()

    retrain_candidate(
        output_dir=args.output_dir,
        dataset_path=Path(args.dataset),
        sample_fraction=args.sample_fraction,
    )


if __name__ == "__main__":
    main()
