"""Acceptance Tests for Stage A/B Scientific Freeze Immutability (T-19).

Requirements:
- T-19: SHA-256 Hash invariance across all protected Stage A/B scientific inputs:
  - XGBoost tuned model: e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9
  - Policy D analysis dataset: e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997
  - Holdout split JSON: 8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FROZEN_ARTIFACTS: dict[str, str] = {
    "artifacts/ml_freeze/xgb_tuned_policy_d.joblib": (
        "e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9"
    ),
    "data/processed/sensitivity/policy_d/analysis.parquet": (
        "e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997"
    ),
    "artifacts/ml_freeze/holdout_split.json": (
        "8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d"
    ),
}


def _compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def test_t19_scientific_freeze_hashes() -> None:
    """T-19: Verify that none of the Stage A/B frozen artifacts have been modified."""
    for rel_path, expected_hash in FROZEN_ARTIFACTS.items():
        full_path = PROJECT_ROOT / rel_path
        assert full_path.exists(), f"Protected scientific artifact missing: {rel_path}"

        actual_hash = _compute_sha256(full_path)
        assert actual_hash == expected_hash, (
            f"CRITICAL: Protected artifact {rel_path} hash mutated!\n"
            f"Expected: {expected_hash}\n"
            f"Actual:   {actual_hash}"
        )
