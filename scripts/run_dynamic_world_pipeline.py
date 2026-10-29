"""CLI tool to execute Dynamic World seasonal extraction and aggregation.

Usage:
    python scripts/run_dynamic_world_pipeline.py --season summer --year 2024 --max-cells 500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from gis.gee.dynamic_world_pipeline import run_dynamic_world_seasonal_extraction


def main():
    parser = argparse.ArgumentParser(description="Run Dynamic World seasonal extraction on Surat grid cells.")
    parser.add_argument("--season", default="summer", choices=["summer", "winter", "monsoon", "post_monsoon"], help="Target season")
    parser.add_argument("--year", type=int, default=2024, help="Target calendar year (default: 2024)")
    parser.add_argument("--batch-size", type=int, default=100, help="Grid cells per GEE reduceRegions batch (default: 100)")
    parser.add_argument("--max-cells", type=int, default=None, help="Maximum number of cells to process (default: all)")
    parser.add_argument("--min-obs", type=int, default=3, help="Minimum valid observation threshold (default: 3)")
    parser.add_argument("--area", default=None, help="Optional OSM place/locality filter (e.g. Udhana, Dindoli)")
    parser.add_argument("--min-hpi", type=float, default=None, help="Optional minimum HPI filter (e.g. 50.0)")
    parser.add_argument("--fixture", action="store_true", help="Generate synthetic offline fixtures instead of querying GEE")

    args = parser.parse_args()

    print(f"=== Starting Dynamic World Extraction: Season={args.season.upper()}, Year={args.year} ===")
    print(f"Batch size: {args.batch_size} | Max cells: {args.max_cells or 'ALL'} | Min obs: {args.min_obs} | Area: {args.area or 'ALL'} | Fixture: {args.fixture}")

    res = run_dynamic_world_seasonal_extraction(
        season=args.season,
        year=args.year,
        batch_size=args.batch_size,
        max_cells=args.max_cells,
        area_name=args.area,
        min_hpi=args.min_hpi,
        min_observations_threshold=args.min_obs,
        use_fixtures=args.fixture,
    )

    print("\n=== Extraction Run Complete ===")
    for k, v in res.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
