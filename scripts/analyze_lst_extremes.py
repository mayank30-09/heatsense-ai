from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.mask
import rasterio.transform

try:
    import ee
    from gis.gee.landsat_lst import (
        build_landsat_collection,
        initialize_earth_engine,
        load_surat_boundary,
    )
    EE_AVAILABLE = True
except Exception:
    EE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants and Paths
# ---------------------------------------------------------------------------

START_YEAR = 2022
END_YEAR = 2026

SEASONS = (
    "winter",
    "summer",
    "monsoon",
    "post_monsoon",
)

SEASON_WINDOWS = {
    "winter": (12, 1, 3, 1),
    "summer": (3, 1, 6, 1),
    "monsoon": (6, 1, 10, 1),
    "post_monsoon": (10, 1, 12, 1),
}

BOUNDARY_PATH = PROJECT_ROOT / "data" / "raw" / "boundaries" / "surat_smc_boundary.geojson"
SEASONAL_COG_ROOT = PROJECT_ROOT / "data" / "processed" / "seasonal"
DEFAULT_OUTPUT_BASE = PROJECT_ROOT / "data" / "diagnostics"
TOTAL_SMC_GRID_CELLS = 50752  # Baseline theoretical count for full Surat SMC grid


# ---------------------------------------------------------------------------
# CLI Argument Parser
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: Landsat LST Extreme-Value Spatial Diagnostic & Extraction Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--year",
        type=int,
        choices=range(START_YEAR, END_YEAR + 1),
        help=f"Target year ({START_YEAR}-{END_YEAR}). If omitted, analyzes all available years.",
    )
    parser.add_argument(
        "--season",
        type=str,
        choices=SEASONS,
        help="Target season. If omitted, analyzes all available seasons.",
    )
    parser.add_argument(
        "--top-percentile",
        type=float,
        default=1.0,
        help="Top percentile for hot extreme identification (e.g. 1.0 for P99).",
    )
    parser.add_argument(
        "--bottom-percentile",
        type=float,
        default=1.0,
        help="Bottom percentile for cold extreme identification (e.g. 1.0 for P01).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Ranked number of absolute highest LST pixels to extract.",
    )
    parser.add_argument(
        "--bottom-n",
        type=int,
        default=20,
        help="Ranked number of absolute lowest LST pixels to extract.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_BASE,
        help="Base directory to store diagnostic GeoJSON and quality CSV outputs.",
    )
    parser.add_argument(
        "--skip-gee",
        action="store_true",
        help="Skip online Google Earth Engine sampling of ST_QA uncertainty values.",
    )
    return parser


# ---------------------------------------------------------------------------
# Date Helpers
# ---------------------------------------------------------------------------

def season_dates(year: int, season: str) -> tuple[str, str]:
    start_month, start_day, end_month, end_day = SEASON_WINDOWS[season]
    if season == "winter":
        start_year = year - 1
        end_year = year
    else:
        start_year = year
        end_year = year
    return f"{start_year:04d}-{start_month:02d}-{start_day:02d}", f"{end_year:04d}-{end_month:02d}-{end_day:02d}"


# ---------------------------------------------------------------------------
# Earth Engine Sampling Helper
# ---------------------------------------------------------------------------

def add_st_qa(image: Any) -> Any:
    qa_k = image.select("ST_QA").multiply(0.01).rename("ST_QA_K")
    return image.addBands(qa_k)


def sample_gee_qa_batch(
    coords: list[tuple[float, float]],
    year: int,
    season: str,
    boundary_ee: Any,
) -> dict[tuple[float, float], float | None]:
    """
    Sample seasonal median ST_QA uncertainty in Kelvin at a list of coordinate pairs.
    """
    if not EE_AVAILABLE:
        return {pt: None for pt in coords}

    start_date, end_date = season_dates(year, season)

    try:
        collection = build_landsat_collection(
            boundary=boundary_ee,
            start_date=start_date,
            end_date=end_date,
        )
        scene_count = int(collection.size().getInfo())
        if scene_count == 0:
            return {pt: None for pt in coords}

        qa_image = collection.map(add_st_qa).select("ST_QA_K").median().rename("ST_QA_K")

        # Build EE FeatureCollection of points
        features = [
            ee.Feature(ee.Geometry.Point([lon, lat]), {"orig_lon": lon, "orig_lat": lat})
            for (lon, lat) in coords
        ]
        fc = ee.FeatureCollection(features)

        sampled = qa_image.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.first(),
            scale=100,
            crs="EPSG:4326",
        ).getInfo()

        qa_map: dict[tuple[float, float], float | None] = {}
        for feat in sampled.get("features", []):
            props = feat.get("properties", {})
            lon = round(float(props["orig_lon"]), 6)
            lat = round(float(props["orig_lat"]), 6)
            first_val = props.get("first")
            qa_map[(lon, lat)] = round(float(first_val), 3) if first_val is not None else None

        return qa_map

    except Exception as e:
        print(f"  [Warning] GEE QA sampling failed for {year} {season}: {e}. Proceeding with None.")
        return {pt: None for pt in coords}


