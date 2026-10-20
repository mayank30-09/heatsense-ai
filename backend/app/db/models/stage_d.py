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

