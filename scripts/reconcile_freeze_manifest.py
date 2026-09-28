"""Reconcile Freeze Manifest, Hashes, and Documentation.

Creates the single authoritative artifact manifest (artifacts/ml_freeze/artifact_manifest.json),
updates checksums.sha256, synchronizes internal hash cross-references, and ensures all reports
reference the exact SHA-256 digests.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GIT_COMMIT = "c91bc69038d1796c568772a5bce9fba900be7e96"
GIT_BRANCH = "feature/scientific-freeze-correction"

def compute_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def get_file_mtime_iso(path: Path) -> str:
    mtime = os.path.getmtime(path)
    return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main() -> None:
    ml_freeze_dir = PROJECT_ROOT / "artifacts" / "ml_freeze"

    # Step 1: Ensure holdout_split hash in evaluation_manifest.json and holdout_performance.json
    holdout_split_path = ml_freeze_dir / "holdout_split.json"
    holdout_split_sha = compute_sha256(holdout_split_path)

    feature_schema_path = ml_freeze_dir / "feature_schema.json"
    feature_schema_sha = compute_sha256(feature_schema_path)

    # Update holdout_performance.json
    perf_path = ml_freeze_dir / "holdout_performance.json"
    if perf_path.exists():
        with open(perf_path, "r", encoding="utf-8") as f:
            perf_data = json.load(f)
        perf_data["feature_schema_hash"] = feature_schema_sha
        perf_data["holdout_split_hash"] = holdout_split_sha
        with open(perf_path, "w", encoding="utf-8") as f:
            json.dump(perf_data, f, indent=2)

    # Update evaluation_manifest.json
    eval_manifest_path = ml_freeze_dir / "evaluation_manifest.json"
    if eval_manifest_path.exists():
        with open(eval_manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest_data["holdout_split_sha256"] = holdout_split_sha
        with open(eval_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

    # Step 2: List all authoritative freeze artifacts
    authoritative_files = [
        # Audits & Specs
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "pre_implementation_audit.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "dataset_validation.json",
        PROJECT_ROOT / "config" / "quality_policy_d.yaml",
        PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet",
        # Split & Tuning
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "spatial_fold_definition.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "best_params.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "xgb_best_params.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "study_summary.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "trial_results.csv",
        # Schema & Models
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "feature_schema.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "model_metadata.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "xgb_tuned_policy_d.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "xgb_tuned_policy_d.joblib",
        # Evaluation & Performance
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_performance.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_season_performance.csv",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_hotspot_performance.csv",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_spatial_residuals.geojson",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "evaluation_manifest.json",
        # QC & Test Summaries
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "qc_summary.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "test_results.json",
        PROJECT_ROOT / "artifacts" / "ml_freeze" / "production_cog_validation.json",
    ]

    # Add all 19 production analytical COGs
    cog_dir = PROJECT_ROOT / "data" / "processed" / "analytical"
    if cog_dir.exists():
        for cog_file in sorted(cog_dir.glob("*.tif")):
            authoritative_files.append(cog_file)

    manifest_records = []
    checksum_lines = []

    for fpath in authoritative_files:
        if not fpath.exists():
            print(f"ERROR: missing required freeze file {fpath}")
            sys.exit(1)

        digest = compute_sha256(fpath)
        size_bytes = os.path.getsize(fpath)
        rel_posix = fpath.relative_to(PROJECT_ROOT).as_posix()
        mtime_iso = get_file_mtime_iso(fpath)

        manifest_records.append({
            "artifact": rel_posix,
            "sha256": digest,
            "size_bytes": size_bytes,
            "generated_at": mtime_iso,
            "git_commit": GIT_COMMIT,
            "freeze_git_commit": GIT_COMMIT,
        })
        checksum_lines.append(f"{digest}  {rel_posix}")

    # Write artifact_manifest.json
    manifest_payload = {
        "schema_version": "1.0",
        "git_commit": GIT_COMMIT,
        "freeze_git_commit": GIT_COMMIT,
        "experiment_git_commit": GIT_COMMIT,
        "branch": GIT_BRANCH,
        "reconciled_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_artifacts": len(manifest_records),
        "artifacts": manifest_records,
    }

    manifest_out = ml_freeze_dir / "artifact_manifest.json"
    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2)
    print(f"Saved authoritative manifest to: {manifest_out}")

    # Write checksums.sha256
    checksum_out = ml_freeze_dir / "checksums.sha256"
    with open(checksum_out, "w", encoding="utf-8") as f:
        f.write("\n".join(checksum_lines) + "\n")
    print(f"Saved {len(checksum_lines)} checksums to: {checksum_out}")


if __name__ == "__main__":
    main()