# ---------------------------------------------------------------------------
# Neighborhood Consistency Analysis
# ---------------------------------------------------------------------------

def compute_neighborhood_stats(
    lst_band: np.ndarray,
    row: int,
    col: int,
) -> dict[str, float | int | None]:
    """
    Calculate 3x3 neighborhood statistics on LST_C strictly excluding the center pixel.
    Handles boundaries and NoData values (-9999.0 / NaN).
    """
    center_val = lst_band[row, col]
    rows, cols = lst_band.shape

    neighbors: list[float] = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                val = lst_band[nr, nc]
                if val != -9999.0 and np.isfinite(val):
                    neighbors.append(float(val))

    valid_count = len(neighbors)
    if valid_count == 0:
        return {
            "neighborhood_median": None,
            "neighborhood_mean": None,
            "neighborhood_std": None,
            "valid_neighbor_count": 0,
            "pixel_minus_neighborhood_median": None,
            "absolute_pixel_minus_neighborhood_median": None,
        }

    n_mean = float(np.mean(neighbors))
    n_med = float(np.median(neighbors))
    n_std = float(np.std(neighbors))
    diff_med = float(center_val - n_med)
    abs_diff = float(abs(diff_med))

    return {
        "neighborhood_median": round(n_med, 4),
        "neighborhood_mean": round(n_mean, 4),
        "neighborhood_std": round(n_std, 4),
        "valid_neighbor_count": valid_count,
        "pixel_minus_neighborhood_median": round(diff_med, 4),
        "absolute_pixel_minus_neighborhood_median": round(abs_diff, 4),
    }


# ---------------------------------------------------------------------------
# Exploratory Diagnostic Classification
# ---------------------------------------------------------------------------

def classify_extreme_pixel(
    obs: float,
    qa: float | None,
    abs_diff_med: float | None,
    valid_neighbors: int,
) -> tuple[str, str, str, str]:
    """
    Produce exploratory 2D quality flags.
    NOTE: These are diagnostic flags; the final production QC rule remains NOT YET FINALIZED.
    """
    # 1. Temporal Support Class
    if obs <= 1.0:
        temporal_class = "low"
    elif obs <= 3.0:
        temporal_class = "moderate"
    else:
        temporal_class = "high"

    # 2. QA Uncertainty Class
    if qa is None:
        qa_class = "unavailable"
    elif qa < 3.0:
        qa_class = "low_uncertainty"
    elif qa <= 5.0:
        qa_class = "moderate_uncertainty"
    else:
        qa_class = "high_uncertainty"

    # 3. Spatial Quality Flag
    flags = []
    if obs <= 1.0:
        flags.append("single_observation_extreme")
    if qa is not None and qa > 5.0:
        flags.append("high_qa_uncertainty")
    if valid_neighbors < 5:
        flags.append("boundary_edge")
    if abs_diff_med is not None:
        if abs_diff_med > 8.0:
            flags.append("isolated_anomaly")
        elif abs_diff_med <= 3.0:
            flags.append("spatially_coherent")

    quality_flag = ";".join(flags) if flags else "standard"

    # 4. Exploratory Eligibility Assessment
    if obs <= 1.0 or (qa is not None and qa > 10.0) or (abs_diff_med is not None and abs_diff_med > 12.0):
        eligibility = "EXPLORATORY_FLAGGED"
    elif obs >= 2.0 and (qa is None or qa <= 5.0):
        eligibility = "EXPLORATORY_ELIGIBLE"
    else:
        eligibility = "EXPLORATORY_NEEDS_REVIEW"

    return temporal_class, qa_class, quality_flag, eligibility


