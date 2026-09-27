from fastapi import APIRouter

from backend.app.api.v1.analysis import router as analysis_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.rasters import router as rasters_router


router = APIRouter()

router.include_router(health_router)
router.include_router(rasters_router)
router.include_router(analysis_router)