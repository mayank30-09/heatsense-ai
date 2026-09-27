from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

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
    z: int,
    x: int,
    y: int,
) -> Response:
    try:
        tile = get_lst_tile(
            x=x,
            y=y,
            z=z,
        )

        return Response(
            content=tile,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
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
            detail=f"Unable to render LST tile: {exc}",
        ) from exc