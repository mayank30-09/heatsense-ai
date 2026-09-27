"""Generate Production Analytical COGs for All Seasonal Composites.

Consumes the frozen Policy D analytical dataset and reference seasonal rasters to produce
standardized 10-band Cloud-Optimized GeoTIFFs under data/processed/analytical/.

Outputs:
    data/processed/analytical/surat_{year}_{season}_analytical_cog.tif
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import rasterio

from gis.production.analytical_cog import (
    ANALYTICAL_BAND_NAMES,
    build_analytical_array,
    write_analytical_cog,
)

DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
SEASONAL_ROOT = PROJECT_ROOT / "data" / "processed" / "seasonal"
ANALYTICAL_OUTPUT_ROOT = PROJECT_ROOT / "data" / "processed" / "analytical"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 10-band production analytical COGs.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--seasonal-dir", type=Path, default=SEASONAL_ROOT)
    parser.add_argument("--output-dir", type=Path, default=ANALYTICAL_OUTPUT_ROOT)
    args = parser.parse_args()

    print("=" * 80)
    print("HEATSENSE AI: PRODUCTION ANALYTICAL COG GENERATION (10-BAND)")
    print("=" * 80)
    print(f"Dataset path : {args.dataset}")
    print(f"Output dir   : {args.output_dir}")

    if not args.dataset.exists():
        raise FileNotFoundError(f"Authoritative dataset not found at {args.dataset}")

    print("\n1. Loading Policy D frozen dataset...")
    df = pd.read_parquet(args.dataset)
    print(f"   Loaded {len(df):,} records.")

    seasons_present = df[["year", "season"]].drop_duplicates().sort_values(["year", "season"])
    print(f"   Found {len(seasons_present)} distinct seasonal periods.")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    generated_cogs = []
    t0 = time.time()

    for _, row in seasons_present.iterrows():
        year = int(row["year"])
        season = str(row["season"]).lower()

        # Find reference seasonal raster
        ref_candidates = list(args.seasonal_dir.glob(f"{year}/{season}/*_features_cog.tif"))
        if not ref_candidates:
            # Fallback to any matching pattern
            ref_candidates = list(args.seasonal_dir.glob(f"*{year}*{season}*_features_cog.tif"))

        if not ref_candidates:
            print(f"  [WARNING] Reference raster not found for {year} {season}. Skipping.")
            continue

        ref_raster = ref_candidates[0]
        out_name = f"surat_{year}_{season}_analytical_cog.tif"
        out_path = args.output_dir / out_name

        print(f"\nProcessing {year} {season.upper()} -> {out_name}...")
        with rasterio.open(ref_raster) as ref_src:
            height, width = ref_src.shape

        sub_df = df[(df["year"] == year) & (df["season"].str.lower() == season)]
        print(f"   Extracted {len(sub_df):,} pixel records. Raster size: {width} x {height}")

        # Build 10-band array
        data_10b = build_analytical_array(sub_df, height=height, width=width)

        # Write COG
        write_analytical_cog(out_path, data_10b, reference_raster_path=ref_raster)
        print(f"   Wrote 10-band COG: {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")
        generated_cogs.append(out_path)

    elapsed = time.time() - t0
    print("\n" + "=" * 80)
    print(f"GENERATION COMPLETE: {len(generated_cogs)} analytical COGs created in {elapsed:.1f}s.")
    print("=" * 80)


if __name__ == "__main__":
    main()
