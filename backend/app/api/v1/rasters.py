from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import Response

from ...raster.catalog import Season, resolve_seasonal_cog
from ...raster.tiles import get_lst_tile

router = APIRouter(
    prefix="/rasters",
    tags=["rasters"],
)


@router.get(
    "/lst/tiles/{z}/{x}/{y}.png",
    response_class=Response,
)
def lst_tile(
    z: int = Path(..., ge=0, le=24, description="Tile zoom level (0-24)"),
    x: int = Path(..., ge=0, description="Tile X column (non-negative)"),
    y: int = Path(..., ge=0, description="Tile Y row (non-negative)"),
    season: Season = Query(Season.summer, description="Season (summer, winter, post_monsoon, monsoon)"),
    year: int | None = Query(None, ge=2020, le=2030, description="Year (e.g. 2026)"),
) -> Response:
    try:
        resolved = resolve_seasonal_cog(season=season, year=year)
        tile = get_lst_tile(
            x=x,
            y=y,
            z=z,
            season=resolved.season,
            year=resolved.effective_year,
        )

        return Response(
            content=tile,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Effective-Year": str(resolved.effective_year),
            },
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to render requested LST raster tile.",
        ) from exc