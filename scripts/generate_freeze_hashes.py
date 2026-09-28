"""Cryptographic Hash Generation for HEATSENSE AI Scientific Freeze.

Calculates SHA-256 hashes of all authoritative freeze artifacts, configurations,
models, and datasets to guarantee tamper-proof scientific reproducibility.

Output:
    artifacts/ml_freeze/checksums.sha256
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CRITICAL_FREEZE_TARGETS = [
    # 1. Audit and Validation Records
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "pre_implementation_audit.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "dataset_validation.json",
    # 2. Configuration & Policy Spec
    PROJECT_ROOT / "config" / "quality_policy_d.yaml",
    # 3. Frozen Analysis Dataset
    PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet",
    # 4. Spatial Holdout Split Partition
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json",
    # 5. Spatial Fold Definition & Tuning
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "spatial_fold_definition.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "best_params.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "xgb_best_params.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "study_summary.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "trial_results.csv",
    # 6. Locked Feature Schema & Model Metadata
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "feature_schema.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "model_metadata.json",
    # 7. Final Trained Candidate Model
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "xgb_tuned_policy_d.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "xgb_tuned_policy_d.joblib",
    # 8. Final One-Time Holdout Evaluation
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_performance.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_season_performance.csv",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_hotspot_performance.csv",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_spatial_residuals.geojson",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "evaluation_manifest.json",
    # 9. QC and Test Suite Summaries
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "qc_summary.json",
    PROJECT_ROOT / "artifacts" / "ml_freeze" / "test_results.json",
]


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file in 64KB blocks."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SHA-256 checksums for HEATSENSE AI freeze artifacts.")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "ml_freeze" / "checksums.sha256",
        help="Path to output checksums.sha256 file.",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("HEATSENSE AI: CRYPTOGRAPHIC FREEZE CHECKSUM GENERATION (SHA-256)")
    print("=" * 80)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    records = []

    for target in CRITICAL_FREEZE_TARGETS:
        if not target.exists():
            print(f"  [MISSING/PENDING]: {target.relative_to(PROJECT_ROOT)}")
            continue

        digest = compute_sha256(target)
        rel_path = target.relative_to(PROJECT_ROOT).as_posix()
        records.append(f"{digest}  {rel_path}")
        print(f"  {digest[:12]}...  {rel_path}")

    # Check for analytical COGs if they exist
    analytical_dir = PROJECT_ROOT / "data" / "processed" / "analytical"
    if analytical_dir.exists():
        for cog_file in sorted(analytical_dir.glob("*.tif")):
            digest = compute_sha256(cog_file)
            rel_path = cog_file.relative_to(PROJECT_ROOT).as_posix()
            records.append(f"{digest}  {rel_path}")
            print(f"  {digest[:12]}...  {rel_path}")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(records) + "\n")

    print(f"\nSaved {len(records)} SHA-256 digests to: {args.output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
