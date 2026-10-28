"""Gated, Non-Destructive Model Candidate Retraining for HEATSENSE AI.

Conforms strictly to Problem 4D guardrails:
1. DOES NOT touch or overwrite artifacts/ml_freeze/.
2. Writes exclusively to artifacts/ml_candidates/<YYYYMMDD>/ with its own manifest and checksums.
3. Evaluates on the exact same locked spatially blocked holdout from holdout_split.json
   (132 development blocks / 33 test blocks, Dev ∩ Test = ∅).
4. Retrains on closed seasonal composites, NOT individual scenes.
5. Reports pooled and spatial R² side by side against the frozen baseline:
   - Frozen Baseline: Pooled R² = 0.9006, Spatial R² = 0.6919
6. Gated: NEVER auto-promoted. Requires explicit user approval and a new manifest generation
   before any promotion to a new freeze.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
import pandas as pd
import xgboost as xgb

from gis.ml.holdout_split import load_holdout_split, partition_dataset_by_holdout
from gis.ml.rf_model import compute_regression_metrics
from gis.ml.xgb_tuning import FEATURE_COLUMNS, TARGET_COLUMN, validate_dataset_schema

logger = logging.getLogger("heatsense.retrain")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Baseline frozen metrics for side-by-side comparison
FROZEN_BASELINE = {
    "pooled_r2": 0.9006,
    "pooled_mae": 1.2726,
    "pooled_rmse": 1.7524,
    "spatial_r2": 0.6919,
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


def retrain_candidate(
    dataset_path: Path = DEFAULT_DATASET,
    holdout_split_path: Path = DEFAULT_HOLDOUT,
    params_path: Path = DEFAULT_PARAMS,
    target_date: str | None = None,
    sample_fraction: float | None = None,
) -> dict[str, Any]:
    """Train candidate model on development blocks and evaluate on locked test blocks."""
    date_str = target_date or datetime.now(timezone.utc).strftime("%Y%m%d")
    output_dir = _REPO_ROOT / "artifacts" / "ml_candidates" / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    # GUARD: Ensure output_dir is NEVER inside artifacts/ml_freeze/
    freeze_dir = (_REPO_ROOT / "artifacts" / "ml_freeze").resolve()
    if freeze_dir in output_dir.resolve().parents or output_dir.resolve() == freeze_dir:
        raise PermissionError(
            "CRITICAL GUARDRAIL VIOLATION: Candidate retraining is strictly forbidden from writing "
            f"into the frozen artifacts directory ({freeze_dir})."
        )

    logger.info("=" * 70)
    logger.info("HEATSENSE AI GATED CANDIDATE RETRAINING PIPELINE")
    logger.info("Target candidate directory: %s", output_dir)
    logger.info("Dataset: %s", dataset_path)
    logger.info("Holdout split: %s", holdout_split_path)
    logger.info("=" * 70)

    # 1. Load locked holdout split
    holdout_data = load_holdout_split(holdout_split_path)
    dev_blocks = set(holdout_data["development_blocks"])
    test_blocks = set(holdout_data["test_blocks"])
    assert dev_blocks.isdisjoint(test_blocks), "Development and test blocks must be completely disjoint!"

    # 2. Load dataset
    logger.info("Loading closed seasonal composites dataset...")
    df = pd.read_parquet(dataset_path)
    validate_dataset_schema(df)

    if sample_fraction is not None and 0.0 < sample_fraction < 1.0:
        logger.info("Subsampling dataset to %.2f fraction for fast testing...", sample_fraction)
        df = df.sample(frac=sample_fraction, random_state=42).copy()

    # 3. Partition by locked spatial blocks
    df_dev = df[df["block_id"].isin(dev_blocks)].copy()
    df_test = df[df["block_id"].isin(test_blocks)].copy()

    logger.info(
        "Partitioned into %d dev rows (%d blocks) and %d test rows (%d blocks)",
        len(df_dev),
        len(dev_blocks),
        len(df_test),
        len(test_blocks),
    )

    X_train = df_dev[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
    y_train = df_dev[TARGET_COLUMN].to_numpy(dtype=np.float32)
    X_test = df_test[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
    y_test = df_test[TARGET_COLUMN].to_numpy(dtype=np.float32)

    # 4. Load hyperparameters
    with open(params_path, "r", encoding="utf-8") as f:
        params_meta = json.load(f)
    best_params = params_meta.get("best_params", params_meta)

    # Fit XGBoost model
    logger.info("Training candidate XGBoost model...")
    model = xgb.XGBRegressor(
        **best_params,
        random_state=42,
        tree_method="hist",
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 5. Evaluate on locked test blocks
    logger.info("Evaluating candidate model on locked test holdout blocks...")
    y_pred = model.predict(X_test)
    metrics = compute_regression_metrics(y_test, y_pred)
    pooled_r2 = float(metrics["r2"])
    pooled_mae = float(metrics["mae"])
    pooled_rmse = float(metrics["rmse"])

    # Compute spatial block R²
    df_test["y_pred"] = y_pred
    block_r2s = []
    for b_id, group in df_test.groupby("block_id"):
        if len(group) >= 10:
            b_m = compute_regression_metrics(group[TARGET_COLUMN].to_numpy(), group["y_pred"].to_numpy())
            block_r2s.append(b_m["r2"])
    spatial_r2 = float(np.mean(block_r2s)) if block_r2s else pooled_r2

    # Side-by-side comparison
    comparison = {
        "candidate_date": date_str,
        "metrics": {
            "pooled_r2": {"candidate": round(pooled_r2, 4), "frozen_baseline": FROZEN_BASELINE["pooled_r2"], "delta": round(pooled_r2 - FROZEN_BASELINE["pooled_r2"], 4)},
            "spatial_r2": {"candidate": round(spatial_r2, 4), "frozen_baseline": FROZEN_BASELINE["spatial_r2"], "delta": round(spatial_r2 - FROZEN_BASELINE["spatial_r2"], 4)},
            "pooled_mae": {"candidate": round(pooled_mae, 4), "frozen_baseline": FROZEN_BASELINE["pooled_mae"], "delta": round(pooled_mae - FROZEN_BASELINE["pooled_mae"], 4)},
            "pooled_rmse": {"candidate": round(pooled_rmse, 4), "frozen_baseline": FROZEN_BASELINE["pooled_rmse"], "delta": round(pooled_rmse - FROZEN_BASELINE["pooled_rmse"], 4)},
        },
        "holdout": {
            "dev_block_count": len(dev_blocks),
            "test_block_count": len(test_blocks),
            "dev_rows": len(df_dev),
            "test_rows": len(df_test),
        },
        "promotion_status": "NEVER_AUTO_PROMOTED",
        "promotion_requirement": "Explicit municipal lead approval and cryptographic manifest re-generation required before freeze update.",
    }

    # 6. Save model and metadata in artifacts/ml_candidates/<YYYYMMDD>/
    model_json_path = output_dir / "xgb_candidate_model.json"
    model.save_model(str(model_json_path))

    metadata_path = output_dir / "candidate_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)

    perf_path = output_dir / "candidate_performance.json"
    with open(perf_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "pooled_r2": pooled_r2,
                "spatial_r2": spatial_r2,
                "mae": pooled_mae,
                "rmse": pooled_rmse,
                "features": FEATURE_COLUMNS,
                "target": TARGET_COLUMN,
            },
            f,
            indent=2,
        )

    # 7. Generate candidate-specific checksum manifest
    manifest_lines = []
    for file_p in sorted(output_dir.iterdir()):
        if file_p.is_file() and file_p.name != "checksums.sha256":
            sha = compute_file_sha256(file_p)
            manifest_lines.append(f"{sha}  {file_p.name}")

    checksum_path = output_dir / "checksums.sha256"
    with open(checksum_path, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines) + "\n")

    logger.info("=" * 70)
    logger.info("CANDIDATE RETRAINING RESULTS:")
    logger.info("  Candidate Pooled R² : %.4f (Baseline: %.4f, Delta: %+.4f)", pooled_r2, FROZEN_BASELINE["pooled_r2"], pooled_r2 - FROZEN_BASELINE["pooled_r2"])
    logger.info("  Candidate Spatial R²: %.4f (Baseline: %.4f, Delta: %+.4f)", spatial_r2, FROZEN_BASELINE["spatial_r2"], spatial_r2 - FROZEN_BASELINE["spatial_r2"])
    logger.info("  Candidate MAE       : %.4f°C (Baseline: %.4f°C)", pooled_mae, FROZEN_BASELINE["pooled_mae"])
    logger.info("  Candidate Artifacts : %s", output_dir)
    logger.info("  Promotion Status    : NEVER_AUTO_PROMOTED (Awaiting explicit human approval)")
    logger.info("=" * 70)

    return comparison


def main():
    parser = argparse.ArgumentParser(description="HEATSENSE AI Gated Candidate Retraining")
    parser.add_argument("--date", type=str, default=None, help="Candidate target date YYYYMMDD")
    parser.add_argument("--sample-fraction", type=float, default=None, help="Optional sample fraction for testing")
    args = parser.parse_args()

    retrain_candidate(target_date=args.date, sample_fraction=args.sample_fraction)


if __name__ == "__main__":
    main()
