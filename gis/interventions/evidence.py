"""
HEATSENSE AI - Evidence Provider Registry and Extraction Layer
Stage D - Spatial Intervention Reasoning Engine

Provides an auditable, explicit interface for querying physical evidence
within an arbitrary spatial geometry. Every evidence provider declares:
  - Availability: AVAILABLE | PARTIAL | UNAVAILABLE
  - Provenance: dataset name, version, acquisition/processing date, authority
  - Spatial Resolution: native resolution (e.g., 30m, 10m, vector)
  - Coverage: fraction of target geometry covered by valid observations
  - Quality Flag: heuristic observation support / QA status
  - Missing Reason: explicit statement if UNAVAILABLE or PARTIAL

HARD RULES:
1. No provider silently returns zeros for missing data.
2. Dynamic World fractions are screening evidence only; they never establish
   cadastral roof area, vacancy, ownership, legal availability, road width,
   or planting suitability.
3. No locality-specific branching anywhere.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models.stage_c import (
    StageCGridCell,
    StageCGridObservation,
    StageCHeatPriorityScore,
)
from backend.app.db.models.stage_d import StageDDynamicWorldLandCover


class EvidenceAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceExtractionResult(BaseModel):
    provider_name: str = Field(..., description="Unique provider identifier")
    display_title: str = Field(..., description="Human-readable evidence layer name")
    availability: EvidenceAvailability = Field(..., description="AVAILABLE, PARTIAL, or UNAVAILABLE")
    dataset_name: str = Field(..., description="Authoritative dataset name")
    version: str = Field(..., description="Dataset or ingestion pipeline version")
    effective_date: str = Field(..., description="Effective observation date or composite window")
    spatial_resolution: str = Field(..., description="Physical or grid resolution")
    authority: str = Field(..., description="Originating scientific or municipal agency")
    coverage_fraction: float = Field(default=0.0, description="Fraction of geometry with valid data (0.0 to 1.0)")
    quality_flag: str = Field(default="UNKNOWN", description="QA classification or confidence support tier")
    missing_reason: Optional[str] = Field(default=None, description="Explicit statement if unavailable or partial")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Extracted numerical and categorical metrics")
    screening_caveats: List[str] = Field(default_factory=list, description="Mandatory screening limitations")


def compute_evidence_cache_key(
    geometry: dict,
    season: str,
    year: int,
    parameters: Optional[dict] = None,
    rule_version: str = "2.0.0",
    data_version: str = "2026.1",
) -> str:
    """Compute a deterministic cache key guaranteeing spatial, temporal, and rule isolation.

    Guarantees isolation across:
    1. Geometry coordinates
    2. Season and year
    3. Operational parameters
    4. Reasoning rule engine version
    5. Underlying dataset versions
    """
    payload = {
        "geom": geometry.get("coordinates") if isinstance(geometry, dict) else str(geometry),
        "season": season.lower(),
        "year": int(year),
        "params": parameters or {},
        "rule_version": rule_version,
        "data_version": data_version,
    }
    dumped = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class EvidenceProvider:
    """Abstract base provider for physical evidence layers."""

    name: str = "base_provider"
    display_title: str = "Base Evidence Provider"
    availability: EvidenceAvailability = EvidenceAvailability.UNAVAILABLE
    dataset_name: str = "Unknown"
    version: str = "1.0.0"
    effective_date: str = "Unknown"
    spatial_resolution: str = "Unknown"
    authority: str = "Unknown"
    missing_reason: Optional[str] = None

    def extract(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> EvidenceExtractionResult:
        raise NotImplementedError


class ObservedLSTProvider(EvidenceProvider):
    """Satellite Land Surface Temperature (LST) evidence provider."""

    name = "observed_lst"
    display_title = "Observed Satellite Land Surface Temperature"
    availability = EvidenceAvailability.AVAILABLE
    dataset_name = "Landsat 8/9 Level-2 Science Product (TIRS Band 10)"
    version = "Collection 2 Level-2 Tier 1"
    effective_date = "Summer 2026 Authoritative Composite"
    spatial_resolution = "30m thermal resampled to 100m SMC grid (EPSG:32643)"
    authority = "USGS / NASA Landsat Science Team"

    def extract(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> EvidenceExtractionResult:
        caveats = [
            "LST measures surface radiometric skin temperature at Landsat overpass time (~10:45 AM local solar time).",
            "Surface skin temperature is NOT ambient 2m air temperature; atmospheric air temperature is unmodeled.",
        ]
        if not cached_cells:
            return EvidenceExtractionResult(
                provider_name=self.name,
                display_title=self.display_title,
                availability=EvidenceAvailability.PARTIAL,
                dataset_name=self.dataset_name,
                version=self.version,
                effective_date=f"{season.title()} {year}",
                spatial_resolution=self.spatial_resolution,
                authority=self.authority,
                coverage_fraction=0.0,
                quality_flag="NO_DATA",
                missing_reason="No intersecting grid cells or observations found for polygon.",
                metrics={},
                screening_caveats=caveats,
            )

        # Extract thermal metrics if present in observation or cell
        lst_values = [
            getattr(c, "lst_summer_2026_c", None) or getattr(c, "observed_lst_c", None)
            for c in cached_cells
            if getattr(c, "lst_summer_2026_c", None) is not None or getattr(c, "observed_lst_c", None) is not None
        ]

        if not lst_values:
            coverage = 0.0
            quality = "NO_OBSERVATIONS"
            mean_lst = None
            max_lst = None
        else:
            coverage = len(lst_values) / len(cached_cells)
            mean_lst = float(sum(lst_values) / len(lst_values))
            max_lst = float(max(lst_values))
            quality = "HIGH" if coverage >= 0.80 else ("PARTIAL" if coverage >= 0.40 else "POOR")

        return EvidenceExtractionResult(
            provider_name=self.name,
            display_title=self.display_title,
            availability=EvidenceAvailability.AVAILABLE if coverage > 0 else EvidenceAvailability.PARTIAL,
            dataset_name=self.dataset_name,
            version=self.version,
            effective_date=f"{season.title()} {year}",
            spatial_resolution=self.spatial_resolution,
            authority=self.authority,
            coverage_fraction=round(coverage, 4),
            quality_flag=quality,
            missing_reason=None if coverage > 0 else f"No valid observations in {season} {year}",
            metrics={
                "mean_lst_c": round(mean_lst, 2) if mean_lst is not None else None,
                "max_lst_c": round(max_lst, 2) if max_lst is not None else None,
                "valid_obs_count": len(lst_values),
                "total_cells": len(cached_cells),
            },
            screening_caveats=caveats,
        )


class HPIPersistenceProvider(EvidenceProvider):
    """Heat Priority Index (HPI), persistence, and chronic hotspot evidence."""

    name = "hpi_persistence"
    display_title = "Heat Priority Index & Chronic Thermal Persistence"
    availability = EvidenceAvailability.AVAILABLE
    dataset_name = "HEATSENSE AI Heat Priority Index (HPI)"
    version = "Stage C Authoritative Frozen Baseline"
    effective_date = "Summer 2026 (Historical 2023-2026 Multi-Year Recurrence)"
    spatial_resolution = "100m planar SMC grid (EPSG:32643)"
    authority = "HEATSENSE AI Heat Health Action Protocol"

    def extract(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> EvidenceExtractionResult:
        caveats = [
            "HPI is a deterministic multi-criteria index (0-100) combining thermal hazard (40%), built density (30%), vegetation deficit (15%), and temporal persistence (15%).",
            "C_i represents an observational quality support heuristic (C_obs × C_qa × C_season × C_sentinel), not a statistical probability.",
            "Chronic hotspots (223 citywide) require multi-year recurrent thermal anomaly (frequency >= 0.50, persistence >= 0.60, min 3 seasons).",
        ]

        if not cached_cells:
            return EvidenceExtractionResult(
                provider_name=self.name,
                display_title=self.display_title,
                availability=EvidenceAvailability.PARTIAL,
                dataset_name=self.dataset_name,
                version=self.version,
                effective_date=self.effective_date,
                spatial_resolution=self.spatial_resolution,
                authority=self.authority,
                coverage_fraction=0.0,
                quality_flag="NO_DATA",
                missing_reason="No intersecting grid cells found.",
                metrics={},
                screening_caveats=caveats,
            )

        hpi_vals = [getattr(c, "heat_priority_score", None) for c in cached_cells if getattr(c, "heat_priority_score", None) is not None]
        chronic_flags = [bool(getattr(c, "is_chronic_hotspot", False)) for c in cached_cells]
        conf_vals = [getattr(c, "confidence_index", None) for c in cached_cells if getattr(c, "confidence_index", None) is not None]

        mean_hpi = float(sum(hpi_vals) / len(hpi_vals)) if hpi_vals else None
        max_hpi = float(max(hpi_vals)) if hpi_vals else None
        chronic_count = sum(1 for f in chronic_flags if f)
        chronic_share = float(chronic_count / len(cached_cells))
        mean_conf = float(sum(conf_vals) / len(conf_vals)) if conf_vals else 0.0

        return EvidenceExtractionResult(
            provider_name=self.name,
            display_title=self.display_title,
            availability=EvidenceAvailability.AVAILABLE,
            dataset_name=self.dataset_name,
            version=self.version,
            effective_date=self.effective_date,
            spatial_resolution=self.spatial_resolution,
            authority=self.authority,
            coverage_fraction=1.0 if hpi_vals else 0.0,
            quality_flag="HIGH" if mean_conf >= 0.75 else ("MEDIUM" if mean_conf >= 0.50 else "LOW"),
            missing_reason=None,
            metrics={
                "mean_hpi": round(mean_hpi, 2) if mean_hpi is not None else None,
                "max_hpi": round(max_hpi, 2) if max_hpi is not None else None,
                "chronic_hotspot_count": chronic_count,
                "chronic_hotspot_share": round(chronic_share, 4),
                "is_chronic_priority": bool(chronic_count > 0 or (max_hpi and max_hpi >= 70.0)),
                "observational_quality_ci": round(mean_conf, 4),
            },
            screening_caveats=caveats,
        )


class DynamicWorldLandCoverProvider(EvidenceProvider):
    """Sentinel-2 10m near-real-time land cover probabilities evidence provider."""

    name = "dynamic_world_landcover"
    display_title = "Sentinel-2 Dynamic World Land Cover (10m LULC)"
    availability = EvidenceAvailability.AVAILABLE
    dataset_name = "ESA/Google Dynamic World Sentinel-2 L2A Near-Real-Time Land Cover"
    version = "V1 (Multi-temporal Composite)"
    effective_date = "Summer 2026 Reference Composite"
    spatial_resolution = "10m pixel-level multi-class probability distribution"
    authority = "World Resources Institute / Google Earth Engine"

    def extract(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> EvidenceExtractionResult:
        caveats = [
            "Dynamic World land-cover probabilities serve as satellite screening evidence only.",
            "Dynamic World does NOT establish cadastral parcel boundaries, roof structural load capacity, property ownership, road right-of-way, or physical planting feasibility.",
            "All derived physical intervention areas are provisional and require on-site municipal engineering survey.",
        ]

        # Extract land cover fractions if db and geometry are provided
        p_built = 0.0
        p_bare = 0.0
        p_grass = 0.0
        p_trees = 0.0
        p_water = 0.0
        has_dw_data = False

        if db is not None and cached_cells:
            pixel_ids = [getattr(c, "pixel_id", None) for c in cached_cells if getattr(c, "pixel_id", None) is not None]
            if pixel_ids:
                dw_rows = (
                    db.query(
                        func.avg(StageDDynamicWorldLandCover.built_ratio).label("avg_built"),
                        func.avg(StageDDynamicWorldLandCover.bare_ratio).label("avg_bare"),
                        func.avg(StageDDynamicWorldLandCover.grass_ratio).label("avg_grass"),
                        func.avg(StageDDynamicWorldLandCover.trees_ratio).label("avg_trees"),
                        func.avg(StageDDynamicWorldLandCover.water_ratio).label("avg_water"),
                    )
                    .filter(StageDDynamicWorldLandCover.pixel_id.in_(pixel_ids))
                    .first()
                )
                if dw_rows and dw_rows.avg_built is not None:
                    p_built = float(dw_rows.avg_built or 0.0)
                    p_bare = float(dw_rows.avg_bare or 0.0)
                    p_grass = float(dw_rows.avg_grass or 0.0)
                    p_trees = float(dw_rows.avg_trees or 0.0)
                    p_water = float(dw_rows.avg_water or 0.0)
                    has_dw_data = True

        return EvidenceExtractionResult(
            provider_name=self.name,
            display_title=self.display_title,
            availability=EvidenceAvailability.AVAILABLE if has_dw_data else EvidenceAvailability.PARTIAL,
            dataset_name=self.dataset_name,
            version=self.version,
            effective_date=self.effective_date,
            spatial_resolution=self.spatial_resolution,
            authority=self.authority,
            coverage_fraction=1.0 if has_dw_data else 0.0,
            quality_flag="HIGH" if has_dw_data else "NO_DW_ROWS",
            missing_reason=None if has_dw_data else "Dynamic World landcover records not populated for these cells.",
            metrics={
                "p_built": round(p_built, 4),
                "p_bare": round(p_bare, 4),
                "p_grass": round(p_grass, 4),
                "p_trees": round(p_trees, 4),
                "p_water": round(p_water, 4),
                "has_dw_coverage": has_dw_data,
            },
            screening_caveats=caveats,
        )


class RoadNetworkProvider(EvidenceProvider):
    """Surat Municipal Corporation road network and right-of-way GIS provider (UNAVAILABLE)."""

    name = "road_network"
    display_title = "Surat Municipal Road Network & Right-of-Way GIS"
    availability = EvidenceAvailability.UNAVAILABLE
    dataset_name = "SMC Municipal Road Network GIS Layer"
    version = "N/A"
    effective_date = "N/A"
    spatial_resolution = "Vector centerlines & pavement boundaries"
    authority = "Surat Municipal Corporation (SMC) Road Development Department"
    missing_reason = (
        "Municipal road network GIS layer with right-of-way (ROW), carriageway width, "
        "sidewalk presence/width, and pedestrian volume is UNAVAILABLE in repository or database."
    )

    def extract(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> EvidenceExtractionResult:
        return EvidenceExtractionResult(
            provider_name=self.name,
            display_title=self.display_title,
            availability=self.availability,
            dataset_name=self.dataset_name,
            version=self.version,
            effective_date=self.effective_date,
            spatial_resolution=self.spatial_resolution,
            authority=self.authority,
            coverage_fraction=0.0,
            quality_flag="UNAVAILABLE",
            missing_reason=self.missing_reason,
            metrics={"road_segments_available": False, "verified_sidewalk_width_m": None},
            screening_caveats=[
                "Avenue trees, shaded corridors, and cool street pavements cannot be aligned to specific road segments without municipal ROW data.",
                "Corridor interventions require field survey verification of utilities, traffic safety clearances, and setback requirements.",
            ],
        )


class BuildingFootprintProvider(EvidenceProvider):
    """Cadastral building footprints and structural capacity provider (UNAVAILABLE)."""

    name = "building_footprints"
    display_title = "Cadastral Building Footprints & Structural Engineering Records"
    availability = EvidenceAvailability.UNAVAILABLE
    dataset_name = "SMC Cadastral Building Footprints & Structural Load Ratings"
    version = "N/A"
    effective_date = "N/A"
    spatial_resolution = "Vector polygon footprints & heights"
    authority = "SMC Town Planning Department & Structural Engineering Cell"
    missing_reason = (
        "Cadastral building footprints layer with structural load ratings (e.g. RCC vs sheet roof), "
        "building heights, and verified roof usable area is UNAVAILABLE in repository or database."
    )

    def extract(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> EvidenceExtractionResult:
        return EvidenceExtractionResult(
            provider_name=self.name,
            display_title=self.display_title,
            availability=self.availability,
            dataset_name=self.dataset_name,
            version=self.version,
            effective_date=self.effective_date,
            spatial_resolution=self.spatial_resolution,
            authority=self.authority,
            coverage_fraction=0.0,
            quality_flag="UNAVAILABLE",
            missing_reason=self.missing_reason,
            metrics={"vector_footprints_available": False, "structural_load_verified": False},
            screening_caveats=[
                "Roof areas derived from satellite built fractions (P_built or NDBI) are screening approximations.",
                "Structural load capacity (especially for extensive green roofs ~120-150 kg/m²) MUST be verified by a licensed structural engineer prior to tender.",
            ],
        )


class CadastralOwnershipProvider(EvidenceProvider):
    """Cadastral parcel boundaries and public/private land tenure provider (UNAVAILABLE)."""

    name = "cadastral_ownership"
    display_title = "Cadastral Parcel Boundaries & Land Tenure Records"
    availability = EvidenceAvailability.UNAVAILABLE
    dataset_name = "Gujarat Revenue Department / SMC Town Planning Scheme (TPS) Cadastre"
    version = "N/A"
    effective_date = "N/A"
    spatial_resolution = "Cadastral revenue parcel polygons"
    authority = "Gujarat Revenue Department / SMC Town Planning"
    missing_reason = (
        "Cadastral parcel boundaries and legal tenure (public municipal vs private commercial/residential) "
        "are UNAVAILABLE in repository or database."
    )

    def extract(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> EvidenceExtractionResult:
        return EvidenceExtractionResult(
            provider_name=self.name,
            display_title=self.display_title,
            availability=self.availability,
            dataset_name=self.dataset_name,
            version=self.version,
            effective_date=self.effective_date,
            spatial_resolution=self.spatial_resolution,
            authority=self.authority,
            coverage_fraction=0.0,
            quality_flag="UNAVAILABLE",
            missing_reason=self.missing_reason,
            metrics={"cadastral_boundary_available": False, "public_ownership_verified": False},
            screening_caveats=[
                "Implementation feasibility status is strictly capped at FEASIBLE_SUBJECT_TO_SURVEY.",
                "Legal clearance and right to execute on private or institutional parcels requires municipal authorization.",
            ],
        )


class DrainageDEMProvider(EvidenceProvider):
    """High-resolution DEM, terrain, and stormwater drainage network provider (UNAVAILABLE)."""

    name = "drainage_dem"
    display_title = "High-Resolution LiDAR DEM & Stormwater Drainage Network"
    availability = EvidenceAvailability.UNAVAILABLE
    dataset_name = "SMC High-Resolution LiDAR DEM & Stormwater Drainage Master Plan"
    version = "N/A"
    effective_date = "N/A"
    spatial_resolution = "1m LiDAR DEM & drainage vector network"
    authority = "SMC Hydraulic / Drainage Engineering Department"
    missing_reason = (
        "High-resolution DEM/elevation, flow accumulation, water table depth, and municipal stormwater "
        "drainage network GIS data are UNAVAILABLE in repository or database."
    )

    def extract(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> EvidenceExtractionResult:
        return EvidenceExtractionResult(
            provider_name=self.name,
            display_title=self.display_title,
            availability=self.availability,
            dataset_name=self.dataset_name,
            version=self.version,
            effective_date=self.effective_date,
            spatial_resolution=self.spatial_resolution,
            authority=self.authority,
            coverage_fraction=0.0,
            quality_flag="UNAVAILABLE",
            missing_reason=self.missing_reason,
            metrics={"dem_available": False, "drainage_network_available": False},
            screening_caveats=[
                "Retention ponds, bioswales, and rain gardens CANNOT be recommended solely because an area is hot.",
                "Blue-green stormwater interventions are marked NOT_APPLICABLE until catchment hydrology and terrain data are integrated.",
            ],
        )


class EvidenceRegistry:
    """Registry managing all evidence providers for spatial reasoning."""

    def __init__(self) -> None:
        self.providers: Dict[str, EvidenceProvider] = {
            "observed_lst": ObservedLSTProvider(),
            "hpi_persistence": HPIPersistenceProvider(),
            "dynamic_world_landcover": DynamicWorldLandCoverProvider(),
            "road_network": RoadNetworkProvider(),
            "building_footprints": BuildingFootprintProvider(),
            "cadastral_ownership": CadastralOwnershipProvider(),
            "drainage_dem": DrainageDEMProvider(),
        }

    def get_provider(self, name: str) -> Optional[EvidenceProvider]:
        return self.providers.get(name)

    def extract_all(
        self,
        geometry: dict,
        season: str,
        year: int,
        db: Optional[Session] = None,
        cached_cells: Optional[List[Any]] = None,
    ) -> Dict[str, EvidenceExtractionResult]:
        """Extract evidence from all registered providers."""
        results: Dict[str, EvidenceExtractionResult] = {}
        for name, provider in self.providers.items():
            results[name] = provider.extract(
                geometry=geometry,
                season=season,
                year=year,
                db=db,
                cached_cells=cached_cells,
            )
        return results

    def get_evidence_availability_panel(
        self,
        extractions: Dict[str, EvidenceExtractionResult],
    ) -> List[Dict[str, Any]]:
        """Produce the standard evidence availability panel required by the UI and API."""
        panel: List[Dict[str, Any]] = []
        for name, res in extractions.items():
            panel.append({
                "provider_id": name,
                "layer_title": res.display_title,
                "availability": res.availability.value,
                "dataset_name": res.dataset_name,
                "version": res.version,
                "effective_date": res.effective_date,
                "spatial_resolution": res.spatial_resolution,
                "authority": res.authority,
                "coverage_fraction": res.coverage_fraction,
                "quality_flag": res.quality_flag,
                "missing_reason": res.missing_reason,
            })
        return panel


# Authoritative Global Singleton
evidence_registry = EvidenceRegistry()
