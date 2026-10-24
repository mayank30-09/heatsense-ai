"""Acceptance Tests for Stage C Database Schema, Row Counts, and Integrity (T-18).

Requirements:
- T-18: Database row counts and integrity:
  - stage_c_grid_cells: 49,747 rows.
  - stage_c_grid_observations: 924,731 rows.
  - stage_c_heat_priority_scores: 49,747 rows for scoring_period='2026_summer_operational'.
  - Foreign key and relational integrity.
  - Value ranges and CHECK constraints.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models.stage_c import (
    StageCGridCell,
    StageCGridObservation,
    StageCHeatPriorityScore,
    StageCScene,
)
from backend.app.db.session import SessionLocal


@pytest.fixture(scope="module")
def db_session() -> Session:
    """Provide a database session connected to PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_t18_database_row_counts(db_session: Session) -> None:
    """T-18: Verify actual row counts in PostgreSQL match analytical and archive counts exactly."""
    # 1. stage_c_grid_cells must equal exactly 49,747
    cell_count = db_session.scalar(select(func.count()).select_from(StageCGridCell))
    assert cell_count == 49747, f"Expected 49,747 grid cells, got {cell_count}"

    # 2. stage_c_grid_observations must equal exactly 924,731
    obs_count = db_session.scalar(select(func.count()).select_from(StageCGridObservation))
    assert obs_count == 924731, f"Expected 924,731 grid observations, got {obs_count}"

    # 3. stage_c_heat_priority_scores must equal 49,747 for operational run
    score_count = db_session.scalar(
        select(func.count())
        .select_from(StageCHeatPriorityScore)
        .where(StageCHeatPriorityScore.scoring_period == "2026_summer_operational")
        .where(StageCHeatPriorityScore.spec_version == "v2.0")
    )
    assert score_count == 49747, f"Expected 49,747 operational HPI scores, got {score_count}"


def test_database_baseline_invariants(db_session: Session) -> None:
    """Verify live PostgreSQL baselines and fail immediately if baseline state or row counts change."""
    from backend.app.db.models.osm_place import OSMPlace
    from backend.app.db.models.stage_d import (
        StageDInterventionCandidate,
        StageDScenarioResult,
    )
    from backend.app.db.models.study_area import StudyArea

    # 1. stage_c_grid_cells: 49,747
    cell_count = db_session.scalar(select(func.count()).select_from(StageCGridCell))
    assert cell_count == 49747, f"Baseline violation: expected 49,747 grid cells, got {cell_count}"

    # 2. stage_c_grid_observations: 924,731
    obs_count = db_session.scalar(select(func.count()).select_from(StageCGridObservation))
    assert obs_count == 924731, f"Baseline violation: expected 924,731 grid observations, got {obs_count}"

    # 3. stage_c_heat_priority_scores: 49,747 with scoring_period only '2026_summer_operational'
    total_scores = db_session.scalar(select(func.count()).select_from(StageCHeatPriorityScore))
    assert total_scores == 49747, f"Baseline violation: expected 49,747 total scores, got {total_scores}"

    periods = set(db_session.scalars(select(StageCHeatPriorityScore.scoring_period).distinct()).all())
    assert periods == {"2026_summer_operational"}, (
        f"Baseline violation: expected scoring_period only {{'2026_summer_operational'}}, got {periods}"
    )

    # 4. stage_d_intervention_candidates: 0
    candidates_count = db_session.scalar(select(func.count()).select_from(StageDInterventionCandidate))
    assert candidates_count == 0, f"Baseline violation: expected 0 intervention candidates, got {candidates_count}"

    # 5. stage_d_scenario_results: 0
    scenario_count = db_session.scalar(select(func.count()).select_from(StageDScenarioResult))
    assert scenario_count == 0, f"Baseline violation: expected 0 scenario results, got {scenario_count}"

    # 6. study_areas: 1
    study_area_count = db_session.scalar(select(func.count()).select_from(StudyArea))
    assert study_area_count == 1, f"Baseline violation: expected 1 study area, got {study_area_count}"

    # 7. osm_places: 44
    osm_count = db_session.scalar(select(func.count()).select_from(OSMPlace))
    assert osm_count == 44, f"Baseline violation: expected 44 osm places, got {osm_count}"

    # 8. Every stage_c_scenes row whose id starts with SYNTHETIC_ or TEST_FIXTURE_ is not PROCESSED
    unexcluded_test_scenes = db_session.scalars(
        select(StageCScene.scene_id).where(
            (StageCScene.scene_id.like("SYNTHETIC_%") | StageCScene.scene_id.like("TEST_FIXTURE_%"))
            & (StageCScene.status == "PROCESSED")
        )
    ).all()
    assert len(unexcluded_test_scenes) == 0, (
        f"Baseline violation: found test/synthetic scenes with status 'PROCESSED': {unexcluded_test_scenes}"
    )


