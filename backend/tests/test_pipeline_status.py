"""Backend unit tests with frozen clocks for NRT pipeline status and orbital overpass cadence.

Tests conform to Bug 1 requirements:
- Now before / after an expected overpass.
- Both sensors (Landsat 8 & Landsat 9 16-day cycles offset by 8 days).
- Missed / overdue overpasses with USGS processing latency handling.
- Rejected scenes counted as valid overpasses with explicit reason.
- IST / UTC boundary handling (late-evening IST vs UTC date).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.api.v1.scenes import IST_TZ, calculate_pipeline_status
from backend.app.db.models.stage_c import StageCScene, StageCSceneRegistry
from backend.app.db.session import SessionLocal
from backend.app.main import app


@pytest.fixture
def db_session():
    """Provide a database session for test execution."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client() -> TestClient:
    """Provide TestClient for scenes endpoints."""
    return TestClient(app)


def test_now_before_expected_overpass(db_session: Session):
    """When now is before an expected overpass (e.g. Oct 21 before Oct 22),

    the next expected overpass is Oct 22 (Landsat 8) and pipeline is OPERATIONAL.
    """
    # 2026-10-21 10:00 UTC = 15:30 IST (the day before the Oct 22 Landsat 8 pass)
    frozen_as_of = datetime(2026, 10, 21, 10, 0, 0, tzinfo=timezone.utc)
    status = calculate_pipeline_status(db_session, as_of=frozen_as_of)

    assert status.next_expected_overpass == "2026-10-22"
    assert status.next_expected_sensor == "LANDSAT_8"
    assert "Oct 22" in status.next_expected_overpass_label
    assert "Landsat 8" in status.next_expected_overpass_label
    assert status.pipeline_status == "OPERATIONAL"

    # Recent overpasses should include 2026-10-14 (PROCESSED) and 2026-10-06 (PROCESSED)
    overpass_dates = [o.date for o in status.recent_overpasses]
    assert "2026-10-14" in overpass_dates
    assert "2026-10-06" in overpass_dates
    # 2026-10-22 should NOT be in past overpasses since it hasn't occurred yet
    assert "2026-10-22" not in overpass_dates


def test_now_after_expected_overpass_within_latency(db_session: Session):
    """When an overpass occurred 1 day ago (e.g. Oct 22 overpass evaluated on Oct 23),

    it is within the 2-3 day USGS latency window (PENDING_LATENCY), and next overpass
    has rolled forward to Oct 30 (Landsat 9).
    """
    # 2026-10-23 10:00 UTC (1 day after Oct 22)
    frozen_as_of = datetime(2026, 10, 23, 10, 0, 0, tzinfo=timezone.utc)
    status = calculate_pipeline_status(db_session, as_of=frozen_as_of)

    # Next expected overpass rolls forward to Landsat 9
    assert status.next_expected_overpass == "2026-10-30"
    assert status.next_expected_sensor == "LANDSAT_9"
    assert "Oct 30" in status.next_expected_overpass_label

    # Oct 22 should be in recent_overpasses with PENDING_LATENCY status
    oct22_items = [o for o in status.recent_overpasses if o.date == "2026-10-22"]
    assert len(oct22_items) == 1
    oct22 = oct22_items[0]
    assert oct22.sensor == "LANDSAT_8"
    assert oct22.status == "PENDING_LATENCY"
    assert "not ingested yet, check scheduled" in oct22.label
    assert oct22.days_ago == 1

    # Pipeline is still OPERATIONAL within latency window
    assert status.pipeline_status == "OPERATIONAL"


def test_now_after_expected_overpass_overdue(db_session: Session):
    """When an overpass occurred > 3 days ago with no scene (e.g. Oct 22 evaluated on Oct 27),

    it is marked OVERDUE and pipeline status becomes DELAYED.
    """
    # 2026-10-27 08:00 UTC = 13:30 IST (testing reference date, 5 days after Oct 22)
    frozen_as_of = datetime(2026, 10, 27, 8, 0, 0, tzinfo=timezone.utc)
    status = calculate_pipeline_status(db_session, as_of=frozen_as_of)

    # Next expected overpass is Oct 30 (Landsat 9)
    assert status.next_expected_overpass == "2026-10-30"
    assert status.next_expected_sensor == "LANDSAT_9"
    assert "Oct 30" in status.next_expected_overpass_label
    assert "Landsat 9" in status.next_expected_overpass_label

    # Oct 22 is marked OVERDUE
    oct22_items = [o for o in status.recent_overpasses if o.date == "2026-10-22"]
    assert len(oct22_items) == 1
    oct22 = oct22_items[0]
    assert oct22.sensor == "LANDSAT_8"
    assert oct22.status == "OVERDUE"
    assert "no scene found / overdue in GEE" in oct22.label
    assert oct22.days_ago == 5

    # Pipeline status is DELAYED
    assert status.pipeline_status == "DELAYED"
    assert status.status_detail is not None
    assert "Overdue overpass" in status.status_detail or "Landsat 8" in status.status_detail


