from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import ee
import geopandas as gpd
import rasterio

PROJECT_ID = "gen-lang-client-0607312119"

BOUNDARY_PATH = Path(
    "data/raw/boundaries/surat_smc_boundary.geojson"
)

OUTPUT_DIR = Path("data/processed/rasters")
TEMP_DIR = OUTPUT_DIR / "tmp"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

TEMP_TIF = TEMP_DIR / "surat_landsat_lst_first_scene.tif"
COG_PATH = OUTPUT_DIR / "surat_landsat_lst_first_scene_cog.tif"

START_DATE = "2025-01-01"
END_DATE = "2025-01-31"

EXPORT_SCALE_METERS = 100


def initialize_gee() -> None:
    ee.Initialize(project=PROJECT_ID)


def load_boundary() -> tuple[dict, ee.Geometry]:
    gdf = gpd.read_file(BOUNDARY_PATH)

    if gdf.empty:
        raise RuntimeError("Study-area boundary is empty.")

    if gdf.crs is None:
        raise RuntimeError("Study-area boundary has no CRS.")

    gdf = gdf.to_crs("EPSG:4326")

    geometry = gdf.geometry.union_all()

    if geometry.is_empty:
        raise RuntimeError("Study-area geometry is empty.")

    if not geometry.is_valid:
        geometry = geometry.buffer(0)

    geojson_geometry = json.loads(
        gpd.GeoSeries([geometry], crs="EPSG:4326")
        .to_json()
    )["features"][0]["geometry"]

    ee_geometry = ee.Geometry(geojson_geometry)

    return geojson_geometry, ee_geometry


def get_first_scene(aoi: ee.Geometry) -> ee.Image:
    collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(aoi)
        .filterDate(START_DATE, END_DATE)
        .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
        .sort("CLOUD_COVER")
    )

    count = collection.size().getInfo()

    print(f"Landsat 8 L2SP scenes found: {count}")

    if count == 0:
        raise RuntimeError("No Landsat L2SP scenes found.")

    image = ee.Image(collection.first())

    info = image.getInfo()

    print(
        "Selected product:",
        info["properties"].get("LANDSAT_PRODUCT_ID"),
    )

    print(
        "Acquisition:",
        info["properties"].get("DATE_ACQUIRED"),
    )

    print(
        "Cloud cover:",
        info["properties"].get("CLOUD_COVER"),
    )

    return image


def create_lst_image(image: ee.Image) -> ee.Image:
    qa = image.select("QA_PIXEL")

    clear = (
        qa.bitwiseAnd(1 << 0).eq(0)
        .And(qa.bitwiseAnd(1 << 1).eq(0))
        .And(qa.bitwiseAnd(1 << 2).eq(0))
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
    )

    lst_celsius = (
        image
        .select("ST_B10")
        .multiply(0.00341802)
        .add(149.0)
        .subtract(273.15)
        .updateMask(clear)
        .rename("LST_C")
    )

    return lst_celsius


def export_geotiff(
    image: ee.Image,
    aoi: ee.Geometry,
) -> None:

    print("Preparing Earth Engine download...")

    url = image.getDownloadURL(
        {
            "name": "surat_landsat_lst",
            "region": aoi,
            "scale": EXPORT_SCALE_METERS,
            "crs": "EPSG:4326",
            "filePerBand": False,
            "format": "GEO_TIFF",
        }
    )

    print("Download URL generated.")
    print("Downloading GeoTIFF...")

    import urllib.request

    urllib.request.urlretrieve(url, TEMP_TIF)

    print(f"Downloaded: {TEMP_TIF}")


def convert_to_cog() -> None:
    print("Converting GeoTIFF → COG...")

    with rasterio.open(TEMP_TIF) as src:
        data = src.read(1).astype("float32")

        # The Earth Engine download uses 0 as NoData.
        # Convert those pixels to the project's standard NoData value.
        source_mask = src.read_masks(1)

        data[source_mask == 0] = -9999.0

        profile = src.profile.copy()

        profile.update(
            driver="GTiff",
            dtype="float32",
            count=1,
            nodata=-9999.0,
            compress="DEFLATE",
            tiled=True,
            blockxsize=256,
            blockysize=256,
            BIGTIFF="IF_SAFER",
        )

        with rasterio.open(COG_PATH, "w", **profile) as dst:
            dst.write(data, 1)

            dst.build_overviews(
                [2, 4, 8, 16],
                rasterio.enums.Resampling.average,
            )

            dst.update_tags(
                ns="rio_overview",
                resampling="average",
            )

    print(f"COG created: {COG_PATH}")

def validate_cog() -> None:
    print("\nValidating COG...")

    with rasterio.open(COG_PATH) as src:

        print("Driver:", src.driver)
        print("CRS:", src.crs)
        print("Size:", src.width, "x", src.height)
        print("Bands:", src.count)
        print("Dtype:", src.dtypes[0])
        print("NoData:", src.nodata)
        print("Bounds:", src.bounds)
        print("Resolution:", src.res)

        if src.driver != "GTiff":
            raise RuntimeError(
            f"Expected GTiff container, got {src.driver}"
        )

        if not src.is_tiled:
            raise RuntimeError("Raster is not tiled.")

        if src.block_shapes[0] != (256, 256):
            raise RuntimeError(
            f"Expected 256x256 blocks, got {src.block_shapes[0]}"
        )

        if not src.overviews(1):
            raise RuntimeError("COG has no overviews.")

        if src.count != 1:
            raise RuntimeError("Expected exactly one raster band.")

        if src.dtypes[0] != "float32":
            raise RuntimeError("Expected float32 raster.")

        if src.nodata != -9999.0:
            raise RuntimeError("Expected NoData = -9999.")

    print("COG validation PASSED.")


def main() -> None:
    print("=== HEATSENSE AI · FIRST LANDSAT LST COG ===")

    initialize_gee()

    _, aoi = load_boundary()

    image = get_first_scene(aoi)

    lst = create_lst_image(image)

    export_geotiff(lst, aoi)

    convert_to_cog()

    validate_cog()

    print("\nSUCCESS")
    print(f"COG: {COG_PATH}")


if __name__ == "__main__":
    main()