def test_t18_database_relational_integrity(db_session: Session) -> None:
    """T-18: Verify foreign key integrity and nearest OSM place resolution."""
    # Ensure all scored cells reference existing grid cells
    unmatched_scores = db_session.scalar(
        select(func.count(StageCHeatPriorityScore.pixel_id))
        .outerjoin(StageCGridCell, StageCHeatPriorityScore.pixel_id == StageCGridCell.pixel_id)
        .where(StageCGridCell.pixel_id.is_(None))
    )
    assert unmatched_scores == 0, "All heat priority scores must link to valid grid cells"

    # Check OSM place resolution coverage
    resolved_places_count = db_session.scalar(
        select(func.count(StageCGridCell.pixel_id)).where(
            StageCGridCell.nearest_osm_place_name.is_not(None)
        )
    )
    assert resolved_places_count == 49747, (
        f"All 49,747 cells should have nearest OSM place resolved, got {resolved_places_count}"
    )


def test_t18_database_score_constraints(db_session: Session) -> None:
    """T-18: Verify score ranges and valid categories in database."""
    # Check score range [0.0, 100.0]
    out_of_range = db_session.scalar(
        select(func.count(StageCHeatPriorityScore.pixel_id)).where(
            (StageCHeatPriorityScore.heat_priority_score < 0.0)
            | (StageCHeatPriorityScore.heat_priority_score > 100.0)
        )
    )
    assert out_of_range == 0, "No HPI score may fall outside [0.0, 100.0]"

    # Check chronic hotspots count
    chronic_count = db_session.scalar(
        select(func.count(StageCHeatPriorityScore.pixel_id))
        .where(StageCHeatPriorityScore.scoring_period == "2026_summer_operational")
        .where(StageCHeatPriorityScore.is_chronic_hotspot.is_(True))
    )
    assert chronic_count == 223, f"Expected exactly 223 chronic hotspots, got {chronic_count}"

    # Check fractional weights in [0.0, 1.0]
    invalid_weights = db_session.scalar(
        select(func.count(StageCGridCell.pixel_id)).where(
            (StageCGridCell.smc_fractional_weight < 0.0)
            | (StageCGridCell.smc_fractional_weight > 1.0)
        )
    )
    assert invalid_weights == 0, "Fractional weights must be bounded in [0.0, 1.0]"


def test_database_genuine_sql_null_handling(db_session: Session) -> None:
    """Verify that PostgreSQL stores and evaluates true SQL NULL (not 0.0, NaN, or -9999) for HPI scores."""
    # Use nested transaction (SAVEPOINT) to test and immediately roll back without altering state
    savepoint = db_session.begin_nested()
    try:
        # Fetch an existing pixel_id
        sample_pixel_id = db_session.scalar(select(StageCGridCell.pixel_id).limit(1))
        assert sample_pixel_id is not None

        test_period = "test_null_validation_period"
        null_score = StageCHeatPriorityScore(
            pixel_id=sample_pixel_id,
            scoring_period=test_period,
            spec_version="v2.0",
            heat_priority_score=None,  # True SQL NULL
            thermal_severity_component=None,
            persistence_component=None,
            vegetation_deficit_component=None,
            built_density_component=None,
            effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
            confidence_index=0.20,
            confidence_tier="INSUFFICIENT",
            persistence_tier="non_hotspot",
            is_chronic_hotspot=False,
            valid_seasons_count=0,
            hot_seasons_count=0,
            hotspot_frequency=0.0,
            distinct_years_count=0,
            eligibility_status="INSUFFICIENT_THERMAL_EVIDENCE",
            provenance_hash="test_null_hash",
        )
        db_session.add(null_score)
        db_session.flush()

        # 1. Query with IS NULL must find the record
        found_null = db_session.scalar(
            select(StageCHeatPriorityScore.pixel_id)
            .where(StageCHeatPriorityScore.scoring_period == test_period)
            .where(StageCHeatPriorityScore.heat_priority_score.is_(None))
        )
        assert found_null == sample_pixel_id, "SQL IS NULL must identify NULL score"

        # 2. Query with == 0.0 must NOT find the record (SQL NULL != 0.0)
        found_zero = db_session.scalar(
            select(StageCHeatPriorityScore.pixel_id)
            .where(StageCHeatPriorityScore.scoring_period == test_period)
            .where(StageCHeatPriorityScore.heat_priority_score == 0.0)
        )
        assert found_zero is None, "SQL NULL must never evaluate as equal to 0.0"

        # 3. Query with == -9999.0 must NOT find the record
        found_sentinel = db_session.scalar(
            select(StageCHeatPriorityScore.pixel_id)
            .where(StageCHeatPriorityScore.scoring_period == test_period)
            .where(StageCHeatPriorityScore.heat_priority_score == -9999.0)
        )
        assert found_sentinel is None, "SQL NULL must never evaluate as equal to -9999.0"

        # 4. Check that CHECK constraint CK_HPI_SCORE_RANGE allows NULL (evaluates to UNKNOWN)
        # Note: If NULL violated the constraint, db_session.flush() above would have raised IntegrityError
    finally:
        savepoint.rollback()


def test_stage_c_scientific_check_constraints_enforcement(db_session: Session) -> None:
    """Verify that PostgreSQL CHECK constraints strictly reject out-of-range components and invalid tiers."""
    from sqlalchemy.exc import IntegrityError
    sample_pixel_id = db_session.scalar(select(StageCGridCell.pixel_id).limit(1))
    assert sample_pixel_id is not None

    # 1. Out-of-range component (thermal_severity > 1.0) must be rejected
    savepoint = db_session.begin_nested()
    try:
        invalid_score = StageCHeatPriorityScore(
            pixel_id=sample_pixel_id,
            scoring_period="test_invalid_comp",
            spec_version="v2.0",
            heat_priority_score=50.0,
            thermal_severity_component=1.05,  # > 1.0 violates ck_hpi_thermal_severity
            persistence_component=0.5,
            vegetation_deficit_component=0.5,
            built_density_component=0.5,
            effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
            confidence_index=0.85,
            confidence_tier="HIGH",
            persistence_tier="non_hotspot",
            is_chronic_hotspot=False,
            valid_seasons_count=19,
            hot_seasons_count=2,
            hotspot_frequency=0.10,
            distinct_years_count=5,
            eligibility_status="ACCEPT",
            provenance_hash="test_invalid_hash",
        )
        db_session.add(invalid_score)
        with pytest.raises(IntegrityError) as exc_info:
            db_session.flush()
        assert "ck_hpi_thermal_severity" in str(exc_info.value).lower()
    finally:
        savepoint.rollback()

    # 2. Invalid persistence tier must be rejected
    savepoint = db_session.begin_nested()
    try:
        invalid_tier_score = StageCHeatPriorityScore(
            pixel_id=sample_pixel_id,
            scoring_period="test_invalid_tier",
            spec_version="v2.0",
            heat_priority_score=50.0,
            thermal_severity_component=0.5,
            persistence_component=0.5,
            vegetation_deficit_component=0.5,
            built_density_component=0.5,
            effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
            confidence_index=0.85,
            confidence_tier="HIGH",
            persistence_tier="SUPER_CRITICAL_HOTSPOT",  # invalid tier violates ck_hpi_persistence_tier
            is_chronic_hotspot=False,
            valid_seasons_count=19,
            hot_seasons_count=2,
            hotspot_frequency=0.10,
            distinct_years_count=5,
            eligibility_status="ACCEPT",
            provenance_hash="test_invalid_hash",
        )
        db_session.add(invalid_tier_score)
        with pytest.raises(IntegrityError) as exc_info:
            db_session.flush()
        assert "ck_hpi_persistence_tier" in str(exc_info.value).lower()
    finally:
        savepoint.rollback()

    # 3. Invalid optical imputation flag on observation must be rejected
    savepoint = db_session.begin_nested()
    try:
        invalid_obs = StageCGridObservation(
            pixel_id=sample_pixel_id,
            year=2026,
            season="summer",
            observed_lst_c=35.0,
            obs_count=5.0,
            st_qa_k=1.2,
            ndvi=0.25,
            ndbi=0.10,
            ndwi=-0.15,
            optical_imputation_flag="UNSUPPORTED_MAGIC_FLAG",  # violates ck_obs_imputation_flag
            eligibility_status="ACCEPT",
            quality_flag="CLEAN",
            source_cog="test_cog.tif",
        )
        db_session.add(invalid_obs)
        with pytest.raises(IntegrityError) as exc_info:
            db_session.flush()
        assert "ck_obs_imputation_flag" in str(exc_info.value).lower()
    finally:
        savepoint.rollback()


