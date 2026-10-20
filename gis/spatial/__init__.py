"""Spatial grid and geographic operations module for HEATSENSE AI."""

from gis.spatial.grid import (
    AUTHORITATIVE_SMC_AREA_KM2,
    CANONICAL_SMC_CELL_COUNT,
    GRID_CRS,
    GRID_HEIGHT,
    GRID_TOTAL_CELLS,
    GRID_WIDTH,
    INTERSECTING_SMC_CELL_COUNT,
    METRIC_CRS,
    PIXEL_SIZE,
    build_affine_transform,
    generate_smc_grid_dataframe,
    get_cell_centroid,
    get_cell_polygon,
    verify_area_conservation,
)

__all__ = [
    "GRID_CRS",
    "METRIC_CRS",
    "GRID_WIDTH",
    "GRID_HEIGHT",
    "GRID_TOTAL_CELLS",
    "PIXEL_SIZE",
    "CANONICAL_SMC_CELL_COUNT",
    "INTERSECTING_SMC_CELL_COUNT",
    "AUTHORITATIVE_SMC_AREA_KM2",
    "get_cell_polygon",
    "get_cell_centroid",
    "build_affine_transform",
    "generate_smc_grid_dataframe",
    "verify_area_conservation",
]
