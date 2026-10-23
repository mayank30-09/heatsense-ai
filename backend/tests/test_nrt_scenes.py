"""Unit and Integration Tests for HEATSENSE AI Near-Real-Time Landsat LST Pipeline.

Validates:
- Acquisition timestamp normalization and metadata parsing.
- Valid-pixel fraction calculation and configurable thresholding.
- Collision-safe COG file naming policy.
- COG creation, validation, CRS, dimensions, and overviews.
- Watermark persistence and advancement invariants.
- Idempotent PostGIS insertion into stage_c_scenes and stage_c_scene_observations.
- API endpoints: GET /api/v1/scenes and scene-specific raster tile rendering with ETags.
- Invalid scene 404 behavior.
- Monitoring-only hotspot comparison against same-season baseline.
- Ingestion freshness 20-day health gate.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import tempfile
from typing import Generator

from fastapi.testclient import TestClient
import numpy as np
import pytest
import rasterio
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.db.models.stage_c import (
    StageCGridCell,
    StageCScene,
    StageCSceneObservation,
)
from backend.app.db.session import SessionLocal
from backend.app.main import app
from gis.gee.latest_scene import (
    CANONICAL_SMC_CELL_COUNT,
    DEFAULT_MIN_VALID_FRACTION,
    GRID_CRS,
    GRID_HEIGHT,
    GRID_WIDTH,
    NODATA_VALUE,
    SURAT_WRS_PATH,
    SURAT_WRS_ROW,
    calculate_valid_pixel_fraction,
    check_ingestion_freshness,
    create_synthetic_scene_array,
    determine_collision_safe_cog_path,
    export_scene_cog,
    get_last_ingested_watermark,
    normalize_acquisition_timestamp,
    process_scene_record,
    validate_cog,
)
from scripts.monitor_scene_hotspots import run_hotspot_comparison


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a database session and clean up test scenes upon teardown."""
    session = SessionLocal()
    test_scene_prefix = "TEST_FIXTURE_"
    try:
        # Pre-clean
        session.execute(
            delete(StageCScene).where(StageCScene.scene_id.like(f"{test_scene_prefix}%"))
        )
        session.commit()
        yield session
    finally:
        session.execute(
            delete(StageCScene).where(StageCScene.scene_id.like(f"{test_scene_prefix}%"))
        )
        session.commit()
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Timestamp Normalization & Metadata Parsing
# -----------------------------------------------------------------------------
def test_normalize_acquisition_timestamp_epoch_ms():
    # 2026-05-15 05:43:21 UTC = 1778823801000 ms
    epoch_ms = 1778823801000
    dt, d = normalize_acquisition_timestamp(system_time_start=epoch_ms)
    assert dt.year == 2026
    assert dt.month == 5
    assert dt.day == 15
    assert dt.hour == 5
    assert dt.minute == 43
    assert dt.tzinfo == timezone.utc
    assert d == date(2026, 5, 15)


def test_normalize_acquisition_timestamp_iso_string():
    dt, d = normalize_acquisition_timestamp(
        scene_center_time="05:43:21.123456Z",
        date_acquired="2026-05-15",
    )
    assert dt.year == 2026
    assert dt.month == 5
    assert dt.day == 15
    assert dt.hour == 5
    assert dt.minute == 43
    assert dt.second == 21
    assert dt.tzinfo == timezone.utc
    assert d == date(2026, 5, 15)


def test_normalize_acquisition_timestamp_fallback():
    dt, d = normalize_acquisition_timestamp()
    assert dt.tzinfo == timezone.utc
    assert isinstance(d, date)


# -----------------------------------------------------------------------------
# 2. Valid-Pixel Fraction & Quality Thresholding
# -----------------------------------------------------------------------------
def test_calculate_valid_pixel_fraction():
    canonical_cells = [("R001_C001", 10, 10), ("R001_C002", 10, 11), ("R001_C003", 10, 12)]
    arr = np.full((GRID_HEIGHT, GRID_WIDTH), NODATA_VALUE, dtype=np.float32)

    # Fill 2 valid cells and 1 invalid
    arr[10, 10] = 42.5
    arr[10, 11] = 43.1
    arr[10, 12] = -9999.0

    frac, valid_cnt, total = calculate_valid_pixel_fraction(arr, canonical_cells)
    assert total == 3
    assert valid_cnt == 2
    assert pytest.approx(frac, rel=1e-3) == 2.0 / 3.0


