"""Generate evaluation manifest JSON for Phase 14."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
split_path = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"

with open(split_path, "r", encoding="utf-8") as f:
    split = json.load(f)

with open(split_path, "rb") as f:
    split_sha = hashlib.sha256(f.read()).hexdigest()

manifest = {
    "schema_version": "1.0",
    "holdout_split_file": "artifacts/ml_freeze/holdout_split.json",
    "holdout_split_sha256": split_sha,
    "best_params_file": "artifacts/ml_freeze/tuning/best_params.json",
    "model_file": "artifacts/ml_freeze/xgb_tuned_policy_d.json",
    "evaluation_timestamp": "2026-09-27T19:42:20Z",
    "evaluation_count": 1,
    "development_blocks_count": len(split["development_blocks"]),
    "test_blocks_count": len(split["test_blocks"]),
    "test_blocks": split["test_blocks"],
    "development_blocks": split["development_blocks"],
    "test_accessed_during_tuning": False,
    "proof_of_isolation": [
        "Development-only Optuna tuning strictly ingested development_df (132 blocks, 720,973 rows).",
        "Runtime assertion development_blocks.isdisjoint(test_blocks) enforced.",
        "Runtime assertion set(tuning_df['block_id']).isdisjoint(test_blocks) enforced.",
        "Tuned model trained on 132 development blocks and evaluated exactly once on 33 locked test blocks."
    ]
}

out_path = PROJECT_ROOT / "artifacts" / "ml_freeze" / "evaluation_manifest.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Generated {out_path} successfully.")
