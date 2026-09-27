from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ee

from gis.gee.landsat_lst import (
    build_landsat_collection,
    initialize_earth_engine,
    load_surat_boundary,
)

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

START_YEAR = 2022
END_YEAR = 2026

THRESHOLDS = [1, 2, 3, 4, 5, 6, 8, 10]

SEASONS = (
    "winter",
    "summer",
    "monsoon",
    "post_monsoon",
)

REDUCTION_CRS = "EPSG:4326"
REDUCTION_SCALE = 100
REDUCTION_MAX_PIXELS = 1_000_000_000

REPORTS_DIR = PROJECT_ROOT / "reports"
CSV_OUTPUT_PATH = REPORTS_DIR / "observation_support_sensitivity.csv"
SUMMARY_CSV_PATH = REPORTS_DIR / "observation_support_sensitivity_summary.csv"


# ---------------------------------------------------------------------
# Seasonal Date Windows
# ---------------------------------------------------------------------

def seasonal_dates(year: int, season: str) -> tuple[str, str]:
    """
    Return the seasonal date range used by HEATSENSE AI.

    Winter:
        December 1 of previous year -> March 1 target year
    Summer:
        March 1 -> June 1
    Monsoon:
        June 1 -> October 1
    Post-monsoon:
        October 1 -> December 1
    """
    if season == "winter":
        return f"{year - 1}-12-01", f"{year}-03-01"
    if season == "summer":
        return f"{year}-03-01", f"{year}-06-01"
    if season == "monsoon":
        return f"{year}-06-01", f"{year}-10-01"
    if season == "post_monsoon":
        return f"{year}-10-01", f"{year}-12-01"

    raise ValueError(f"Unknown season: {season}")


# ---------------------------------------------------------------------
# Quality Indicator (ST_QA)
# ---------------------------------------------------------------------

def add_st_qa(image: ee.Image) -> ee.Image:
    """
    Add Landsat ST_QA converted to Kelvin (scale factor 0.01 K).

    Scientific Note:
        This is treated as a quality indicator for the seasonal
        analysis. It represents the seasonal median of per-scene ST_QA,
        NOT the exact uncertainty of the seasonal median LST composite.
    """
    qa_k = (
        image.select("ST_QA")
        .multiply(0.01)
        .rename("ST_QA_K")
    )
    return image.addBands(qa_k)


# ---------------------------------------------------------------------
# Helper for Numeric Formatting
# ---------------------------------------------------------------------

def safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return f
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------
# Analyze One Season
# ---------------------------------------------------------------------