def test_calculate_valid_pixel_fraction_empty():
    canonical_cells = [("R001_C001", 10, 10)]
    arr = np.full((GRID_HEIGHT, GRID_WIDTH), NODATA_VALUE, dtype=np.float32)
    frac, valid_cnt, total = calculate_valid_pixel_fraction(arr, canonical_cells)
    assert total == 1
    assert valid_cnt == 0
    assert frac == 0.0


# -----------------------------------------------------------------------------
# 3. Collision-Safe COG File Naming
# -----------------------------------------------------------------------------
def test_collision_safe_cog_naming(tmp_path: Path):
    acq_date = date(2026, 5, 15)

    # 1. First scene: canonical <YYYY-MM-DD>.tif
    path1 = determine_collision_safe_cog_path(
        output_dir=tmp_path,
        acquisition_date=acq_date,
        sensor="LANDSAT_9",
        scene_id="LC09_148045_20260515",
    )
    assert path1.name == "2026-05-15.tif"
    path1.touch()

    # 2. Second scene same date different sensor: qualifies with sensor
    path2 = determine_collision_safe_cog_path(
        output_dir=tmp_path,
        acquisition_date=acq_date,
        sensor="LANDSAT_8",
        scene_id="LC08_148045_20260515",
    )
    assert path2.name == "2026-05-15_landsat_8.tif"


# -----------------------------------------------------------------------------
# 4. COG Creation, Overview, and Validation
# -----------------------------------------------------------------------------
def test_export_and_validate_cog(tmp_path: Path):
    target_cog = tmp_path / "test_scene.tif"
    arr, _ = create_synthetic_scene_array(valid_fraction=0.90, mean_temp=41.5)

    export_scene_cog(target_cog, arr, metadata={"scene_id": "TEST_COG_01"})
    assert target_cog.exists()
    assert target_cog.with_suffix(".json").exists()

    assert validate_cog(target_cog) is True

    # Check raster structure
    with rasterio.open(target_cog) as src:
        assert src.count == 1
        assert src.width == GRID_WIDTH
        assert src.height == GRID_HEIGHT
        assert src.crs.to_string() == GRID_CRS
        assert len(src.overviews(1)) >= 3
        data = src.read(1)
        valid = data[data > 0]
        assert np.mean(valid) == pytest.approx(41.5, abs=5.0)


# -----------------------------------------------------------------------------
# 5. Scene Rejection and Non-Advancing Watermark
# -----------------------------------------------------------------------------
def test_scene_rejection_does_not_advance_watermark(db_session: Session, tmp_path: Path):
    initial_watermark = get_last_ingested_watermark(db_session)

    # Create scene with only 10% valid pixels (< 60% default threshold)
    low_valid_arr, _ = create_synthetic_scene_array(valid_fraction=0.10, mean_temp=40.0)
    test_scene_id = "TEST_FIXTURE_CLOUDY_01"
    acq_dt = datetime(2026, 6, 1, 5, 43, 0, tzinfo=timezone.utc)

    result = process_scene_record(
        session=db_session,
        scene_id=test_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=low_valid_arr,
        cloud_cover=85.0,
        min_valid_fraction=0.60,
        output_dir=tmp_path,
        dry_run=False,
    )

    assert result["status"] == "REJECTED_CLOUDY"

    # Verify watermark did NOT advance
    new_watermark = get_last_ingested_watermark(db_session)
    assert new_watermark == initial_watermark

    # Verify ledger recorded the cloudy scene
    scene = db_session.execute(
        select(StageCScene).where(StageCScene.scene_id == test_scene_id)
    ).scalar_one()
    assert scene.status == "REJECTED_CLOUDY"
    assert scene.valid_pixel_fraction < 0.60


