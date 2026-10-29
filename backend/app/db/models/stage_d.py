"""SQLAlchemy models for Stage D Interventions and Scenarios database schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class StageDInterventionCandidate(Base):
    """Database model for Stage D candidate interventions."""

    __tablename__ = "stage_d_intervention_candidates"

    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cell_id: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    intervention_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    usable_area_m2: Mapped[float] = mapped_column(Float, nullable=False)
    tree_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    cost_inr_min: Mapped[float] = mapped_column(Float, nullable=False)
    cost_inr_max: Mapped[float] = mapped_column(Float, nullable=False)
    expected_cooling_c: Mapped[float] = mapped_column(Float, nullable=False)
    expected_cooling_c_min: Mapped[float] = mapped_column(Float, nullable=False)
    expected_cooling_c_max: Mapped[float] = mapped_column(Float, nullable=False)
    feasibility_status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    rejection_reason: Mapped[str] = mapped_column(String(40), nullable=False)
    baseline_hpi: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_lst_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_chronic_hotspot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    administrative_zone: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    evidence_status: Mapped[str] = mapped_column(
        String(64), default="CALIBRATED_EMPIRICAL_MICROCLIMATE", nullable=False
    )

    geometry = mapped_column(
        Geometry(
            geometry_type="POLYGON",
            srid=4326,
            spatial_index=True,
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_stage_d_candidates_zone_type", "administrative_zone", "intervention_type"),
        Index("ix_stage_d_candidates_feasibility", "feasibility_status"),
    )


class StageDScenarioResult(Base):
    """Database model for saved Stage D optimization scenario runs and Pareto solutions."""

    __tablename__ = "stage_d_scenario_results"

    scenario_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    algorithm: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    budget_inr: Mapped[float] = mapped_column(Float, nullable=False)
    total_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    # Corrected extensive & area-weighted cooling metrics
    portfolio_thermal_benefit_c_m2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    treated_area_m2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    mean_local_cooling_c: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    citywide_cooling_c: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    domain_area_m2: Mapped[float] = mapped_column(Float, nullable=False, default=461630791.0)
    heat_priority_weighted_benefit_c_m2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    population_exposure_benefit: Mapped[float | None] = mapped_column(Float, nullable=True)
    population_exposure_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="POPULATION_DATA_UNAVAILABLE"
    )
    # Legacy fields maintained for backward schema compatibility
    total_cooling_c: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    heat_weighted_cooling: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    chronic_hotspots_count: Mapped[int] = mapped_column(Integer, nullable=False)
    interventions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_feasible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pareto_rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    selected_candidates_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )



class StageDLandCoverPipelineRun(Base):
    """Database model for tracking Dynamic World pipeline run provenance."""

    __tablename__ = "stage_d_landcover_pipeline_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    total_cells: Mapped[int] = mapped_column(Integer, nullable=False)
    cells_sufficient: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cells_insufficient: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cells_no_observations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_observations_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    source_dataset: Mapped[str] = mapped_column(String(64), nullable=False, default="GOOGLE/DYNAMICWORLD/V1")
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    attribution: Mapped[str] = mapped_column(String(256), nullable=False)
    citation: Mapped[str] = mapped_column(String(256), nullable=False)
    license: Mapped[str] = mapped_column(String(64), nullable=False, default="CC-BY-4.0")
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StageDDynamicWorldLandCover(Base):
    """Database model for cell-level seasonal Dynamic World land-cover probabilities & hard-label proportions."""

    __tablename__ = "stage_d_dynamic_world_landcover"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cell_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("stage_c_grid_cells.pixel_id", ondelete="CASCADE"), index=True, nullable=False
    )
    season: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)

    # 9 Class Mean Probabilities
    mean_water: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_trees: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_grass: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_flooded_vegetation: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_crops: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_shrub_and_scrub: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_built: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_bare: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_snow_and_ice: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 9 Hard-Label Proportions
    prop_water: Mapped[float | None] = mapped_column(Float, nullable=True)
    prop_trees: Mapped[float | None] = mapped_column(Float, nullable=True)
    prop_grass: Mapped[float | None] = mapped_column(Float, nullable=True)
    prop_flooded_vegetation: Mapped[float | None] = mapped_column(Float, nullable=True)
    prop_crops: Mapped[float | None] = mapped_column(Float, nullable=True)
    prop_shrub_and_scrub: Mapped[float | None] = mapped_column(Float, nullable=True)
    prop_built: Mapped[float | None] = mapped_column(Float, nullable=True)
    prop_bare: Mapped[float | None] = mapped_column(Float, nullable=True)
    prop_snow_and_ice: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Classification diagnostics
    valid_observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_class: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    entropy: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="SUFFICIENT")

    # Provenance
    source_dataset: Mapped[str] = mapped_column(String(64), nullable=False, default="GOOGLE/DYNAMICWORLD/V1")
    class_schema: Mapped[str] = mapped_column(String(64), nullable=False, default="dw_9class_v1")
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
