"""Near-Real-Time Landsat LST Pipeline: Scene Discovery, Filtering, Export & Ingestion.

Discovers Landsat 8 and Landsat 9 Collection 2, Tier 1, Level 2 scenes for Surat (WRS 148/45),
enforces SMC boundary constraints, filters by persistent database ingestion watermark,
evaluates QA_PIXEL / QA_RADSAT validity against the canonical 49,747 SMC grid cells,
exports accepted scenes to Cloud-Optimized GeoTIFFs (data/processed/scenes/<YYYY-MM-DD>.tif),
and idempotently ingests per-pixel observations into PostGIS (stage_c_scene_observations).
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any
import sys

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
import rasterio
from rasterio.enums import Resampling
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.app.db.models.stage_c import (
    StageCGridCell,
    StageCScene,
    StageCSceneObservation,
)
from backend.app.db.session import SessionLocal
from gis.gee.landsat_lst import (
    BOUNDARY_FILE,
    PROJECT_ID,
    load_surat_boundary,
    mask_landsat_l2,
    scale_lst,
)
from gis.spatial.grid import (
    CANONICAL_SMC_CELL_COUNT,
    GRID_CRS,
    GRID_HEIGHT,
    GRID_WIDTH,
    PIXEL_SIZE,
    build_affine_transform,
)

logger = logging.getLogger("heatsense.nrt")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Authoritative spatial and processing parameters
SURAT_WRS_PATH: int = 148
SURAT_WRS_ROW: int = 45
DEFAULT_MIN_VALID_FRACTION: float = 0.60
NODATA_VALUE: float = -9999.0
DEFAULT_SCENES_DIR: Path = Path("data/processed/scenes")
DEFAULT_MOCK_SCENES_DIR: Path = Path("data/processed/mock_scenes")


def get_last_ingested_watermark(session: Session) -> datetime | None:
    """Query database for the latest successfully ingested scene acquisition timestamp.

    A failed or rejected scene never advances this watermark.
    """
    stmt = (
        select(func.max(StageCScene.acquisition_time))
        .where(StageCScene.status == "PROCESSED")
    )
    result = session.execute(stmt).scalar_one_or_none()
    return result


def normalize_acquisition_timestamp(
    system_time_start: int | None = None,
    scene_center_time: str | None = None,
    date_acquired: str | None = None,
) -> tuple[datetime, date]:
    """Derive timezone-aware UTC datetime and date from Landsat metadata.

    Landsat Collection 2 metadata provides:
    1. 'system:time_start': Epoch milliseconds (integer).
    2. 'SCENE_CENTER_TIME': UTC time string e.g. '05:43:21.123456Z'.
    3. 'DATE_ACQUIRED': 'YYYY-MM-DD' date string.
    """
    if system_time_start is not None and system_time_start > 0:
        dt = datetime.fromtimestamp(system_time_start / 1000.0, tz=timezone.utc)
        return dt, dt.date()

    if date_acquired and scene_center_time:
        clean_time = scene_center_time.strip().rstrip("Z")
        time_part = clean_time.split(".")[0]
        iso_str = f"{date_acquired.strip()}T{time_part}+00:00"
        dt = datetime.fromisoformat(iso_str)
        return dt, dt.date()

    if date_acquired:
        d = date.fromisoformat(date_acquired.strip())
        dt = datetime(d.year, d.month, d.day, 5, 0, 0, tzinfo=timezone.utc)
        return dt, d

    now = datetime.now(timezone.utc)
    return now, now.date()


def determine_collision_safe_cog_path(
    output_dir: Path,
    acquisition_date: date,
    sensor: str,
    scene_id: str,
    existing_scenes: set[str] | None = None,
) -> Path:
    """Determine a deterministic, collision-safe file path for the scene COG.

    Canonical naming: data/processed/scenes/<YYYY-MM-DD>.tif.
    If multiple scenes share the same acquisition date (e.g. Landsat 8 & Landsat 9
    or orbital overlaps), collision is prevented by appending sensor/scene_id.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = acquisition_date.isoformat()
    canonical_name = f"{date_str}.tif"
    canonical_path = output_dir / canonical_name

    # If canonical file does not exist, use it
    if not canonical_path.exists():
        return canonical_path

    # Check sidecar or metadata to see if it's the exact same scene
    sidecar_path = output_dir / f"{date_str}.json"
    if sidecar_path.exists():
        try:
            with open(sidecar_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                if meta.get("scene_id") == scene_id:
                    return canonical_path
        except Exception:
            pass

    # Collision detected: construct sensor-qualified name
    sensor_slug = sensor.lower().replace(" ", "_").replace("-", "_")
    qualified_name = f"{date_str}_{sensor_slug}.tif"
    qualified_path = output_dir / qualified_name

    if not qualified_path.exists():
        return qualified_path

    # Secondary collision: append clean scene ID
    clean_scene_id = scene_id.replace("/", "_")
    return output_dir / f"{date_str}_{sensor_slug}_{clean_scene_id}.tif"


def calculate_valid_pixel_fraction(
    lst_array: np.ndarray,
    canonical_cells: list[tuple[str, int, int]],
) -> tuple[float, int, int]:
    """Calculate valid-pixel fraction over the canonical 49,747 SMC grid cells.

    Returns:
        (valid_fraction, valid_count, total_count)
    """
    total_cells = len(canonical_cells)
    if total_cells == 0:
        return 0.0, 0, 0

    valid_count = 0
    for _, row, col in canonical_cells:
        if 0 <= row < lst_array.shape[0] and 0 <= col < lst_array.shape[1]:
            val = float(lst_array[row, col])
            if (
                np.isfinite(val)
                and val != NODATA_VALUE
                and 0.0 < val < 100.0
            ):
                valid_count += 1

    valid_fraction = float(valid_count / total_cells)
    return valid_fraction, valid_count, total_cells


def export_scene_cog(
    output_path: Path,
    lst_array: np.ndarray,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Export 2D LST Celsius array to Cloud-Optimized GeoTIFF format.

    Uses DEFLATE compression, 256x256 internal tiling, and built-in overviews.
    Writes a companion JSON sidecar with scene provenance.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    transform = build_affine_transform()

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": NODATA_VALUE,
        "width": GRID_WIDTH,
        "height": GRID_HEIGHT,
        "count": 1,
        "crs": GRID_CRS,
        "transform": transform,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
    }

    clean_arr = lst_array.astype(np.float32).copy()
    invalid_mask = ~np.isfinite(clean_arr) | (clean_arr <= 0.0) | (clean_arr >= 100.0)
    clean_arr[invalid_mask] = NODATA_VALUE

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(clean_arr, 1)
        dst.set_band_description(1, "LST_C")
        dst.build_overviews([2, 4, 8, 16], Resampling.average)
        dst.update_tags(ns="rio_overview", resampling="average")

    # Write companion sidecar metadata
    if metadata:
        sidecar_path = output_path.with_suffix(".json")
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)

    return output_path


