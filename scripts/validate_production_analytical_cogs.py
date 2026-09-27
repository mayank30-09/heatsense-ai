"""Validation Suite for Production Analytical Cloud-Optimized GeoTIFFs (COGs).

Validates all 19 production analytical COGs under data/processed/analytical/:
- CRS (EPSG:4326)
- Dimensions (324 x 318)
- Ground resolution (~0.0009 degrees / ~100m analytical scale)
- Data type (float32)
- NoData value (-9999.0)
- Band count (exactly 10 bands)
- Band descriptions (LST_C, NDVI, NDBI, NDWI, LST_OBS_COUNT, LST_QA_MEDIAN_K, QUALITY_FLAG, ELIGIBILITY, HOTSPOT_FREQUENCY, IS_PERSISTENT_HOTSPOT)
- COG properties (tiling block size 256x256, deflate compression, overviews present)
- Finite value checks (no NaNs or infinities outside NoData)
- Numerical encoding bounds for quality and eligibility
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import rasterio

from gis.production.analytical_cog import ANALYTICAL_BAND_NAMES, NODATA_VALUE

DEFAULT_ANALYTICAL_DIR = PROJECT_ROOT / "data" / "processed" / "analytical"


def validate_cog_file(cog_path: Path) -> dict[str, Any]:
    errors = []
    warnings = []

    with rasterio.open(cog_path) as src:
        # 1. CRS
        crs_str = str(src.crs)
        if not ("4326" in crs_str or "WGS 84" in crs_str or "WGS_1984" in crs_str):
            errors.append(f"CRS mismatch: expected EPSG:4326 / WGS 84, found {src.crs}")

        # 2. Dimensions
        if src.height != 324 or src.width != 318:
            errors.append(f"Dimensions mismatch: expected 324x318, found {src.height}x{src.width}")

        # 3. Band Count
        if src.count != 10:
            errors.append(f"Band count mismatch: expected 10, found {src.count}")

        # 4. Band Descriptions
        actual_desc = list(src.descriptions)
        if actual_desc != ANALYTICAL_BAND_NAMES:
            errors.append(f"Band descriptions mismatch: expected {ANALYTICAL_BAND_NAMES}, found {actual_desc}")

        # 5. Dtype and NoData
        for i, dt in enumerate(src.dtypes, 1):
            if dt != "float32":
                errors.append(f"Band {i} dtype mismatch: expected float32, found {dt}")
        if src.nodata != NODATA_VALUE:
            errors.append(f"NoData mismatch: expected {NODATA_VALUE}, found {src.nodata}")

        # 6. Tiling and Compression
        if not src.is_tiled:
            errors.append("Raster is not tiled (COG violation)")
        if src.profile.get("compress") != "deflate":
            warnings.append(f"Compression is {src.profile.get('compress')} instead of deflate")

        # 7. Overviews
        for b in range(1, src.count + 1):
            ovr = src.overviews(b)
            if not ovr:
                errors.append(f"Band {b} is missing pyramid overviews (COG violation)")

        # 8. Data integrity, finite values, and value ranges
        for b_idx, name in enumerate(ANALYTICAL_BAND_NAMES, start=1):
            arr = src.read(b_idx)

            # Check for non-finite values (NaN / Inf)
            nan_count = np.isnan(arr).sum()
            inf_count = np.isinf(arr).sum()
            if nan_count > 0 or inf_count > 0:
                errors.append(f"Band {b_idx} ({name}) contains non-finite values: {nan_count} NaNs, {inf_count} Infs")

            valid_mask = arr != NODATA_VALUE
            valid_vals = arr[valid_mask]

            if len(valid_vals) == 0:
                errors.append(f"Band {b_idx} ({name}) has 0 valid pixels")
                continue

            vmin = float(valid_vals.min())
            vmax = float(valid_vals.max())

            # Specific range checks
            if name == "LST_C":
                if vmin < 0.0 or vmax > 70.0:
                    warnings.append(f"LST_C range warning: [{vmin:.2f}, {vmax:.2f}] degC")
            elif name in ["NDVI", "NDBI", "NDWI"]:
                if vmin < -1.1 or vmax > 1.1:
                    warnings.append(f"{name} range warning: [{vmin:.2f}, {vmax:.2f}]")
            elif name == "ELIGIBILITY":
                unique_elig = np.unique(valid_vals)
                if not set(unique_elig).issubset({0.0, 1.0, 2.0}):
                    errors.append(f"ELIGIBILITY encoding error: unexpected values {unique_elig}")
            elif name == "HOTSPOT_FREQUENCY":
                if vmin < 0.0 or vmax > 1.0:
                    errors.append(f"HOTSPOT_FREQUENCY out of bounds: [{vmin:.4f}, {vmax:.4f}]")
            elif name == "IS_PERSISTENT_HOTSPOT":
                unique_pers = np.unique(valid_vals)
                if not set(unique_pers).issubset({0.0, 1.0}):
                    errors.append(f"IS_PERSISTENT_HOTSPOT encoding error: unexpected values {unique_pers}")

    return {
        "path": cog_path,
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Production Analytical COGs.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_ANALYTICAL_DIR)
    args = parser.parse_args()

    print("=" * 80)
    print("HEATSENSE AI: PRODUCTION ANALYTICAL COG VALIDATION SUITE")
    print("=" * 80)
    print(f"Target directory: {args.dir}")

    cogs = sorted(args.dir.glob("*_analytical_cog.tif"))
    if not cogs:
        print(f"ERROR: No analytical COGs found in {args.dir}")
        sys.exit(1)

    print(f"Found {len(cogs)} analytical COGs to validate.\n")

    all_passed = True
    for cog in cogs:
        res = validate_cog_file(cog)
        status_str = "[PASS]" if res["valid"] else "[FAIL]"
        print(f"{status_str} {cog.name}")
        for err in res["errors"]:
            print(f"    - ERROR: {err}")
            all_passed = False
        for warn in res["warnings"]:
            print(f"    - WARNING: {warn}")

    print("\n" + "=" * 80)
    if all_passed:
        print(f"ALL {len(cogs)} PRODUCTION ANALYTICAL COGS VALIDATED SUCCESSFULLY!")
    else:
        print("VALIDATION FAILED WITH ERRORS")
        sys.exit(1)
    print("=" * 80)


if __name__ == "__main__":
    main()
