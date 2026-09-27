"""Authoritative Production Analytical Cloud-Optimized GeoTIFF (COG) Generator.

Builds 10-band analytical COG raster products under data/processed/analytical/
from the frozen Policy D analytical dataset, referencing the validated seasonal grid.

Bands:
1.  LST_C (Land Surface Temperature in Celsius, ~100m analytical scale)
2.  NDVI (Normalized Difference Vegetation Index)
3.  NDBI (Normalized Difference Built-Up Index)
4.  NDWI (Normalized Difference Water Index)
5.  LST_OBS_COUNT (Clear-sky scene count / temporal support)
6.  LST_QA_MEDIAN_K (Radiometric uncertainty / atmospheric context in Kelvin)
7.  QUALITY_FLAG (Numerically encoded quality diagnostic flags)
8.  ELIGIBILITY (Numerically encoded Policy D eligibility: 1=ACCEPT, 2=FLAG, 0=EXCLUDE)
9.  HOTSPOT_FREQUENCY (Normalized multi-season recurrence frequency in [0, 1])
10. IS_PERSISTENT_HOTSPOT (Binary persistence indicator: 1.0=True, 0.0=False)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling

# Canonical Analytical Band Names
ANALYTICAL_BAND_NAMES: list[str] = [
    "LST_C",
    "NDVI",
    "NDBI",
    "NDWI",
    "LST_OBS_COUNT",
    "LST_QA_MEDIAN_K",
    "QUALITY_FLAG",
    "ELIGIBILITY",
    "HOTSPOT_FREQUENCY",
    "IS_PERSISTENT_HOTSPOT",
]

NODATA_VALUE: float = -9999.0

# Numerical Encodings
ELIGIBILITY_ENCODING: dict[str, float] = {
    "EXCLUDE": 0.0,
    "ACCEPT": 1.0,
    "FLAG": 2.0,
}

QUALITY_FLAG_ENCODING: dict[str, float] = {
    "SPATIALLY_COHERENT": 1.0,
    "LOW_TEMPORAL_SUPPORT;SPATIALLY_COHERENT": 2.0,
    "BOUNDARY_CONTEXT": 3.0,
    "LOW_TEMPORAL_SUPPORT;BOUNDARY_CONTEXT": 4.0,
    "SPATIAL_ANOMALY": 5.0,
    "SPATIALLY_COHERENT;BOUNDARY_CONTEXT": 6.0,
    "LOW_TEMPORAL_SUPPORT;SPATIALLY_COHERENT;BOUNDARY_CONTEXT": 7.0,
}


def encode_eligibility(series: pd.Series) -> pd.Series:
    """Encode string eligibility states into float indicators."""
    return series.map(ELIGIBILITY_ENCODING).fillna(0.0)


def encode_quality_flag(series: pd.Series) -> pd.Series:
    """Encode string quality flags into float category codes."""
    return series.map(QUALITY_FLAG_ENCODING).fillna(0.0)


def build_analytical_array(
    df_season: pd.DataFrame,
    height: int = 324,
    width: int = 318,
    nodata: float = NODATA_VALUE,
) -> np.ndarray:
    """
    Construct a (10, height, width) float32 raster array for a given season.

    Parameters
    ----------
    df_season : pd.DataFrame
        Filtered rows for a specific year and season from analysis.parquet.
    height : int
        Raster row count (default 324).
    width : int
        Raster col count (default 318).
    nodata : float
        NoData fill value.

    Returns
    -------
    np.ndarray of shape (10, height, width), dtype float32.
    """
    n_bands = len(ANALYTICAL_BAND_NAMES)
    arr = np.full((n_bands, height, width), nodata, dtype=np.float32)

    rows = df_season["row"].to_numpy().astype(int)
    cols = df_season["col"].to_numpy().astype(int)

    # Valid bounds check
    valid_locs = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    rows = rows[valid_locs]
    cols = cols[valid_locs]
    df_valid = df_season.iloc[valid_locs]

    # Band 1: LST_C
    arr[0, rows, cols] = df_valid["LST_C"].to_numpy(dtype=np.float32)

    # Band 2: NDVI
    arr[1, rows, cols] = df_valid["NDVI"].to_numpy(dtype=np.float32)

    # Band 3: NDBI
    arr[2, rows, cols] = df_valid["NDBI"].to_numpy(dtype=np.float32)

    # Band 4: NDWI
    arr[3, rows, cols] = df_valid["NDWI"].to_numpy(dtype=np.float32)

    # Band 5: LST_OBS_COUNT
    arr[4, rows, cols] = df_valid["LST_OBS_COUNT"].to_numpy(dtype=np.float32)

    # Band 6: LST_QA_MEDIAN_K
    arr[5, rows, cols] = df_valid["LST_QA_MEDIAN_K"].to_numpy(dtype=np.float32)

    # Band 7: QUALITY_FLAG
    arr[6, rows, cols] = encode_quality_flag(df_valid["quality_flag"]).to_numpy(dtype=np.float32)

    # Band 8: ELIGIBILITY
    arr[7, rows, cols] = encode_eligibility(df_valid["eligibility"]).to_numpy(dtype=np.float32)

    # Band 9: HOTSPOT_FREQUENCY
    arr[8, rows, cols] = df_valid["hotspot_frequency"].to_numpy(dtype=np.float32)

    # Band 10: IS_PERSISTENT_HOTSPOT
    arr[9, rows, cols] = (df_valid["is_persistent_hotspot"] == True).to_numpy(dtype=np.float32)

    return arr


def write_analytical_cog(
    output_path: Path,
    data: np.ndarray,
    reference_raster_path: Path,
    band_names: list[str] = ANALYTICAL_BAND_NAMES,
) -> Path:
    """
    Write a 10-band array to Cloud-Optimized GeoTIFF format with spatial metadata
    cloned from reference_raster_path.

    Parameters
    ----------
    output_path : Path
        Target GeoTIFF path.
    data : np.ndarray
        Array of shape (bands, height, width).
    reference_raster_path : Path
        Source seasonal raster from which CRS and affine transform are derived.
    band_names : list[str]
        Band descriptions.

    Returns
    -------
    Path to written COG.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(reference_raster_path) as ref:
        profile = ref.profile.copy()
        profile.update(
            driver="GTiff",
            dtype="float32",
            nodata=NODATA_VALUE,
            count=data.shape[0],
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress="deflate",
        )

        with rasterio.open(output_path, "w", **profile) as dst:
            for b_idx in range(data.shape[0]):
                band_num = b_idx + 1
                dst.write(data[b_idx], band_num)
                if b_idx < len(band_names):
                    dst.set_band_description(band_num, band_names[b_idx])

            # Build overviews for COG compliance
            dst.build_overviews([2, 4, 8, 16], Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")

    return output_path
