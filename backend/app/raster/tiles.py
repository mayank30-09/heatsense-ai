from __future__ import annotations

from pathlib import Path

import numpy as np
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import COGReader
from rio_tiler.utils import render

from .catalog import Season, resolve_seasonal_cog

LST_MIN_C = 20.0
LST_MAX_C = 60.0

# Fixed 20°C - 60°C Thermal Color Palette:
# 20°C: #3b82f6 (59, 130, 246)
# 30°C: #10b981 (16, 185, 129)
# 40°C: #f59e0b (245, 158, 11)
# 50°C: #ea580c (234, 88, 12)
# 60°C: #7f1d1d (127, 29, 29)
_STOPS = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float32)
_R_POINTS = np.array([59, 16, 245, 234, 127], dtype=np.float32)
_G_POINTS = np.array([130, 185, 158, 88, 29], dtype=np.float32)
_B_POINTS = np.array([246, 129, 11, 12, 29], dtype=np.float32)

_INDEX_256 = np.linspace(0.0, 1.0, 256, dtype=np.float32)
LUT_R = np.interp(_INDEX_256, _STOPS, _R_POINTS).astype(np.uint8)
LUT_G = np.interp(_INDEX_256, _STOPS, _G_POINTS).astype(np.uint8)
LUT_B = np.interp(_INDEX_256, _STOPS, _B_POINTS).astype(np.uint8)


def get_lst_tile(
    x: int,
    y: int,
    z: int,
    season: Season | str = Season.summer,
    year: int | None = None,
    tilesize: int = 256,
) -> bytes:
    resolved = resolve_seasonal_cog(season=season, year=year)

    try:
        with COGReader(str(resolved.path)) as cog:
            image = cog.tile(
                x,
                y,
                z,
                indexes=1,
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
    nodata = -9999.0

    valid = (
        np.isfinite(data)
        & (data != nodata)
        & (data > 0.0)
        & (data < 100.0)
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

    values = (normalized * 255.0).astype(np.uint8)

    rgba = np.zeros(
        (4, data.shape[0], data.shape[1]),
        dtype=np.uint8,
    )

    # Standardized 20°C - 60°C thermal LUT ramp
    rgba[0] = LUT_R[values]
    rgba[1] = LUT_G[values]
    rgba[2] = LUT_B[values]

    # Transparent where the LST pixel is invalid/unobserved
    rgba[3] = np.where(
        valid,
        255,
        0,
    ).astype(np.uint8)

    return render(
        rgba,
        img_format="PNG",
    )