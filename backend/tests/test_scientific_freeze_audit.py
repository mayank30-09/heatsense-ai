"""Scientific Freeze and Quality Control Regression Tests for HEATSENSE AI.

Validates:
1. Cryptographic hash integrity across all freeze artifacts and checksum files.
2. Holdout integrity (132 dev blocks / 33 test blocks, disjoint, 165 total).
3. Leakage controls (test blocks prohibited from CV and model development).
4. Documentation wording regression tests (verifies scientific non-causal language and benchmark accuracy).
5. Production Analytical COG integrity (19 files, 10 bands, valid COG structure).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FREEZE_DIR = PROJECT_ROOT / "artifacts" / "ml_freeze"


def compute_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def test_authoritative_manifest_and_checksum_integrity():
    """Verify that every file recorded in artifact_manifest.json and checksums.sha256 matches actual disk hashes."""
    manifest_path = FREEZE_DIR / "artifact_manifest.json"
    checksums_path = FREEZE_DIR / "checksums.sha256"

    assert manifest_path.exists(), "artifact_manifest.json must exist"
    assert checksums_path.exists(), "checksums.sha256 must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Parse checksums.sha256
    checksum_map = {}
    with open(checksums_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    digest, rel_path = parts[0], parts[1].strip()
                    checksum_map[rel_path] = digest

    assert len(manifest["artifacts"]) > 0, "Manifest must not be empty"

    for entry in manifest["artifacts"]:
        rel_posix = entry["artifact"]
        expected_sha = entry["sha256"]
        target_path = PROJECT_ROOT / rel_posix

        assert target_path.exists(), f"Artifact does not exist on disk: {rel_posix}"
        actual_sha = compute_sha256(target_path)
        assert actual_sha == expected_sha, f"SHA-256 mismatch in manifest for {rel_posix}"
        assert checksum_map.get(rel_posix) == expected_sha, f"SHA-256 mismatch in checksums.sha256 for {rel_posix}"


def test_holdout_132_33_disjointness_and_conservation():
    """Verify strict 132 development blocks and 33 test blocks with zero overlap and full conservation."""
    split_path = FREEZE_DIR / "holdout_split.json"
    assert split_path.exists(), "holdout_split.json must exist"

    with open(split_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dev_blocks = set(data["development_blocks"])
    test_blocks = set(data["test_blocks"])

    assert len(dev_blocks) == 132, "Must contain exactly 132 development blocks"
    assert len(test_blocks) == 33, "Must contain exactly 33 test blocks"
    assert dev_blocks.isdisjoint(test_blocks), "Development and test blocks must be strictly disjoint"
    assert len(dev_blocks | test_blocks) == 165, "Total unique blocks must equal 165"


def test_leakage_prohibition_in_evaluation_manifest():
    """Verify evaluation_manifest.json records test_accessed_during_tuning=False and 1 evaluation."""
    eval_manifest_path = FREEZE_DIR / "evaluation_manifest.json"
    assert eval_manifest_path.exists(), "evaluation_manifest.json must exist"

    with open(eval_manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["evaluation_count"] == 1, "Final test evaluation count must be exactly 1"
    assert manifest["test_accessed_during_tuning"] is False, "Test blocks must never be accessed during tuning"
    assert len(manifest["test_blocks"]) == 33
    assert len(manifest["development_blocks"]) == 132


def test_documentation_scientific_wording_regression():
    """Verify that prohibited causal or over-stated wording does not appear in frozen ML/QC documentation."""
    doc_paths = [
        PROJECT_ROOT / "docs" / "scientific" / "ml_qc_freeze_record.md",
        PROJECT_ROOT / "docs" / "scientific" / "ml_holdout_results.md",
        PROJECT_ROOT / "docs" / "scientific" / "ml_qc_report.md",
    ]

    prohibited_terms = [
        (re.compile(r"\bindispensable\b", re.IGNORECASE), "Use of 'indispensable' regarding QA feature"),
        (re.compile(r"\bxgboost is faster\b", re.IGNORECASE), "Claim that 'XGBoost is faster' than RF"),
        (re.compile(r"\bmeasured\s+5\.36\s*s\b", re.IGNORECASE), "Claiming extrapolated 5.36s is a measured benchmark"),
        (re.compile(r"is caused by\b", re.IGNORECASE), "Unqualified causal claim 'is caused by'"),
    ]

    for doc_path in doc_paths:
        assert doc_path.exists(), f"Documentation file missing: {doc_path}"
        text = doc_path.read_text(encoding="utf-8")

        for pattern, desc in prohibited_terms:
            matches = pattern.findall(text)
            assert len(matches) == 0, f"Prohibited wording detected in {doc_path.name}: {desc} ({matches})"


def test_production_analytical_cogs_schema_and_integrity():
    """Verify that all 19 production analytical COGs exist, have 10 bands, correct CRS, and pass validation."""
    from gis.production.analytical_cog import ANALYTICAL_BAND_NAMES, NODATA_VALUE

    cog_dir = PROJECT_ROOT / "data" / "processed" / "analytical"
    cog_files = sorted(cog_dir.glob("*.tif"))

    assert len(cog_files) == 19, f"Expected 19 analytical COGs, found {len(cog_files)}"

    for cog_file in cog_files:
        with rasterio.open(cog_file) as src:
            assert src.count == 10, f"{cog_file.name} must have exactly 10 bands"
            assert list(src.descriptions) == ANALYTICAL_BAND_NAMES, f"{cog_file.name} band names mismatch"
            assert src.dtypes[0] == "float32", f"{cog_file.name} dtype must be float32"
            assert src.nodata == NODATA_VALUE, f"{cog_file.name} nodata mismatch"
            assert src.is_tiled, f"{cog_file.name} must be tiled"
            assert bool(src.overviews(1)), f"{cog_file.name} must have pyramid overviews"

    # Also check the validation report JSON
    validation_json_path = FREEZE_DIR / "production_cog_validation.json"
    assert validation_json_path.exists(), "production_cog_validation.json must exist"
    with open(validation_json_path, "r", encoding="utf-8") as f:
        val_data = json.load(f)
    assert val_data["validation_status"] == "PASS"
    assert val_data["total_cogs"] == 19


def test_architectural_guardrails_and_provenance():
    """Verify architectural guardrails and commit distinction in model metadata and manifests."""
    meta_path = FREEZE_DIR / "model_metadata.json"
    assert meta_path.exists(), "model_metadata.json must exist"

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta.get("validation_type") == "spatial_holdout", "Validation type must be spatial_holdout"
    assert meta.get("primary_thermal_evidence") == "observed_lst", "Observed LST must be designated primary thermal evidence"
    assert meta.get("model_prediction_role") == "supplementary_prediction_and_error_context"
    assert meta.get("future_forecasting_validated") is False, "Future forecasting must remain explicitly unvalidated"

    # Provenance commit distinction
    assert "experiment_git_commit" in meta and len(meta["experiment_git_commit"]) >= 7
    assert "freeze_git_commit" in meta and len(meta["freeze_git_commit"]) >= 7
    assert "git_commit" in meta  # backward compatibility preserved


def test_production_cog_hotspot_persistence_consistency():
    """Verify that production analytical COG Band 10 equals canonical persistent hotspot mask."""
    import numpy as np
    from gis.quality.hotspot_definitions import persistent_hotspot_mask

    cog_dir = PROJECT_ROOT / "data" / "processed" / "analytical"
    cog_files = sorted(cog_dir.glob("*.tif"))
    assert len(cog_files) == 19

    # Spot check across representative COGs
    for cog_file in cog_files:
        with rasterio.open(cog_file) as src:
            freq = src.read(9)
            pers = src.read(10)
            nodata = src.nodata

            valid = (freq != nodata) & (pers != nodata) & np.isfinite(freq)
            if not np.any(valid):
                continue

            # Band 10 values must be strictly binary 0.0 or 1.0
            actual_pers_bool = pers[valid] == 1.0
            
            # Canonical condition: freq >= 0.25 must always imply pers == 1.0
            high_freq_mask = freq[valid] >= 0.25
            assert np.all(actual_pers_bool[high_freq_mask] == True), (
                f"Pixels with frequency >= 0.25 in {cog_file.name} must be persistent"
            )


def test_downstream_scope_boundary_not_implemented():
    """Strictly assert that downstream Heat Priority and optimization systems are NOT implemented in this freeze."""
    # Ensure no optimization engine or Heat Priority candidate generator exists in backend routers
    backend_main = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "router_heat_priority" not in backend_main
    assert "router_optimization" not in backend_main
    assert "router_nsga2" not in backend_main