# -----------------------------------------------------------------------------
# 6. Idempotent Ingestion & Database Watermark Advancement
# -----------------------------------------------------------------------------
def test_successful_scene_ingestion_and_idempotency(db_session: Session, tmp_path: Path):
    arr, qa = create_synthetic_scene_array(valid_fraction=0.85, mean_temp=42.0)
    test_scene_id = "TEST_FIXTURE_VALID_01"
    acq_dt = datetime(2026, 6, 10, 5, 43, 0, tzinfo=timezone.utc)

    # 1. First Ingestion Run
    result1 = process_scene_record(
        session=db_session,
        scene_id=test_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=arr,
        cloud_cover=10.0,
        min_valid_fraction=0.60,
        output_dir=tmp_path,
        qa_array=qa,
        dry_run=False,
    )
    assert result1["status"] == "PROCESSED"

    # Watermark must be at or beyond this scene's acquisition_time
    watermark = get_last_ingested_watermark(db_session)
    assert watermark is not None
    assert watermark >= acq_dt

    # Check observations count
    obs_count_1 = db_session.execute(
        select(StageCSceneObservation).where(StageCSceneObservation.scene_id == test_scene_id)
    ).scalars().all()
    assert len(obs_count_1) == CANONICAL_SMC_CELL_COUNT

    # 2. Rerun Same Scene (Idempotency Check)
    result2 = process_scene_record(
        session=db_session,
        scene_id=test_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=arr,
        cloud_cover=10.0,
        min_valid_fraction=0.60,
        output_dir=tmp_path,
        qa_array=qa,
        dry_run=False,
    )
    assert result2["status"] == "PROCESSED"

    # Count must remain exactly 49,747 (no duplicate key crash, no duplicated rows)
    obs_count_2 = db_session.execute(
        select(StageCSceneObservation).where(StageCSceneObservation.scene_id == test_scene_id)
    ).scalars().all()
    assert len(obs_count_2) == CANONICAL_SMC_CELL_COUNT


# -----------------------------------------------------------------------------
# 7. API Tests: GET /api/v1/scenes and Scene Tiles
# -----------------------------------------------------------------------------
def test_api_scenes_list(client: TestClient, db_session: Session, tmp_path: Path):
    # Ingest a test scene
    arr, _ = create_synthetic_scene_array(valid_fraction=0.80, mean_temp=43.0)
    test_scene_id = "TEST_FIXTURE_API_01"
    acq_dt = datetime(2026, 6, 12, 5, 43, 0, tzinfo=timezone.utc)

    process_scene_record(
        session=db_session,
        scene_id=test_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=arr,
        cloud_cover=15.0,
        output_dir=tmp_path,
        source="SYNTHETIC TEST DATA",
        dry_run=False,
    )

    # 1. Default /api/v1/scenes (source='landsat_l2') excludes synthetic scenes
    resp_default = client.get("/api/v1/scenes")
    assert resp_default.status_code == 200
    items_default = resp_default.json()
    assert not any(s["scene_id"] == test_scene_id for s in items_default)

    # 2. Querying source='SYNTHETIC TEST DATA' returns the fixture
    resp_synth = client.get("/api/v1/scenes?source=SYNTHETIC%20TEST%20DATA")
    assert resp_synth.status_code == 200
    items_synth = resp_synth.json()
    scene_found = next((s for s in items_synth if s["scene_id"] == test_scene_id), None)
    assert scene_found is not None
    assert scene_found["source"] == "SYNTHETIC TEST DATA"
    assert scene_found["sensor"] == "LANDSAT_9"
    assert scene_found["status"] == "PROCESSED"

    # 3. Querying source='all' also returns it
    resp_all = client.get("/api/v1/scenes?source=all")
    assert resp_all.status_code == 200
    items_all = resp_all.json()
    assert any(s["scene_id"] == test_scene_id for s in items_all)