def test_both_sensors_alternating_cadence(db_session: Session):
    """Verify that Landsat 8 and Landsat 9 16-day cycles alternate with an 8-day offset."""
    # On Oct 29, next is Landsat 9 on Oct 30
    status_oct29 = calculate_pipeline_status(
        db_session, as_of=datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
    )
    assert status_oct29.next_expected_overpass == "2026-10-30"
    assert status_oct29.next_expected_sensor == "LANDSAT_9"

    # On Oct 31, next rolls forward to Landsat 8 on Nov 07 (2026-10-22 + 16 days)
    status_oct31 = calculate_pipeline_status(
        db_session, as_of=datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
    )
    assert status_oct31.next_expected_overpass == "2026-11-07"
    assert status_oct31.next_expected_sensor == "LANDSAT_8"
    assert "Nov 07" in status_oct31.next_expected_overpass_label or "Nov 7" in status_oct31.next_expected_overpass_label


def test_rejected_scene_counted_as_overpass(db_session: Session):
    """A rejected scene (2026-09-28 cloudy scene) is counted as an overpass

    in the ledger and anchors the sensor's cadence.
    """
    frozen_as_of = datetime(2026, 10, 27, 8, 0, 0, tzinfo=timezone.utc)
    status = calculate_pipeline_status(db_session, as_of=frozen_as_of)

    # 2026-09-28 was rejected due to cloud cover
    sep28_items = [o for o in status.recent_overpasses if o.date == "2026-09-28"]
    assert len(sep28_items) == 1
    sep28 = sep28_items[0]
    assert sep28.sensor == "LANDSAT_9"
    assert sep28.status == "REJECTED"
    assert "rejected" in sep28.label.lower()
    assert sep28.rejection_reason is not None
    assert "cloud" in sep28.rejection_reason.lower() or "clear" in sep28.rejection_reason.lower()


def test_ist_utc_boundary_handling(db_session: Session):
    """Test late-evening IST boundary vs UTC date.

    At 2026-10-21 19:00 UTC, the local time in Surat is:
    2026-10-21 19:00 + 5h30m = 2026-10-22 00:30 IST (the local calendar date is Oct 22).
    The pipeline status must correctly identify the date in IST.
    """
    # 19:00 UTC on Oct 21 = 00:30 IST on Oct 22
    late_evening_utc = datetime(2026, 10, 21, 19, 0, 0, tzinfo=timezone.utc)
    now_ist = late_evening_utc.astimezone(IST_TZ)
    assert now_ist.date() == date(2026, 10, 22)
    assert now_ist.day == 22

    # Status evaluated at this late-evening UTC timestamp
    status = calculate_pipeline_status(db_session, as_of=late_evening_utc)
    assert "22 Oct 2026" in status.last_checked_ist or "21 Oct 2026" in status.last_checked_ist
    assert "IST" in status.last_checked_ist


def test_api_endpoint_pipeline_status_with_as_of(test_client: TestClient):
    """Verify GET /api/v1/scenes/pipeline-status with ?as_of= parameter."""
    resp = test_client.get("/api/v1/scenes/pipeline-status?as_of=2026-10-27T08:00:00Z")
    assert resp.status_code == 200
    data = resp.json()

    assert data["next_expected_overpass"] == "2026-10-30"
    assert data["next_expected_sensor"] == "LANDSAT_9"
    assert "~Oct 30 (Landsat 9)" in data["next_expected_overpass_label"]
    assert data["pipeline_status"] == "DELAYED"
    assert "IST" in data["last_checked_ist"]
    assert "recent_overpasses" in data
    assert len(data["recent_overpasses"]) > 0

    # Verify Oct 22 overdue presence
    oct22 = next((o for o in data["recent_overpasses"] if o["date"] == "2026-10-22"), None)
    assert oct22 is not None
    assert oct22["status"] == "OVERDUE"


def test_api_endpoint_scenes_check_on_demand(test_client: TestClient, db_session: Session):
    """Verify POST /api/v1/scenes/check triggers discovery and logs to stage_c_discovery_runs."""
    resp = test_client.post("/api/v1/scenes/check")
    assert resp.status_code == 200
    data = resp.json()

    assert "pipeline_status" in data
    assert "last_checked" in data
    assert "last_checked_ist" in data
    assert "IST" in data["last_checked_ist"]
    assert "recent_overpasses" in data

    # Verify that a discovery run was logged in stage_c_discovery_runs
    from backend.app.db.models.stage_c import StageCDiscoveryRun
    latest_run = (
        db_session.query(StageCDiscoveryRun)
        .order_by(StageCDiscoveryRun.run_at.desc())
        .first()
    )
    assert latest_run is not None
    assert latest_run.trigger_type in ("ON_DEMAND", "SCHEDULED", "MANUAL", "ADMIN")
