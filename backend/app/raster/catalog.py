"""Seasonal Cloud-Optimized GeoTIFF (COG) Catalog and Resolver.

Builds an authoritative seasonal raster inventory dynamically from files present
under data/processed/seasonal/<year>/<season>/surat_<year>_<season>_features_cog.tif.
Enforces strict season validation, explicit 404 behavior (no silent legacy fallbacks),
and returns the effective observation year for each resolved dataset.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import NamedTuple


class Season(str, Enum):
    """Supported meteorological and analytical seasons."""

    summer = "summer"
    winter = "winter"
    monsoon = "monsoon"
    post_monsoon = "post_monsoon"


class SeasonalRasterEntry(NamedTuple):
    season: Season
    requested_year: int
    effective_year: int
    path: Path
    is_fallback_year: bool = False


DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"
SEASONAL_COG_DIR = DATA_DIR / "seasonal"
LEGACY_COG_PATH = DATA_DIR / "rasters" / "surat_landsat_lst_first_scene_cog.tif"

CANONICAL_SEASONS: list[tuple[Season, int]] = [
    (Season.summer, 2026),
    (Season.winter, 2026),
    (Season.post_monsoon, 2025),
    (Season.monsoon, 2026),
]


def discover_seasonal_cogs() -> dict[tuple[str, int], Path]:
    """Scan disk dynamically for available seasonal feature COGs."""
    catalog: dict[tuple[str, int], Path] = {}
    if not SEASONAL_COG_DIR.exists():
        return catalog

    for tif_path in SEASONAL_COG_DIR.glob("*/*/surat_*_features_cog.tif"):
        # Expected structure: seasonal/<year>/<season>/surat_<year>_<season>_features_cog.tif
        parts = tif_path.parts
        try:
            year_val = int(parts[-3])
            season_val = parts[-2].strip().lower()
            catalog[(season_val, year_val)] = tif_path.resolve()
        except (ValueError, IndexError):
            continue
    return catalog


def resolve_seasonal_cog(
    season: Season | str = Season.summer,
    year: int | None = None,
) -> SeasonalRasterEntry:
    """Resolve the authoritative COG file path for given season and year.

    Raises FileNotFoundError if the dataset is not available on disk.
    Never silently falls back to legacy or un-seasoned rasters.
    """
    if isinstance(season, Season):
        season_clean = season.value
    else:
        season_clean = str(season).strip().lower()

    valid_seasons = {s.value: s for s in Season}
    if season_clean not in valid_seasons:
        raise ValueError(
            f"Invalid season '{season}'. Must be one of: {list(valid_seasons.keys())}"
        )
    season_enum = valid_seasons[season_clean]

    req_year = year if year is not None else (2025 if season_enum == Season.post_monsoon else 2026)
    catalog = discover_seasonal_cogs()

    # Exact match check
    if (season_clean, req_year) in catalog:
        return SeasonalRasterEntry(
            season=season_enum,
            requested_year=req_year,
            effective_year=req_year,
            path=catalog[(season_clean, req_year)],
            is_fallback_year=False,
        )

    # Post-Monsoon special resolution: 2026 is incomplete, resolve to 2025 if available
    if season_enum == Season.post_monsoon and req_year == 2026:
        if (season_clean, 2025) in catalog:
            return SeasonalRasterEntry(
                season=season_enum,
                requested_year=2026,
                effective_year=2025,
                path=catalog[(season_clean, 2025)],
                is_fallback_year=True,
            )

    raise FileNotFoundError(
        f"No seasonal raster found for season '{season_clean}' and year '{req_year}'."
    )
