from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import router as api_v1_router
from backend.app.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.core.middleware import setup_security_and_audit

configure_logging()
settings = get_settings()

app = FastAPI(
    title="HEATSENSE AI API",
    version="0.1.0",
    description="HeatSense AI urban heat mitigation and decision-support platform.",
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