def test_duplicate_key_primary_key_conflict_handling(db_session: Session) -> None:
    """Verify composite primary key enforcement and duplicate key prevention."""
    from sqlalchemy.exc import IntegrityError
    sample_pixel_id = db_session.scalar(select(StageCGridCell.pixel_id).limit(1))
    assert sample_pixel_id is not None

    test_period = "test_dup_period"
    savepoint = db_session.begin_nested()
    try:
        score1 = StageCHeatPriorityScore(
            pixel_id=sample_pixel_id,
            scoring_period=test_period,
            spec_version="v2.0",
            heat_priority_score=60.0,
            thermal_severity_component=0.6,
            persistence_component=0.4,
            vegetation_deficit_component=0.5,
            built_density_component=0.5,
            effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
            confidence_index=0.88,
            confidence_tier="HIGH",
            persistence_tier="occasional_hotspot",
            is_chronic_hotspot=False,
            valid_seasons_count=19,
            hot_seasons_count=5,
            hotspot_frequency=0.26,
            distinct_years_count=5,
            eligibility_status="ACCEPT",
            provenance_hash="test_dup_hash_1",
        )
        db_session.add(score1)
        db_session.flush()

        # Duplicate insert with exact same primary key (pixel_id, scoring_period, spec_version)
        score2 = StageCHeatPriorityScore(
            pixel_id=sample_pixel_id,
            scoring_period=test_period,
            spec_version="v2.0",
            heat_priority_score=75.0,
            thermal_severity_component=0.7,
            persistence_component=0.5,
            vegetation_deficit_component=0.5,
            built_density_component=0.5,
            effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
            confidence_index=0.90,
            confidence_tier="HIGH",
            persistence_tier="frequent_hotspot",
            is_chronic_hotspot=False,
            valid_seasons_count=19,
            hot_seasons_count=8,
            hotspot_frequency=0.42,
            distinct_years_count=5,
            eligibility_status="ACCEPT",
            provenance_hash="test_dup_hash_2",
        )
        db_session.add(score2)
        with pytest.raises(IntegrityError) as exc_info:
            db_session.flush()
        assert "stage_c_heat_priority_scores_pkey" in str(exc_info.value).lower() or "duplicate key" in str(exc_info.value).lower()
    finally:
        savepoint.rollback()


