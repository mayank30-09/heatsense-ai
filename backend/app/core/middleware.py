"""Security headers, audit logging telemetry, and error information disclosure shielding."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("heatsense.audit")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces authoritative OWASP security response headers across all HTTP responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "geolocation=(self), microphone=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: blob: https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'"
        )
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Logs request/response telemetry with X-Request-ID while strictly redacting sensitive tokens."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()

        # Sanitize client IP
        client_ip = request.client.host if request.client else "unknown"

        # Record incoming request (exclude body/passwords)
        path = request.url.path
        method = request.method

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        response.headers["X-Request-ID"] = request_id

        # Redact Authorization header if present
        auth_header_present = "authorization" in request.headers

        logger.info(
            "request_id=%s client_ip=%s method=%s path=%s status=%d duration_ms=%.2f authenticated=%s",
            request_id,
            client_ip,
            method,
            path,
            response.status_code,
            duration_ms,
            auth_header_present,
        )

        return response


def setup_security_and_audit(app: FastAPI) -> None:
    """Register security and audit middleware on the FastAPI application."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuditLogMiddleware)

    @app.exception_handler(Exception)
    async def global_exception_shield(request: Request, exc: Exception) -> JSONResponse:
        """Shield clients from internal implementation details, file paths, and database exceptions."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        logger.error(
            "Unhandled server exception [request_id=%s] on %s %s: %s",
            request_id,
            request.method,
            request.url.path,
            str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": (
                    "An unexpected internal error occurred while processing the request. "
                    "Diagnostic telemetry has been captured."
                ),
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )
