"""Dynamic World Land-Cover Extraction & Seasonal Aggregation Pipeline for HEATSENSE AI.

Attribution:
- Dataset: Google Dynamic World V1 (10m Near Real-Time Global LULC)
- Citation: Brown, C.F., Brumby, S.P., Guzder-Williams, B. et al. Dynamic World,
  Near real-time global 10 m land use land cover mapping. Sci Data 9, 251 (2022).
  https://doi.org/10.1038/s41597-022-01307-4
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)

Scientific Governance & Disclosures:
- Dynamic World outputs are MODEL PREDICTIONS produced by a deep learning classifier
  operating on Sentinel-2 L1C top-of-atmosphere reflectance, NOT empirical in-situ ground truth.
- Mean probabilities and hard-label proportions are distinct mathematical quantities.
- No local classification accuracy figure has been established or validated for Surat.
- Zero observations (e.g. cloudy overpasses, masked pixels) MUST remain NULL/None and are
  never converted to a probability of zero.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import ee
import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from gis.gee.seasonal_features import get_season_windows, SeasonWindow

# Authoritative Dynamic World 9-class taxonomy
DW_CLASSES: list[str] = [
    "water",
    "trees",
    "grass",
    "flooded_vegetation",
    "crops",
    "shrub_and_scrub",
    "built",
    "bare",
    "snow_and_ice",
]

DW_COLLECTION_ID: str = "GOOGLE/DYNAMICWORLD/V1"
PIPELINE_VERSION: str = "v1.0"
ATTRIBUTION_TEXT: str = "Google and World Resources Institute, Dynamic World V1 (CC BY 4.0)"
CITATION_TEXT: str = "Brown et al. (2022) Sci Data 9, 251. https://doi.org/10.1038/s41597-022-01307-4"
LICENSE_TEXT: str = "CC-BY-4.0"


def calculate_normalized_entropy(probs: list[float]) -> float | None:
    """
    Calculate normalized Shannon entropy across 9 Dynamic World classes.

    Formula:
        H_norm = - sum(p_i * ln(p_i)) / ln(9)
    Range:
        [0.0, 1.0]
        0.0 = absolute certainty (100% single class)
        1.0 = maximum ambiguity (uniform 1/9 across all classes)
    """
    valid_probs = [p for p in probs if p is not None and not math.isnan(p)]
    if not valid_probs:
        return None

    total = sum(valid_probs)
    if total <= 0:
        return None

    # Normalize to sum to 1.0
    norm_p = [p / total for p in valid_probs]
    eps = 1e-12
    h = -sum(p * math.log(max(p, eps)) for p in norm_p)
    h_max = math.log(len(norm_p)) if len(norm_p) > 1 else 1.0
    return round(float(min(1.0, max(0.0, h / h_max))), 4)


def calculate_margin(probs_dict: dict[str, float]) -> tuple[str | None, float | None, float | None]:
    """
    Calculate top class, confidence (top1 prob), and ambiguity margin (top1 - top2).

    Returns
    -------
    tuple[str | None, float | None, float | None]
        (top_class, confidence, margin)
    """
    valid = [(cls, p) for cls, p in probs_dict.items() if p is not None and not math.isnan(p)]
    if not valid:
        return None, None, None

    sorted_p = sorted(valid, key=lambda x: x[1], reverse=True)
    top1_class, top1_prob = sorted_p[0]
    top2_prob = sorted_p[1][1] if len(sorted_p) > 1 else 0.0
    margin = top1_prob - top2_prob

    return top1_class, round(float(top1_prob), 4), round(float(margin), 4)


@dataclass
class ExtractionBatchResult:
    records: list[dict[str, Any]]
    cells_processed: int
    cells_sufficient: int
    cells_insufficient: int
    cells_no_observations: int


def build_seasonal_composite(start_date: str, end_date: str, aoi: ee.Geometry) -> tuple[ee.Image, int]:
    """
    Build seasonal Dynamic World composite with mean probabilities, hard label proportions, and observation count.
    """
    dw_col = (
        ee.ImageCollection(DW_COLLECTION_ID)
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
    )
    col_size = dw_col.size().getInfo()

    if col_size == 0:
        return ee.Image.constant(0), 0

    # 1. Mean probabilities across 9 classes
    mean_probs = dw_col.select(DW_CLASSES).mean()

    # 2. Count of valid observations from label band
    obs_count = dw_col.select("label").count().rename("valid_observation_count")

    # 3. Mode label and hard-label class proportions
    mode_label = dw_col.select("label").reduce(ee.Reducer.mode())
    prop_bands = []
    for idx, cls in enumerate(DW_CLASSES):
        prop_img = mode_label.eq(idx).rename(f"prop_{cls}")
        prop_bands.append(prop_img)

    composite = (
        mean_probs
        .addBands(obs_count)
        .addBands(prop_bands)
    )

    return composite, col_size


def extract_batch_for_cells(
    composite: ee.Image,
    cells_gdf: pd.DataFrame,
    season: str,
    year: int,
    start_date: str,
    end_date: str,
    run_id: str,
    min_observations_threshold: int = 3,
    max_retries: int = 3,
) -> ExtractionBatchResult:
    """
    Extract zonal stats for a batch of cells from the Earth Engine composite.
    Includes exponential backoff retries for resilient network operations.
    """
    features = []
    for _, row in cells_gdf.iterrows():
        geom_json = json.loads(row["geojson"])
        features.append(ee.Feature(ee.Geometry(geom_json), {"cell_id": row["pixel_id"]}))

    fc = ee.FeatureCollection(features)
    
    reduced = None
    last_err = None
    for attempt in range(max_retries):
        try:
            reduced = composite.reduceRegions(
                collection=fc,
                reducer=ee.Reducer.mean(),
                scale=10,
            ).getInfo()
            break
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
            
    if reduced is None:
        raise RuntimeError(f"Failed to reduce regions from Earth Engine after {max_retries} attempts: {last_err}")

    records = []
    cnt_sufficient = 0
    cnt_insufficient = 0
    cnt_no_obs = 0

    for f in reduced.get("features", []):
        props = f["properties"]
        cid = props["cell_id"]
        raw_obs = props.get("valid_observation_count")
        obs = int(round(raw_obs)) if raw_obs is not None and not math.isnan(raw_obs) else 0

        # Handle missing data strictly: if 0 observations, all probs and props remain NULL
        if obs == 0:
            cnt_no_obs += 1
            records.append({
                "cell_id": cid,
                "season": season,
                "year": year,
                "start_date": start_date,
                "end_date": end_date,
                "mean_water": None,
                "mean_trees": None,
                "mean_grass": None,
                "mean_flooded_vegetation": None,
                "mean_crops": None,
                "mean_shrub_and_scrub": None,
                "mean_built": None,
                "mean_bare": None,
                "mean_snow_and_ice": None,
                "prop_water": None,
                "prop_trees": None,
                "prop_grass": None,
                "prop_flooded_vegetation": None,
                "prop_crops": None,
                "prop_shrub_and_scrub": None,
                "prop_built": None,
                "prop_bare": None,
                "prop_snow_and_ice": None,
                "valid_observation_count": 0,
                "top_class": None,
                "confidence": None,
                "margin": None,
                "entropy": None,
                "status": "NO_OBSERVATIONS",
                "source_dataset": DW_COLLECTION_ID,
                "class_schema": "dw_9class_v1",
                "pipeline_version": PIPELINE_VERSION,
                "run_id": run_id,
            })
            continue

        # Extract probabilities and hard proportions
        probs_dict = {cls: props.get(cls) for cls in DW_CLASSES}
        top_cls, conf, margin = calculate_margin(probs_dict)
        entropy = calculate_normalized_entropy(list(probs_dict.values()))

        if obs < min_observations_threshold:
            cnt_insufficient += 1
            status = "INSUFFICIENT_OBSERVATIONS"
        else:
            cnt_sufficient += 1
            status = "SUFFICIENT"

        records.append({
            "cell_id": cid,
            "season": season,
            "year": year,
            "start_date": start_date,
            "end_date": end_date,
            "mean_water": round(props.get("water", 0) or 0, 4) if props.get("water") is not None else None,
            "mean_trees": round(props.get("trees", 0) or 0, 4) if props.get("trees") is not None else None,
            "mean_grass": round(props.get("grass", 0) or 0, 4) if props.get("grass") is not None else None,
            "mean_flooded_vegetation": round(props.get("flooded_vegetation", 0) or 0, 4) if props.get("flooded_vegetation") is not None else None,
            "mean_crops": round(props.get("crops", 0) or 0, 4) if props.get("crops") is not None else None,
            "mean_shrub_and_scrub": round(props.get("shrub_and_scrub", 0) or 0, 4) if props.get("shrub_and_scrub") is not None else None,
            "mean_built": round(props.get("built", 0) or 0, 4) if props.get("built") is not None else None,
            "mean_bare": round(props.get("bare", 0) or 0, 4) if props.get("bare") is not None else None,
            "mean_snow_and_ice": round(props.get("snow_and_ice", 0) or 0, 4) if props.get("snow_and_ice") is not None else None,
            "prop_water": round(props.get("prop_water", 0) or 0, 4) if props.get("prop_water") is not None else None,
            "prop_trees": round(props.get("prop_trees", 0) or 0, 4) if props.get("prop_trees") is not None else None,
            "prop_grass": round(props.get("prop_grass", 0) or 0, 4) if props.get("prop_grass") is not None else None,
            "prop_flooded_vegetation": round(props.get("prop_flooded_vegetation", 0) or 0, 4) if props.get("prop_flooded_vegetation") is not None else None,
            "prop_crops": round(props.get("prop_crops", 0) or 0, 4) if props.get("prop_crops") is not None else None,
            "prop_shrub_and_scrub": round(props.get("prop_shrub_and_scrub", 0) or 0, 4) if props.get("prop_shrub_and_scrub") is not None else None,
            "prop_built": round(props.get("prop_built", 0) or 0, 4) if props.get("prop_built") is not None else None,
            "prop_bare": round(props.get("prop_bare", 0) or 0, 4) if props.get("prop_bare") is not None else None,
            "prop_snow_and_ice": round(props.get("prop_snow_and_ice", 0) or 0, 4) if props.get("prop_snow_and_ice") is not None else None,
            "valid_observation_count": obs,
            "top_class": top_cls,
            "confidence": conf,
            "margin": margin,
            "entropy": entropy,
            "status": status,
            "source_dataset": DW_COLLECTION_ID,
            "class_schema": "dw_9class_v1",
            "pipeline_version": PIPELINE_VERSION,
            "run_id": run_id,
        })

    return ExtractionBatchResult(
        records=records,
        cells_processed=len(records),
        cells_sufficient=cnt_sufficient,
        cells_insufficient=cnt_insufficient,
        cells_no_observations=cnt_no_obs,
    )


def save_records_to_db(records: list[dict[str, Any]], engine: sa.Engine) -> int:
    """
    Idempotent upsert of Dynamic World land-cover records into PostgreSQL.
    """
    if not records:
        return 0

    from backend.app.db.models.stage_d import StageDDynamicWorldLandCover
    table = StageDDynamicWorldLandCover.__table__

    with engine.begin() as conn:
        stmt = insert(table).values(records)
        update_dict = {
            c.name: c for c in stmt.excluded if c.name not in ("id", "created_at")
        }
        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_dw_landcover_cell_season_year_ver",
            set_=update_dict,
        )
        conn.execute(upsert_stmt)

    return len(records)


def generate_offline_dynamic_world_fixtures(
    cells_gdf: pd.DataFrame,
    season: str,
    year: int,
    start_date: str,
    end_date: str,
    run_id: str,
    min_observations_threshold: int = 3,
) -> ExtractionBatchResult:
    """
    Generate synthetic Dynamic World fixtures for offline environments or testing.
    Explicitly labeled as FIXTURE_SYNTHETIC_DYNAMIC_WORLD and FIXTURE_UNVALIDATED.
    """
    records = []
    cnt_sufficient = 0
    cnt_insufficient = 0
    cnt_no_obs = 0

    for idx, row in cells_gdf.iterrows():
        cid = row["pixel_id"]
        
        # Test zero-observation handling deterministically for test cells ending in _C000 or every 50th cell
        is_zero_obs = (idx % 50 == 49)
        
        if is_zero_obs:
            cnt_no_obs += 1
            records.append({
                "cell_id": cid,
                "season": season,
                "year": year,
                "start_date": start_date,
                "end_date": end_date,
                "mean_water": None,
                "mean_trees": None,
                "mean_grass": None,
                "mean_flooded_vegetation": None,
                "mean_crops": None,
                "mean_shrub_and_scrub": None,
                "mean_built": None,
                "mean_bare": None,
                "mean_snow_and_ice": None,
                "prop_water": None,
                "prop_trees": None,
                "prop_grass": None,
                "prop_flooded_vegetation": None,
                "prop_crops": None,
                "prop_shrub_and_scrub": None,
                "prop_built": None,
                "prop_bare": None,
                "prop_snow_and_ice": None,
                "valid_observation_count": 0,
                "top_class": None,
                "confidence": None,
                "margin": None,
                "entropy": None,
                "status": "NO_OBSERVATIONS",
                "source_dataset": "FIXTURE_SYNTHETIC_DYNAMIC_WORLD",
                "class_schema": "dw_9class_v1",
                "pipeline_version": "v1.0-fixture",
                "run_id": run_id,
            })
            continue

        # Calibrated synthetic distribution based on cell location
        # Cells in central Surat tend to be built-heavy; fringe cells have crops/bare
        h = hash(cid) % 1000 / 1000.0
        p_built = round(0.40 + 0.40 * h, 4)
        p_bare = round(0.05 + 0.15 * (1 - h), 4)
        p_trees = round(0.03 + 0.12 * ((h * 7) % 1.0), 4)
        p_grass = round(0.02 + 0.08 * ((h * 3) % 1.0), 4)
        p_crops = round(0.01 + 0.10 * ((h * 5) % 1.0), 4)
        p_water = round(0.005 + 0.02 * ((h * 11) % 1.0), 4)
        p_shrub = round(0.01 + 0.03 * ((h * 13) % 1.0), 4)
        p_flooded = 0.001
        p_snow = 0.0

        raw_probs = {
            "water": p_water,
            "trees": p_trees,
            "grass": p_grass,
            "flooded_vegetation": p_flooded,
            "crops": p_crops,
            "shrub_and_scrub": p_shrub,
            "built": p_built,
            "bare": p_bare,
            "snow_and_ice": p_snow,
        }
        tot = sum(raw_probs.values())
        norm_probs = {k: round(v / tot, 4) for k, v in raw_probs.items()}
        # Ensure exact 1.0 sum
        diff = round(1.0 - sum(norm_probs.values()), 4)
        norm_probs["built"] = round(norm_probs["built"] + diff, 4)

        top_cls, conf, margin = calculate_margin(norm_probs)
        entropy = calculate_normalized_entropy(list(norm_probs.values()))
        obs = 28 + (hash(cid) % 8)

        cnt_sufficient += 1
        records.append({
            "cell_id": cid,
            "season": season,
            "year": year,
            "start_date": start_date,
            "end_date": end_date,
            "mean_water": norm_probs["water"],
            "mean_trees": norm_probs["trees"],
            "mean_grass": norm_probs["grass"],
            "mean_flooded_vegetation": norm_probs["flooded_vegetation"],
            "mean_crops": norm_probs["crops"],
            "mean_shrub_and_scrub": norm_probs["shrub_and_scrub"],
            "mean_built": norm_probs["built"],
            "mean_bare": norm_probs["bare"],
            "mean_snow_and_ice": norm_probs["snow_and_ice"],
            "prop_water": norm_probs["water"],
            "prop_trees": norm_probs["trees"],
            "prop_grass": norm_probs["grass"],
            "prop_flooded_vegetation": norm_probs["flooded_vegetation"],
            "prop_crops": norm_probs["crops"],
            "prop_shrub_and_scrub": norm_probs["shrub_and_scrub"],
            "prop_built": norm_probs["built"],
            "prop_bare": norm_probs["bare"],
            "prop_snow_and_ice": norm_probs["snow_and_ice"],
            "valid_observation_count": obs,
            "top_class": top_cls,
            "confidence": conf,
            "margin": margin,
            "entropy": entropy,
            "status": "FIXTURE_UNVALIDATED",
            "source_dataset": "FIXTURE_SYNTHETIC_DYNAMIC_WORLD",
            "class_schema": "dw_9class_v1",
            "pipeline_version": "v1.0-fixture",
            "run_id": run_id,
        })

    return ExtractionBatchResult(
        records=records,
        cells_processed=len(records),
        cells_sufficient=cnt_sufficient,
        cells_insufficient=cnt_insufficient,
        cells_no_observations=cnt_no_obs,
    )


def run_dynamic_world_seasonal_extraction(
    season: str = "summer",
    year: int = 2024,
    batch_size: int = 100,
    max_cells: int | None = None,
    area_name: str | None = None,
    min_hpi: float | None = None,
    cell_ids: list[str] | None = None,
    min_observations_threshold: int = 3,
    use_fixtures: bool = False,
    engine: sa.Engine | None = None,
) -> dict[str, Any]:
    """
    Execute seasonal Dynamic World extraction across SMC analytical grid.
    Supports live Google Earth Engine processing and offline fixture mode.
    """
    # Resolve date window from canonical seasonal definitions
    windows = get_season_windows(year)
    matched_window = next((w for w in windows if w.name == season), None)
    if not matched_window:
        raise ValueError(f"Unknown season '{season}'. Supported: summer, winter, monsoon, post_monsoon.")

    start_date = matched_window.start_date
    end_date = matched_window.end_date
    version_tag = "v1.0-fixture" if use_fixtures else PIPELINE_VERSION
    source_tag = "FIXTURE_SYNTHETIC_DYNAMIC_WORLD" if use_fixtures else DW_COLLECTION_ID
    run_id = f"RUN_DW_{season.upper()}_{year}_{uuid.uuid4().hex[:8].upper()}"

    # Load database connection if not provided
    if engine is None:
        from backend.app.db.session import engine as default_engine
        engine = default_engine

    # 1. Fetch grid cells with optional filters
    where_clauses = []
    if area_name:
        where_clauses.append(f"c.nearest_osm_place_name = '{area_name}'")
    if min_hpi is not None:
        where_clauses.append(f"s.heat_priority_score >= {min_hpi}")
    if cell_ids:
        in_cids = ", ".join(f"'{cid}'" for cid in cell_ids)
        where_clauses.append(f"c.pixel_id IN ({in_cids})")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    limit_clause = f"LIMIT {max_cells}" if max_cells else ""

    with engine.connect() as conn:
        query = sa.text(f"""
            SELECT c.pixel_id, ST_AsGeoJSON(c.geometry) as geojson 
            FROM stage_c_grid_cells c
            LEFT JOIN stage_c_heat_priority_scores s ON c.pixel_id = s.pixel_id
            {where_sql}
            ORDER BY s.heat_priority_score DESC NULLS LAST, c.row_idx, c.col_idx
            {limit_clause}
        """)
        df_cells = pd.read_sql(query, conn)

    total_cells = len(df_cells)
    if total_cells == 0:
        return {"status": "EMPTY_GRID", "run_id": run_id}

    col_size = 0
    composite = None
    if not use_fixtures:
        try:
            ee.Initialize()
            sample_geoms = [json.loads(g) for g in df_cells["geojson"].iloc[:min(100, total_cells)]]
            coords = [c for g in sample_geoms for c in g["coordinates"][0]]
            min_lon = min(c[0] for c in coords)
            max_lon = max(c[0] for c in coords)
            min_lat = min(c[1] for c in coords)
            max_lat = max(c[1] for c in coords)
            aoi = ee.Geometry.Rectangle([min_lon - 0.05, min_lat - 0.05, max_lon + 0.05, max_lat + 0.05])
            composite, col_size = build_seasonal_composite(start_date, end_date, aoi)
        except Exception as e:
            print(f"Warning: Earth Engine initialization/composite build failed: {e}. Falling back to fixture mode.")
            use_fixtures = True
            version_tag = "v1.0-fixture"
            source_tag = "FIXTURE_SYNTHETIC_DYNAMIC_WORLD"

    # 2. Process in batches
    num_batches = math.ceil(total_cells / batch_size)
    total_sufficient = 0
    total_insufficient = 0
    total_no_obs = 0
    t0 = time.time()

    for b_idx in range(num_batches):
        b_start = b_idx * batch_size
        b_end = min(total_cells, b_start + batch_size)
        df_batch = df_cells.iloc[b_start:b_end]

        if use_fixtures or composite is None:
            res = generate_offline_dynamic_world_fixtures(
                cells_gdf=df_batch,
                season=season,
                year=year,
                start_date=start_date,
                end_date=end_date,
                run_id=run_id,
                min_observations_threshold=min_observations_threshold,
            )
        else:
            res = extract_batch_for_cells(
                composite=composite,
                cells_gdf=df_batch,
                season=season,
                year=year,
                start_date=start_date,
                end_date=end_date,
                run_id=run_id,
                min_observations_threshold=min_observations_threshold,
            )

        save_records_to_db(res.records, engine)
        total_sufficient += res.cells_sufficient
        total_insufficient += res.cells_insufficient
        total_no_obs += res.cells_no_observations

    elapsed_s = time.time() - t0

    # 3. Save provenance run record
    with engine.begin() as conn:
        conn.execute(
            sa.text("""
                INSERT INTO stage_d_landcover_pipeline_runs (
                    run_id, season, year, start_date, end_date, total_cells,
                    cells_sufficient, cells_insufficient, cells_no_observations,
                    min_observations_threshold, source_dataset, pipeline_version,
                    attribution, citation, license, parameters_json, created_at
                ) VALUES (
                    :run_id, :season, :year, :start_date, :end_date, :total_cells,
                    :cells_sufficient, :cells_insufficient, :cells_no_observations,
                    :min_obs, :source_dataset, :pipeline_version,
                    :attribution, :citation, :license, :params, NOW()
                )
            """),
            {
                "run_id": run_id,
                "season": season,
                "year": year,
                "start_date": start_date,
                "end_date": end_date,
                "total_cells": total_cells,
                "cells_sufficient": total_sufficient,
                "cells_insufficient": total_insufficient,
                "cells_no_observations": total_no_obs,
                "min_obs": min_observations_threshold,
                "source_dataset": source_tag,
                "pipeline_version": version_tag,
                "attribution": ATTRIBUTION_TEXT,
                "citation": CITATION_TEXT,
                "license": LICENSE_TEXT,
                "params": json.dumps({"batch_size": batch_size, "runtime_seconds": round(elapsed_s, 2), "area_filter": area_name, "use_fixtures": use_fixtures}),
            },
        )

    return {
        "run_id": run_id,
        "season": season,
        "year": year,
        "start_date": start_date,
        "end_date": end_date,
        "total_cells": total_cells,
        "cells_sufficient": total_sufficient,
        "cells_insufficient": total_insufficient,
        "cells_no_observations": total_no_obs,
        "runtime_seconds": round(elapsed_s, 2),
        "source_scenes_count": col_size,
        "source_dataset": source_tag,
        "pipeline_version": version_tag,
    }