def test_foreign_key_integrity_and_cascade_behavior(db_session: Session) -> None:
    """Verify that foreign keys enforce valid grid cell references and reject orphaned records."""
    from sqlalchemy.exc import IntegrityError

    non_existent_pixel = "NON_EXIST_9999"

    # Attempt inserting score referencing nonexistent grid cell -> Foreign Key Violation
    savepoint = db_session.begin_nested()
    try:
        orphan_score = StageCHeatPriorityScore(
            pixel_id=non_existent_pixel,
            scoring_period="test_fk_period",
            spec_version="v2.0",
            heat_priority_score=50.0,
            thermal_severity_component=0.5,
            persistence_component=0.5,
            vegetation_deficit_component=0.5,
            built_density_component=0.5,
            effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
            confidence_index=0.80,
            confidence_tier="HIGH",
            persistence_tier="non_hotspot",
            is_chronic_hotspot=False,
            valid_seasons_count=19,
            hot_seasons_count=1,
            hotspot_frequency=0.05,
            distinct_years_count=5,
            eligibility_status="ACCEPT",
            provenance_hash="test_fk_hash",
        )
        db_session.add(orphan_score)
        with pytest.raises(IntegrityError) as exc_info:
            db_session.flush()
        assert "violates foreign key constraint" in str(exc_info.value).lower()
    finally:
        savepoint.rollback()


def test_idempotent_score_upsert_behavior(db_session: Session) -> None:
    """Verify PostgreSQL ON CONFLICT DO UPDATE behavior for idempotent score ingestion."""
    from sqlalchemy.dialects.postgresql import insert
    sample_pixel_id = db_session.scalar(select(StageCGridCell.pixel_id).limit(1))
    assert sample_pixel_id is not None

    test_period = "test_upsert_period"
    savepoint = db_session.begin_nested()
    try:
        # Initial insert
        stmt1 = (
            insert(StageCHeatPriorityScore)
            .values(
                pixel_id=sample_pixel_id,
                scoring_period=test_period,
                spec_version="v2.0",
                heat_priority_score=55.0,
                thermal_severity_component=0.55,
                persistence_component=0.45,
                vegetation_deficit_component=0.50,
                built_density_component=0.50,
                effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
                confidence_index=0.85,
                confidence_tier="HIGH",
                persistence_tier="occasional_hotspot",
                is_chronic_hotspot=False,
                valid_seasons_count=19,
                hot_seasons_count=4,
                hotspot_frequency=0.21,
                distinct_years_count=5,
                eligibility_status="ACCEPT",
                provenance_hash="hash_v1",
            )
            .on_conflict_do_update(
                index_elements=["pixel_id", "scoring_period", "spec_version"],
                set_={"heat_priority_score": 55.0},
            )
        )
        db_session.execute(stmt1)
        db_session.flush()

        # Idempotent re-run with updated score and components
        stmt2 = (
            insert(StageCHeatPriorityScore)
            .values(
                pixel_id=sample_pixel_id,
                scoring_period=test_period,
                spec_version="v2.0",
                heat_priority_score=72.5,
                thermal_severity_component=0.725,
                persistence_component=0.60,
                vegetation_deficit_component=0.50,
                built_density_component=0.50,
                effective_weights={"w_T": 0.4, "w_P": 0.3, "w_V": 0.15, "w_B": 0.15},
                confidence_index=0.92,
                confidence_tier="HIGH",
                persistence_tier="frequent_hotspot",
                is_chronic_hotspot=False,
                valid_seasons_count=19,
                hot_seasons_count=7,
                hotspot_frequency=0.37,
                distinct_years_count=5,
                eligibility_status="ACCEPT",
                provenance_hash="hash_v2",
            )
            .on_conflict_do_update(
                index_elements=["pixel_id", "scoring_period", "spec_version"],
                set_={
                    "heat_priority_score": 72.5,
                    "confidence_index": 0.92,
                    "provenance_hash": "hash_v2",
                },
            )
        )
        db_session.execute(stmt2)
        db_session.flush()

        # Verify only one row exists and score was updated
        updated_score = db_session.scalar(
            select(StageCHeatPriorityScore.heat_priority_score)
            .where(StageCHeatPriorityScore.pixel_id == sample_pixel_id)
            .where(StageCHeatPriorityScore.scoring_period == test_period)
        )
        assert updated_score == pytest.approx(72.5, rel=1e-3)
    finally:
        savepoint.rollback()