def validate_cog(cog_path: Path) -> bool:
    """Verify that the generated raster is a valid Cloud-Optimized GeoTIFF."""
    if not cog_path.exists():
        return False
    try:
        with rasterio.open(cog_path) as src:
            if src.count != 1:
                return False
            if src.width != GRID_WIDTH or src.height != GRID_HEIGHT:
                return False
            if src.crs is None or src.crs.to_string() != GRID_CRS:
                return False
            # Check overviews
            overviews = src.overviews(1)
            if not overviews:
                return False
        return True
    except Exception as exc:
        logger.error("COG validation failed for %s: %s", cog_path, exc)
        return False


def get_canonical_grid_cells(session: Session) -> list[tuple[str, int, int]]:
    """Retrieve the authoritative 49,747 SMC grid cells (pixel_id, row_idx, col_idx)."""
    stmt = (
        select(StageCGridCell.pixel_id, StageCGridCell.row_idx, StageCGridCell.col_idx)
        .where(StageCGridCell.is_centroid_inside.is_(True))
        .order_by(StageCGridCell.pixel_id)
    )
    cells = session.execute(stmt).all()
    return [(c[0], c[1], c[2]) for c in cells]


def ingest_scene_observations(
    session: Session,
    scene_id: str,
    lst_array: np.ndarray,
    canonical_cells: list[tuple[str, int, int]],
    qa_array: np.ndarray | None = None,
    batch_size: int = 5000,
) -> int:
    """Idempotently insert per-pixel observations into stage_c_scene_observations."""
    rows: list[dict[str, Any]] = []

    for pixel_id, row, col in canonical_cells:
        if 0 <= row < lst_array.shape[0] and 0 <= col < lst_array.shape[1]:
            val = float(lst_array[row, col])
            is_valid = bool(
                np.isfinite(val)
                and val != NODATA_VALUE
                and 0.0 < val < 100.0
            )
            qa_val = None
            if qa_array is not None and 0 <= row < qa_array.shape[0] and 0 <= col < qa_array.shape[1]:
                q = float(qa_array[row, col])
                if np.isfinite(q) and q > 0.0:
                    qa_val = round(q, 3)

            rows.append(
                {
                    "scene_id": scene_id,
                    "pixel_id": pixel_id,
                    "observed_lst_c": round(val, 2) if is_valid else None,
                    "st_qa_k": qa_val,
                    "is_valid": is_valid,
                }
            )

    inserted = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        stmt = pg_insert(StageCSceneObservation).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["scene_id", "pixel_id"],
            set_={
                "observed_lst_c": stmt.excluded.observed_lst_c,
                "st_qa_k": stmt.excluded.st_qa_k,
                "is_valid": stmt.excluded.is_valid,
            },
        )
        session.execute(stmt)
        inserted += len(chunk)

    return inserted


