from pathlib import Path

import ee
import geopandas as gpd


PROJECT_ID = "gen-lang-client-0607312119"

BOUNDARY_FILE = Path(
    "data/raw/boundaries/surat_smc_boundary.geojson"
)


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


def main() -> None:
    initialize_earth_engine()

    boundary = load_surat_boundary()

    collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(boundary)
        .filterDate("2025-01-01", "2025-12-31")
        .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
        .map(mask_landsat_l2)
        .map(scale_lst)
        .sort("system:time_start")
    )

    count = collection.size().getInfo()

    print(f"Landsat 8 L2SP scenes: {count}")

    if count == 0:
        raise RuntimeError("No Landsat scenes found.")

    image = ee.Image(collection.first())

    product_id = image.get("LANDSAT_PRODUCT_ID").getInfo()
    acquisition = image.date().format(
        "YYYY-MM-dd HH:mm:ss"
    ).getInfo()

    print(f"Product: {product_id}")
    print(f"Acquisition: {acquisition}")

    lst = image.select("lst_c").clip(boundary)

    stats = lst.reduceRegion(
        reducer=(
            ee.Reducer.min()
            .combine(
                reducer2=ee.Reducer.max(),
                sharedInputs=True,
            )
            .combine(
                reducer2=ee.Reducer.mean(),
                sharedInputs=True,
            )
            .combine(
                reducer2=ee.Reducer.stdDev(),
                sharedInputs=True,
            )
        ),
        geometry=boundary,
        scale=100,
        maxPixels=1e9,
    )

    print("\nLST statistics:")
    print(stats.getInfo())

    valid_fraction = (
        lst.mask()
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=boundary,
            scale=100,
            maxPixels=1e9,
        )
        .get("lst_c")
    )

    print("\nValid pixel fraction:")
    print(valid_fraction.getInfo())


if __name__ == "__main__":
    main()