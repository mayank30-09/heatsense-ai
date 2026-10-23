from fastapi import APIRouter

from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.analysis import router as analysis_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.heat_priority import router as heat_priority_router
from backend.app.api.v1.interventions import router as interventions_router
from backend.app.api.v1.rasters import router as rasters_router
from backend.app.api.v1.scenes import router as scenes_router


router = APIRouter()

router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(health_router)
router.include_router(rasters_router)
router.include_router(scenes_router)
router.include_router(analysis_router)
router.include_router(heat_priority_router)
router.include_router(interventions_router)