from pathlib import Path

import ee
import geopandas as gpd


PROJECT_ID = "gen-lang-client-0607312119"

BOUNDARY_FILE = Path(
    "data/raw/boundaries/surat_smc_boundary.geojson"
)

LANDSAT_COLLECTIONS = [
    "LANDSAT/LC08/C02/T1_L2",
    "LANDSAT/LC09/C02/T1_L2",
]


def initialize_earth_engine() -> None:
    ee.Initialize(project=PROJECT_ID)


def load_surat_boundary() -> ee.Geometry:
    gdf = gpd.read_file(BOUNDARY_FILE)

    if gdf.empty:
        raise RuntimeError("Surat boundary is empty.")

    if gdf.crs is None:
        raise RuntimeError("Surat boundary has no CRS.")

    gdf = gdf.to_crs("EPSG:4326")

    geometry = gdf.geometry.union_all()

    if geometry.is_empty:
        raise RuntimeError("Surat boundary geometry is empty.")

    if not geometry.is_valid:
        raise RuntimeError("Surat boundary geometry is invalid.")

    return ee.Geometry(geometry.__geo_interface__)


def mask_landsat_l2(image: ee.Image) -> ee.Image:
    qa = image.select("QA_PIXEL")

    clear = (
        qa.bitwiseAnd(1 << 0).eq(0)
        .And(qa.bitwiseAnd(1 << 1).eq(0))
        .And(qa.bitwiseAnd(1 << 2).eq(0))
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
    )

    return image.updateMask(clear)


def scale_lst(image: ee.Image) -> ee.Image:
    lst_c = (
        image.select("ST_B10")
        .multiply(0.00341802)
        .add(149.0)
        .subtract(273.15)
        .rename("lst_c")
    )

    return image.addBands(lst_c)


def build_landsat_collection(
    boundary: ee.Geometry,
    start_date: str,
    end_date: str,
) -> ee.ImageCollection:

    landsat8 = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(boundary)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
        .map(mask_landsat_l2)
        .map(scale_lst)
    )

    landsat9 = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterBounds(boundary)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
        .map(mask_landsat_l2)
        .map(scale_lst)
    )

    return landsat8.merge(landsat9).sort("system:time_start")


def main() -> None:
    initialize_earth_engine()

    boundary = load_surat_boundary()

    collection = build_landsat_collection(
        boundary=boundary,
        start_date="2025-01-01",
        end_date="2025-12-31",
    )

    count = collection.size().getInfo()

    print(f"Landsat L2SP scenes found: {count}")

    if count == 0:
        raise RuntimeError(
            "No Landsat L2SP scenes found for Surat."
        )

    first = ee.Image(collection.first())

    print(
        "First Landsat product:",
        first.get("LANDSAT_PRODUCT_ID").getInfo(),
    )

    print(
        "Acquisition:",
        first.date().format(
            "YYYY-MM-dd HH:mm:ss"
        ).getInfo(),
    )

    print(
        "Processing level:",
        first.get("PROCESSING_LEVEL").getInfo(),
    )

    print(
        "Cloud cover:",
        first.get("CLOUD_COVER").getInfo(),
    )


if __name__ == "__main__":
    main()