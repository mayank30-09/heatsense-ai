"""Daily Discovery Job for Near-Real-Time Landsat Scenes over Surat SMC.

Automated NRT discovery job conforming to Problem 4:
- Queries Landsat 8/9 Level-2 scenes over Surat (WRS 148/45).
- Enforces idempotent registry transitions:
  discovered -> downloaded -> qa_passed -> scored -> published | rejected(reason).
- Evaluates QA clear percentage over the official SMC boundary.
- Scores provisional NRT hotspots without altering frozen HPI tables.
- Writes Cloud-Optimized GeoTIFFs to data/processed/scenes/.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.config import get_settings
from backend.app.db.models.stage_c import StageCSceneRegistry
from backend.app.db.session import SessionLocal
from gis.gee.latest_scene import create_synthetic_scene_array
from gis.gee.nrt_pipeline import (
    DEFAULT_CLEAR_THRESHOLD,
    process_scene_lifecycle,
    verify_wrs2_path_row_from_boundary,
)

logger = logging.getLogger("heatsense.discovery")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def run_discovery(
    mock: bool = False,
    dry_run: bool = False,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    target_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Execute scene discovery and ingestion."""
    settings = get_settings()
    threshold = clear_threshold or settings.nrt_min_valid_fraction
    path_val, row_val = verify_wrs2_path_row_from_boundary()
    logger.info("Running NRT discovery for Surat (WRS %d/%d, threshold: %.1f%%)", path_val, row_val, threshold * 100.0)

    session = SessionLocal()
    results = []
    try:
        if mock:
            date_str = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            d = date.fromisoformat(date_str)
            dt = datetime(d.year, d.month, d.day, 5, 43, 21, tzinfo=timezone.utc)
            scene_id = f"LC09_L2SP_148045_{date_str.replace('-', '')}_02_T1"
            sensor = "LANDSAT_9"

            lst, qa = create_synthetic_scene_array(valid_fraction=0.85, mean_temp=42.5)
            res = process_scene_lifecycle(
                session=session,
                scene_id=scene_id,
                sensor=sensor,
                acquisition_time=dt,
                acquisition_date=d,
                lst_array=lst,
                cloud_cover=10.0,
                qa_array=qa,
                clear_threshold=threshold,
                dry_run=dry_run,
            )
            results.append(res)
            logger.info("Mock scene processed: %s", json.dumps(res, default=str))
            return results

        # Live GEE Discovery
        try:
            from gis.gee.landsat_lst import initialize_earth_engine
            from gis.gee.latest_scene import discover_gee_scenes, fetch_gee_scene_arrays, get_last_ingested_watermark

            initialize_earth_engine()
            watermark = get_last_ingested_watermark(session)
            candidate_scenes = discover_gee_scenes(
                start_date=start_date,
                end_date=end_date,
                watermark_dt=watermark if not start_date else None,
            )
            logger.info("Discovered %d candidate GEE scenes", len(candidate_scenes))

            for sc in candidate_scenes:
                scene_id = sc["scene_id"]
                # Idempotency check: skip already published scenes
                existing = session.query(StageCSceneRegistry).filter_by(scene_id=scene_id).first()
                if existing and existing.status == "published":
                    logger.info("Scene %s already published; skipping.", scene_id)
                    continue

                lst, qa = fetch_gee_scene_arrays(sc["ee_image_id"])
                res = process_scene_lifecycle(
                    session=session,
                    scene_id=scene_id,
                    sensor=sc["sensor"],
                    acquisition_time=sc["acquisition_time"],
                    acquisition_date=sc["acquisition_date"],
                    lst_array=lst,
                    cloud_cover=sc.get("cloud_cover"),
                    qa_array=qa,
                    clear_threshold=threshold,
                    dry_run=dry_run,
                )
                results.append(res)
        except Exception as exc:
            logger.warning("Earth Engine live discovery could not be reached: %s", exc)
            logger.info("For automated local tests, use --mock flag.")

        return results
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="HEATSENSE AI Daily NRT Discovery Job")
    parser.add_argument("--mock", action="store_true", help="Process synthetic mock scene for offline testing")
    parser.add_argument("--dry-run", action="store_true", help="Run without persisting changes")
    parser.add_argument("--min-valid-fraction", type=float, default=DEFAULT_CLEAR_THRESHOLD, help="Clear threshold (0.0 - 1.0)")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--start-date", type=str, default=None, help="GEE query start date")
    parser.add_argument("--end-date", type=str, default=None, help="GEE query end date")
    args = parser.parse_args()

    run_discovery(
        mock=args.mock,
        dry_run=args.dry_run,
        clear_threshold=args.min_valid_fraction,
        target_date=args.date,
        start_date=args.start_date,
        end_date=args.end_date,
    )


if __name__ == "__main__":
    main()
