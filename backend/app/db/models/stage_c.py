"""SQLAlchemy models for Stage C Heat Priority database schema."""

from datetime import date, datetime
from typing import Any
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class StageCGridCell(Base):
    """Authoritative analytical grid cell geometry and spatial properties."""

    __tablename__ = "stage_c_grid_cells"

    pixel_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    row_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    col_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[float] = mapped_column(Float(53), nullable=False)
    longitude: Mapped[float] = mapped_column(Float(53), nullable=False)
    x_utm: Mapped[float] = mapped_column(Float(53), nullable=False)
    y_utm: Mapped[float] = mapped_column(Float(53), nullable=False)

    geometry = mapped_column(
        Geometry(
            geometry_type="POLYGON",
            srid=4326,
            spatial_index=True,
        ),
        nullable=False,
    )

    nominal_area_m2: Mapped[float] = mapped_column(Float(53), nullable=False)
    smc_clipped_area_m2: Mapped[float] = mapped_column(Float(53), nullable=False)
    smc_fractional_weight: Mapped[float] = mapped_column(Float(53), nullable=False)
    is_centroid_inside: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_boundary_cell: Mapped[bool] = mapped_column(Boolean, nullable=False)

    nearest_osm_place_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osm_places.id", ondelete="SET NULL"), nullable=True
    )
    nearest_osm_place_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nearest_osm_distance_m: Mapped[float | None] = mapped_column(Float(24), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "smc_fractional_weight >= 0.0 AND smc_fractional_weight <= 1.0",
            name="ck_cells_fractional_weight",
        ),
    )

    # Relationships
    observations = relationship(
        "StageCGridObservation", back_populates="grid_cell", cascade="all, delete-orphan"
    )
    scores = relationship(
        "StageCHeatPriorityScore", back_populates="grid_cell", cascade="all, delete-orphan"
    )
    scene_observations = relationship(
        "StageCSceneObservation", back_populates="grid_cell", cascade="all, delete-orphan"
    )


class StageCGridObservation(Base):
    """Multi-temporal seasonal observations per grid cell."""

    __tablename__ = "stage_c_grid_observations"

    pixel_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("stage_c_grid_cells.pixel_id", ondelete="CASCADE"), primary_key=True
    )
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    season: Mapped[str] = mapped_column(String(16), primary_key=True)

    observed_lst_c: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    obs_count: Mapped[float] = mapped_column(Float(24), nullable=False)
    st_qa_k: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    ndvi: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    ndbi: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    ndwi: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    optical_imputation_flag: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NONE", server_default="NONE"
    )
    eligibility_status: Mapped[str] = mapped_column(String(16), nullable=False)
    quality_flag: Mapped[str] = mapped_column(String(128), nullable=False)
    source_cog: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "season IN ('winter', 'summer', 'monsoon', 'post_monsoon')",
            name="ck_obs_season",
        ),
        CheckConstraint(
            "eligibility_status IN ('ACCEPT', 'FLAG', 'EXCLUDE')",
            name="ck_obs_eligibility",
        ),
        CheckConstraint(
            "optical_imputation_flag IN ('NONE', 'OPTICAL_IMPUTED_MEDIAN', 'OPTICAL_IMPUTED_BOUNDARY', 'OPTICAL_FALLBACK_NEUTRAL')",
            name="ck_obs_imputation_flag",
        ),
    )

    grid_cell = relationship("StageCGridCell", back_populates="observations")


class StageCHeatPriorityScore(Base):
    """Versioned Heat Priority composite scores and component layers."""

    __tablename__ = "stage_c_heat_priority_scores"

    pixel_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("stage_c_grid_cells.pixel_id", ondelete="CASCADE"), primary_key=True
    )
    scoring_period: Mapped[str] = mapped_column(String(32), primary_key=True)
    spec_version: Mapped[str] = mapped_column(
        String(16), primary_key=True, default="v2.0", server_default="v2.0"
    )

    heat_priority_score: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    thermal_severity_component: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    persistence_component: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    vegetation_deficit_component: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    built_density_component: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    effective_weights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    confidence_index: Mapped[float] = mapped_column(Float(24), nullable=False)
    confidence_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    persistence_tier: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    is_chronic_hotspot: Mapped[bool] = mapped_column(Boolean, nullable=False)
    valid_seasons_count: Mapped[int] = mapped_column(Integer, nullable=False)
    hot_seasons_count: Mapped[int] = mapped_column(Integer, nullable=False)
    hotspot_frequency: Mapped[float] = mapped_column(Float(24), nullable=False)
    distinct_years_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "heat_priority_score >= 0.0 AND heat_priority_score <= 100.0",
            name="ck_hpi_score_range",
        ),
        CheckConstraint(
            "thermal_severity_component >= 0.0 AND thermal_severity_component <= 1.0",
            name="ck_hpi_thermal_severity",
        ),
        CheckConstraint(
            "persistence_component >= 0.0 AND persistence_component <= 1.0",
            name="ck_hpi_persistence",
        ),
        CheckConstraint(
            "vegetation_deficit_component >= 0.0 AND vegetation_deficit_component <= 1.0",
            name="ck_hpi_vegetation_deficit",
        ),
        CheckConstraint(
            "built_density_component >= 0.0 AND built_density_component <= 1.0",
            name="ck_hpi_built_density",
        ),
        CheckConstraint(
            "confidence_index >= 0.0 AND confidence_index <= 1.0",
            name="ck_hpi_confidence_index",
        ),
        CheckConstraint(
            "hotspot_frequency >= 0.0 AND hotspot_frequency <= 1.0",
            name="ck_hpi_hotspot_frequency",
        ),
        CheckConstraint(
            "confidence_tier IN ('HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT')",
            name="ck_hpi_confidence_tier",
        ),
        CheckConstraint(
            "persistence_tier IN ('chronic_hotspot', 'frequent_hotspot', 'occasional_hotspot', 'transient_extreme', 'non_hotspot')",
            name="ck_hpi_persistence_tier",
        ),
        CheckConstraint(
            "eligibility_status IN ('ACCEPT', 'FLAG', 'EXCLUDE', 'INSUFFICIENT_THERMAL_EVIDENCE')",
            name="ck_hpi_eligibility",
        ),
    )

    grid_cell = relationship("StageCGridCell", back_populates="scores")


