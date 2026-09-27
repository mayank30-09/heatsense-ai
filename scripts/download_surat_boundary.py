from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import geopandas as gpd
from shapely.geometry import shape


FEATURE_SERVER_URL = (
    "https://services6.arcgis.com/"
    "uUlL3kz5ibba5Tdo/arcgis/rest/services/"
    "SMC_Boundary/FeatureServer/7/query"
)

OUTPUT_DIR = Path("data/raw/boundaries")
OUTPUT_FILE = OUTPUT_DIR / "surat_smc_boundary.geojson"

# UTM zone 43N is appropriate for metric calculations around Surat.
METRIC_CRS = "EPSG:32643"


def download_boundary() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    params = urlencode(
        {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
        }
    )

    url = f"{FEATURE_SERVER_URL}?{params}"

    print("Downloading Surat Municipal Corporation boundary...")
    print(url)

    with urlopen(url, timeout=60) as response:
        payload = json.load(response)

    if payload.get("type") != "FeatureCollection":
        raise RuntimeError("Boundary service did not return a GeoJSON FeatureCollection.")

    features = payload.get("features", [])

    if not features:
        raise RuntimeError("Boundary service returned zero features.")

    gdf = gpd.GeoDataFrame.from_features(
        features,
        crs="EPSG:4326",
    )

    if gdf.empty:
        raise RuntimeError("Loaded boundary GeoDataFrame is empty.")

    # Merge multiple returned features if necessary.
    geometry = gdf.geometry.union_all()

    if geometry.is_empty:
        raise RuntimeError("Merged Surat boundary geometry is empty.")

    if not geometry.is_valid:
        print("Boundary geometry is invalid. Attempting make-valid repair.")
        geometry = geometry.make_valid()

    boundary = gpd.GeoDataFrame(
        {
            "name": ["Surat Municipal Corporation"],
            "source": [FEATURE_SERVER_URL],
        },
        geometry=[geometry],
        crs="EPSG:4326",
    )

    # Calculate area in metres using UTM 43N.
    metric = boundary.to_crs(METRIC_CRS)
    area_m2 = float(metric.geometry.area.iloc[0])
    area_km2 = area_m2 / 1_000_000

    boundary["area_m2"] = area_m2
    boundary["area_km2"] = area_km2

    boundary.to_file(
        OUTPUT_FILE,
        driver="GeoJSON",
    )

    print()
    print("Boundary saved:")
    print(OUTPUT_FILE)
    print()
    print(f"CRS: {boundary.crs}")
    print(f"Area: {area_km2:.3f} km²")
    print(f"Geometry type: {boundary.geometry.iloc[0].geom_type}")
    print(f"Valid: {boundary.geometry.iloc[0].is_valid}")

    return {
        "output": str(OUTPUT_FILE),
        "area_km2": area_km2,
        "geometry_type": boundary.geometry.iloc[0].geom_type,
    }


if __name__ == "__main__":
    download_boundary()