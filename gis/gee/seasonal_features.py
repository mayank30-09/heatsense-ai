from __future__ import annotations

from dataclasses import dataclass

import ee


LANDSAT_COLLECTIONS = [
    "LANDSAT/LC08/C02/T1_L2",
    "LANDSAT/LC09/C02/T1_L2",
]

FEATURE_BANDS = [
    "LST_C",
    "NDVI",
    "NDBI",
    "NDWI",
]

OBSERVATION_COUNT_BANDS = [
    "LST_OBS_COUNT",
    "NDVI_OBS_COUNT",
    "NDBI_OBS_COUNT",
    "NDWI_OBS_COUNT",
]

ALL_OUTPUT_BANDS = FEATURE_BANDS + OBSERVATION_COUNT_BANDS


@dataclass(frozen=True)
class SeasonWindow:
    year: int
    name: str
    start_date: str
    end_date: str


def get_season_windows(year: int) -> list[SeasonWindow]:
    """
    Build Surat seasonal windows.

    Winter is assigned to the year containing January/February.
    Therefore Winter 2022 = Dec 2021 through Feb 2022.
    """

    return [
        SeasonWindow(
            year=year,
            name="winter",
            start_date=f"{year - 1}-12-01",
            end_date=f"{year}-03-01",
        ),
        SeasonWindow(
            year=year,
            name="summer",
            start_date=f"{year}-03-01",
            end_date=f"{year}-06-01",
        ),
        SeasonWindow(
            year=year,
            name="monsoon",
            start_date=f"{year}-06-01",
            end_date=f"{year}-10-01",
        ),
        SeasonWindow(
            year=year,
            name="post_monsoon",
            start_date=f"{year}-10-01",
            end_date=f"{year}-12-01",
        ),
    ]


def mask_landsat_l2(image: ee.Image) -> ee.Image:
    """
    Mask clouds, cloud shadows, cirrus, snow and fill pixels.

    QA_PIXEL bits:
        0 = Fill
        1 = Dilated cloud
        2 = Cirrus
        3 = Cloud
        4 = Cloud shadow
        5 = Snow

    QA_RADSAT is also used to remove saturated pixels.
    """

    qa_pixel = image.select("QA_PIXEL")

    clear = (
        qa_pixel.bitwiseAnd(1 << 0).eq(0)
        .And(qa_pixel.bitwiseAnd(1 << 1).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 2).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 3).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 4).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 5).eq(0))
    )

    qa_radsat = image.select("QA_RADSAT")
    unsaturated = qa_radsat.eq(0)

    return (
        image
        .updateMask(clear)
        .updateMask(unsaturated)
    )


def add_seasonal_features(image: ee.Image) -> ee.Image:
    """
    Add LST, NDVI, NDBI and NDWI to a Landsat L2 image.

    Surface-reflectance pixels must be physically usable before
    spectral indices are calculated.
    """

    surface_reflectance = (
        image
        .select(
            [
                "SR_B2",
                "SR_B3",
                "SR_B4",
                "SR_B5",
                "SR_B6",
                "SR_B7",
            ]
        )
        .multiply(0.0000275)
        .add(-0.2)
    )

    blue = surface_reflectance.select("SR_B2")
    green = surface_reflectance.select("SR_B3")
    red = surface_reflectance.select("SR_B4")
    nir = surface_reflectance.select("SR_B5")
    swir1 = surface_reflectance.select("SR_B6")
    swir2 = surface_reflectance.select("SR_B7")

    # ------------------------------------------------------------------
    # Valid reflectance masks
    # ------------------------------------------------------------------

    valid_ndvi = (
        red.gt(0)
        .And(nir.gt(0))
        .And(
            red.add(nir).abs().gt(0.001)
        )
    )

    valid_ndbi = (
        swir1.gt(0)
        .And(nir.gt(0))
        .And(
            swir1.add(nir).abs().gt(0.001)
        )
    )

    valid_ndwi = (
        green.gt(0)
        .And(nir.gt(0))
        .And(
            green.add(nir).abs().gt(0.001)
        )
    )

    # ------------------------------------------------------------------
    # Spectral indices
    # ------------------------------------------------------------------

    ndvi = (
        nir.subtract(red)
        .divide(nir.add(red))
        .updateMask(valid_ndvi)
        .rename("NDVI")
    )

    ndbi = (
        swir1.subtract(nir)
        .divide(swir1.add(nir))
        .updateMask(valid_ndbi)
        .rename("NDBI")
    )

    ndwi = (
        green.subtract(nir)
        .divide(green.add(nir))
        .updateMask(valid_ndwi)
        .rename("NDWI")
    )

    # ------------------------------------------------------------------
    # Land Surface Temperature
    # ------------------------------------------------------------------

    lst_c = (
        image
        .select("ST_B10")
        .multiply(0.00341802)
        .add(149.0)
        .subtract(273.15)
        .rename("LST_C")
    )

    return image.addBands(
        [
            lst_c,
            ndvi,
            ndbi,
            ndwi,
        ]
    )

def build_landsat_collection(
    aoi: ee.Geometry,
    start_date: str,
    end_date: str,
) -> ee.ImageCollection:
    """
    Build a merged Landsat 8 + Landsat 9 collection.
    """

    collections = []

    for collection_id in LANDSAT_COLLECTIONS:
        collection = (
            ee.ImageCollection(collection_id)
            .filterBounds(aoi)
            .filterDate(start_date, end_date)
            .filter(
                ee.Filter.eq(
                    "PROCESSING_LEVEL",
                    "L2SP",
                )
            )
            .filter(
                ee.Filter.lte(
                    "CLOUD_COVER",
                    80,
                )
            )
            .map(mask_landsat_l2)
            .map(add_seasonal_features)
        )

        collections.append(collection)

    merged = collections[0].merge(collections[1])

    return merged.sort("system:time_start")

def create_seasonal_composite(
    collection: ee.ImageCollection,
) -> ee.Image:
    """
    Create a pixel-wise seasonal median composite.

    Pixels with no valid seasonal observation are explicitly
    encoded as -9999 before export so that masked pixels cannot
    be confused with real measurements.
    """

    composite = (
        collection
        .select(FEATURE_BANDS)
        .median()
    )

    counts = (
        collection
        .select(FEATURE_BANDS)
        .count()
        .rename(OBSERVATION_COUNT_BANDS)
    )

    result = composite.addBands(counts)

    # Explicit project-wide NoData value.
    return result.unmask(-9999)
   

   