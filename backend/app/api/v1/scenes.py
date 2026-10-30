"""API endpoints for Near-Real-Time Landsat LST Scenes catalog and pipeline status."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

import logging
from backend.app.db.models.stage_c import (
    StageCDiscoveryRun,
    StageCProvisionalHotspot,
    StageCScene,
    StageCSceneRegistry,
)

logger = logging.getLogger("heatsense.scenes")
from backend.app.db.session import get_db

router = APIRouter(
    prefix="/scenes",
    tags=["scenes"],
)

GENUINE_LANDSAT_PRODUCT_PATTERN = re.compile(
    r"^LC0[89]_L2SP_148045_\d{8}_\d{8}_02_T[12]$"
)


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
    status: str = Field(..., description="Ingestion processing status (PROCESSED, REJECTED_CLOUDY, rejected, published, etc.)")
    rejection_reason: str | None = Field(None, description="Detailed explanation if scene was rejected")
    provisional_hotspots_count: int | None = Field(None, description="Number of provisional NRT hotspots flagged")
    cog_path: str | None = Field(None, description="Relative path to Cloud-Optimized GeoTIFF raster")
    source: str = Field("landsat_l2", description="Catalog source: 'landsat_l2' or 'SYNTHETIC TEST DATA'")


class ExpectedOverpassItem(BaseModel):
    """Details for a single scheduled or observed satellite overpass."""

    date: str = Field(..., description="Date of overpass (YYYY-MM-DD)")
    sensor: str = Field(..., description="Satellite sensor name (e.g. LANDSAT_8, LANDSAT_9)")
    status: str = Field(..., description="Overpass status: PROCESSED, REJECTED, PENDING_LATENCY, or OVERDUE")
    label: str = Field(..., description="Human-readable status text")
    rejection_reason: str | None = Field(None, description="Detailed explanation if scene was rejected")
    days_ago: int = Field(..., description="Days elapsed since overpass date relative to evaluation time")


class PipelineStatusResponse(BaseModel):
    """Near-real-time pipeline operational status and scheduling metadata."""

    last_checked: str = Field(..., description="UTC ISO timestamp of the last discovery job run")
    last_checked_ist: str = Field(..., description="Formatted IST timestamp (e.g. '12:45 AM IST, 27 Oct 2026')")
    last_checked_relative: str = Field(..., description="Relative time since last check (e.g. '3 hours ago')")
    last_ingested_date: str | None = Field(None, description="Acquisition date of the latest processed scene")
    next_expected_overpass: str = Field(..., description="Estimated date of the next Landsat 8/9 orbital overpass (YYYY-MM-DD)")
    next_expected_sensor: str = Field(..., description="Spacecraft sensor for next expected overpass (LANDSAT_8 or LANDSAT_9)")
    next_expected_overpass_label: str = Field(..., description="Human-readable next overpass label (e.g. '~Oct 30 (Landsat 9)')")
    pipeline_status: str = Field(..., description="Operational status: OPERATIONAL, DELAYED, or ERROR")
    status_detail: str | None = Field(None, description="Explanation or error message if DELAYED or ERROR")
    processed_count: int = Field(..., description="Count of successfully processed scenes in catalog")
    rejected_count: int = Field(..., description="Count of rejected scenes due to cloud contamination")
    recent_overpasses: list[ExpectedOverpassItem] = Field(default_factory=list, description="List of recent expected overpasses with individual ingestion status")


IST_TZ = timezone(timedelta(hours=5, minutes=30))


def _format_relative_time(dt: datetime, now_dt: datetime) -> str:
    """Format elapsed time in human readable format like '3 hours ago'."""
    diff_sec = max(0, int((now_dt - dt).total_seconds()))
    if diff_sec < 60:
        return "just now"
    minutes = diff_sec // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def _is_scene_synthetic(r: Any) -> bool:
    """Detect whether a scene record represents synthetic test data."""
    status_val = getattr(r, "status", None)
    if status_val == "SYNTHETIC_EXCLUDED":
        return True

    sid = getattr(r, "scene_id", "").upper()
    if sid.startswith("TEST_FIXTURE_") or sid.startswith("SYNTHETIC_") or "MOCK" in sid:
        return True

    if not GENUINE_LANDSAT_PRODUCT_PATTERN.match(sid):
        return True

    cog_p = getattr(r, "cog_path", None)
    if status_val in ("PROCESSED", "published"):
        if not cog_p:
            return True
        p = Path(cog_p)
        if not p.exists() or "mock_scenes" in p.as_posix():
            return True
    elif cog_p:
        p = Path(cog_p)
        if not p.exists() or "mock_scenes" in p.as_posix():
            return True

    acq_date = getattr(r, "acquisition_date", None)
    if acq_date:
        date_str = acq_date.isoformat() if isinstance(acq_date, date) else str(acq_date)
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

    return False


def calculate_pipeline_status(
    db: Session,
    as_of: datetime | None = None,
    last_error: str | None = None,
) -> PipelineStatusResponse:
    """Compute near-real-time pipeline operational status, orbital roll-forward, and overpass ledger."""
    # 1. Determine evaluation time (UTC and IST)
    now_utc = as_of if as_of is not None else datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_ist = now_utc.astimezone(IST_TZ)
    as_of_date = now_ist.date()

    # 2. Derive WRS-2 path/row dynamically from SMC vector boundary
    try:
        from gis.gee.nrt_pipeline import verify_wrs2_path_row_from_boundary
        path_val, row_val = verify_wrs2_path_row_from_boundary()
    except Exception:
        path_val, row_val = 148, 45

    # 3. Gather known acquisitions from StageCScene and StageCSceneRegistry for path/row
    known_scenes: dict[date, dict[str, Any]] = {}

    # Check StageCScene
    scenes_q = select(StageCScene).where(
        StageCScene.path == path_val,
        StageCScene.row == row_val,
    )
    for s in db.execute(scenes_q).scalars().all():
        if _is_scene_synthetic(s):
            continue
        vpf = float(s.valid_pixel_fraction or 0.0)
        reason = f"Excessive cloud cover: {vpf * 100:.1f}% clear (< 40.0% threshold)" if s.status in ("REJECTED_CLOUDY", "rejected") else None
        known_scenes[s.acquisition_date] = {
            "date": s.acquisition_date,
            "sensor": s.sensor.upper(),
            "status": s.status,
            "valid_pixel_fraction": vpf,
            "rejection_reason": reason,
            "updated_at": s.ingested_at,
        }

    # Check StageCSceneRegistry (takes precedence for richer rejection reasons)
    reg_q = select(StageCSceneRegistry).where(
        StageCSceneRegistry.path == path_val,
        StageCSceneRegistry.row == row_val,
    )
    for r in db.execute(reg_q).scalars().all():
        if _is_scene_synthetic(r):
            continue
        vpf = float(r.valid_pixel_fraction or 0.0)
        reason = r.rejection_reason
        if not reason and r.status == "rejected":
            reason = f"Excessive cloud cover: {vpf * 100:.1f}% clear (< 40.0% threshold)"
        known_scenes[r.acquisition_date] = {
            "date": r.acquisition_date,
            "sensor": r.sensor.upper(),
            "status": "PROCESSED" if r.status == "published" else r.status.upper(),
            "valid_pixel_fraction": vpf,
            "rejection_reason": reason,
            "updated_at": r.updated_at or r.created_at,
        }

    # Find latest known acquisition per sensor
    sensor_anchors: dict[str, date] = {}
    for acq_date, info in known_scenes.items():
        sens = info["sensor"]
        if sens not in sensor_anchors or acq_date > sensor_anchors[sens]:
            sensor_anchors[sens] = acq_date

    # Canonical baseline anchors for Surat WRS 148/45 if one or both missing
    # L8 anchor: 2026-10-06; L9 anchor: 2026-10-14 (16-day cycle, L9 offset 8 days from L8)
    if "LANDSAT_8" not in sensor_anchors and "LANDSAT_9" in sensor_anchors:
        sensor_anchors["LANDSAT_8"] = sensor_anchors["LANDSAT_9"] - timedelta(days=8)
    elif "LANDSAT_9" not in sensor_anchors and "LANDSAT_8" in sensor_anchors:
        sensor_anchors["LANDSAT_9"] = sensor_anchors["LANDSAT_8"] + timedelta(days=8)
    elif "LANDSAT_8" not in sensor_anchors and "LANDSAT_9" not in sensor_anchors:
        sensor_anchors["LANDSAT_8"] = date(2026, 10, 6)
        sensor_anchors["LANDSAT_9"] = date(2026, 10, 14)

    # 4. Roll forward cadence for each sensor (16 days repeat cycle)
    # Next overpass must be strictly after as_of_date
    next_overpass_per_sensor: dict[str, date] = {}
    for sens in ["LANDSAT_8", "LANDSAT_9"]:
        d = sensor_anchors[sens]
        while d <= as_of_date:
            d += timedelta(days=16)
        next_overpass_per_sensor[sens] = d

    # Next expected overpass is the earliest of the two sensors
    earliest_sensor = min(next_overpass_per_sensor, key=next_overpass_per_sensor.get)
    next_overpass_date = next_overpass_per_sensor[earliest_sensor]
    sensor_display = "Landsat 8" if earliest_sensor == "LANDSAT_8" else "Landsat 9"
    next_overpass_label = f"~{next_overpass_date.strftime('%b %d')} ({sensor_display})"

    # 5. Compute recent overpasses ledger in a lookback window since earliest tracked registry date
    scheduled_overpasses: list[tuple[date, str]] = []
    earliest_tracked = min(known_scenes.keys()) if known_scenes else as_of_date - timedelta(days=16)
    window_start = max(as_of_date - timedelta(days=35), earliest_tracked)
    for sens in ["LANDSAT_8", "LANDSAT_9"]:
        base_d = sensor_anchors[sens]
        while base_d > window_start:
            base_d -= timedelta(days=16)
        while base_d <= as_of_date:
            if base_d >= window_start:
                scheduled_overpasses.append((base_d, sens))
            base_d += timedelta(days=16)

    # Sort newest first
    scheduled_overpasses.sort(key=lambda x: x[0], reverse=True)

    recent_items: list[ExpectedOverpassItem] = []
    has_overdue = False
    overdue_details: list[str] = []

    for exp_date, sens in scheduled_overpasses:
        sens_short = "Landsat 8" if sens == "LANDSAT_8" else "Landsat 9"
        m_day = exp_date.strftime("%b %d")
        days_ago = (as_of_date - exp_date).days

        if exp_date in known_scenes:
            sc_info = known_scenes[exp_date]
            st = sc_info["status"]
            if st in ("PROCESSED", "PUBLISHED"):
                clear_pct = int(round(sc_info["valid_pixel_fraction"] * 100))
                recent_items.append(
                    ExpectedOverpassItem(
                        date=exp_date.isoformat(),
                        sensor=sens,
                        status="PROCESSED",
                        label=f"{m_day} ({sens_short}): Processed ({clear_pct}% clear)",
                        rejection_reason=None,
                        days_ago=days_ago,
                    )
                )
            else:
                clear_pct = int(round(sc_info["valid_pixel_fraction"] * 100))
                reason = sc_info.get("rejection_reason") or f"{clear_pct}% clear"
                recent_items.append(
                    ExpectedOverpassItem(
                        date=exp_date.isoformat(),
                        sensor=sens,
                        status="REJECTED",
                        label=f"{m_day} rejected: {reason}",
                        rejection_reason=reason,
                        days_ago=days_ago,
                    )
                )
        else:
            # Overpass was expected but not present in database
            # USGS Landsat C2 L2 products take ~2 to 3 days processing latency
            if days_ago <= 3:
                recent_items.append(
                    ExpectedOverpassItem(
                        date=exp_date.isoformat(),
                        sensor=sens,
                        status="PENDING_LATENCY",
                        label=f"{m_day} ({sens_short}): not ingested yet, check scheduled",
                        rejection_reason=None,
                        days_ago=days_ago,
                    )
                )
            else:
                has_overdue = True
                msg = f"{m_day} ({sens_short}): no scene found / overdue in GEE (> 3 days)"
                overdue_details.append(f"{sens_short} on {exp_date.isoformat()}")
                recent_items.append(
                    ExpectedOverpassItem(
                        date=exp_date.isoformat(),
                        sensor=sens,
                        status="OVERDUE",
                        label=msg,
                        rejection_reason=None,
                        days_ago=days_ago,
                    )
                )

    # 6. Derive dynamic pipeline status
    last_check_dt: datetime | None = None
    try:
        run_query = db.query(StageCDiscoveryRun)
        if as_of is not None:
            run_query = run_query.filter(StageCDiscoveryRun.run_at <= as_of)
        latest_run = run_query.order_by(desc(StageCDiscoveryRun.run_at)).first()
        if latest_run and latest_run.run_at:
            last_check_dt = latest_run.run_at
            if last_check_dt.tzinfo is None:
                last_check_dt = last_check_dt.replace(tzinfo=timezone.utc)
    except Exception as exc:
        logger.warning("Could not query stage_c_discovery_runs: %s", exc)

    if last_check_dt is None:
        all_updated = [
            info["updated_at"]
            for info in known_scenes.values()
            if info.get("updated_at") is not None
        ]
        if all_updated:
            last_check_dt = max(all_updated)
            if last_check_dt.tzinfo is None:
                last_check_dt = last_check_dt.replace(tzinfo=timezone.utc)
        else:
            last_check_dt = now_utc - timedelta(hours=3)

    if last_check_dt > now_utc:
        last_check_dt = now_utc

    time_since_check = now_utc - last_check_dt

    if last_error:
        pipeline_status = "ERROR"
        status_detail = f"Last discovery job failed: {last_error}"
    elif has_overdue:
        pipeline_status = "DELAYED"
        status_detail = (
            f"Overdue overpass detected: {', '.join(overdue_details)} passed > 3 days ago "
            f"with no Level-2 product published in GEE catalog (USGS reported upstream data availability interruption starting Oct 20; standard L8 turnaround is 4–11 days)."
        )
    elif time_since_check > timedelta(hours=24):
        pipeline_status = "DELAYED"
        status_detail = f"Discovery job has not run in {int(time_since_check.total_seconds() // 3600)} hours (> 24h threshold)."
    else:
        pipeline_status = "OPERATIONAL"
        status_detail = "Checked within last 24h; all overpasses ingested or within standard 3-day USGS latency."

    # 7. Formatted timestamps
    last_check_ist = last_check_dt.astimezone(IST_TZ)
    formatted_ist = f"{last_check_ist.strftime('%I:%M %p')} IST, {last_check_ist.strftime('%d %b %Y')}"
    relative_str = _format_relative_time(last_check_dt, now_utc)

    # Latest processed scene date
    processed_dates = [
        d for d, info in known_scenes.items()
        if info["status"] in ("PROCESSED", "PUBLISHED")
    ]
    latest_processed_date = max(processed_dates).isoformat() if processed_dates else None

    # Counts
    processed_count = sum(
        1 for info in known_scenes.values()
        if info["status"] in ("PROCESSED", "PUBLISHED")
    )
    rejected_count = sum(
        1 for info in known_scenes.values()
        if info["status"] in ("REJECTED", "REJECTED_CLOUDY")
    )

    return PipelineStatusResponse(
        last_checked=last_check_dt.isoformat(),
        last_checked_ist=formatted_ist,
        last_checked_relative=relative_str,
        last_ingested_date=latest_processed_date,
        next_expected_overpass=next_overpass_date.isoformat(),
        next_expected_sensor=earliest_sensor,
        next_expected_overpass_label=next_overpass_label,
        pipeline_status=pipeline_status,
        status_detail=status_detail,
        processed_count=processed_count,
        rejected_count=rejected_count,
        recent_overpasses=recent_items,
    )


@router.get(
    "/pipeline-status",
    response_model=PipelineStatusResponse,
    summary="NRT pipeline health and next overpass schedule",
    description="Returns discovery job status, last ingested scene date, next expected Landsat overpass, and overpass ledger.",
)
def get_pipeline_status(
    as_of: datetime | None = Query(None, description="Optional frozen reference datetime for status computation"),
    db: Session = Depends(get_db),
) -> PipelineStatusResponse:
    """Retrieve operational status for the near-real-time scene ingestion pipeline."""
    return calculate_pipeline_status(db=db, as_of=as_of)


@router.post(
    "/check",
    response_model=PipelineStatusResponse,
    summary="Trigger on-demand NRT Landsat discovery and status refresh",
    description="Runs live Earth Engine scene discovery over Surat (WRS 148/45) and returns refreshed pipeline status.",
)
def trigger_pipeline_check(
    db: Session = Depends(get_db),
) -> PipelineStatusResponse:
    """Trigger an on-demand check for new Landsat scenes and refresh pipeline status."""
    from scripts.discover_nrt_scenes import run_discovery

    # Debounce: if a run occurred in the last 15 seconds, return current status without re-hammering GEE
    try:
        latest_run = (
            db.query(StageCDiscoveryRun)
            .order_by(desc(StageCDiscoveryRun.run_at))
            .first()
        )
        now_utc = datetime.now(timezone.utc)
        if latest_run and latest_run.run_at:
            run_at = latest_run.run_at if latest_run.run_at.tzinfo else latest_run.run_at.replace(tzinfo=timezone.utc)
            if (now_utc - run_at).total_seconds() < 15:
                return calculate_pipeline_status(db=db)
    except Exception as exc:
        logger.warning("Error checking latest run debounce: %s", exc)

    # Run discovery with trigger_type="ON_DEMAND"
    try:
        run_discovery(trigger_type="ON_DEMAND")
    except Exception as exc:
        logger.error("On-demand discovery failed: %s", exc)

    return calculate_pipeline_status(db=db)


@router.get(
    "",
    response_model=list[SceneMetadataItem],
    summary="List available near-real-time Landsat scenes",
    description="Returns all successfully processed single-scene LST observations plus rejected scenes if requested.",
)
def list_scenes(
    source: str = Query(
        "landsat_l2",
        description="Data source filter (default 'landsat_l2' for authentic Landsat Level-2 observations; use 'SYNTHETIC TEST DATA' or 'all' to include synthetic data)",
    ),
    status: str = Query("ALL", description="Filter by status (default 'ALL' to show processed and rejected, or 'PROCESSED')"),
    min_valid_fraction: float | None = Query(None, ge=0.0, le=1.0, description="Minimum valid pixel fraction filter"),
    include_rejected: bool = Query(False, description="Include rejected scenes with reasons (default False)"),
    db: Session = Depends(get_db),
) -> list[SceneMetadataItem]:
    """Retrieve catalog of ingested Landsat scenes including rejected scenes and reasons."""
    req_source = source.strip().lower()
    is_asking_synthetic = req_source in ("synthetic test data", "synthetic", "mock", "all")

    # 1. Fetch registry items for rich status and rejection reasons
    reg_items = {r.scene_id: r for r in db.query(StageCSceneRegistry).all()}

    # 2. Query stage_c_scenes
    stmt = select(StageCScene).order_by(desc(StageCScene.acquisition_time))
    if status.upper() not in ("ALL", "ANY"):
        stmt = stmt.where(StageCScene.status == status.upper())
    elif not include_rejected and not is_asking_synthetic:
        stmt = stmt.where(StageCScene.status == "PROCESSED")
    elif not include_rejected and is_asking_synthetic:
        stmt = stmt.where(StageCScene.status.in_(["PROCESSED", "SYNTHETIC_EXCLUDED"]))

    if min_valid_fraction is not None:
        stmt = stmt.where(StageCScene.valid_pixel_fraction >= min_valid_fraction)

    records = db.execute(stmt).scalars().all()

    # Query count of provisional hotspots per scene
    hotspot_counts_q = (
        select(
            StageCProvisionalHotspot.scene_id,
            func.count(StageCProvisionalHotspot.pixel_id).label("cnt"),
        )
        .group_by(StageCProvisionalHotspot.scene_id)
    )
    hotspot_counts = dict(db.execute(hotspot_counts_q).all())

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    req_source = source.strip().lower()

    items: list[SceneMetadataItem] = []
    seen_ids: set[str] = set()

    for r in records:
        is_synth = _is_scene_synthetic(r)
        record_source = "SYNTHETIC TEST DATA" if is_synth else "landsat_l2"

        if req_source == "landsat_l2" and is_synth:
            continue
        elif req_source in ("synthetic test data", "synthetic", "mock"):
            if not is_synth:
                continue
        elif req_source != "all" and record_source.lower() != req_source:
            continue

        seen_ids.add(r.scene_id)
        reg_record = reg_items.get(r.scene_id)

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

        # Rejection reason from registry or legacy status
        reason = None
        if reg_record and reg_record.rejection_reason:
            reason = reg_record.rejection_reason
        elif r.status == "REJECTED_CLOUDY":
            reason = f"Excessive cloud cover: {r.valid_pixel_fraction * 100:.1f}% clear over SMC boundary (< 40.0% threshold)"

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
                rejection_reason=reason,
                provisional_hotspots_count=hotspot_counts.get(r.scene_id, 0),
                cog_path=r.cog_path,
                source=record_source,
            )
        )

    # 3. If include_rejected is True, also include any registry records that weren't in stage_c_scenes
    if include_rejected:
        for reg_id, reg in reg_items.items():
            if reg_id in seen_ids:
                continue
            is_synth = _is_scene_synthetic(reg)
            record_source = "SYNTHETIC TEST DATA" if is_synth else "landsat_l2"
            if req_source == "landsat_l2" and is_synth:
                continue

            items.append(
                SceneMetadataItem(
                    scene_id=reg.scene_id,
                    acquisition_date=reg.acquisition_date.isoformat(),
                    acquisition_time=reg.acquisition_time.isoformat(),
                    acquisition_time_ist=reg.acquisition_time.strftime("%Y-%m-%d %H:%M:%S IST"),
                    sensor=reg.sensor,
                    path=reg.path,
                    row=reg.row,
                    cloud_cover=reg.cloud_cover,
                    valid_pixel_fraction=round(float(reg.valid_pixel_fraction or 0.0), 4),
                    mean_lst_c=round(float(reg.mean_lst_c), 2) if reg.mean_lst_c is not None else None,
                    max_lst_c=round(float(reg.max_lst_c), 2) if reg.max_lst_c is not None else None,
                    status=reg.status,
                    rejection_reason=reg.rejection_reason,
                    provisional_hotspots_count=hotspot_counts.get(reg.scene_id, 0),
                    cog_path=reg.cog_path,
                    source=record_source,
                )
            )
    items.sort(key=lambda x: (x.acquisition_date, x.acquisition_time), reverse=True)
    return items