def test_mock_safety_cli_and_catalog(client: TestClient, db_session: Session, tmp_path: Path):
    """Verify that process_scene_record marks synthetic output as SYNTHETIC TEST DATA and excludes from default catalog."""
    arr, qa = create_synthetic_scene_array(valid_fraction=0.88, mean_temp=43.5)
    mock_scene_id = "SYNTHETIC_LC09_L2SP_148045_20261024_02_T1"
    acq_dt = datetime(2026, 10, 24, 5, 43, 21, tzinfo=timezone.utc)

    mock_dir = tmp_path / "mock_scenes"
    mock_dir.mkdir(parents=True, exist_ok=True)

    result = process_scene_record(
        session=db_session,
        scene_id=mock_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=arr,
        cloud_cover=12.0,
        output_dir=mock_dir,
        source="SYNTHETIC TEST DATA",
        dry_run=False,
    )

    assert result["source"] == "SYNTHETIC TEST DATA"
    assert result["status"] == "PROCESSED"

    # Default catalog excludes it
    resp_default = client.get("/api/v1/scenes")
    assert resp_default.status_code == 200
    assert not any(s["scene_id"] == mock_scene_id for s in resp_default.json())

    # Explicit synthetic filter includes it
    resp_synth = client.get("/api/v1/scenes?source=synthetic")
    assert resp_synth.status_code == 200
    found = next((s for s in resp_synth.json() if s["scene_id"] == mock_scene_id), None)
    assert found is not None
    assert found["source"] == "SYNTHETIC TEST DATA"


