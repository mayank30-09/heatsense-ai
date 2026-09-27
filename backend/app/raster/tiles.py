from __future__ import annotations

from pathlib import Path

import numpy as np
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import COGReader
from rio_tiler.utils import render


COG_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "rasters"
    / "surat_landsat_lst_first_scene_cog.tif"
)

LST_MIN_C = 20.0
LST_MAX_C = 50.0


def get_lst_tile(
    x: int,
    y: int,
    z: int,
    tilesize: int = 256,
) -> bytes:

    if not COG_PATH.exists():
        raise FileNotFoundError(
            f"LST COG not found: {COG_PATH}"
        )

    try:
        with COGReader(str(COG_PATH)) as cog:
            image = cog.tile(
                x,
                y,
                z,
                tilesize=tilesize,
            )
    except TileOutsideBounds:
        empty = np.zeros(
            (4, tilesize, tilesize),
            dtype=np.uint8,
        )
        return render(
            empty,
            img_format="PNG",
        )

    data = image.data[0].astype(np.float32)

    # Do not use image.mask directly.
    # rio-tiler is returning an unusual float32 mask for this COG.
    # Build the alpha mask from the actual NoData value instead.
    nodata = -9999.0

    valid = (
        np.isfinite(data)
        & (data != nodata)
        & (data >= LST_MIN_C)
        & (data <= LST_MAX_C)
    )

    normalized = np.zeros_like(
        data,
        dtype=np.float32,
    )

    normalized[valid] = (
        (data[valid] - LST_MIN_C)
        / (LST_MAX_C - LST_MIN_C)
    )

    normalized = np.clip(
        normalized,
        0.0,
        1.0,
    )

    values = (
        normalized * 255.0
    ).astype(np.uint8)

    rgba = np.zeros(
        (4, data.shape[0], data.shape[1]),
        dtype=np.uint8,
    )

    # Blue → green → red style thermal gradient.
    rgba[0] = np.clip(
        values.astype(np.int16) * 2,
        0,
        255,
    ).astype(np.uint8)

    rgba[1] = np.clip(
        255 - np.abs(
            values.astype(np.int16) - 128
        ) * 2,
        0,
        255,
    ).astype(np.uint8)

    rgba[2] = np.clip(
        255 - values.astype(np.int16) * 2,
        0,
        255,
    ).astype(np.uint8)

    # Transparent where the LST pixel is invalid.
    rgba[3] = np.where(
        valid,
        255,
        0,
    ).astype(np.uint8)

    return render(
        rgba,
        img_format="PNG",
    )