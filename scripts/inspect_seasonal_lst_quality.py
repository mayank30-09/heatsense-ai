from __future__ import annotations

import ee

from gis.gee.landsat_lst import (
    initialize_earth_engine,
    load_surat_boundary,
)

import math
from pathlib import Path
import geopandas as gpd

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

START_YEAR = 2022
END_YEAR = 2026

SEASONS = {
    "winter": (12, 1, 3, 1),
    "summer": (3, 1, 6, 1),
    "monsoon": (6, 1, 10, 1),
    "post_monsoon": (10, 1, 12, 1),
}

COLLECTIONS = [
    "LANDSAT/LC08/C02/T1_L2",
    "LANDSAT/LC09/C02/T1_L2",
]

# Change this to the same Surat boundary asset/path already used by
# landsat_lst.py if your project uses an EE FeatureCollection asset.

# ---------------------------------------------------------------------------
# EARTH ENGINE INITIALIZATION
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# LANDSAT PREPROCESSING
# ---------------------------------------------------------------------------

def mask_landsat_l2(image: ee.Image) -> ee.Image:
    """
    Apply the existing HEATSENSE Landsat Collection 2 Level-2 QA masks.

    QA_PIXEL bits:
        0 = fill
        1 = dilated cloud
        2 = cirrus
        3 = cloud
        4 = cloud shadow
        5 = snow

    QA_RADSAT:
        0 = valid
    """

    qa_pixel = image.select("QA_PIXEL")

    mask = (
        qa_pixel.bitwiseAnd(1 << 0).eq(0)
        .And(qa_pixel.bitwiseAnd(1 << 1).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 2).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 3).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 4).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 5).eq(0))
    )

    qa_radsat = image.select("QA_RADSAT").eq(0)

    return image.updateMask(mask).updateMask(qa_radsat)


def add_lst_and_quality(image: ee.Image) -> ee.Image:
    """
    Add LST in Celsius and ST_QA uncertainty in Kelvin.

    ST_B10:
        Kelvin = DN * 0.00341802 + 149.0

    ST_QA:
        uncertainty_K = DN * 0.01
    """

    lst_c = (
        image.select("ST_B10")
        .multiply(0.00341802)
        .add(149.0)
        .subtract(273.15)
        .rename("LST_C")
    )

    # ST_QA is the uncertainty associated with surface temperature.
    # Keep it in Kelvin because that is the unit represented by the
    # documented scale factor.
    st_qa_k = (
        image.select("ST_QA")
        .multiply(0.01)
        .rename("ST_QA_K")
    )

    # Keep QA paired with valid LST pixels.
    st_qa_k = st_qa_k.updateMask(lst_c.mask())

    return image.addBands([lst_c, st_qa_k])


def prepare_collection(
    start_date: str,
    end_date: str,
    boundary: ee.Geometry,
) -> ee.ImageCollection:

    collections = []

    for collection_id in COLLECTIONS:
        collection = (
            ee.ImageCollection(collection_id)
            .filterBounds(boundary)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
            .map(mask_landsat_l2)
            .map(add_lst_and_quality)
        )

        collections.append(collection)

    merged = collections[0].merge(collections[1])

    return merged


# ---------------------------------------------------------------------------
# DATE HANDLING
# ---------------------------------------------------------------------------

def season_dates(year: int, season: str) -> tuple[str, str]:
    start_month, start_day, end_month, end_day = SEASONS[season]

    if season == "winter":
        start_year = year - 1
        end_year = year
    else:
        start_year = year
        end_year = year

    start_date = f"{start_year:04d}-{start_month:02d}-{start_day:02d}"
    end_date = f"{end_year:04d}-{end_month:02d}-{end_day:02d}"

    return start_date, end_date


# ---------------------------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------------------------

def get_region_statistics(
    image: ee.Image,
    boundary: ee.Geometry,
) -> dict:

    reducer = (
        ee.Reducer.percentile(
            [1, 5, 25, 50, 75, 95, 99]
        )
        .combine(
            reducer2=ee.Reducer.mean(),
            sharedInputs=True,
        )
        .combine(
            reducer2=ee.Reducer.minMax(),
            sharedInputs=True,
        )
    )

    result = image.reduceRegion(
        reducer=reducer,
        geometry=boundary,
        scale=100,
        maxPixels=1e8,
        bestEffort=True,
    )

    return result.getInfo()


def get_observation_statistics(
    observation_count: ee.Image,
    boundary: ee.Geometry,
) -> dict:

    reducer = (
        ee.Reducer.percentile(
            [1, 5, 25, 50, 75, 95, 99]
        )
        .combine(
            reducer2=ee.Reducer.mean(),
            sharedInputs=True,
        )
        .combine(
            reducer2=ee.Reducer.minMax(),
            sharedInputs=True,
        )
    )

    result = observation_count.reduceRegion(
        reducer=reducer,
        geometry=boundary,
        scale=100,
        maxPixels=1e8,
        bestEffort=True,
    )

    return result.getInfo()


# ---------------------------------------------------------------------------
# SEASONAL QUALITY INSPECTION
# ---------------------------------------------------------------------------

def inspect_season(
    year: int,
    season: str,
    boundary: ee.Geometry,
) -> None:

    start_date, end_date = season_dates(year, season)

    print()
    print("=" * 80)
    print(f"{year} {season}")
    print(f"Date range: {start_date} -> {end_date}")

    collection = prepare_collection(
        start_date=start_date,
        end_date=end_date,
        boundary=boundary,
    )

    scene_count = collection.size().getInfo()

    print(f"Landsat scenes: {scene_count}")

    if scene_count == 0:
        print("SKIPPED: no scenes found")
        return

    # Seasonal median LST.
    lst = (
        collection
        .select("LST_C")
        .median()
        .rename("LST_C")
    )

    # Seasonal median ST_QA uncertainty.
    #
    # This is deliberately named MEDIAN because it is not being presented
    # as the exact uncertainty of the median composite. It is a seasonal
    # quality indicator.
    qa = (
        collection
        .select("ST_QA_K")
        .median()
        .rename("LST_QA_MEDIAN_K")
    )

    # Number of valid LST observations per pixel.
    observation_count = (
        collection
        .select("LST_C")
        .count()
        .rename("LST_OBS_COUNT")
    )

    stats_image = lst.addBands(qa)

    lst_qa_stats = get_region_statistics(
        stats_image,
        boundary,
    )

    obs_stats = get_observation_statistics(
        observation_count,
        boundary,
    )

    print()
    print("LST + QA statistics:")
    for key, value in sorted(lst_qa_stats.items()):
        print(f"  {key}: {value}")

    print()
    print("Observation-count statistics:")
    for key, value in sorted(obs_stats.items()):
        print(f"  {key}: {value}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:

    initialize_earth_engine()

    boundary = load_surat_boundary()

    for year in range(START_YEAR, END_YEAR + 1):
        for season in SEASONS:
            inspect_season(
                year=year,
                season=season,
                boundary=boundary,
            )


if __name__ == "__main__":
    main()