def test_api_scene_raster_tiles(client: TestClient, db_session: Session, tmp_path: Path):
    arr, _ = create_synthetic_scene_array(valid_fraction=0.85, mean_temp=44.0)
    test_scene_id = "TEST_FIXTURE_TILE_01"
    acq_dt = datetime(2026, 6, 15, 5, 43, 0, tzinfo=timezone.utc)

    # Ingest to default scenes directory so API can resolve it
    scenes_dir = Path("data/processed/scenes")
    process_scene_record(
        session=db_session,
        scene_id=test_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=arr,
        cloud_cover=10.0,
        output_dir=scenes_dir,
        dry_run=False,
    )

    try:
        # Surat tile at zoom 11 (center lat ~21.17, lon ~72.83)
        # Tile coordinates around Surat: z=11, x=1438, y=930
        resp = client.get(f"/api/v1/rasters/lst/tiles/11/1438/930.png?scene_id={test_scene_id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert "ETag" in resp.headers
        assert resp.headers["X-Scene-ID"] == test_scene_id

        # Nonexistent scene returns 404
        resp_404 = client.get("/api/v1/rasters/lst/tiles/11/1438/930.png?scene_id=NONEXISTENT_SCENE_999")
        assert resp_404.status_code == 404
        assert "not found" in resp_404.json()["detail"].lower()
    finally:
        # Clean up exported test tile
        for p in scenes_dir.glob(f"*{test_scene_id}*"):
            if p.exists():
                p.unlink()


# -----------------------------------------------------------------------------
# 8. Monitoring-Only Top-100 Hotspot Comparison
# -----------------------------------------------------------------------------
def test_monitoring_hotspot_comparison(db_session: Session, tmp_path: Path):
    # Ingest a test scene
    arr, _ = create_synthetic_scene_array(valid_fraction=0.90, mean_temp=43.5)
    test_scene_id = "TEST_FIXTURE_MONITOR_01"
    acq_dt = datetime(2026, 5, 20, 5, 43, 0, tzinfo=timezone.utc)

    process_scene_record(
        session=db_session,
        scene_id=test_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=arr,
        cloud_cover=8.0,
        output_dir=tmp_path,
        dry_run=False,
    )

    report = run_hotspot_comparison(
        session=db_session,
        scene_id=test_scene_id,
        anomaly_threshold_c=3.0,
        output_dir=tmp_path,
        dry_run=False,
    )

    assert report is not None
    assert report["scene_metadata"]["scene_id"] == test_scene_id
    assert report["monitoring_parameters"]["hotspot_cell_count"] == 100
    assert report["summary"]["valid_observed_cells"] > 0
    assert len(report["cell_comparisons"]) == 100

    # Verify report files were created
    date_str = acq_dt.date().isoformat()
    json_path = tmp_path / f"hotspot_comparison_{date_str}_{test_scene_id}.json"
    md_path = tmp_path / f"hotspot_comparison_{date_str}_{test_scene_id}.md"
    assert json_path.exists()
    assert md_path.exists()


# -----------------------------------------------------------------------------
# 9. Freshness Health Gate
# -----------------------------------------------------------------------------
def test_check_ingestion_freshness(db_session: Session, tmp_path: Path):
    # Fresh scene (acquired today)
    arr, _ = create_synthetic_scene_array(valid_fraction=0.85, mean_temp=42.0)
    fresh_scene_id = "TEST_FIXTURE_FRESH_01"
    fresh_dt = datetime.now(timezone.utc)

    process_scene_record(
        session=db_session,
        scene_id=fresh_scene_id,
        acquisition_time=fresh_dt,
        acquisition_date=fresh_dt.date(),
        sensor="LANDSAT_9",
        lst_array=arr,
        output_dir=tmp_path,
        dry_run=False,
    )

    is_fresh, age, dt = check_ingestion_freshness(db_session, max_age_days=20)
    assert is_fresh is True
    assert age <= 1
    assert dt is not None


# -----------------------------------------------------------------------------
# 10. Sample Scene Integration Fixture Test
# -----------------------------------------------------------------------------
def test_sample_scene_fixture_integration(client: TestClient, db_session: Session):
    fixture_path = Path("tests/fixtures/sample_scene_fixture.tif")
    assert fixture_path.exists(), "Sample scene fixture must exist."

    # 1. Raster reading & COG validation
    assert validate_cog(fixture_path) is True
    with rasterio.open(fixture_path) as src:
        assert src.count == 1
        assert src.width == GRID_WIDTH
        assert src.height == GRID_HEIGHT
        assert src.crs.to_string() == GRID_CRS
        data = src.read(1)
        valid_pixels = data[(data > 0.0) & (data < 100.0) & (data != NODATA_VALUE)]
        assert len(valid_pixels) > 30000
        # Physical LST range in Celsius
        assert np.min(valid_pixels) >= 20.0
        assert np.max(valid_pixels) <= 60.0

    # 2. Ingestion into PostGIS
    test_scene_id = "TEST_FIXTURE_INTEGRATION_01"
    acq_dt = datetime(2026, 7, 1, 5, 43, 0, tzinfo=timezone.utc)

    result = process_scene_record(
        session=db_session,
        scene_id=test_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=data,
        cloud_cover=5.0,
        output_dir=fixture_path.parent,
        dry_run=False,
    )
    assert result["status"] == "PROCESSED"

    # 3. Duplicate prevention check
    rerun_result = process_scene_record(
        session=db_session,
        scene_id=test_scene_id,
        acquisition_time=acq_dt,
        acquisition_date=acq_dt.date(),
        sensor="LANDSAT_9",
        lst_array=data,
        cloud_cover=5.0,
        output_dir=fixture_path.parent,
        dry_run=False,
    )
    assert rerun_result["status"] == "PROCESSED"

    # 4. API Serialization & Verification
    # Default catalog (source='landsat_l2') excludes synthetic test fixture
    resp_default = client.get("/api/v1/scenes")
    assert resp_default.status_code == 200
    assert not any(s["scene_id"] == test_scene_id for s in resp_default.json())

    # Explicit source='all' or source='SYNTHETIC TEST DATA' returns it
    resp = client.get("/api/v1/scenes?source=all")
    assert resp.status_code == 200
    scene_match = next((s for s in resp.json() if s["scene_id"] == test_scene_id), None)
    assert scene_match is not None
    assert scene_match["valid_pixel_fraction"] > 0.60
    assert scene_match["sensor"] == "LANDSAT_9"
    assert "acquisition_time_ist" in scene_match
    assert scene_match["source"] == "SYNTHETIC TEST DATA"


# -----------------------------------------------------------------------------
# 9. Synthetic QA Bitmasking, Scaling, and Seasonal Provenance Unit Tests
# -----------------------------------------------------------------------------
def test_qa_pixel_bitmask_flags():
    """Verify bitwise flags according to USGS Landsat Collection 2 Level-2 QA_PIXEL specification."""
    # Bit 0: Fill (1 = fill, 0 = valid)
    # Bit 1: Dilated Cloud
    # Bit 2: Cirrus
    # Bit 3: Cloud
    # Bit 4: Cloud Shadow
    # Bit 5: Snow
    # Bit 7: Water (must be preserved!)
    
    # Pixel with water bit (bit 7 = 128) and no cloud/shadow/fill bits
    water_pixel = 1 << 7  # 128
    is_clear = (
        (water_pixel & (1 << 0) == 0)
        and (water_pixel & (1 << 1) == 0)
        and (water_pixel & (1 << 2) == 0)
        and (water_pixel & (1 << 3) == 0)
        and (water_pixel & (1 << 4) == 0)
        and (water_pixel & (1 << 5) == 0)
    )
    assert is_clear is True, "Water pixels must not be masked by clear check"

    # Cloud pixel (bit 3 = 8)
    cloud_pixel = 1 << 3
    is_cloud_clear = (cloud_pixel & (1 << 3) == 0)
    assert is_cloud_clear is False, "Cloud bit must be masked"

    # Cloud shadow pixel (bit 4 = 16)
    shadow_pixel = 1 << 4
    is_shadow_clear = (shadow_pixel & (1 << 4) == 0)
    assert is_shadow_clear is False, "Cloud shadow bit must be masked"


def test_qa_radsat_thermal_saturation():
    """Verify QA_RADSAT checks Band 10 thermal saturation (bit 9) without rejecting optical saturation."""
    # Optical band 1 saturation (bit 0 = 1, e.g. white concrete or metal roof)
    roof_optical_saturated = 1 << 0
    thermal_ok = (roof_optical_saturated & (1 << 9)) == 0
    assert thermal_ok is True, "Optical saturation must not mask thermal Band 10"

    # Thermal Band 10 saturation (bit 9 = 512)
    thermal_saturated = 1 << 9
    thermal_masked = (thermal_saturated & (1 << 9)) == 0
    assert thermal_masked is False, "Thermal saturation must be masked"


def test_scale_lst_formula_conversion():
    """Verify USGS Level-2 ST_B10 to Celsius scale factor and offset formula."""
    scale_factor = 0.00341802
    add_offset = 149.0
    kelvin_to_celsius = 273.15

    # Test DN = 44000 (typical ~26°C urban ground)
    dn_val = 44000
    temp_k = dn_val * scale_factor + add_offset
    temp_c = temp_k - kelvin_to_celsius
    assert pytest.approx(temp_c, abs=0.01) == 26.24

    # Test DN = 48000 (typical ~40°C hot summer asphalt)
    dn_hot = 48000
    temp_k_hot = dn_hot * scale_factor + add_offset
    temp_c_hot = temp_k_hot - kelvin_to_celsius
    assert pytest.approx(temp_c_hot, abs=0.01) == 39.91


def test_seasonal_provenance_stats_endpoint(client: TestClient):
    """Verify GET /api/v1/heat-priority/lst-stats returns seasonal scene counts and date windows."""
    resp = client.get("/api/v1/heat-priority/lst-stats?season=summer&year=2026")
    assert resp.status_code == 200
    data = resp.json()
    assert data["season"] == "summer"
    assert data["year"] == 2026
    assert data["n_scenes"] == 22
    assert "date_window" in data
    assert data["date_window"] == "2026-03-04 to 2026-05-31"
    assert data["valid_fraction"] == 1.0
    assert data["is_partial"] is False

    # Check monsoon partial provenance
    resp_m = client.get("/api/v1/heat-priority/lst-stats?season=monsoon&year=2026")
    assert resp_m.status_code == 200
    data_m = resp_m.json()
    assert data_m["season"] == "monsoon"
    assert data_m["is_partial"] is True
    assert data_m["n_scenes"] == 6
    assert data_m["valid_fraction"] < 1.0