class StageCScene(Base):
    """Near-real-time scene acquisition ledger and metadata."""

    __tablename__ = "stage_c_scenes"

    scene_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    acquisition_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sensor: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[int] = mapped_column(Integer, nullable=False, default=148)
    row: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    cloud_cover: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    valid_pixel_fraction: Mapped[float] = mapped_column(Float(24), nullable=False)
    mean_lst_c: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    max_lst_c: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROCESSED", index=True)
    cog_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PROCESSED', 'REJECTED_CLOUDY', 'FAILED', 'PENDING', 'SYNTHETIC_EXCLUDED')",
            name="ck_scene_status",
        ),
        CheckConstraint(
            "valid_pixel_fraction >= 0.0 AND valid_pixel_fraction <= 1.0",
            name="ck_scene_valid_pixel_fraction",
        ),
    )

    observations = relationship(
        "StageCSceneObservation", back_populates="scene", cascade="all, delete-orphan"
    )


class StageCSceneObservation(Base):
    """Pixel-level LST observation for an ingested near-real-time scene."""

    __tablename__ = "stage_c_scene_observations"

    scene_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("stage_c_scenes.scene_id", ondelete="CASCADE"), primary_key=True
    )
    pixel_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("stage_c_grid_cells.pixel_id", ondelete="CASCADE"), primary_key=True
    )
    observed_lst_c: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    st_qa_k: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    scene = relationship("StageCScene", back_populates="observations")
    grid_cell = relationship("StageCGridCell", back_populates="scene_observations")


class StageCSceneRegistry(Base):
    """Near-real-time scene lifecycle registry tracking discovery to publication/rejection."""

    __tablename__ = "stage_c_scene_registry"

    scene_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sensor: Mapped[str] = mapped_column(String(32), nullable=False)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    acquisition_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    path: Mapped[int] = mapped_column(Integer, nullable=False, default=148)
    row: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    cloud_cover: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    valid_pixel_fraction: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    clear_threshold: Mapped[float] = mapped_column(Float(24), nullable=False, default=0.40)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="discovered", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mean_lst_c: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    max_lst_c: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    cog_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('discovered', 'downloaded', 'qa_passed', 'scored', 'published', 'rejected')",
            name="ck_scene_registry_status",
        ),
        CheckConstraint(
            "clear_threshold >= 0.0 AND clear_threshold <= 1.0",
            name="ck_scene_registry_threshold",
        ),
    )


class StageCProvisionalHotspot(Base):
    """Provisional single-scene NRT hotspot flagged independently of frozen HPI tables."""

    __tablename__ = "stage_c_provisional_hotspots"

    scene_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    pixel_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("stage_c_grid_cells.pixel_id", ondelete="CASCADE"), primary_key=True, index=True
    )
    observed_lst_c: Mapped[float] = mapped_column(Float(24), nullable=False)
    climatology_lst_c: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    thermal_anomaly_c: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    percentile_rank: Mapped[float | None] = mapped_column(Float(24), nullable=True)
    is_provisional_hotspot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hotspot_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Provisional NRT hotspot, single scene"
    )
    flagged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    grid_cell = relationship("StageCGridCell")


class StageCDiscoveryRun(Base):
    """Execution audit log for NRT Landsat scene discovery checks."""

    __tablename__ = "stage_c_discovery_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    trigger_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SCHEDULED"
    )
    scenes_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scenes_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[str | None] = mapped_column(String(512), nullable=True)


