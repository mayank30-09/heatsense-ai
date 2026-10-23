"""Monitoring-Only Hotspot Comparison for HEATSENSE AI.

Compares the latest ingested near-real-time Landsat LST scene against the
authoritative same-season baseline for the top 100 Heat Priority Index (HPI) cells.

STRICT INVARIANTS:
1. Purely read-only and observational.
2. Never modifies HPI scores, trained ML models, or operational recommendations.
3. Explicitly records unobserved/cloud-masked cells without guessing or imputation.
4. Outputs reproducible JSON and Markdown reports to reports/monitoring/.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any
import numpy as np

# Ensure project root is in sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models.stage_c import (
    StageCGridCell,
    StageCGridObservation,
    StageCHeatPriorityScore,
    StageCScene,
    StageCSceneObservation,
)
from backend.app.db.session import SessionLocal

logger = logging.getLogger("heatsense.monitoring")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

DEFAULT_ANOMALY_THRESHOLD_C: float = 3.0
DEFAULT_OUTPUT_DIR: Path = Path("reports/monitoring")


def determine_season_from_month(month: int) -> str:
    """Map calendar month to Surat meteorological season."""
    if month in (3, 4, 5, 6):
        return "summer"
    elif month in (7, 8, 9):
        return "monsoon"
    elif month in (10, 11):
        return "post_monsoon"
    else:
        return "winter"


def run_hotspot_comparison(
    session: Session,
    scene_id: str | None = None,
    anomaly_threshold_c: float = DEFAULT_ANOMALY_THRESHOLD_C,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    """Compare top 100 hotspot cells between latest scene and same-season baseline."""
    # 1. Resolve Target Scene
    if scene_id:
        stmt_scene = select(StageCScene).where(StageCScene.scene_id == scene_id)
        target_scene = session.execute(stmt_scene).scalar_one_or_none()
        if not target_scene:
            logger.error("Requested scene '%s' not found in database.", scene_id)
            return None
    else:
        stmt_scene = (
            select(StageCScene)
            .where(StageCScene.status == "PROCESSED")
            .order_by(desc(StageCScene.acquisition_time))
            .limit(1)
        )
        target_scene = session.execute(stmt_scene).scalar_one_or_none()
        if not target_scene:
            logger.warning("No successfully processed scenes available for hotspot monitoring.")
            return None

    actual_scene_id = target_scene.scene_id
    acq_date = target_scene.acquisition_date
    acq_month = acq_date.month
    matched_season = determine_season_from_month(acq_month)
    baseline_year = 2025 if matched_season == "post_monsoon" else 2026

    logger.info(
        "Monitoring comparison for scene %s (%s, sensor: %s, matched season: %s)",
        actual_scene_id,
        acq_date.isoformat(),
        target_scene.sensor,
        matched_season,
    )

    # 2. Query Top 100 Hotspots from Stage C HPI Scores
    stmt_hpi = (
        select(
            StageCHeatPriorityScore.pixel_id,
            StageCHeatPriorityScore.heat_priority_score,
            StageCHeatPriorityScore.persistence_tier,
            StageCHeatPriorityScore.is_chronic_hotspot,
            StageCGridCell.latitude,
            StageCGridCell.longitude,
            StageCGridCell.nearest_osm_place_name,
        )
        .join(StageCGridCell, StageCHeatPriorityScore.pixel_id == StageCGridCell.pixel_id)
        .order_by(desc(StageCHeatPriorityScore.heat_priority_score))
        .limit(100)
    )
    top_hotspots = session.execute(stmt_hpi).all()
    if not top_hotspots:
        logger.error("Top 100 hotspot cells could not be retrieved from stage_c_heat_priority_scores.")
        return None

    pixel_ids = [h[0] for h in top_hotspots]

    # 3. Retrieve Baseline LST Observations for Same Season
    stmt_base = select(
        StageCGridObservation.pixel_id,
        StageCGridObservation.observed_lst_c,
    ).where(
        (StageCGridObservation.pixel_id.in_(pixel_ids))
        & (StageCGridObservation.season == matched_season)
        & (StageCGridObservation.year == baseline_year)
    )
    baseline_lookup = dict(session.execute(stmt_base).all())

    # 4. Retrieve Scene Observations
    stmt_obs = select(
        StageCSceneObservation.pixel_id,
        StageCSceneObservation.observed_lst_c,
        StageCSceneObservation.st_qa_k,
        StageCSceneObservation.is_valid,
    ).where(
        (StageCSceneObservation.scene_id == actual_scene_id)
        & (StageCSceneObservation.pixel_id.in_(pixel_ids))
    )
    scene_obs_lookup = {
        row[0]: {
            "lst_c": row[1],
            "st_qa_k": row[2],
            "is_valid": row[3],
        }
        for row in session.execute(stmt_obs).all()
    }

    # 5. Build Comparison Table
    cell_comparisons: list[dict[str, Any]] = []
    differences: list[float] = []
    valid_observed_count = 0
    cloud_masked_count = 0
    anomalous_cells_count = 0

    for idx, (p_id, hpi, tier, is_chronic, lat, lon, osm_name) in enumerate(top_hotspots, 1):
        base_lst = baseline_lookup.get(p_id)
        scene_info = scene_obs_lookup.get(p_id, {"lst_c": None, "st_qa_k": None, "is_valid": False})

        scene_lst = scene_info["lst_c"]
        is_valid = scene_info["is_valid"] and scene_lst is not None

        diff_c: float | None = None
        is_anomaly = False

        if is_valid and base_lst is not None:
            diff_c = round(float(scene_lst - base_lst), 2)
            differences.append(diff_c)
            valid_observed_count += 1
            if abs(diff_c) >= anomaly_threshold_c:
                is_anomaly = True
                anomalous_cells_count += 1
        else:
            cloud_masked_count += 1

        cell_comparisons.append(
            {
                "rank": idx,
                "pixel_id": p_id,
                "place_name": osm_name or "Unknown",
                "hpi_score": round(float(hpi), 2) if hpi is not None else None,
                "is_chronic": bool(is_chronic),
                "baseline_lst_c": round(float(base_lst), 2) if base_lst is not None else None,
                "scene_lst_c": round(float(scene_lst), 2) if scene_lst is not None else None,
                "difference_c": diff_c,
                "is_valid_scene_observation": is_valid,
                "is_anomaly": is_anomaly,
                "latitude": round(float(lat), 5),
                "longitude": round(float(lon), 5),
            }
        )

    # Summary Statistics
    valid_diffs = np.array(differences, dtype=np.float32) if differences else np.array([], dtype=np.float32)
    mean_diff = float(np.mean(valid_diffs)) if valid_diffs.size > 0 else 0.0
    max_diff = float(np.max(np.abs(valid_diffs))) if valid_diffs.size > 0 else 0.0

    report_payload: dict[str, Any] = {
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "scene_metadata": {
            "scene_id": actual_scene_id,
            "acquisition_date": acq_date.isoformat(),
            "sensor": target_scene.sensor,
            "cloud_cover": target_scene.cloud_cover,
            "valid_pixel_fraction": target_scene.valid_pixel_fraction,
            "matched_season": matched_season,
            "baseline_year": baseline_year,
        },
        "monitoring_parameters": {
            "hotspot_cell_count": len(top_hotspots),
            "anomaly_threshold_c": anomaly_threshold_c,
            "comparison_methodology": "Cell-to-cell absolute difference against same-season baseline",
        },
        "summary": {
            "valid_observed_cells": valid_observed_count,
            "cloud_masked_or_missing_cells": cloud_masked_count,
            "coverage_percentage": round(valid_observed_count / len(top_hotspots) * 100.0, 1),
            "mean_difference_c": round(mean_diff, 2),
            "max_absolute_difference_c": round(max_diff, 2),
            "anomalous_cells_count": anomalous_cells_count,
        },
        "cell_comparisons": cell_comparisons,
        "governance_notice": (
            "This report is for real-time monitoring and situational awareness only. "
            "Single-scene observations are strictly isolated and do NOT alter frozen operational "
            "HPI scores, trained ML models, or Stage D intervention recommendations."
        ),
    }

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = acq_date.isoformat()
        clean_scene_slug = actual_scene_id.replace("/", "_")

        # 1. JSON Report
        json_path = output_dir / f"hotspot_comparison_{date_str}_{clean_scene_slug}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2)

        # 2. Markdown Summary Report
        md_path = output_dir / f"hotspot_comparison_{date_str}_{clean_scene_slug}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Landsat NRT Hotspot Monitoring Report: {actual_scene_id}\n\n")
            f.write(f"- **Acquisition Date:** {acq_date.isoformat()}\n")
            f.write(f"- **Sensor:** {target_scene.sensor}\n")
            f.write(f"- **Matched Baseline Season:** {matched_season} ({baseline_year})\n")
            f.write(f"- **Valid Top-100 Coverage:** {valid_observed_count}/100 ({report_payload['summary']['coverage_percentage']}%)\n")
            f.write(f"- **Mean Difference:** {mean_diff:+.2f}°C (Max Abs Diff: {max_diff:.2f}°C)\n")
            f.write(f"- **Anomalies (|Δ| ≥ {anomaly_threshold_c}°C):** {anomalous_cells_count} cells\n\n")
            f.write("> **Governance Invariant:** Single-scene observations are observational only and do not alter frozen HPI v2.0 scores or ML models.\n\n")

            f.write("### Top 20 Hotspot Cells Comparison Sample\n\n")
            f.write("| Rank | Pixel ID | Location | HPI | Chronic? | Baseline LST | Scene LST | Δ LST (°C) | Status |\n")
            f.write("|---|---|---|---|---|---|---|---|---|\n")
            for c in cell_comparisons[:20]:
                diff_str = f"{c['difference_c']:+.2f}" if c['difference_c'] is not None else "N/A"
                scene_str = f"{c['scene_lst_c']:.2f}°C" if c['scene_lst_c'] is not None else "Cloud Masked"
                base_str = f"{c['baseline_lst_c']:.2f}°C" if c['baseline_lst_c'] is not None else "N/A"
                status_str = "⚠️ ANOMALY" if c["is_anomaly"] else ("✓ VALID" if c["is_valid_scene_observation"] else "☁️ CLOUDY")
                f.write(
                    f"| {c['rank']} | `{c['pixel_id']}` | {c['place_name']} | {c['hpi_score']} | "
                    f"{'Yes' if c['is_chronic'] else 'No'} | {base_str} | {scene_str} | {diff_str} | {status_str} |\n"
                )

        logger.info("Saved monitoring report to %s and %s", json_path, md_path)

    return report_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="HEATSENSE AI Top-100 Hotspot LST Monitoring")
    parser.add_argument("--scene-id", type=str, default=None, help="Target scene ID (default: latest processed scene)")
    parser.add_argument("--anomaly-threshold", type=float, default=DEFAULT_ANOMALY_THRESHOLD_C, help="Anomaly difference threshold in °C")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Report destination directory")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing files to disk")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        report = run_hotspot_comparison(
            session=session,
            scene_id=args.scene_id,
            anomaly_threshold_c=args.anomaly_threshold,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        )
        if report:
            summary = report["summary"]
            print("\n=======================================================")
            print("HEATSENSE AI Hotspot Monitoring Summary")
            print("=======================================================")
            print(f"Scene ID:               {report['scene_metadata']['scene_id']}")
            print(f"Acquisition Date:       {report['scene_metadata']['acquisition_date']}")
            print(f"Valid Cells in Top 100: {summary['valid_observed_cells']}/100 ({summary['coverage_percentage']}%)")
            print(f"Cloud/Missing Cells:    {summary['cloud_masked_or_missing_cells']}")
            print(f"Mean Difference:        {summary['mean_difference_c']:+.2f}°C")
            print(f"Max Absolute Diff:      {summary['max_absolute_difference_c']:.2f}°C")
            print(f"Anomalous Cells:        {summary['anomalous_cells_count']}")
            print("=======================================================\n")
    finally:
        session.close()


if __name__ == "__main__":
    main()
