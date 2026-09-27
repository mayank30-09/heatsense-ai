from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import rasterio


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from gis.gee.seasonal_features import (
    ALL_OUTPUT_BANDS,
    create_seasonal_composite,
    build_landsat_collection,
    get_season_windows,
)


PROJECT_ID = "gen-lang-client-0607312119"

BOUNDARY_PATH = Path(
    "data/raw/boundaries/surat_smc_boundary.geojson"
)

OUTPUT_ROOT = Path(
    "data/processed/seasonal"
)

TEMP_ROOT = OUTPUT_ROOT / "tmp"

ANALYSIS_START_YEAR = 2022
ANALYSIS_END_YEAR = 2026

EXPORT_SCALE_METERS = 100

OUTPUT_CRS = "EPSG:4326"


OUTPUT_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

TEMP_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


def initialize_gee() -> None:
    ee.Initialize(
        project=PROJECT_ID
    )


def load_boundary() -> ee.Geometry:
    gdf = gpd.read_file(
        BOUNDARY_PATH
    )

    if gdf.empty:
        raise RuntimeError(
            "Study-area boundary is empty."
        )

    if gdf.crs is None:
        raise RuntimeError(
            "Study-area boundary has no CRS."
        )

    gdf = gdf.to_crs(
        "EPSG:4326"
    )

    geometry = gdf.geometry.union_all()

    if geometry.is_empty:
        raise RuntimeError(
            "Study-area geometry is empty."
        )

    if not geometry.is_valid:
        geometry = geometry.buffer(0)

    geojson_geometry = json.loads(
        gpd.GeoSeries(
            [geometry],
            crs="EPSG:4326",
        ).to_json()
    )["features"][0]["geometry"]

    return ee.Geometry(
        geojson_geometry
    )


def export_geotiff(
    image: ee.Image,
    aoi: ee.Geometry,
    output_path: Path,
) -> None:

    print(
        f"Preparing Earth Engine download: {output_path}"
    )

    url = image.getDownloadURL(
        {
            "name": output_path.stem,
            "region": aoi,
            "scale": EXPORT_SCALE_METERS,
            "crs": OUTPUT_CRS,
            "filePerBand": False,
            "format": "GEO_TIFF",
        }
    )

    print("Download URL generated.")
    print("Downloading GeoTIFF...")

    urllib.request.urlretrieve(
        url,
        output_path,
    )

    print(
        f"Downloaded: {output_path}"
    )

def convert_to_cog(
    source_path: Path,
    cog_path: Path,
) -> None:

    print(
        f"Converting to COG: {cog_path}"
    )

    with rasterio.open(
        source_path
    ) as src:

        data = src.read().astype(
            "float32"
        )

        profile = src.profile.copy()

        profile.update(
            driver="GTiff",
            dtype="float32",
            count=data.shape[0],
            nodata=-9999.0,
            compress="DEFLATE",
            tiled=True,
            blockxsize=256,
            blockysize=256,
            BIGTIFF="IF_SAFER",
        )

        with rasterio.open(
            cog_path,
            "w",
            **profile,
        ) as dst:

            for band_index in range(
                data.shape[0]
            ):

                band_number = (
                    band_index + 1
                )

                band_data = data[
                    band_index
                ].copy()

                # Convert NaN and infinity
                # to project NoData.
                invalid = ~np.isfinite(
                    band_data
                )

                band_data[
                    invalid
                ] = -9999.0

                dst.write(
                    band_data,
                    band_number,
                )

                dst.set_band_description(
                    band_number,
                    ALL_OUTPUT_BANDS[
                        band_index
                    ],
                )

            dst.build_overviews(
                [2, 4, 8, 16],
                rasterio.enums.Resampling.average,
            )

            dst.update_tags(
                ns="rio_overview",
                resampling="average",
            )

    print(
        f"COG created: {cog_path}"
    )


def validate_cog(
    cog_path: Path,
) -> None:

    print(
        f"\nValidating: {cog_path}"
    )

    with rasterio.open(
        cog_path
    ) as src:

        print(
            "Driver:",
            src.driver,
        )

        print(
            "CRS:",
            src.crs,
        )

        print(
            "Size:",
            src.width,
            "x",
            src.height,
        )

        print(
            "Bands:",
            src.count,
        )

        print(
            "Dtypes:",
            src.dtypes,
        )

        print(
            "NoData:",
            src.nodata,
        )

        print(
            "Resolution:",
            src.res,
        )

        print(
            "Band names:",
            src.descriptions,
        )

        if src.driver != "GTiff":
            raise RuntimeError(
                "Expected GTiff."
            )

        if not src.is_tiled:
            raise RuntimeError(
                "Raster is not tiled."
            )

        if src.block_shapes[0] != (
            256,
            256,
        ):
            raise RuntimeError(
                "Expected 256x256 blocks."
            )

        if not src.overviews(1):
            raise RuntimeError(
                "COG has no overviews."
            )

        if src.count != len(
            ALL_OUTPUT_BANDS
        ):
            raise RuntimeError(
                "Unexpected band count."
            )

        if src.nodata != -9999.0:
            raise RuntimeError(
                "Expected NoData = -9999."
            )

    print(
        "COG validation PASSED."
    )


def process_season(
    aoi: ee.Geometry,
    year: int,
    season_name: str,
    start_date: str,
    end_date: str,
) -> None:

    print("\n" + "=" * 70)

    print(
        f"YEAR: {year}"
    )

    print(
        f"SEASON: {season_name}"
    )

    print(
        f"DATE RANGE: {start_date} -> {end_date}"
    )

    print("=" * 70)

    collection = build_landsat_collection(
        aoi=aoi,
        start_date=start_date,
        end_date=end_date,
    )

    count = collection.size().getInfo()

    print(
        f"Landsat scenes found: {count}"
    )

    if count == 0:
        print(
            "No scenes available. Skipping."
        )
        return

    print(
        "Creating seasonal composite..."
    )

    composite = create_seasonal_composite(
        collection
    )

    season_dir = (
        OUTPUT_ROOT
        / str(year)
        / season_name
    )

    season_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = (
        TEMP_ROOT
        / f"surat_{year}_{season_name}.tif"
    )

    cog_path = (
        season_dir
        / f"surat_{year}_{season_name}_features_cog.tif"
    )

    export_geotiff(
        image=composite,
        aoi=aoi,
        output_path=temp_path,
    )

    convert_to_cog(
        source_path=temp_path,
        cog_path=cog_path,
    )

    validate_cog(
        cog_path
    )

    print(
        f"\nSUCCESS: {cog_path}"
    )


def main() -> None:

    print(
        "=== HEATSENSE AI ==="
    )

    print(
        "=== SEASONAL LANDSAT FEATURE PIPELINE ==="
    )

    print(
        f"Dataset range: "
        f"{ANALYSIS_START_YEAR}-{ANALYSIS_END_YEAR}"
    )

    initialize_gee()

    aoi = load_boundary()

    for year in range(
        ANALYSIS_START_YEAR,
        ANALYSIS_END_YEAR + 1,
    ):

        seasons = get_season_windows(
            year
        )

        for season in seasons:

            process_season(
                aoi=aoi,
                year=season.year,
                season_name=season.name,
                start_date=season.start_date,
                end_date=season.end_date,
            )

    print(
        "\n=== SEASONAL PIPELINE COMPLETE ==="
    )


if __name__ == "__main__":
    main()