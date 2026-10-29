"""Stage D Intervention Candidate Materialization Service.

Reads canonical Stage C grid cells, HPI scores, and seasonal optical features from PostGIS,
evaluates hard feasibility constraints, calculates projected footprint areas in EPSG:32643,
and idempotently persists the canonical candidate catalog into `stage_d_intervention_candidates`.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import psycopg
from psycopg.rows import dict_row

from gis.interventions import (
    FeasibilityStatus,
    InterventionCandidate,
    InterventionType,
    RejectionReason,
)
from gis.interventions.cooling_effects import estimate_cooling_effect
from gis.interventions.costs import estimate_intervention_cost
from gis.interventions.feasibility import evaluate_candidate_feasibility
from gis.spatial.grid import get_cell_centroid, get_cell_polygon

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "stage_d"
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class MaterializationSummary:
    timestamp_utc: str
    total_cells_examined: int
    total_candidates_evaluated: int
    feasible_count: int
    rejected_count: int
    feasible_by_type: dict[str, int]
    rejected_by_reason: dict[str, int]
    catalog_fingerprint: str
    execution_duration_seconds: float


def get_db_connection() -> psycopg.Connection:
    """Connect to heatsense database using environment or .env configuration."""
    port = int(os.environ.get("POSTGRES_PORT", 5433))
    dbname = os.environ.get("POSTGRES_DB", "heatsense")
    user = os.environ.get("POSTGRES_USER", "heatsense")
    password = os.environ.get("POSTGRES_PASSWORD")
    host = os.environ.get("POSTGRES_HOST", "localhost")

    if not password:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            return psycopg.connect(
                db_url.replace("postgresql+psycopg://", "postgresql://"),
                autocommit=False,
            )
        raise ValueError("Database credentials not configured: POSTGRES_PASSWORD or DATABASE_URL required in .env.")

    return psycopg.connect(
        f"host={host} port={port} dbname={dbname} user={user} password={password}",
        autocommit=False,
    )


def calculate_candidate_footprint(
    intervention_type: InterventionType,
    clipped_cell_area_m2: float,
) -> tuple[float, int]:
    """
    Calculate defensible intervention usable footprint area in projected CRS EPSG:32643.

    Allocations are strictly bounded by the cell's actual clipped area inside the SMC boundary:
    - TREE_CANOPY: min(1500.0, clipped_area * 0.25), ~1 tree per 30 m²
    - COOL_ROOF: min(2000.0, clipped_area * 0.35)
    - GREEN_ROOF: min(1200.0, clipped_area * 0.20)
    - COOL_PAVEMENT: min(1000.0, clipped_area * 0.15)
    """
    if intervention_type == InterventionType.TREE_CANOPY:
        usable_area = min(1500.0, clipped_cell_area_m2 * 0.25)
        tree_count = max(1, round(usable_area / 30.0))
        return round(usable_area, 2), tree_count
    elif intervention_type == InterventionType.COOL_ROOF:
        usable_area = min(2000.0, clipped_cell_area_m2 * 0.35)
        return round(usable_area, 2), 0
    elif intervention_type == InterventionType.GREEN_ROOF:
        usable_area = min(1200.0, clipped_cell_area_m2 * 0.20)
        return round(usable_area, 2), 0
    elif intervention_type == InterventionType.COOL_PAVEMENT:
        usable_area = min(1000.0, clipped_cell_area_m2 * 0.15)
        return round(usable_area, 2), 0
    else:
        raise ValueError(f"Unsupported intervention type: {intervention_type}")


def materialize_stage_d_candidates(
    conn: psycopg.Connection | None = None,
    batch_size: int = 2000,
    spec_version: str = "v2.0",
    scoring_period: str = "2026_summer_operational",
) -> MaterializationSummary:
    """
    Generate and idempotently persist the complete canonical Stage D candidate catalog.

    Parameters
    ----------
    conn : psycopg.Connection, optional
        Database connection. If None, a new connection is established and closed.
    batch_size : int, default 2000
        Batch size for database upserts.
    spec_version : str, default 'v2.0'
        Stage C specification version.
    scoring_period : str, default '2026_summer_operational'
        Scoring period in stage_c_heat_priority_scores.

    Returns
    -------
    MaterializationSummary
        Structured audit report of the candidate materialization run.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    t0 = time.time()
    try:
        query = """
            SELECT
                c.pixel_id,
                c.row_idx,
                c.col_idx,
                c.latitude,
                c.longitude,
                c.smc_clipped_area_m2,
                c.is_centroid_inside,
                c.nearest_osm_place_name,
                s.heat_priority_score,
                s.is_chronic_hotspot,
                o.observed_lst_c,
                o.ndvi,
                o.ndbi,
                o.ndwi
            FROM stage_c_grid_cells c
            INNER JOIN stage_c_heat_priority_scores s
                ON c.pixel_id = s.pixel_id
                AND s.scoring_period = %s
                AND s.spec_version = %s
            LEFT JOIN stage_c_grid_observations o
                ON c.pixel_id = o.pixel_id
                AND o.year = 2026
                AND o.season = 'summer'
            ORDER BY c.row_idx, c.col_idx;
        """

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (scoring_period, spec_version))
            cells = cur.fetchall()

        total_cells = len(cells)
        if total_cells == 0:
            raise RuntimeError(
                f"No Stage C cells found for scoring_period='{scoring_period}' and spec_version='{spec_version}'."
            )

        candidate_records: list[tuple[Any, ...]] = []
        feasible_by_type: dict[str, int] = {t.value: 0 for t in InterventionType}
        rejected_by_reason: dict[str, int] = {r.value: 0 for r in RejectionReason}
        hasher = hashlib.sha256()

        target_types = [
            InterventionType.TREE_CANOPY,
            InterventionType.COOL_ROOF,
            InterventionType.GREEN_ROOF,
            InterventionType.COOL_PAVEMENT,
        ]

        for cell in cells:
            row = int(cell["row_idx"])
            col = int(cell["col_idx"])
            pixel_id = str(cell["pixel_id"])
            clipped_area = float(cell["smc_clipped_area_m2"])
            is_inside = bool(cell["is_centroid_inside"])
            raw_hpi = cell["heat_priority_score"]
            hpi_val = (float(raw_hpi) / 100.0) if raw_hpi is not None else None
            lst_val = float(cell["observed_lst_c"]) if cell["observed_lst_c"] is not None else 38.0
            is_chronic = bool(cell["is_chronic_hotspot"])
            zone_name = str(cell["nearest_osm_place_name"] or "Unassigned Zone")
            ndvi = float(cell["ndvi"]) if cell["ndvi"] is not None else 0.25
            ndbi = float(cell["ndbi"]) if cell["ndbi"] is not None else 0.05
            ndwi = float(cell["ndwi"]) if cell["ndwi"] is not None else -0.20

            poly = get_cell_polygon(row, col)
            poly_wkt = poly.wkt

            for itype in target_types:
                cand_id = f"CAND_{itype.value.upper()}_R{row:03d}_C{col:03d}"
                usable_area, tree_cnt = calculate_candidate_footprint(itype, clipped_area)

                cost_base, cost_min, cost_max, _ = estimate_intervention_cost(
                    intervention_type=itype,
                    usable_area_m2=usable_area,
                    tree_count=tree_cnt,
                )

                cooling_base, cooling_min, cooling_max, _ = estimate_cooling_effect(
                    intervention_type=itype,
                    usable_area_m2=usable_area,
                    tree_count=tree_cnt,
                    baseline_lst_c=lst_val,
                )

                # Construct temporary candidate to evaluate constraints
                lon, lat = get_cell_centroid(row, col)
                cand_obj = InterventionCandidate(
                    candidate_id=cand_id,
                    cell_id=pixel_id,
                    row=row,
                    col=col,
                    longitude=lon,
                    latitude=lat,
                    intervention_type=itype,
                    usable_area_m2=usable_area,
                    tree_count=tree_cnt,
                    baseline_hpi=hpi_val if hpi_val is not None else 0.5,
                    baseline_lst_c=lst_val,
                    is_chronic_hotspot=is_chronic,
                    administrative_zone=zone_name,
                    cost_inr=cost_base,
                    cost_inr_min=cost_min,
                    cost_inr_max=cost_max,
                    expected_cooling_c=cooling_base,
                    expected_cooling_c_min=cooling_min,
                    expected_cooling_c_max=cooling_max,
                )

                status, reason, _ = evaluate_candidate_feasibility(
                    candidate=cand_obj,
                    ndvi=ndvi,
                    ndbi=ndbi,
                    ndwi=ndwi,
                    is_inside_smc_boundary=is_inside,
                )

                if status == FeasibilityStatus.FEASIBLE:
                    feasible_by_type[itype.value] += 1
                rejected_by_reason[reason.value] += 1

                # Update fingerprint
                fingerprint_str = f"{cand_id}:{status.value}:{reason.value}:{usable_area}:{cost_base}:{cooling_base}"
                hasher.update(fingerprint_str.encode("utf-8"))

                candidate_records.append(
                    (
                        cand_id,
                        pixel_id,
                        itype.value,
                        usable_area,
                        tree_cnt,
                        round(cost_base, 2),
                        round(cost_min, 2),
                        round(cost_max, 2),
                        round(cooling_base, 3),
                        round(cooling_min, 3),
                        round(cooling_max, 3),
                        status.value,
                        reason.value,
                        round(hpi_val, 4) if hpi_val is not None else None,
                        round(lst_val, 2),
                        is_chronic,
                        zone_name,
                        "CALIBRATED_EMPIRICAL_MICROCLIMATE",
                        poly_wkt,
                    )
                )

        catalog_fingerprint = hasher.hexdigest()

        # Idempotent batch upsert into stage_d_intervention_candidates
        upsert_sql = """
            INSERT INTO stage_d_intervention_candidates (
                candidate_id, cell_id, intervention_type, usable_area_m2, tree_count,
                cost_inr, cost_inr_min, cost_inr_max, expected_cooling_c, expected_cooling_c_min, expected_cooling_c_max,
                feasibility_status, rejection_reason, baseline_hpi, baseline_lst_c, is_chronic_hotspot,
                administrative_zone, evidence_status, geometry
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326)
            ) ON CONFLICT (candidate_id) DO UPDATE SET
                usable_area_m2 = EXCLUDED.usable_area_m2,
                tree_count = EXCLUDED.tree_count,
                cost_inr = EXCLUDED.cost_inr,
                cost_inr_min = EXCLUDED.cost_inr_min,
                cost_inr_max = EXCLUDED.cost_inr_max,
                expected_cooling_c = EXCLUDED.expected_cooling_c,
                expected_cooling_c_min = EXCLUDED.expected_cooling_c_min,
                expected_cooling_c_max = EXCLUDED.expected_cooling_c_max,
                feasibility_status = EXCLUDED.feasibility_status,
                rejection_reason = EXCLUDED.rejection_reason,
                baseline_hpi = EXCLUDED.baseline_hpi,
                baseline_lst_c = EXCLUDED.baseline_lst_c,
                is_chronic_hotspot = EXCLUDED.is_chronic_hotspot,
                administrative_zone = EXCLUDED.administrative_zone,
                evidence_status = EXCLUDED.evidence_status,
                geometry = EXCLUDED.geometry;
        """

        with conn.transaction():
            with conn.cursor() as cur:
                for i in range(0, len(candidate_records), batch_size):
                    chunk = candidate_records[i : i + batch_size]
                    cur.executemany(upsert_sql, chunk)

        duration = round(time.time() - t0, 2)
        total_candidates = len(candidate_records)
        total_feasible = sum(feasible_by_type.values())
        total_rejected = total_candidates - total_feasible

        summary = MaterializationSummary(
            timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            total_cells_examined=total_cells,
            total_candidates_evaluated=total_candidates,
            feasible_count=total_feasible,
            rejected_count=total_rejected,
            feasible_by_type=feasible_by_type,
            rejected_by_reason=rejected_by_reason,
            catalog_fingerprint=catalog_fingerprint,
            execution_duration_seconds=duration,
        )

        # Export manifest to artifacts/stage_d/
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = ARTIFACTS_DIR / "stage_d_candidate_catalog_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2)

        return summary

    finally:
        if should_close:
            conn.close()