# ---------------------------------------------------------------------------
# Single Season Analysis
# ---------------------------------------------------------------------------

def analyze_season_extremes(
    year: int,
    season: str,
    top_pct: float,
    bottom_pct: float,
    top_n: int,
    bottom_n: int,
    boundary_geom: list[Any],
    boundary_ee: Any,
    skip_gee: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]] | None:
    cog_path = SEASONAL_COG_ROOT / str(year) / season / f"surat_{year}_{season}_features_cog.tif"
    if not cog_path.exists():
        print(f"Skipping {year} {season}: Raster not found at {cog_path}")
        return None

    print(f"\nProcessing {year} {season.upper()} ({cog_path.name})...")

    with rasterio.open(cog_path) as src:
        out_image, out_transform = rasterio.mask.mask(src, boundary_geom, crop=False)
        profile = src.profile

    # Bands:
    # 0: LST_C, 1: NDVI, 2: NDBI, 3: NDWI
    # 4: LST_OBS_COUNT, 5: NDVI_OBS_COUNT, 6: NDBI_OBS_COUNT, 7: NDWI_OBS_COUNT
    lst_band = out_image[0]
    valid_mask = (lst_band != -9999.0) & np.isfinite(lst_band)
    valid_pixel_count = int(np.sum(valid_mask))

    if valid_pixel_count == 0:
        print(f"  [Warning] No valid pixels inside SMC boundary for {year} {season}.")
        return None

    valid_lst = lst_band[valid_mask]
    obs_band = out_image[4]
    valid_obs = obs_band[valid_mask]

    # Calculate percentiles
    p_low = float(np.percentile(valid_lst, bottom_pct))
    p_high = float(np.percentile(valid_lst, 100.0 - top_pct))
    p05 = float(np.percentile(valid_lst, 5.0))
    p50 = float(np.median(valid_lst))
    p95 = float(np.percentile(valid_lst, 95.0))
    p99 = float(np.percentile(valid_lst, 99.0))
    lst_min = float(np.min(valid_lst))
    lst_max = float(np.max(valid_lst))

    print(f"  Valid pixels: {valid_pixel_count} | LST: min={lst_min:.2f}°C, p01={p_low:.2f}°C, p50={p50:.2f}°C, p99={p_high:.2f}°C, max={lst_max:.2f}°C")

    # Indices of valid pixels
    valid_rows, valid_cols = np.where(valid_mask)

    # Sort indices by LST ascending (cold to hot)
    sort_indices = np.argsort(lst_band[valid_rows, valid_cols])
    sorted_rows = valid_rows[sort_indices]
    sorted_cols = valid_cols[sort_indices]

    # 1. Bottom N coldest
    actual_bottom_n = min(bottom_n, valid_pixel_count)
    bottom_n_set = {(sorted_rows[i], sorted_cols[i]): i + 1 for i in range(actual_bottom_n)}

    # 2. Top N hottest
    actual_top_n = min(top_n, valid_pixel_count)
    top_n_set = {(sorted_rows[-1 - i], sorted_cols[-1 - i]): i + 1 for i in range(actual_top_n)}

    # 3. Bottom Percentile (cold <= p_low)
    cold_pct_set = set(zip(valid_rows[valid_lst <= p_low], valid_cols[valid_lst <= p_low]))

    # 4. Top Percentile (hot >= p_high)
    hot_pct_set = set(zip(valid_rows[valid_lst >= p_high], valid_cols[valid_lst >= p_high]))

    all_extreme_pixels = set(bottom_n_set.keys()) | set(top_n_set.keys()) | cold_pct_set | hot_pct_set
    print(f"  Extracted unique extreme pixels: {len(all_extreme_pixels)} (Top {top_n}, Bottom {bottom_n}, Top {top_pct}%, Bottom {bottom_pct}%)")

    # Coordinate mapping and unique point coordinates
    pixel_coords: dict[tuple[int, int], tuple[float, float]] = {}
    unique_coords_list: list[tuple[float, float]] = []

    for r, c in all_extreme_pixels:
        lon, lat = rasterio.transform.xy(out_transform, r, c)
        lon_r, lat_r = round(float(lon), 6), round(float(lat), 6)
        pixel_coords[(r, c)] = (lon_r, lat_r)
        unique_coords_list.append((lon_r, lat_r))

    # Sample GEE QA if requested and available
    qa_map: dict[tuple[float, float], float | None] = {}
    if not skip_gee and EE_AVAILABLE and boundary_ee is not None:
        print("  Sampling GEE ST_QA uncertainty for extreme coordinates...")
        qa_map = sample_gee_qa_batch(unique_coords_list, year, season, boundary_ee)

    # Build pixel records
    records: list[dict[str, Any]] = []
    for r, c in all_extreme_pixels:
        lon, lat = pixel_coords[(r, c)]
        val_lst = float(lst_band[r, c])
        val_obs = float(out_image[4, r, c])
        qa_k = qa_map.get((lon, lat))

        # Extreme Type classification
        types = []
        if (r, c) in top_n_set:
            types.append(f"hot_top_{top_n}")
        if (r, c) in hot_pct_set:
            types.append(f"hot_top_{top_pct:g}pct")
        if (r, c) in bottom_n_set:
            types.append(f"cold_bottom_{bottom_n}")
        if (r, c) in cold_pct_set:
            types.append(f"cold_bottom_{bottom_pct:g}pct")

        extreme_type = ",".join(types)

        # 3x3 Neighborhood context
        neigh = compute_neighborhood_stats(lst_band, r, c)

        # 2D Diagnostic classifications
        t_class, qa_c, q_flag, elig = classify_extreme_pixel(
            obs=val_obs,
            qa=qa_k,
            abs_diff_med=neigh["absolute_pixel_minus_neighborhood_median"],
            valid_neighbors=neigh["valid_neighbor_count"],
        )

        rec = {
            "year": year,
            "season": season,
            "extreme_type": extreme_type,
            "rank_hot": top_n_set.get((r, c)),
            "rank_cold": bottom_n_set.get((r, c)),
            "longitude": lon,
            "latitude": lat,
            "row": int(r),
            "col": int(c),
            "lst_c": round(val_lst, 4),
            "obs_count": round(val_obs, 1),
            "qa_k": qa_k,
            "ndvi": round(float(out_image[1, r, c]), 4) if out_image[1, r, c] != -9999.0 else None,
            "ndbi": round(float(out_image[2, r, c]), 4) if out_image[2, r, c] != -9999.0 else None,
            "ndwi": round(float(out_image[3, r, c]), 4) if out_image[3, r, c] != -9999.0 else None,
            "ndvi_obs_count": round(float(out_image[5, r, c]), 1) if out_image[5, r, c] != -9999.0 else None,
            "ndbi_obs_count": round(float(out_image[6, r, c]), 1) if out_image[6, r, c] != -9999.0 else None,
            "ndwi_obs_count": round(float(out_image[7, r, c]), 1) if out_image[7, r, c] != -9999.0 else None,
            "neighborhood_median": neigh["neighborhood_median"],
            "neighborhood_mean": neigh["neighborhood_mean"],
            "neighborhood_std": neigh["neighborhood_std"],
            "valid_neighbor_count": neigh["valid_neighbor_count"],
            "pixel_minus_neighborhood_median": neigh["pixel_minus_neighborhood_median"],
            "absolute_pixel_minus_neighborhood_median": neigh["absolute_pixel_minus_neighborhood_median"],
            "temporal_support_class": t_class,
            "qa_class": qa_c,
            "quality_flag": q_flag,
            "eligibility": elig,
        }
        records.append(rec)

    # -----------------------------------------------------------------------
    # Seasonal Quality Summary
    # -----------------------------------------------------------------------
    hot_records = [r for r in records if "hot" in r["extreme_type"]]
    cold_records = [r for r in records if "cold" in r["extreme_type"]]

    hot_obs_p50 = float(np.median([r["obs_count"] for r in hot_records])) if hot_records else None
    cold_obs_p50 = float(np.median([r["obs_count"] for r in cold_records])) if cold_records else None

    hot_qa_vals = [r["qa_k"] for r in hot_records if r["qa_k"] is not None]
    cold_qa_vals = [r["qa_k"] for r in cold_records if r["qa_k"] is not None]

    hot_qa_p50 = float(np.median(hot_qa_vals)) if hot_qa_vals else None
    cold_qa_p50 = float(np.median(cold_qa_vals)) if cold_qa_vals else None

    # Estimate scene count from max obs_count in raster
    est_scene_count = int(np.max(valid_obs))

    seasonal_summary = {
        "year": year,
        "season": season,
        "scene_count": est_scene_count,
        "valid_pixels": valid_pixel_count,
        "obs_count_mean": round(float(np.mean(valid_obs)), 2),
        "obs_count_p50": round(float(np.median(valid_obs)), 1),
        "obs_count_p95": round(float(np.percentile(valid_obs, 95)), 1),
        "lst_p01": round(p_low, 2),
        "lst_p05": round(p05, 2),
        "lst_p50": round(p50, 2),
        "lst_p95": round(p95, 2),
        "lst_p99": round(p_high, 2),
        "lst_min": round(lst_min, 2),
        "lst_max": round(lst_max, 2),
        "qa_p50": hot_qa_p50,  # Representative seasonal indicator
        "qa_p95": float(np.percentile(hot_qa_vals, 95)) if hot_qa_vals else None,
        "qa_max": float(np.max(hot_qa_vals)) if hot_qa_vals else None,
        "hot_extreme_obs_p50": round(hot_obs_p50, 1) if hot_obs_p50 is not None else None,
        "hot_extreme_qa_p50": round(hot_qa_p50, 2) if hot_qa_p50 is not None else None,
        "cold_extreme_obs_p50": round(cold_obs_p50, 1) if cold_obs_p50 is not None else None,
        "cold_extreme_qa_p50": round(cold_qa_p50, 2) if cold_qa_p50 is not None else None,
    }

    # -----------------------------------------------------------------------
    # Observation Support Sensitivity (Thresholds 1, 2, 3)
    # -----------------------------------------------------------------------
    sensitivity_records: list[dict[str, Any]] = []
    hot_top1_mask = valid_lst >= p_high
    cold_bot1_mask = valid_lst <= p_low
    total_hot1 = int(np.sum(hot_top1_mask))
    total_cold1 = int(np.sum(cold_bot1_mask))

    for t in (1, 2, 3):
        retained = valid_obs >= t
        ret_cnt = int(np.sum(retained))
        ret_pct = round((ret_cnt / valid_pixel_count) * 100.0, 4) if valid_pixel_count > 0 else 0.0

        if ret_cnt > 0:
            ret_lst = valid_lst[retained]
            t_min = round(float(np.min(ret_lst)), 2)
            t_p95 = round(float(np.percentile(ret_lst, 95)), 2)
            t_p99 = round(float(np.percentile(ret_lst, 99)), 2)
            t_max = round(float(np.max(ret_lst)), 2)
        else:
            t_min = t_p95 = t_p99 = t_max = None

        hot_ret = round(float(np.sum(valid_obs[hot_top1_mask] >= t) / total_hot1 * 100.0), 2) if total_hot1 > 0 else 0.0
        cold_ret = round(float(np.sum(valid_obs[cold_bot1_mask] >= t) / total_cold1 * 100.0), 2) if total_cold1 > 0 else 0.0
        spatial_cov = round((ret_cnt / TOTAL_SMC_GRID_CELLS) * 100.0, 2)

        sens_rec = {
            "year": year,
            "season": season,
            "threshold": t,
            "valid_pixel_count": valid_pixel_count,
            "retained_pixel_count": ret_cnt,
            "retention_percent": ret_pct,
            "LST_min": t_min,
            "LST_p95": t_p95,
            "LST_p99": t_p99,
            "LST_max": t_max,
            "hotspot_retention": hot_ret,
            "cold_extreme_retention": cold_ret,
            "spatial_coverage": spatial_cov,
        }
        sensitivity_records.append(sens_rec)

    return records, seasonal_summary, sensitivity_records


