"""Reproduce Validation Report Script (Read-Only).

Verifies the cryptographic freeze manifest and recomputes validation metrics
strictly from STORED evaluation artifacts. Compares recomputed metrics against
the authoritative displayed values in the UI and validation reports.

Usage:
    python scripts/reproduce_validation_report.py [--output path/to/report.json]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DIR = PROJECT_ROOT / "artifacts" / "ml_freeze"
CHECKSUMS_FILE = FREEZE_DIR / "checksums.sha256"
HOLDOUT_PERF_FILE = FREEZE_DIR / "holdout_performance.json"
QC_SUMMARY_FILE = FREEZE_DIR / "qc_summary.json"
MODEL_META_FILE = FREEZE_DIR / "model_metadata.json"
MODEL_COMPARISON_CSV = PROJECT_ROOT / "data" / "diagnostics" / "ml" / "model_comparison_rf_xgb.csv"
ML_EXP_FILE = PROJECT_ROOT / "artifacts" / "ml_experiments" / "ml_experimental_evaluation.json"
SPATIAL_RESIDUALS_FILE = FREEZE_DIR / "holdout_spatial_residuals.geojson"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest() -> dict[str, Any]:
    """Verify all files listed in checksums.sha256 manifest."""
    if not CHECKSUMS_FILE.exists():
        return {"status": "FAIL", "error": f"Missing {CHECKSUMS_FILE}", "verified": 0, "total": 0}

    total = 0
    verified = 0
    mismatches: list[str] = []
    missing: list[str] = []

    with open(CHECKSUMS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            expected_hash, rel_path = parts
            target = PROJECT_ROOT / rel_path
            total += 1
            if not target.exists():
                missing.append(rel_path)
                continue
            actual_hash = sha256_file(target)
            if actual_hash.lower() == expected_hash.lower():
                verified += 1
            else:
                mismatches.append(rel_path)

    status = "PASS" if (verified == total and total > 0 and not missing and not mismatches) else "FAIL"
    return {
        "status": status,
        "total_manifest_entries": total,
        "verified_matches": verified,
        "missing_files": missing,
        "checksum_mismatches": mismatches,
    }


def recompute_spatial_residual_metrics() -> dict[str, Any]:
    """Recompute holdout MAE and RMSE from the stored per-block spatial residuals GeoJSON artifact."""
    if not SPATIAL_RESIDUALS_FILE.exists():
        return {"error": f"Missing {SPATIAL_RESIDUALS_FILE}"}

    with open(SPATIAL_RESIDUALS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    total_samples = sum(f["properties"].get("n_samples", 0) for f in features)
    if total_samples == 0:
        return {"error": "Zero total samples in spatial residuals GeoJSON"}

    weighted_mae = sum(
        f["properties"].get("n_samples", 0) * f["properties"].get("mae", 0.0)
        for f in features
    ) / total_samples

    weighted_mse = sum(
        f["properties"].get("n_samples", 0) * (f["properties"].get("rmse", 0.0) ** 2)
        for f in features
    ) / total_samples
    weighted_rmse = math.sqrt(weighted_mse)

    return {
        "total_blocks": len(features),
        "total_samples": total_samples,
        "sample_weighted_mae": round(weighted_mae, 4),
        "sample_weighted_rmse": round(weighted_rmse, 4),
        "raw_sample_weighted_mae": float(weighted_mae),
        "raw_sample_weighted_rmse": float(weighted_rmse),
    }


def recompute_validation_metrics() -> dict[str, Any]:
    """Recompute metrics strictly from stored evaluation artifacts."""
    recomputed: dict[str, Any] = {}

    # 1. Holdout performance from JSON
    if HOLDOUT_PERF_FILE.exists():
        with open(HOLDOUT_PERF_FILE, "r", encoding="utf-8") as f:
            holdout = json.load(f)
        mae = holdout.get("MAE") or holdout.get("metrics", {}).get("mae") or holdout.get("mae", 0.0)
        rmse = holdout.get("RMSE") or holdout.get("metrics", {}).get("rmse") or holdout.get("rmse", 0.0)
        r2 = holdout.get("R2") or holdout.get("metrics", {}).get("r2") or holdout.get("r2", 0.0)
        inf_lat = holdout.get("inference_time_seconds") or holdout.get("inference_latency_seconds", 0.0)
        recomputed["holdout"] = {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "evaluation_count": int(holdout.get("evaluation_count", 0)),
            "inference_latency_seconds": float(inf_lat),
        }
    else:
        recomputed["holdout"] = {"error": "Missing holdout_performance.json"}

    # 2. Recomputed holdout metrics from spatial residuals GeoJSON
    recomputed["spatial_residuals"] = recompute_spatial_residual_metrics()

    # 2. QC Summary
    if QC_SUMMARY_FILE.exists():
        with open(QC_SUMMARY_FILE, "r", encoding="utf-8") as f:
            qc = json.load(f)
        recomputed["qc_summary"] = {
            "row_count": qc.get("dataset_integrity", {}).get("row_count"),
            "dev_blocks": qc.get("spatial_split_integrity", {}).get("development_blocks"),
            "test_blocks": qc.get("spatial_split_integrity", {}).get("test_blocks"),
            "total_blocks": qc.get("spatial_split_integrity", {}).get("total_blocks"),
            "seasonal_seasons": list(qc.get("seasonal_performance", {}).keys()),
            "hotspot_strata": list(qc.get("hotspot_performance", {}).keys()),
        }
    else:
        recomputed["qc_summary"] = {"error": "Missing qc_summary.json"}

    # 3. Model Metadata
    if MODEL_META_FILE.exists():
        with open(MODEL_META_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        recomputed["model_metadata"] = {
            "model_id": meta.get("model_id"),
            "best_development_cv_rmse": float(meta.get("best_development_cv_rmse", 0.0)),
        }
    else:
        recomputed["model_metadata"] = {"error": "Missing model_metadata.json"}

    # 4. Controlled Model Comparison CSV
    if MODEL_COMPARISON_CSV.exists():
        comparison: dict[str, Any] = {}
        with open(MODEL_COMPARISON_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                comparison[row["model"]] = {
                    "mean_mae": float(row["mean_MAE"]),
                    "std_mae": float(row["std_MAE"]),
                    "mean_rmse": float(row["mean_RMSE"]),
                    "std_rmse": float(row["std_RMSE"]),
                    "mean_r2": float(row["mean_R2"]),
                    "std_r2": float(row["std_R2"]),
                }
        recomputed["model_comparison"] = comparison
    else:
        recomputed["model_comparison"] = {"error": "Missing model_comparison_rf_xgb.csv"}

    # 5. Conformal Calibration
    if ML_EXP_FILE.exists():
        with open(ML_EXP_FILE, "r", encoding="utf-8") as f:
            exp_data = json.load(f)
        conf = exp_data.get("experiments", {}).get("conformal_calibration", {})
        recomputed["conformal_calibration"] = {
            "nominal_coverage": conf.get("nominal_coverage"),
            "overall_empirical_coverage": conf.get("overall_empirical_coverage"),
            "monsoon_coverage": conf.get("subgroups", {}).get("season", {}).get("monsoon", {}).get("coverage"),
            "d10_coverage": conf.get("subgroups", {}).get("heat_decile", {}).get("D10", {}).get("coverage"),
        }
    else:
        recomputed["conformal_calibration"] = {"error": "Missing ml_experimental_evaluation.json"}

    return recomputed


def compare_with_displayed(recomputed: dict[str, Any]) -> dict[str, Any]:
    """Compare recomputed metrics with displayed benchmarks."""
    expected = {
        "holdout_mae": 1.2726,
        "holdout_rmse": 1.7524,
        "holdout_r2": 0.9006,
        "dev_blocks": 132,
        "test_blocks": 33,
        "total_rows": 924731,
        "rf_cv_rmse": 1.8024,
        "xgb_cv_rmse": 1.8280,
        "monsoon_conformal_coverage": 0.7919,
        "d10_conformal_coverage": 0.8343,
    }

    checks: list[dict[str, Any]] = []

    def check(name: str, actual: float | int | None, target: float | int, tolerance: float = 0.001):
        if actual is None:
            passed = False
            diff = None
        elif isinstance(target, int):
            passed = (actual == target)
            diff = actual - target
        else:
            diff = abs(actual - target)
            passed = diff <= tolerance

        checks.append({
            "metric": name,
            "artifact_value": actual,
            "displayed_value": target,
            "diff": round(diff, 6) if diff is not None else None,
            "passed": passed,
        })

    holdout = recomputed.get("holdout", {})
    check("holdout_mae", holdout.get("mae"), expected["holdout_mae"])
    check("holdout_rmse", holdout.get("rmse"), expected["holdout_rmse"])
    check("holdout_r2", holdout.get("r2"), expected["holdout_r2"])

    spat = recomputed.get("spatial_residuals", {})
    check("spatial_residuals_mae", spat.get("sample_weighted_mae"), expected["holdout_mae"])
    check("spatial_residuals_rmse", spat.get("sample_weighted_rmse"), expected["holdout_rmse"])

    qc = recomputed.get("qc_summary", {})
    check("dev_blocks", qc.get("dev_blocks"), expected["dev_blocks"], 0)
    check("test_blocks", qc.get("test_blocks"), expected["test_blocks"], 0)
    check("total_rows", qc.get("row_count"), expected["total_rows"], 0)

    mc = recomputed.get("model_comparison", {})
    rf = mc.get("RandomForest", {})
    xgb = mc.get("XGBoost", {})
    check("rf_cv_rmse", rf.get("mean_rmse"), expected["rf_cv_rmse"])
    check("xgb_cv_rmse", xgb.get("mean_rmse"), expected["xgb_cv_rmse"])

    conf = recomputed.get("conformal_calibration", {})
    check("monsoon_conformal_coverage", conf.get("monsoon_coverage"), expected["monsoon_conformal_coverage"])
    check("d10_conformal_coverage", conf.get("d10_coverage"), expected["d10_conformal_coverage"])

    all_passed = all(c["passed"] for c in checks)
    return {
        "status": "PASS" if all_passed else "FAIL",
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["passed"]),
        "checks": checks,
    }


def generate_validation_report() -> dict[str, Any]:
    """Execute full read-only validation reproduction."""
    manifest_result = verify_manifest()
    recomputed_metrics = recompute_validation_metrics()
    comparison_result = compare_with_displayed(recomputed_metrics)

    overall_status = "PASS" if (manifest_result["status"] == "PASS" and comparison_result["status"] == "PASS") else "FAIL"

    return {
        "tool": "reproduce_validation_report",
        "mode": "READ_ONLY",
        "overall_status": overall_status,
        "manifest_verification": manifest_result,
        "recomputed_metrics": recomputed_metrics,
        "displayed_comparison": comparison_result,
        "disclosures": {
            "holdout_usage": (
                "The final model (xgb_tuned_policy_d, SHA-256 e1aedd49...) was evaluated once on the 33 locked test blocks: "
                "MAE 1.2726 C, RMSE 1.7524 C, R2 0.9006. Earlier, a preliminary tuning study (artifacts/xgb_tuning/) was run "
                "before the holdout split existed; its CV used all 165 blocks (unique_blocks_count 165), so the blocks later "
                "locked as the test set were part of that study, and a configuration from it was evaluated on them "
                "(RMSE 1.7342 C in the file committed in 32197ef, which does not match the frozen model). That result is superseded. "
                "The frozen study searched the 132 development blocks only (unique_blocks_in_search 132). evaluation_count: 1 "
                "is a constant written by scripts/final_holdout_evaluation.py, not a runtime counter."
            ),
            "confidence_index": "confidence index is a heuristic, not a calibrated probability",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Reproduce Validation Report from Stored Artifacts (Read-Only)")
    parser.add_argument("--output", type=str, help="Optional path to write JSON report")
    args = parser.parse_args()

    report = generate_validation_report()
    report_json = json.dumps(report, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_json)
        print(f"Report written to {out_path}")
    else:
        print(report_json)

    if report["overall_status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
