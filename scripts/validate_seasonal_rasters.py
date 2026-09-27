from pathlib import Path

import rasterio


ROOT = Path("data/processed/seasonal")


def validate_raster(path: Path) -> None:
    print("\n" + "=" * 70)
    print(path)
    print("=" * 70)

    with rasterio.open(path) as src:
        print(f"CRS: {src.crs}")
        print(f"Size: {src.width} x {src.height}")
        print(f"Bands: {src.count}")
        print(f"NoData: {src.nodata}")

        for band_index, name in enumerate(src.descriptions, start=1):
            data = src.read(band_index).astype("float64")

            valid = data[data != -9999.0]

            if valid.size == 0:
                print(f"{name:18s}: NO VALID PIXELS")
                continue

            print(
                f"{name:18s}"
                f" min={valid.min():10.4f}"
                f" max={valid.max():10.4f}"
                f" mean={valid.mean():10.4f}"
            )


def main() -> None:
    rasters = sorted(
        ROOT.glob("*/*/*_features_cog.tif")
    )

    if not rasters:
        raise RuntimeError(
            "No seasonal COGs found."
        )

    print(f"Seasonal rasters found: {len(rasters)}")

    for raster in rasters:
        validate_raster(raster)


if __name__ == "__main__":
    main()