def process_scene_record(
    session: Session,
    scene_id: str,
    acquisition_time: datetime,
    acquisition_date: date,
    sensor: str,
    lst_array: np.ndarray,
    cloud_cover: float | None = None,
    min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION,
    output_dir: Path = DEFAULT_SCENES_DIR,
    qa_array: np.ndarray | None = None,
    source: str = "landsat_l2",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Evaluate, export, and ingest a single candidate Landsat scene.

    If valid pixel fraction is below threshold, records status='REJECTED_CLOUDY'
    in stage_c_scenes without advancing the successful watermark.
    """
    canonical_cells = get_canonical_grid_cells(session)
    valid_fraction, valid_count, total_cells = calculate_valid_pixel_fraction(
        lst_array, canonical_cells
    )

    valid_vals = [
        float(lst_array[r, c])
        for _, r, c in canonical_cells
        if np.isfinite(lst_array[r, c])
        and lst_array[r, c] != NODATA_VALUE
        and 0.0 < lst_array[r, c] < 100.0
    ]

    mean_lst = float(np.mean(valid_vals)) if valid_vals else None
    max_lst = float(np.max(valid_vals)) if valid_vals else None

    logger.info(
        "Scene %s (%s): valid pixels %d/%d (%.1f%%, min req: %.1f%%)",
        scene_id,
        acquisition_date.isoformat(),
        valid_count,
        total_cells,
        valid_fraction * 100.0,
        min_valid_fraction * 100.0,
    )

    if valid_fraction < min_valid_fraction:
        logger.warning(
            "Scene %s rejected due to cloud/invalid mask: %.1f%% < %.1f%%",
            scene_id,
            valid_fraction * 100.0,
            min_valid_fraction * 100.0,
        )
        if not dry_run:
            scene_record = StageCScene(
                scene_id=scene_id,
                acquisition_date=acquisition_date,
                acquisition_time=acquisition_time,
                sensor=sensor,
                path=SURAT_WRS_PATH,
                row=SURAT_WRS_ROW,
                cloud_cover=cloud_cover,
                valid_pixel_fraction=valid_fraction,
                mean_lst_c=mean_lst,
                max_lst_c=max_lst,
                status="REJECTED_CLOUDY",
                cog_path=None,
            )
            stmt = pg_insert(StageCScene).values(
                scene_id=scene_id,
                acquisition_date=acquisition_date,
                acquisition_time=acquisition_time,
                sensor=sensor,
                path=SURAT_WRS_PATH,
                row=SURAT_WRS_ROW,
                cloud_cover=cloud_cover,
                valid_pixel_fraction=valid_fraction,
                mean_lst_c=mean_lst,
                max_lst_c=max_lst,
                status="REJECTED_CLOUDY",
                cog_path=None,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["scene_id"],
                set_={
                    "valid_pixel_fraction": stmt.excluded.valid_pixel_fraction,
                    "status": stmt.excluded.status,
                },
            )
            session.execute(stmt)
            session.commit()

        return {
            "scene_id": scene_id,
            "status": "REJECTED_CLOUDY",
            "valid_pixel_fraction": valid_fraction,
            "mean_lst_c": mean_lst,
            "max_lst_c": max_lst,
            "message": "Scene rejected due to excessive cloud cover / invalid pixels.",
        }

    # Accepted scene: export COG
    cog_path = determine_collision_safe_cog_path(
        output_dir=output_dir,
        acquisition_date=acquisition_date,
        sensor=sensor,
        scene_id=scene_id,
    )

    meta = {
        "scene_id": scene_id,
        "acquisition_date": acquisition_date.isoformat(),
        "acquisition_time": acquisition_time.isoformat(),
        "sensor": sensor,
        "path": SURAT_WRS_PATH,
        "row": SURAT_WRS_ROW,
        "cloud_cover": cloud_cover,
        "valid_pixel_fraction": valid_fraction,
        "mean_lst_c": mean_lst,
        "max_lst_c": max_lst,
        "units": "Celsius",
        "spatial_resolution": "100m",
        "crs": GRID_CRS,
        "source": source,
    }

    if not dry_run:
        export_scene_cog(cog_path, lst_array, metadata=meta)
        if not validate_cog(cog_path):
            raise RuntimeError(f"Generated COG at {cog_path} failed validation.")

        # Ingest scene metadata
        scene_stmt = pg_insert(StageCScene).values(
            scene_id=scene_id,
            acquisition_date=acquisition_date,
            acquisition_time=acquisition_time,
            sensor=sensor,
            path=SURAT_WRS_PATH,
            row=SURAT_WRS_ROW,
            cloud_cover=cloud_cover,
            valid_pixel_fraction=valid_fraction,
            mean_lst_c=mean_lst,
            max_lst_c=max_lst,
            status="PROCESSED",
            cog_path=str(cog_path).replace("\\", "/"),
        )
        scene_stmt = scene_stmt.on_conflict_do_update(
            index_elements=["scene_id"],
            set_={
                "valid_pixel_fraction": scene_stmt.excluded.valid_pixel_fraction,
                "mean_lst_c": scene_stmt.excluded.mean_lst_c,
                "max_lst_c": scene_stmt.excluded.max_lst_c,
                "status": scene_stmt.excluded.status,
                "cog_path": scene_stmt.excluded.cog_path,
            },
        )
        session.execute(scene_stmt)

        # Ingest per-pixel observations
        obs_count = ingest_scene_observations(
            session=session,
            scene_id=scene_id,
            lst_array=lst_array,
            canonical_cells=canonical_cells,
            qa_array=qa_array,
        )
        session.commit()
        logger.info("Successfully ingested scene %s (%d observations)", scene_id, obs_count)

    return {
        "scene_id": scene_id,
        "status": "PROCESSED",
        "acquisition_date": acquisition_date.isoformat(),
        "acquisition_time": acquisition_time.isoformat(),
        "sensor": sensor,
        "valid_pixel_fraction": valid_fraction,
        "mean_lst_c": mean_lst,
        "max_lst_c": max_lst,
        "cog_path": str(cog_path).replace("\\", "/"),
        "source": source,
    }


def create_synthetic_scene_array(
    valid_fraction: float = 0.85,
    mean_temp: float = 42.0,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a deterministic synthetic LST and QA array for testing."""
    rng = np.random.default_rng(seed)
    lst = np.full((GRID_HEIGHT, GRID_WIDTH), NODATA_VALUE, dtype=np.float32)
    qa = np.full((GRID_HEIGHT, GRID_WIDTH), 0.0, dtype=np.float32)

    # Base thermal gradient
    y_coords, x_coords = np.mgrid[0:GRID_HEIGHT, 0:GRID_WIDTH]
    center_y, center_x = GRID_HEIGHT / 2.0, GRID_WIDTH / 2.0
    dist = np.sqrt((y_coords - center_y) ** 2 + (x_coords - center_x) ** 2)
    temp_grid = mean_temp + 5.0 * np.exp(-dist / 80.0) + rng.normal(0.0, 1.5, size=(GRID_HEIGHT, GRID_WIDTH))

    # Apply valid mask
    mask_rand = rng.uniform(0.0, 1.0, size=(GRID_HEIGHT, GRID_WIDTH))
    valid_mask = mask_rand < valid_fraction

    lst[valid_mask] = temp_grid[valid_mask]
    qa[valid_mask] = rng.uniform(0.8, 1.6, size=np.count_nonzero(valid_mask))

    return lst, qa


def discover_gee_scenes(
    start_date: str | None = None,
    end_date: str | None = None,
    watermark_dt: datetime | None = None,
) -> list[dict[str, Any]]:
    """Query Earth Engine for Landsat 8 and Landsat 9 scenes over Surat WRS 148/45.

    If Earth Engine is not initialized or credentials are missing, raises RuntimeError.
    """
    try:
        import ee
    except ImportError as exc:
        raise RuntimeError("earthengine-api is not installed.") from exc

    boundary = load_surat_boundary()

    if watermark_dt:
        start_str = watermark_dt.strftime("%Y-%m-%d")
    elif start_date:
        start_str = start_date
    else:
        start_str = "2026-01-01"

    end_str = end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    l8 = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(boundary)
        .filter(ee.Filter.eq("WRS_PATH", SURAT_WRS_PATH))
        .filter(ee.Filter.eq("WRS_ROW", SURAT_WRS_ROW))
        .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
        .filterDate(start_str, end_str)
        .map(mask_landsat_l2)
        .map(scale_lst)
    )
    l9 = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterBounds(boundary)
        .filter(ee.Filter.eq("WRS_PATH", SURAT_WRS_PATH))
        .filter(ee.Filter.eq("WRS_ROW", SURAT_WRS_ROW))
        .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
        .filterDate(start_str, end_str)
        .map(mask_landsat_l2)
        .map(scale_lst)
    )

    merged = l8.merge(l9).sort("system:time_start")
    count = merged.size().getInfo()
    logger.info("Discovered %d candidate Landsat scenes between %s and %s", count, start_str, end_str)

    scenes_info: list[dict[str, Any]] = []
    if count == 0:
        return scenes_info

    feature_list = merged.toList(count).getInfo()
    for feat in feature_list:
        props = feat.get("properties", {})
        scene_id = props.get("LANDSAT_PRODUCT_ID") or props.get("system:index")
        acq_time, acq_date = normalize_acquisition_timestamp(
            system_time_start=props.get("system:time_start"),
            scene_center_time=props.get("SCENE_CENTER_TIME"),
            date_acquired=props.get("DATE_ACQUIRED"),
        )
        scenes_info.append(
            {
                "scene_id": scene_id,
                "acquisition_time": acq_time,
                "acquisition_date": acq_date,
                "sensor": props.get("SPACECRAFT_ID", "LANDSAT"),
                "cloud_cover": props.get("CLOUD_COVER"),
                "ee_image_id": feat.get("id"),
            }
        )

    return scenes_info


