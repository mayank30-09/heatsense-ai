from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path
from fastapi import APIRouter, HTTPException, Path as PathParam, Query
from fastapi.responses import Response
from sqlalchemy import select

from ...db.models.stage_c import StageCScene
from ...db.session import SessionLocal
from ...raster.catalog import Season, resolve_seasonal_cog
from ...raster.tiles import get_lst_tile, get_scene_lst_tile

router = APIRouter(
    prefix="/rasters",
    tags=["rasters"],
)


def _resolve_scene_cog_path(scene_id: str) -> tuple[Path, str]:
    """Resolve COG file path and canonical scene identifier for a given scene_id or date string."""
    clean_id = scene_id.strip()

    # 1. Direct file path check under data/processed/scenes and data/processed/mock_scenes
    for base_dir in [Path("data/processed/scenes"), Path("data/processed/mock_scenes")]:
        direct_path = base_dir / f"{clean_id}.tif"
        if direct_path.exists():
            return direct_path, clean_id

    # 2. Database lookup in stage_c_scenes
    db = SessionLocal()
    try:
        stmt = select(StageCScene).where(StageCScene.scene_id == clean_id)
        scene = db.execute(stmt).scalar_one_or_none()

        if not scene:
            # Try parsing as date
            try:
                target_date = date.fromisoformat(clean_id)
                stmt = (
                    select(StageCScene)
                    .where(
                        (StageCScene.acquisition_date == target_date)
                        & (StageCScene.status == "PROCESSED")
                    )
                    .order_by(StageCScene.acquisition_time.desc())
                )
                scene = db.execute(stmt).scalars().first()
            except ValueError:
                pass

        if scene and scene.cog_path:
            cog_p = Path(scene.cog_path)
            if cog_p.exists():
                return cog_p, scene.scene_id
            # Fallback to mock_scenes if file was relocated
            mock_p = Path("data/processed/mock_scenes") / cog_p.name
            if mock_p.exists():
                return mock_p, scene.scene_id
    finally:
        db.close()

    # 3. Check for pattern match in data/processed/scenes/ and data/processed/mock_scenes/
    for scenes_dir in [Path("data/processed/scenes"), Path("data/processed/mock_scenes")]:
        if scenes_dir.exists():
            for candidate in scenes_dir.glob(f"*{clean_id}*.tif"):
                return candidate, candidate.stem

    raise FileNotFoundError(f"Scene '{scene_id}' not found.")


@router.get(
    "/lst/tiles/{z}/{x}/{y}.png",
    response_class=Response,
)
def lst_tile(
    z: int = PathParam(..., ge=0, le=24, description="Tile zoom level (0-24)"),
    x: int = PathParam(..., ge=0, description="Tile X column (non-negative)"),
    y: int = PathParam(..., ge=0, description="Tile Y row (non-negative)"),
    season: Season = Query(Season.summer, description="Season (summer, winter, post_monsoon, monsoon)"),
    year: int | None = Query(None, ge=2020, le=2030, description="Year (e.g. 2026)"),
    scene_id: str | None = Query(None, description="Optional scene product ID or acquisition date for single-scene rendering"),
) -> Response:
    try:
        # Scene-specific rendering branch
        if scene_id:
            cog_path, canonical_scene_id = _resolve_scene_cog_path(scene_id)
            tile = get_scene_lst_tile(x=x, y=y, z=z, cog_path=cog_path)
            etag = f'"{hashlib.sha256(tile).hexdigest()[:16]}"'

            return Response(
                content=tile,
                media_type="image/png",
                headers={
                    "Cache-Control": "public, max-age=3600, must-revalidate",
                    "ETag": etag,
                    "X-Data-Source": cog_path.name,
                    "X-Scene-ID": canonical_scene_id,
                },
            )

        # Standard seasonal composite rendering branch
        resolved = resolve_seasonal_cog(season=season, year=year)
        tile = get_lst_tile(
            x=x,
            y=y,
            z=z,
            season=resolved.season,
            year=resolved.effective_year,
        )
        etag = f'"{hashlib.sha256(tile).hexdigest()[:16]}"'

        return Response(
            content=tile,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600, must-revalidate",
                "ETag": etag,
                "X-Data-Source": resolved.path.name,
                "X-Effective-Year": str(resolved.effective_year),
                "X-Effective-Season": str(resolved.season.value),
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