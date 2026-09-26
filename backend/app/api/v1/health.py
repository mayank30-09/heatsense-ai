from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.session import get_db

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Return API and PostGIS connectivity status."""
    try:
        db.execute(text("SELECT 1"))
        db.execute(text("SELECT PostGIS_Version()"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "service": settings.app_name,
                "database": "unavailable",
            },
        ) from exc

    return {
        "status": "ok",
        "service": settings.app_name,
        "database": "connected",
    }