def check_ingestion_freshness(session: Session, max_age_days: int = 20) -> tuple[bool, int, datetime | None]:
    """Check if the latest successfully ingested scene is within max_age_days.

    Returns:
        (is_fresh: bool, age_in_days: int, latest_dt: datetime | None)
    """
    watermark = get_last_ingested_watermark(session)
    if watermark is None:
        return False, 9999, None

    now = datetime.now(timezone.utc)
    if watermark.tzinfo is None:
        watermark = watermark.replace(tzinfo=timezone.utc)

    age_days = (now - watermark).days
    is_fresh = age_days <= max_age_days
    return is_fresh, age_days, watermark


def main() -> None:
    parser = argparse.ArgumentParser(description="HEATSENSE AI Near-Real-Time Landsat LST Ingestion")
    parser.add_argument("--mock", action="store_true", help="Ingest a synthetic scene for offline testing")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without writing COG or database rows")
    parser.add_argument("--min-valid-fraction", type=float, default=DEFAULT_MIN_VALID_FRACTION, help="Min valid fraction")
    parser.add_argument("--check-freshness-days", type=int, default=None, help="Fail if no scene ingested within N days")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD for synthetic/manual ingestion")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        # Freshness gate check
        if args.check_freshness_days is not None:
            is_fresh, age, latest_dt = check_ingestion_freshness(session, args.check_freshness_days)
            if not is_fresh:
                logger.error(
                    "FRESHNESS FAILURE: Latest scene ingested was %d days ago (%s), exceeding threshold of %d days.",
                    age,
                    latest_dt.isoformat() if latest_dt else "NEVER",
                    args.check_freshness_days,
                )
                raise SystemExit(1)
            logger.info("Freshness check PASSED: Latest scene is %d days old (<= %d days).", age, args.check_freshness_days)
            return

        watermark = get_last_ingested_watermark(session)
        logger.info("Current ingestion watermark: %s", watermark.isoformat() if watermark else "None (initial)")

        if args.mock:
            target_date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            d = date.fromisoformat(target_date_str)
            dt = datetime(d.year, d.month, d.day, 5, 43, 21, tzinfo=timezone.utc)
            scene_id = f"SYNTHETIC_LC09_L2SP_148045_{target_date_str.replace('-', '')}_02_T1"
            sensor = "LANDSAT_9"

            mock_dir = DEFAULT_MOCK_SCENES_DIR
            mock_dir.mkdir(parents=True, exist_ok=True)

            lst, qa = create_synthetic_scene_array(valid_fraction=0.88, mean_temp=43.5)
            result = process_scene_record(
                session=session,
                scene_id=scene_id,
                acquisition_time=dt,
                acquisition_date=d,
                sensor=sensor,
                lst_array=lst,
                cloud_cover=12.0,
                min_valid_fraction=args.min_valid_fraction,
                qa_array=qa,
                output_dir=mock_dir,
                source="SYNTHETIC TEST DATA",
                dry_run=args.dry_run,
            )
            result["source"] = "SYNTHETIC TEST DATA"
            result["warning"] = "SYNTHETIC TEST DATA: Excluded from default catalog /scenes queries."
            print(json.dumps(result, indent=2))
            return

        # Attempt Earth Engine live discovery
        try:
            scenes = discover_gee_scenes(watermark_dt=watermark)
            logger.info("Found %d new eligible GEE scenes", len(scenes))
        except Exception as exc:
            logger.warning("Earth Engine discovery could not run: %s", exc)
            logger.info("To test offline, invoke with --mock flag.")
            return

    finally:
        session.close()


if __name__ == "__main__":
    main()