# ---------------------------------------------------------------------------
# Output Exporters
# ---------------------------------------------------------------------------

def export_season_geojson(
    records: list[dict[str, Any]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features = []
    for r in records:
        geom = {
            "type": "Point",
            "coordinates": [r["longitude"], r["latitude"]],
        }
        # Copy properties, excluding internal row/col if desired or keep
        props = {k: v for k, v in r.items() if k not in ("longitude", "latitude")}
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props,
        })

    geojson_doc = {
        "type": "FeatureCollection",
        "name": output_path.stem,
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": features,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson_doc, f, indent=2)

    print(f"  -> Saved GeoJSON: {output_path} ({len(features)} features)")


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    # Determine execution scope
    years = [args.year] if args.year else list(range(START_YEAR, END_YEAR + 1))
    seasons = [args.season] if args.season else list(SEASONS)

    output_base: Path = args.output
    extremes_dir = output_base / "lst_extremes"
    quality_dir = output_base / "quality"

    extremes_dir.mkdir(parents=True, exist_ok=True)
    quality_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("HEATSENSE AI — LANDSAT LST EXTREME-VALUE SPATIAL INVESTIGATION")
    print("=" * 80)
    print(f"Target Scope       : Years={years}, Seasons={seasons}")
    print(f"Extreme Cutoffs    : Top {args.top_percentile}%, Bottom {args.bottom_percentile}% | Top {args.top_n}, Bottom {args.bottom_n}")
    print(f"Output Directory   : {output_base}")
    print(f"GEE Sampling       : {'DISABLED' if args.skip_gee else 'ENABLED'}")

    # Load Boundary
    if not BOUNDARY_PATH.exists():
        raise FileNotFoundError(f"Surat SMC boundary not found at {BOUNDARY_PATH}")

    gdf_boundary = gpd.read_file(BOUNDARY_PATH).to_crs("EPSG:4326")
    boundary_geom = [gdf_boundary.geometry.union_all()]

    boundary_ee = None
    if not args.skip_gee and EE_AVAILABLE:
        try:
            print("\nInitializing Earth Engine...")
            initialize_earth_engine()
            boundary_ee = load_surat_boundary()
            print("Earth Engine initialized successfully.")
        except Exception as e:
            print(f"[Warning] Earth Engine initialization failed: {e}. Running without GEE QA sampling.")

    all_pixel_records: list[dict[str, Any]] = []
    all_seasonal_summaries: list[dict[str, Any]] = []
    all_sensitivity_records: list[dict[str, Any]] = []

    t_start = time.time()
    seasons_analyzed = 0

    for y in years:
        for s in seasons:
            res = analyze_season_extremes(
                year=y,
                season=s,
                top_pct=args.top_percentile,
                bottom_pct=args.bottom_percentile,
                top_n=args.top_n,
                bottom_n=args.bottom_n,
                boundary_geom=boundary_geom,
                boundary_ee=boundary_ee,
                skip_gee=args.skip_gee,
            )
            if res is None:
                continue

            records, summary, sens_rows = res
            seasons_analyzed += 1

            # Export seasonal GeoJSON
            geojson_file = extremes_dir / f"{y}_{s}_extremes.geojson"
            export_season_geojson(records, geojson_file)

            all_pixel_records.extend(records)
            all_seasonal_summaries.append(summary)
            all_sensitivity_records.extend(sens_rows)

    elapsed = time.time() - t_start

    print("\n" + "=" * 80)
    print(f"EXTREME ANALYSIS COMPLETE: {seasons_analyzed} seasons analyzed in {elapsed:.2f} seconds.")
    print("=" * 80)

    # -----------------------------------------------------------------------
    # Write Quality CSVs
    # -----------------------------------------------------------------------
    if all_seasonal_summaries:
        summary_csv = quality_dir / "seasonal_quality_summary.csv"
        with open(summary_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_seasonal_summaries[0].keys()))
            writer.writeheader()
            writer.writerows(all_seasonal_summaries)
        print(f"Saved seasonal quality summary: {summary_csv}")

    if all_pixel_records:
        pixel_csv = quality_dir / "extreme_pixel_quality.csv"
        with open(pixel_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_pixel_records[0].keys()))
            writer.writeheader()
            writer.writerows(all_pixel_records)
        print(f"Saved extreme pixel quality: {pixel_csv} ({len(all_pixel_records)} records)")

    if all_sensitivity_records:
        sens_csv = quality_dir / "observation_support_sensitivity.csv"
        with open(sens_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_sensitivity_records[0].keys()))
            writer.writeheader()
            writer.writerows(all_sensitivity_records)
        print(f"Saved observation sensitivity: {sens_csv}")


if __name__ == "__main__":
    main()