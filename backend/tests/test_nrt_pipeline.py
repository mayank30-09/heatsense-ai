"""Unit and integration tests for Problem 4: Automated NRT Landsat pipeline respecting ML freeze.

Validates:
1. QA masking bitmask (mask_qa_pixel): bits 0, 1, 2, 3, 4.
2. Clear-% computation over official SMC boundary.
3. Idempotent scene-ID registry transitions and deduplication.
4. Rejection threshold logic (<40% clear marked as rejected with clear reason).
5. Provisional hotspot scoring and strict isolation from the 223 chronic hotspots.
6. Absolute freeze safety: discovery and retraining pipelines NEVER write into artifacts/ml_freeze/.
7. Scene catalog and pipeline status API endpoints (/scenes, /scenes/pipeline-status, /admin/scenes/check).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.core.auth import User, UserRole
from backend.app.core.security import create_access_token
from backend.app.db.models.stage_c import (
    StageCGridCell,
    StageCHeatPriorityScore,
    StageCProvisionalHotspot,
    StageCScene,
    StageCSceneRegistry,
)
from backend.app.db.session import SessionLocal
from backend.app.main import app
from fastapi.testclient import TestClient
from gis.gee.latest_scene import create_synthetic_scene_array
from gis.gee.nrt_pipeline import (
    CANONICAL_SMC_CELL_COUNT,
    DEFAULT_CLEAR_THRESHOLD,
    calculate_smc_clear_fraction,
    mask_qa_pixel,
    process_scene_lifecycle,
    scale_st_b10_to_lst_celsius,
    score_provisional_hotspots,
    verify_wrs2_path_row_from_boundary,
)
from scripts.discover_nrt_scenes import run_discovery

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FREEZE_DIR = _REPO_ROOT / "artifacts" / "ml_freeze"


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client():
    return TestClient(app)


def test_wrs2_path_row_from_boundary():
    """Verify nominal Landsat WRS-2 Path/Row calculated from SMC boundary polygon."""
    path, row = verify_wrs2_path_row_from_boundary()
    assert path == 148, f"Expected Path 148, got {path}"
    assert row == 45, f"Expected Row 45, got {row}"


def test_scale_st_b10_to_lst_celsius():
    """Verify USGS Landsat Collection 2 Level-2 ST_B10 DN to Celsius scaling."""
    # Scale: DN * 0.00341802 + 149.0 - 273.15
    # If raw DN = 44177:
    # 44177 * 0.00341802 = 151.0009
    # 151.0009 + 149.0 = 300.0009 K - 273.15 = 26.85°C
    raw_dn = 44177
    lst_c = scale_st_b10_to_lst_celsius(raw_dn)
    assert 26.8 <= lst_c <= 26.9

    # NoData (0 or np.nan)
    assert scale_st_b10_to_lst_celsius(0) != scale_st_b10_to_lst_celsius(0)  # np.isnan


def test_mask_qa_pixel_bitmask():
    """Verify USGS QA_PIXEL bitmasking for Fill(0), Dilated(1), Cirrus(2), Cloud(3), CloudShadow(4)."""
    # QA = 21824 (binary: 0101 0101 0100 0000) -> clear land pixel (bits 0-4 are 0)
    assert mask_qa_pixel(21824) is True

    # QA = 0 (Fill) -> bit 0 is 0? If fill bit (bit 0) is 1:
    assert mask_qa_pixel(1) is False  # bit 0 set: fill

    # Bit 1: dilated cloud (2)
    assert mask_qa_pixel(2) is False

    # Bit 2: cirrus (4)
    assert mask_qa_pixel(4) is False

    # Bit 3: cloud (8)
    assert mask_qa_pixel(8) is False

    # Bit 4: cloud shadow (16)
    assert mask_qa_pixel(16) is False

    # Combined cloudy value: 22280 has cloud/shadow bits set
    assert mask_qa_pixel(22280) is False


def test_smc_clear_fraction_computation():
    """Verify clear fraction calculation against SMC boundary."""
    # Synthetic array with valid_fraction = 0.75
    lst, qa = create_synthetic_scene_array(valid_fraction=0.75, mean_temp=40.0)
    frac, _, _ = calculate_smc_clear_fraction(lst)
    assert 0.70 <= frac <= 0.80, f"Expected ~0.75, got {frac}"


def test_pipeline_idempotency(db_session: Session):
    """Verify running scene lifecycle processing twice on same scene is idempotent."""
    scene_id = "LC09_L2SP_148045_20261027_20261027_02_T1_IDEMP"
    acq_date = date(2026, 10, 27)
    acq_time = datetime(2026, 10, 27, 5, 43, 21, tzinfo=timezone.utc)

    lst, qa = create_synthetic_scene_array(valid_fraction=0.85, mean_temp=42.0)

    try:
        # Run 1
        res1 = process_scene_lifecycle(
            session=db_session,
            scene_id=scene_id,
            sensor="LANDSAT_9",
            acquisition_time=acq_time,
            acquisition_date=acq_date,
            lst_array=lst,
            cloud_cover=5.0,
            qa_array=qa,
            clear_threshold=DEFAULT_CLEAR_THRESHOLD,
        )
        assert res1["status"] == "published"

        # Count records
        count1 = db_session.query(StageCSceneRegistry).filter_by(scene_id=scene_id).count()
        assert count1 == 1

        # Run 2 (duplicate)
        res2 = process_scene_lifecycle(
            session=db_session,
            scene_id=scene_id,
            sensor="LANDSAT_9",
            acquisition_time=acq_time,
            acquisition_date=acq_date,
            lst_array=lst,
            cloud_cover=5.0,
            qa_array=qa,
            clear_threshold=DEFAULT_CLEAR_THRESHOLD,
        )
        assert res2["status"] == "published"

        # Count records again: must still be exactly 1
        count2 = db_session.query(StageCSceneRegistry).filter_by(scene_id=scene_id).count()
        assert count2 == 1, f"Expected 1 record after duplicate run, got {count2}"

    finally:
        # Cleanup test fixture
        db_session.query(StageCProvisionalHotspot).filter_by(scene_id=scene_id).delete()
        db_session.query(StageCSceneRegistry).filter_by(scene_id=scene_id).delete()
        db_session.query(StageCScene).filter_by(scene_id=scene_id).delete()
        db_session.commit()


def test_scene_rejection_below_threshold(db_session: Session):
    """Verify scene with clear fraction below threshold is rejected with explicit reason."""
    scene_id = "LC08_L2SP_148045_20261027_20261027_02_T1_CLOUDY"
    acq_date = date(2026, 10, 27)
    acq_time = datetime(2026, 10, 27, 5, 43, 21, tzinfo=timezone.utc)

    # 15% clear (well below 40% default)
    lst, qa = create_synthetic_scene_array(valid_fraction=0.15, mean_temp=35.0)

    try:
        res = process_scene_lifecycle(
            session=db_session,
            scene_id=scene_id,
            sensor="LANDSAT_8",
            acquisition_time=acq_time,
            acquisition_date=acq_date,
            lst_array=lst,
            cloud_cover=85.0,
            qa_array=qa,
            clear_threshold=DEFAULT_CLEAR_THRESHOLD,
        )
        assert res["status"] == "rejected"
        assert "cloud contamination" in res["rejection_reason"].lower()
        assert "15." in res["rejection_reason"] or "below required 40.0%" in res["rejection_reason"]

        # Check DB registry
        reg = db_session.query(StageCSceneRegistry).filter_by(scene_id=scene_id).first()
        assert reg is not None
        assert reg.status == "rejected"
        assert reg.rejection_reason is not None

        # Check that NO provisional hotspots were created for a rejected scene
        prov_count = db_session.query(StageCProvisionalHotspot).filter_by(scene_id=scene_id).count()
        assert prov_count == 0

    finally:
        db_session.query(StageCSceneRegistry).filter_by(scene_id=scene_id).delete()
        db_session.query(StageCScene).filter_by(scene_id=scene_id).delete()
        db_session.commit()


def test_provisional_hotspots_isolation(db_session: Session):
    """Verify provisional hotspots are strictly isolated from the 223 chronic hotspots and HPI."""
    scene_id = "LC09_L2SP_148045_20261027_20261027_02_T1_PROV"
    acq_date = date(2026, 10, 27)
    acq_time = datetime(2026, 10, 27, 5, 43, 21, tzinfo=timezone.utc)

    # 90% clear with high mean temp (46.0°C) to generate hotspots
    lst, qa = create_synthetic_scene_array(valid_fraction=0.90, mean_temp=46.0)

    try:
        # Pre-condition: count chronic hotspots in grid
        chronic_before = db_session.query(func.count(StageCHeatPriorityScore.pixel_id)).filter(
            StageCHeatPriorityScore.is_chronic_hotspot.is_(True)
        ).scalar()
        assert chronic_before == 223, f"Expected exactly 223 chronic hotspots, got {chronic_before}"

        res = process_scene_lifecycle(
            session=db_session,
            scene_id=scene_id,
            sensor="LANDSAT_9",
            acquisition_time=acq_time,
            acquisition_date=acq_date,
            lst_array=lst,
            cloud_cover=5.0,
            qa_array=qa,
            clear_threshold=DEFAULT_CLEAR_THRESHOLD,
        )

        assert res["status"] == "published"
        prov_count = res["provisional_hotspots_count"]
        assert prov_count > 0, "Expected at least some provisional hotspots for hot scene"

        # Check provisional hotspots table
        hotspots = db_session.query(StageCProvisionalHotspot).filter_by(scene_id=scene_id).all()
        assert len(hotspots) == prov_count
        for h in hotspots:
            assert h.hotspot_type == "Provisional NRT hotspot, single scene"
            assert h.observed_lst_c >= 40.0

        # CRITICAL ISOLATION INVARIANT: Chronic hotspots count MUST still be exactly 223!
        chronic_after = db_session.query(func.count(StageCHeatPriorityScore.pixel_id)).filter(
            StageCHeatPriorityScore.is_chronic_hotspot.is_(True)
        ).scalar()
        assert chronic_after == 223, f"Chronic hotspots count altered! {chronic_before} -> {chronic_after}"

    finally:
        db_session.query(StageCProvisionalHotspot).filter_by(scene_id=scene_id).delete()
        db_session.query(StageCSceneRegistry).filter_by(scene_id=scene_id).delete()
        db_session.query(StageCScene).filter_by(scene_id=scene_id).delete()
        db_session.commit()


def test_ml_freeze_immutability_guard():
    """Verify that artifacts/ml_freeze/ contains all 41 files and is strictly untouched."""
    import json
    checksums_path = _FREEZE_DIR / "checksums.sha256"
    assert checksums_path.exists(), "checksums.sha256 missing"

    with open(checksums_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    verified_count = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected_sha, rel_name = line.split(None, 1)
        rel_name = rel_name.strip("* \t")
        target_file = _REPO_ROOT / rel_name
        assert target_file.exists(), f"Frozen file missing: {rel_name}"

        with open(target_file, "rb") as tf:
            actual_sha = hashlib.sha256(tf.read()).hexdigest()
        assert actual_sha == expected_sha, f"Checksum mismatch for frozen file {rel_name}!"
        verified_count += 1

    assert verified_count == 41, f"Expected 41 frozen files verified, got {verified_count}"


def test_scenes_api_and_pipeline_status(test_client: TestClient):
    """Verify GET /api/v1/scenes and GET /api/v1/scenes/pipeline-status endpoints."""
    # 1. Pipeline status
    resp = test_client.get("/api/v1/scenes/pipeline-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "last_checked" in data
    assert "next_expected_overpass" in data
    assert data["pipeline_status"] in ("OPERATIONAL", "IDLE", "DEGRADED", "DELAYED", "ERROR")
    assert "processed_count" in data
    assert "rejected_count" in data

    # 2. List scenes (including rejected)
    resp_scenes = test_client.get("/api/v1/scenes?include_rejected=true")
    assert resp_scenes.status_code == 200
    scenes = resp_scenes.json()
    assert isinstance(scenes, list)
    if len(scenes) > 0:
        first = scenes[0]
        assert "scene_id" in first
        assert "valid_pixel_fraction" in first
        assert "status" in first


def test_admin_scenes_check_endpoint(test_client: TestClient):
    """Verify POST /api/v1/admin/scenes/check triggers discovery and requires admin role."""
    # Unauthorized request (no token) -> 401
    resp_no_auth = test_client.post("/api/v1/admin/scenes/check", json={"mock": True, "dry_run": True})
    assert resp_no_auth.status_code == 401

    # Authorized admin request -> 200
    admin_token = create_access_token(
        subject="smc_admin",
        role=UserRole.ADMIN.value,
    )
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp_auth = test_client.post(
        "/api/v1/admin/scenes/check",
        json={"mock": True, "dry_run": True, "min_valid_fraction": 0.40},
        headers=headers,
    )
    assert resp_auth.status_code == 200
    payload = resp_auth.json()
    assert payload["status"] == "success"
    assert "scenes_processed" in payload
    assert len(payload["results"]) > 0
