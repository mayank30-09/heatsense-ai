from pathlib import Path

import geopandas as gpd

from backend.app.db.session import engine


BOUNDARY_FILE = Path(
    "data/raw/boundaries/surat_smc_boundary.geojson"
)


def main() -> None:
    if not BOUNDARY_FILE.exists():
        raise FileNotFoundError(
            f"Boundary file not found: {BOUNDARY_FILE}"
        )

    gdf = gpd.read_file(BOUNDARY_FILE)

    if gdf.empty:
        raise RuntimeError(
            "Surat boundary GeoDataFrame is empty."
        )

    if gdf.crs is None:
        raise RuntimeError(
            "Surat boundary has no CRS."
        )

    gdf = gdf.to_crs("EPSG:4326")

    metric = gdf.to_crs("EPSG:32643")

    area_km2 = (
        metric.geometry.area / 1_000_000
    )

    db_gdf = gpd.GeoDataFrame(
        {
            "name": [
                "Surat Municipal Corporation"
            ],
            "code": [
                "SURAT_SMC"
            ],
            "area_km2": area_km2,
        },
        geometry=gdf.geometry,
        crs="EPSG:4326",
    )

    db_gdf.to_postgis(
        "study_areas",
        engine,
        if_exists="append",
        index=False,
    )

    print("Surat boundary inserted into PostGIS.")
    print()
    print(db_gdf[
        ["name", "code", "area_km2"]
    ])


if __name__ == "__main__":
    main()