import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import router as api_v1_router
from backend.app.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.core.middleware import setup_security_and_audit

configure_logging()
settings = get_settings()
logger = logging.getLogger("heatsense.main")


async def _periodic_nrt_checker():
    """Background task to keep NRT Landsat overpasses verified periodically."""
    await asyncio.sleep(5)
    while True:
        try:
            from scripts.discover_nrt_scenes import run_discovery
            logger.info("Executing scheduled NRT Landsat discovery check...")
            await asyncio.to_thread(run_discovery, trigger_type="SCHEDULED")
        except Exception as exc:
            logger.warning("Periodic NRT discovery check encountered an error: %s", exc)
        # Run periodic check every 6 hours
        await asyncio.sleep(6 * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is initialized
    try:
        from backend.app.db.session import engine
        from backend.app.db.models.stage_c import StageCDiscoveryRun
        StageCDiscoveryRun.__table__.create(bind=engine, checkfirst=True)
    except Exception as exc:
        logger.warning("Schema check during startup: %s", exc)

    checker_task = asyncio.create_task(_periodic_nrt_checker())
    try:
        yield
    finally:
        checker_task.cancel()
        try:
            await checker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="HEATSENSE AI API",
    version="0.1.0",
    description="HeatSense AI urban heat mitigation and decision-support platform.",
    lifespan=lifespan,
)

# Apply OWASP security headers, audit telemetry, and exception shielding
setup_security_and_audit(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