def analyze_season(
    year: int,
    season: str,
    boundary: ee.Geometry,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Analyze observation-support sensitivity for one year/season using a single
    unified reduction across all candidate thresholds.

    Returns:
        (rows, season_metadata)
    """
    start_date, end_date = seasonal_dates(year, season)

    print()
    print("-" * 90)
    print(f"Season      : {year} {season.upper()}")
    print(f"Date range  : {start_date} -> {end_date}")

    collection = build_landsat_collection(
        boundary=boundary,
        start_date=start_date,
        end_date=end_date,
    )

    scene_count = int(collection.size().getInfo())
    print(f"Scene count : {scene_count}")

    season_meta = {
        "year": year,
        "season": season,
        "start_date": start_date,
        "end_date": end_date,
        "scene_count": scene_count,
        "status": "PROCESSED",
    }

    if scene_count == 0:
        print("Status      : SKIPPED (0 Landsat L2SP scenes found)")
        season_meta["status"] = "SKIPPED_ZERO_SCENES"
        return [], season_meta

    # 1. Build median LST and pixel observation count
    lst_collection = collection.select("lst_c")
    lst = lst_collection.median().rename("lst_c")
    obs = lst_collection.count().rename("OBS_COUNT")

    # 2. Build median ST_QA indicator, masked consistently with valid LST
    qa = collection.map(add_st_qa).select("ST_QA_K").median().rename("ST_QA_K")
    qa = qa.updateMask(lst.mask())

    # 3. Assemble all threshold bands for unified single reduction
    band_images: list[ee.Image] = []
    for t in THRESHOLDS:
        mask_t = obs.gte(t)
        lst_t = lst.updateMask(mask_t).rename(f"lst_t{t}")
        qa_t = qa.updateMask(mask_t).rename(f"qa_t{t}")
        obs_t = obs.updateMask(mask_t).rename(f"obs_t{t}")
        band_images.extend([lst_t, qa_t, obs_t])

    multi_band = ee.Image.cat(band_images)

    reducer = (
        ee.Reducer.count()
        .combine(ee.Reducer.mean(), sharedInputs=True)
        .combine(ee.Reducer.percentile([50, 95, 99]), sharedInputs=True)
        .combine(ee.Reducer.max(), sharedInputs=True)
    )

    t_start = time.time()
    stats = multi_band.reduceRegion(
        reducer=reducer,
        geometry=boundary,
        scale=REDUCTION_SCALE,
        crs=REDUCTION_CRS,
        maxPixels=REDUCTION_MAX_PIXELS,
        bestEffort=False,
    ).getInfo()
    t_elapsed = time.time() - t_start

    # 4. Extract baseline (Threshold = 1)
    baseline_raw = stats.get("lst_t1_count")
    baseline = int(baseline_raw) if baseline_raw is not None else 0

    print(f"Reduction   : {t_elapsed:.2f}s | Baseline valid pixels (T>=1): {baseline}")

    if baseline <= 0:
        print("Status      : SKIPPED (No valid pixels inside boundary)")
        season_meta["status"] = "SKIPPED_NO_VALID_PIXELS"
        return [], season_meta

    # 5. Extract statistics for each threshold and perform mathematical checks
    results: list[dict[str, Any]] = []
    prev_retained = baseline

    for t in THRESHOLDS:
        raw_count = stats.get(f"lst_t{t}_count")
        retained = int(raw_count) if raw_count is not None else 0

        # Mathematical consistency validations
        if t == 1 and retained != baseline:
            raise RuntimeError(
                f"Threshold-1 consistency violation in {year} {season}: "
                f"baseline={baseline}, threshold_1={retained}. Must be identical."
            )

        if retained > baseline:
            raise RuntimeError(
                f"Threshold overflow in {year} {season} (T={t}): "
                f"retained={retained} > baseline={baseline}."
            )

        if retained > prev_retained:
            raise RuntimeError(
                f"Monotonicity violation in {year} {season} (T={t}): "
                f"retained={retained} > prev_threshold_retained={prev_retained}."
            )

        retention_pct = (retained / baseline) * 100.0 if baseline > 0 else 0.0

        lst_mean = safe_float(stats.get(f"lst_t{t}_mean"))
        lst_p95 = safe_float(stats.get(f"lst_t{t}_p95"))
        lst_p99 = safe_float(stats.get(f"lst_t{t}_p99"))
        lst_max = safe_float(stats.get(f"lst_t{t}_max"))

        qa_mean = safe_float(stats.get(f"qa_t{t}_mean"))
        qa_p50 = safe_float(stats.get(f"qa_t{t}_p50"))
        qa_p95 = safe_float(stats.get(f"qa_t{t}_p95"))

        obs_mean = safe_float(stats.get(f"obs_t{t}_mean"))
        obs_p50 = safe_float(stats.get(f"obs_t{t}_p50"))
        obs_p95 = safe_float(stats.get(f"obs_t{t}_p95"))

        row = {
            "year": year,
            "season": season,
            "scenes": scene_count,
            "threshold": t,
            "baseline": baseline,
            "retained": retained,
            "retention_pct": round(retention_pct, 4),
            "lst_mean": round(lst_mean, 4) if lst_mean is not None else None,
            "lst_p95": round(lst_p95, 4) if lst_p95 is not None else None,
            "lst_p99": round(lst_p99, 4) if lst_p99 is not None else None,
            "lst_max": round(lst_max, 4) if lst_max is not None else None,
            "qa_mean": round(qa_mean, 4) if qa_mean is not None else None,
            "qa_p50": round(qa_p50, 4) if qa_p50 is not None else None,
            "qa_p95": round(qa_p95, 4) if qa_p95 is not None else None,
            "obs_mean": round(obs_mean, 4) if obs_mean is not None else None,
            "obs_p50": round(obs_p50, 4) if obs_p50 is not None else None,
            "obs_p95": round(obs_p95, 4) if obs_p95 is not None else None,
        }
        results.append(row)
        prev_retained = retained

        # Console log line
        lst_mean_str = f"{lst_mean:7.2f}°C" if lst_mean is not None else "     NA"
        lst_p95_str = f"{lst_p95:7.2f}°C" if lst_p95 is not None else "     NA"
        lst_max_str = f"{lst_max:7.2f}°C" if lst_max is not None else "     NA"
        qa_p50_str = f"{qa_p50:5.2f}K" if qa_p50 is not None else "   NA"
        obs_mean_str = f"{obs_mean:5.1f}" if obs_mean is not None else "   NA"

        print(
            f"  T >= {t:>2} | Retained: {retained:>5} ({retention_pct:6.2f}%) | "
            f"LST Mean: {lst_mean_str} | P95: {lst_p95_str} | Max: {lst_max_str} | "
            f"QA Median: {qa_p50_str} | OBS Mean: {obs_mean_str}"
        )

    return results, season_meta


# ---------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------

def main() -> None:
    print("=" * 90)
    print("HEATSENSE AI")
    print("LANDSAT SEASONAL OBSERVATION-SUPPORT SENSITIVITY ANALYSIS")
    print("=" * 90)
    print(f"Target Year Range : {START_YEAR} -> {END_YEAR}")
    print(f"Candidate Cutoffs : {THRESHOLDS}")
    print(f"Grid Parameters   : {REDUCTION_CRS}, Scale={REDUCTION_SCALE}m")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\nInitializing Google Earth Engine...")
    initialize_earth_engine()
    print("Earth Engine initialized successfully.")

    print("Loading Surat SMC boundary...")
    boundary = load_surat_boundary()
    print("Surat boundary loaded successfully.")

    all_results: list[dict[str, Any]] = []
    season_summaries: list[dict[str, Any]] = []

    total_start = time.time()

    for year in range(START_YEAR, END_YEAR + 1):
        for season in SEASONS:
            rows, meta = analyze_season(
                year=year,
                season=season,
                boundary=boundary,
            )
            season_summaries.append(meta)
            all_results.extend(rows)

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 90)
    print(f"ANALYSIS COMPLETE in {total_elapsed:.2f} seconds.")
    print("=" * 90)

    # -----------------------------------------------------------------
    # Write Full Sensitivity CSV
    # -----------------------------------------------------------------
    fieldnames = [
        "year",
        "season",
        "scenes",
        "threshold",
        "baseline",
        "retained",
        "retention_pct",
        "lst_mean",
        "lst_p95",
        "lst_p99",
        "lst_max",
        "qa_mean",
        "qa_p50",
        "qa_p95",
        "obs_mean",
        "obs_p50",
        "obs_p95",
    ]

    with open(CSV_OUTPUT_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            # Map None to empty string for clean CSV
            row_clean = {k: ("" if v is None else v) for k, v in r.items()}
            writer.writerow(row_clean)

    print(f"\nSaved full sensitivity CSV to: {CSV_OUTPUT_PATH}")

    # -----------------------------------------------------------------
    # Write Summary CSV
    # -----------------------------------------------------------------
    summary_fieldnames = [
        "year",
        "season",
        "date_range",
        "scene_count",
        "status",
        "baseline_pixels",
        "retention_t2_pct",
        "retention_t3_pct",
        "retention_t4_pct",
        "lst_max_t1",
        "lst_max_t2",
        "lst_max_t3",
    ]

    with open(SUMMARY_CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fieldnames)
        writer.writeheader()
        for s in season_summaries:
            y = s["year"]
            sea = s["season"]
            s_rows = [r for r in all_results if r["year"] == y and r["season"] == sea]

            row_summary: dict[str, Any] = {
                "year": y,
                "season": sea,
                "date_range": f"{s['start_date']} to {s['end_date']}",
                "scene_count": s["scene_count"],
                "status": s["status"],
                "baseline_pixels": s_rows[0]["baseline"] if s_rows else 0,
                "retention_t2_pct": next((r["retention_pct"] for r in s_rows if r["threshold"] == 2), ""),
                "retention_t3_pct": next((r["retention_pct"] for r in s_rows if r["threshold"] == 3), ""),
                "retention_t4_pct": next((r["retention_pct"] for r in s_rows if r["threshold"] == 4), ""),
                "lst_max_t1": next((r["lst_max"] for r in s_rows if r["threshold"] == 1), ""),
                "lst_max_t2": next((r["lst_max"] for r in s_rows if r["threshold"] == 2), ""),
                "lst_max_t3": next((r["lst_max"] for r in s_rows if r["threshold"] == 3), ""),
            }
            writer.writerow(row_summary)

    print(f"Saved summary CSV to: {SUMMARY_CSV_PATH}")

    # -----------------------------------------------------------------
    # Consistency Verification Summary
    # -----------------------------------------------------------------
    print("\n--- FINAL VERIFICATION CHECKS ---")
    t1_checks = [r for r in all_results if r["threshold"] == 1]
    all_t1_equal_baseline = all(r["retained"] == r["baseline"] for r in t1_checks)
    all_retention_le_100 = all(r["retention_pct"] <= 100.0 for r in all_results)

    print(f"Total processed seasons with data : {len(t1_checks)}")
    print(f"Threshold=1 == Baseline check     : {'PASSED (100% exact match)' if all_t1_equal_baseline else 'FAILED'}")
    print(f"Retention <= 100% check            : {'PASSED' if all_retention_le_100 else 'FAILED'}")


if __name__ == "__main__":
    main()