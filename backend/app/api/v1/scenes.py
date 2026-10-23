"""API endpoints for Near-Real-Time Landsat LST Scenes catalog."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models.stage_c import StageCScene
from backend.app.db.session import get_db

router = APIRouter(
    prefix="/scenes",
    tags=["scenes"],
)


from pathlib import Path
import json

class SceneMetadataItem(BaseModel):
    """Metadata response model for an ingested near-real-time Landsat scene."""

    scene_id: str = Field(..., description="Unique Landsat product identifier")
    acquisition_date: str = Field(..., description="Date of satellite acquisition (YYYY-MM-DD)")
    acquisition_time: str = Field(..., description="UTC ISO acquisition timestamp")
    acquisition_time_ist: str | None = Field(None, description="Acquisition timestamp in Indian Standard Time (IST, UTC+05:30)")
    sensor: str = Field(..., description="Spacecraft / sensor name (e.g. LANDSAT_8, LANDSAT_9)")
    path: int = Field(148, description="WRS path")
    row: int = Field(45, description="WRS row")
    cloud_cover: float | None = Field(None, description="Reported scene cloud cover percentage")
    valid_pixel_fraction: float = Field(..., description="Fraction of valid pixels over SMC grid [0.0, 1.0]")
    mean_lst_c: float | None = Field(None, description="Mean land surface temperature in Celsius")
    max_lst_c: float | None = Field(None, description="Maximum land surface temperature in Celsius")
    status: str = Field(..., description="Ingestion processing status (PROCESSED, REJECTED_CLOUDY, etc.)")
    cog_path: str | None = Field(None, description="Relative path to Cloud-Optimized GeoTIFF raster")
    source: str = Field("landsat_l2", description="Catalog source: 'landsat_l2' or 'SYNTHETIC TEST DATA'")


def _is_scene_synthetic(r: StageCScene) -> bool:
    """Detect whether a scene record represents synthetic test data."""
    sid = r.scene_id.upper()
    if sid.startswith("TEST_FIXTURE_") or sid.startswith("SYNTHETIC_") or "MOCK" in sid:
        return True

    if r.cog_path and "mock_scenes" in r.cog_path:
        return True

    date_str = (
        r.acquisition_date.isoformat()
        if isinstance(r.acquisition_date, date)
        else str(r.acquisition_date)
    )
    for base_dir in [Path("data/processed/mock_scenes"), Path("data/processed/scenes")]:
        sidecar = base_dir / f"{date_str}.json"
        if sidecar.exists():
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    if meta.get("source") == "SYNTHETIC TEST DATA" or meta.get("is_synthetic"):
                        return True
            except Exception:
                pass

    if r.cog_path:
        p = Path(r.cog_path)
        if not p.exists():
            mock_p = Path("data/processed/mock_scenes") / p.name
            if mock_p.exists():
                return True

    return False


@router.get(
    "",
    response_model=list[SceneMetadataItem],
    summary="List available near-real-time Landsat scenes",
    description="Returns all successfully processed single-scene LST observations in reverse chronological order.",
)
def list_scenes(
    source: str = Query(
        "landsat_l2",
        description="Data source filter (default 'landsat_l2' for authentic Landsat Level-2 observations; use 'SYNTHETIC TEST DATA' or 'all' to include synthetic data)",
    ),
    status: str = Query("PROCESSED", description="Filter by status (default 'PROCESSED', use 'ALL' for ledger)"),
    min_valid_fraction: float | None = Query(0.60, ge=0.0, le=1.0, description="Minimum valid pixel fraction filter (default 0.60 for adequate coverage)"),
    db: Session = Depends(get_db),
) -> list[SceneMetadataItem]:
    """Retrieve catalog of ingested Landsat scenes.

    Restricted to authentic satellite scenes (source='landsat_l2') and adequate coverage by default.
    Synthetic mock scenes are strictly excluded unless explicitly requested via source='all' or 'SYNTHETIC TEST DATA'.
    """
    stmt = select(StageCScene).order_by(desc(StageCScene.acquisition_time))
    if status.upper() != "ALL":
        stmt = stmt.where(StageCScene.status == status.upper())

    if min_valid_fraction is not None and status.upper() == "PROCESSED":
        stmt = stmt.where(StageCScene.valid_pixel_fraction >= min_valid_fraction)

    records = db.execute(stmt).scalars().all()

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    req_source = source.strip().lower()

    items: list[SceneMetadataItem] = []
    for r in records:
        is_synth = _is_scene_synthetic(r)
        record_source = "SYNTHETIC TEST DATA" if is_synth else "landsat_l2"

        # Apply source filter
        if req_source == "landsat_l2":
            if is_synth:
                continue
        elif req_source in ("synthetic test data", "synthetic", "mock"):
            if not is_synth:
                continue
        elif req_source == "all":
            pass
        else:
            if record_source.lower() != req_source:
                continue

        acq_time_str = (
            r.acquisition_time.isoformat()
            if isinstance(r.acquisition_time, datetime)
            else str(r.acquisition_time)
        )
        acq_date_str = (
            r.acquisition_date.isoformat()
            if isinstance(r.acquisition_date, date)
            else str(r.acquisition_date)
        )

        acq_time_ist_str: str | None = None
        if isinstance(r.acquisition_time, datetime):
            utc_dt = r.acquisition_time if r.acquisition_time.tzinfo else r.acquisition_time.replace(tzinfo=timezone.utc)
            ist_dt = utc_dt.astimezone(ist_tz)
            acq_time_ist_str = ist_dt.strftime("%Y-%m-%d %H:%M:%S IST")

        items.append(
            SceneMetadataItem(
                scene_id=r.scene_id,
                acquisition_date=acq_date_str,
                acquisition_time=acq_time_str,
                acquisition_time_ist=acq_time_ist_str,
                sensor=r.sensor,
                path=r.path,
                row=r.row,
                cloud_cover=r.cloud_cover,
                valid_pixel_fraction=round(float(r.valid_pixel_fraction), 4),
                mean_lst_c=round(float(r.mean_lst_c), 2) if r.mean_lst_c is not None else None,
                max_lst_c=round(float(r.max_lst_c), 2) if r.max_lst_c is not None else None,
                status=r.status,
                cog_path=r.cog_path,
                source=record_source,
            )
        )

    return items
