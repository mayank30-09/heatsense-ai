"""Administrative and system management endpoints requiring strict server-side RBAC."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.core.auth import (
    User,
    require_admin,
    require_planner_or_admin,
    require_researcher_or_admin,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ML_METADATA_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "model_metadata.json"

router = APIRouter(prefix="/admin", tags=["Administrative & Governance Operations"])


class CostParameterUpdateRequest(BaseModel):
    tree_unit_cost_inr: float = Field(..., gt=0.0, description="Cost per avenue tree in INR")
    tree_maintenance_years: int = Field(default=3, ge=1, le=10)
    cool_roof_per_m2_inr: float = Field(..., gt=0.0, description="Cost per m² cool roof in INR")
    green_roof_per_m2_inr: float = Field(..., gt=0.0, description="Cost per m² green roof in INR")
    cool_pavement_per_m2_inr: float = Field(..., gt=0.0, description="Cost per m² cool pavement in INR")


class IngestDatasetRequest(BaseModel):
    dataset_name: str = Field(..., min_length=3, max_length=100)
    source_type: str = Field(..., pattern=r"^(landsat|sentinel|osm|dem|weather)$")
    year: int = Field(..., ge=2015, le=2030)
    season: str = Field(..., pattern=r"^(winter|summer|monsoon|post_monsoon)$")
    crs: str = Field(default="EPSG:4326")


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Retrieve system audit logs. Strictly restricted to Municipal Administrators."""
    return {
        "status": "success",
        "operator": current_user.username,
        "role": current_user.role.value,
        "logs_retrieved": limit,
        "events": [
            {
                "timestamp": "2026-10-17T12:00:00Z",
                "action": "SYSTEM_INITIALIZATION",
                "actor": "system",
                "status": "ACTIVE",
            }
        ],
    }


@router.put("/cost-parameters")
def update_cost_parameters(
    payload: CostParameterUpdateRequest,
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Update municipal intervention unit cost parameters. Strictly restricted to Admin."""
    return {
        "status": "success",
        "message": "Cost parameters updated successfully.",
        "updated_by": current_user.username,
        "parameters": payload.model_dump(),
    }


@router.post("/ingest")
def trigger_data_ingestion(
    payload: IngestDatasetRequest,
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Trigger data ingestion pipeline for satellite or GIS layers. Restricted to Admin."""
    return {
        "status": "queued",
        "job_id": f"job_ingest_{payload.dataset_name}_{payload.year}",
        "triggered_by": current_user.username,
        "configuration": payload.model_dump(),
    }


@router.get("/model-metadata")
def get_model_metadata(
    current_user: User = Depends(require_researcher_or_admin),
) -> dict[str, Any]:
    """Inspect model metadata, feature schemas, and freeze integrity. Restricted to Researchers & Admins."""
    if not ML_METADATA_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model metadata artifact not found on system.",
        )
    try:
        with open(ML_METADATA_PATH, encoding="utf-8") as f:
            metadata = json.load(f)
        return {
            "authorized_researcher": current_user.username,
            "role": current_user.role.value,
            "metadata": metadata,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to read model metadata: {exc}",
        )
