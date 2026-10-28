"""Automated unit and integration tests for scripts/validation_harness.py.

Verifies:
- End-to-end execution of all 25 validation checks (17 PASS, 8 UNVERIFIED, 0 FAIL).
- Correctness of each individual check logic and invariant extraction.
- Resilient error handling when evidence files are missing.
- Resilient error handling when evidence files contain malformed/corrupted JSON.
- Report serialization (JSON and Markdown generation).
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.validation_harness import ValidationCheck, ValidationHarness


def test_validation_harness_end_to_end_passes():
    """Verify that the full validation harness passes with 17 PASS, 8 UNVERIFIED, and 0 FAIL."""
    harness = ValidationHarness()
    results = harness.run_all_checks()

    assert results["overall_status"] == "PASS"
    assert results["total_checks"] == 25
    assert results["passed_checks"] == 17
    assert results["failed_checks"] == 0
    assert results["unverified_checks"] == 8
    assert len(results["checks"]) == 25

    # Verify each check has required fields
    for c in results["checks"]:
        assert "check_id" in c
        assert "category" in c
        assert "status" in c
        assert c["status"] in ("PASS", "FAIL", "UNVERIFIED")


def test_validation_harness_individual_checks():
    """Verify each individual check logic returns expected values and PASS status."""
    harness = ValidationHarness()

    chk_freeze = harness.check_freeze_manifest()
    assert chk_freeze.status == "PASS"
    assert chk_freeze.actual["verified_matches"] == 41

    chk_split = harness.check_spatial_holdout_split()
    assert chk_split.status == "PASS"
    assert chk_split.actual["dev_blocks_count"] == 132
    assert chk_split.actual["test_blocks_count"] == 33
    assert chk_split.actual["overlap_count"] == 0

    chk_rows = harness.check_dataset_row_partitions()
    assert chk_rows.status == "PASS"
    assert chk_rows.actual["total_rows"] == 924731
    assert chk_rows.actual["test_rows"] == 203758
    assert chk_rows.actual["dev_rows"] == 720973

    chk_coords = harness.check_coordinate_feature_exclusion()
    assert chk_coords.status == "PASS"
    assert len(chk_coords.actual["leaked_coordinates"]) == 0

    chk_single = harness.check_single_holdout_evaluation()
    assert chk_single.status == "UNVERIFIED"
    assert "declared constant" in chk_single.name
    assert chk_single.actual["evaluation_count"] == 1

    chk_holdout = harness.check_holdout_metrics()
    assert chk_holdout.status == "PASS"
    assert pytest.approx(chk_holdout.actual["mae"], abs=0.001) == 1.2726
    assert pytest.approx(chk_holdout.actual["rmse"], abs=0.001) == 1.7524
    assert pytest.approx(chk_holdout.actual["r2"], abs=0.001) == 0.9006

    chk_residuals = harness.check_spatial_residuals_recomputation()
    assert chk_residuals.status == "PASS"
    assert chk_residuals.actual["total_blocks"] == 33
    assert chk_residuals.actual["total_samples"] == 203758
    assert pytest.approx(chk_residuals.actual["recomputed_mae"], abs=0.001) == 1.2726
    assert pytest.approx(chk_residuals.actual["recomputed_rmse"], abs=0.001) == 1.7524

    chk_r2 = harness.check_spatial_r2_provenance()
    assert chk_r2.status == "PASS"
    assert len(chk_r2.actual["r2_06919_active_claims"]) == 0
    assert pytest.approx(chk_r2.actual["summer_partition_r2"], abs=0.001) == 0.7119

    chk_mc = harness.check_model_comparison()
    assert chk_mc.status == "PASS"
    assert pytest.approx(chk_mc.actual["RandomForest"]["mean_rmse"], abs=0.001) == 1.8024
    assert pytest.approx(chk_mc.actual["XGBoost"]["mean_rmse"], abs=0.001) == 1.8280

    chk_conf = harness.check_conformal_calibration()
    assert chk_conf.status == "PASS"
    assert pytest.approx(chk_conf.actual["overall_empirical_coverage"], abs=0.001) == 0.9015
    assert pytest.approx(chk_conf.actual["monsoon_coverage"], abs=0.001) == 0.7919
    assert pytest.approx(chk_conf.actual["d10_coverage"], abs=0.001) == 0.8343

    chk_scenes = harness.check_scene_manifest_provenance()
    assert chk_scenes.status == "PASS"
    assert chk_scenes.actual["summer_2026"] == 22
    assert chk_scenes.actual["winter_2026"] == 20
    assert chk_scenes.actual["monsoon_2026"] == 6
    assert chk_scenes.actual["post_monsoon_2025"] == 14

    chk_monsoon = harness.check_monsoon_discrepancy_reconciliation()
    assert chk_monsoon.status == "PASS"
    assert chk_monsoon.actual["reconciliation_documented"] is True

    chk_grid = harness.check_canonical_grid_invariants()
    assert chk_grid.status == "PASS"
    assert chk_grid.actual["canonical_cells"] == 49747
    assert chk_grid.actual["chronic_definitions_present"] is True

    chk_caps = harness.check_cooling_intervention_bounds()
    assert chk_caps.status == "PASS"
    assert chk_caps.actual["tree_saturation_cap_verified"] is True
    assert chk_caps.actual["cell_combined_cap_verified"] is True

    chk_patch = harness.check_parked_stage_d_patch()
    assert chk_patch.status == "PASS"
    assert chk_patch.actual["status"] == "PARKED_UNAPPLIED"

    chk_paths = harness.check_doc_paths()
    assert chk_paths.status == "PASS"
    assert chk_paths.actual["total_missing"] == 0

    chk_counts = harness.check_doc_harness_counts()
    assert chk_counts.status == "PASS"

    chk_costs = harness.check_doc_costs_consistency()
    assert chk_costs.status == "PASS"

    unverified = harness.get_unverified_limitations()
    assert len(unverified) == 7
    for u in unverified:
        assert u.status == "UNVERIFIED"


def test_validation_harness_missing_evidence_error_handling(tmp_path: Path):
    """Verify that when evidence files do not exist, checks record FAIL and an error message without crashing."""
    fake_root = tmp_path / "empty_repo"
    fake_root.mkdir()

    harness = ValidationHarness(root_dir=fake_root)

    # 1. Missing checksum manifest
    res1 = harness.check_freeze_manifest()
    assert res1.status == "FAIL"
    assert res1.error is not None
    assert "missing" in res1.error.lower()

    # 2. Missing holdout split
    res2 = harness.check_spatial_holdout_split()
    assert res2.status == "FAIL"
    assert res2.error is not None
    assert "missing" in res2.error.lower()

    # 3. Missing row partition
    res3 = harness.check_dataset_row_partitions()
    assert res3.status == "FAIL"
    assert res3.error is not None
    assert "missing" in res3.error.lower()

    # 4. Missing feature schema
    res4 = harness.check_coordinate_feature_exclusion()
    assert res4.status == "FAIL"
    assert res4.error is not None
    assert "missing" in res4.error.lower()

    # 5. Missing holdout performance
    res5 = harness.check_holdout_metrics()
    assert res5.status == "FAIL"
    assert res5.error is not None
    assert "missing" in res5.error.lower()

    # 6. Missing spatial residuals
    res6 = harness.check_spatial_residuals_recomputation()
    assert res6.status == "FAIL"
    assert res6.error is not None
    assert "missing" in res6.error.lower()

    # 7. Missing model comparison
    res7 = harness.check_model_comparison()
    assert res7.status == "FAIL"
    assert res7.error is not None
    assert "missing" in res7.error.lower()

    # 8. Missing seasonal scene manifest
    res8 = harness.check_scene_manifest_provenance()
    assert res8.status == "FAIL"
    assert res8.error is not None
    assert "missing" in res8.error.lower()


def test_validation_harness_corrupted_json_error_handling(tmp_path: Path):
    """Verify that when an evidence file contains malformed JSON, checks record FAIL without raising unhandled exceptions."""
    fake_root = tmp_path / "corrupted_repo"
    fake_freeze = fake_root / "artifacts" / "ml_freeze"
    fake_freeze.mkdir(parents=True)

    # Write a malformed holdout_split.json
    corrupted_file = fake_freeze / "holdout_split.json"
    with open(corrupted_file, "w", encoding="utf-8") as f:
        f.write("{invalid_json: True, unclosed_bracket: [")

    harness = ValidationHarness(root_dir=fake_root)
    result = harness.check_spatial_holdout_split()

    assert result.status == "FAIL"
    assert result.error is not None
    assert "Expecting property name" in result.error or "JSON" in result.error or "char" in result.error


def test_validation_harness_report_generation(tmp_path: Path):
    """Verify that report generation outputs valid markdown and json artifacts."""
    harness = ValidationHarness()
    results = harness.run_all_checks()

    # Test Markdown generation
    md_content = harness.generate_markdown_report(results)
    assert "# HEATSENSE AI — Validation Harness Audit Report" in md_content
    assert "CHK-01-FREEZE-MANIFEST" in md_content
    assert "CHK-06-HOLDOUT-METRICS" in md_content
    assert "CHK-19-UNVERIFIED-ROOF-STRUCTURAL" in md_content

    # Test saving both JSON and Markdown
    out_json = tmp_path / "test_report.json"
    out_md = tmp_path / "test_report.md"

    harness.save_report(results, json_path=out_json, md_path=out_md)

    assert out_json.exists()
    assert out_md.exists()

    with open(out_json, "r", encoding="utf-8") as f:
        loaded_json = json.load(f)
    assert loaded_json["overall_status"] == "PASS"
    assert loaded_json["total_checks"] == 25
