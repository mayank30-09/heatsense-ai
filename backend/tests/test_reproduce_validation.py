"""Unit tests for scripts/reproduce_validation_report.py."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.reproduce_validation_report import (
    generate_validation_report,
    verify_manifest,
    recompute_validation_metrics,
    recompute_spatial_residual_metrics,
    compare_with_displayed,
)


def test_manifest_verification_matches_freeze():
    """Verify that all 41 protected freeze artifacts match their SHA-256 hashes."""
    result = verify_manifest()
    assert result["status"] == "PASS"
    assert result["total_manifest_entries"] == 41
    assert result["verified_matches"] == 41
    assert len(result["missing_files"]) == 0
    assert len(result["checksum_mismatches"]) == 0


def test_spatial_residuals_recomputation_matches_holdout():
    """Verify that sample-weighted aggregation over 33 locked test blocks in GeoJSON matches holdout metrics."""
    spat = recompute_spatial_residual_metrics()
    assert spat["total_blocks"] == 33
    assert spat["total_samples"] == 203758
    assert pytest.approx(spat["sample_weighted_mae"], abs=0.0001) == 1.2726
    assert pytest.approx(spat["sample_weighted_rmse"], abs=0.0001) == 1.7524


def test_recomputed_metrics_from_stored_artifacts():
    """Verify metrics extracted strictly from stored evaluation artifacts."""
    recomputed = recompute_validation_metrics()

    # Holdout
    holdout = recomputed["holdout"]
    assert pytest.approx(holdout["mae"], abs=0.001) == 1.2726
    assert pytest.approx(holdout["rmse"], abs=0.001) == 1.7524
    assert pytest.approx(holdout["r2"], abs=0.001) == 0.9006
    assert holdout["evaluation_count"] == 1

    # Spatial Residuals
    spat = recomputed["spatial_residuals"]
    assert spat["total_blocks"] == 33
    assert spat["total_samples"] == 203758
    assert pytest.approx(spat["sample_weighted_mae"], abs=0.0001) == 1.2726
    assert pytest.approx(spat["sample_weighted_rmse"], abs=0.0001) == 1.7524

    # QC Summary
    qc = recomputed["qc_summary"]
    assert qc["row_count"] == 924731
    assert qc["dev_blocks"] == 132
    assert qc["test_blocks"] == 33
    assert qc["total_blocks"] == 165

    # Controlled Model Comparison
    mc = recomputed["model_comparison"]
    assert "RandomForest" in mc and "XGBoost" in mc
    assert pytest.approx(mc["RandomForest"]["mean_rmse"], abs=0.001) == 1.8024
    assert pytest.approx(mc["XGBoost"]["mean_rmse"], abs=0.001) == 1.8280

    # Conformal Calibration
    conf = recomputed["conformal_calibration"]
    assert pytest.approx(conf["overall_empirical_coverage"], abs=0.001) == 0.9015
    assert pytest.approx(conf["monsoon_coverage"], abs=0.001) == 0.7919
    assert pytest.approx(conf["d10_coverage"], abs=0.001) == 0.8343


def test_full_reproduction_report_passes():
    """Verify end-to-end validation reproduction report generation."""
    report = generate_validation_report()
    assert report["overall_status"] == "PASS"
    assert report["manifest_verification"]["status"] == "PASS"
    assert report["displayed_comparison"]["status"] == "PASS"
    assert report["displayed_comparison"]["passed_checks"] == 12

    # Verify required verbatim disclosures
    disclosures = report["disclosures"]
    assert "evaluated once on the 33 locked test blocks: MAE 1.2726 C, RMSE 1.7524 C, R2 0.9006" in disclosures["holdout_usage"]
    assert "evaluation_count: 1 is a constant written by scripts/final_holdout_evaluation.py, not a runtime counter" in disclosures["holdout_usage"]
    assert disclosures["confidence_index"] == "confidence index is a heuristic, not a calibrated probability"

