from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import router as api_v1_router
from backend.app.config import get_settings
from backend.app.core.logging import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(
    title="HEATSENSE AI API",
    version="0.1.0",
    description="Day 1 backend skeleton for the HEATSENSE AI platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
