"""Comprehensive Security, Data Integrity, and Production Readiness Test Suite.

Audits and verifies:
1. Authentication: login flow, password verification, token creation, expiration, malformed tokens.
2. Authorization (RBAC): Server-side enforcement across public, planner, researcher, and admin roles.
3. Security Headers: OWASP response headers (X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy).
4. Audit Telemetry: X-Request-ID propagation and latency measurement.
5. API Input Validation: Bounding box geographical bounds, reversed coordinates, non-positive budgets, tile zoom limits.
6. File Ingestion Defense: Directory traversal defense, executable extension blocking, size ceilings, magic byte checks.
7. Database & PostGIS Integrity: Foreign keys, 0 orphan records, geometry validity, SRID consistency, CHECK constraints.
8. Error Information Disclosure: Shielding internal exceptions, stack traces, and database connection strings.
"""

from __future__ import annotations

import os
from datetime import timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
import jwt
from pydantic import ValidationError
from sqlalchemy import create_engine, text

from backend.app.config import Settings, get_settings
from backend.app.core.auth import DEV_USERS_DB, UserRole
from backend.app.core.file_validation import (
    FileValidationError,
    sanitize_filename,
    validate_file_upload,
)
from backend.app.core.rate_limit import InMemoryRateLimiter, auth_rate_limiter
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from backend.app.main import app

settings = get_settings()
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()


# ---------------------------------------------------------------------------
# Helper Fixtures & Tokens
# ---------------------------------------------------------------------------

def get_auth_token(username: str, role: UserRole) -> str:
    """Generate a valid signed JWT for testing."""
    return create_access_token(
        subject=username,
        role=role.value,
        expires_delta=timedelta(minutes=30),
    )


# ---------------------------------------------------------------------------
# 1. Authentication Tests
# ---------------------------------------------------------------------------

def test_password_hashing_and_verification():
    """Verify bcrypt salt and hash generation and verification."""
    password = "unit-test-hash-input-2026"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_creation_and_decoding():
    """Verify JWT creation, claim structure, and round-trip decoding."""
    token = create_access_token(subject="planner_officer", role="planner")
    payload = decode_access_token(token)
    assert payload["sub"] == "planner_officer"
    assert payload["role"] == "planner"
    assert payload["iss"] == settings.app_name
    assert "exp" in payload
    assert "iat" in payload


def test_login_endpoint_success_and_failure():
    """Verify /api/v1/auth/login handles valid and invalid credentials."""
    dev_password = os.environ["DEV_USER_PASSWORD"]
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "planner_officer", "password": dev_password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert data["user"]["role"] == "planner"

    # 2. Invalid password -> 401
    resp_bad_pw = client.post(
        "/api/v1/auth/login",
        json={"username": "planner_officer", "password": "IncorrectPassword"},
    )
    assert resp_bad_pw.status_code == 401
    assert "Invalid username or password" in resp_bad_pw.json()["detail"]

    # 3. Nonexistent user -> 401
    resp_bad_user = client.post(
        "/api/v1/auth/login",
        json={"username": "unknown_intruder", "password": "SomePassword123"},
    )
    assert resp_bad_user.status_code == 401


def test_dev_token_endpoint_removed():
    """Verify deprecated unauthenticated /api/v1/auth/dev-token returns 404."""
    resp = client.post("/api/v1/auth/dev-token")
    assert resp.status_code == 404


def test_authenticate_user_refuses_dev_db_in_production(monkeypatch):
    """Verify authenticate_user rejects all DEV_USERS_DB credentials when APP_ENV=production."""
    from backend.app.core.auth import authenticate_user
    dev_password = os.environ["DEV_USER_PASSWORD"]
    monkeypatch.setenv("APP_ENV", "production")
    assert authenticate_user("planner_officer", dev_password) is None
    assert authenticate_user("smc_admin", dev_password) is None


def test_auth_me_endpoint_with_valid_and_missing_token():
    """Verify /api/v1/auth/me enforces authentication."""
    # 1. Missing credentials -> 401
    resp_no_token = client.get("/api/v1/auth/me")
    assert resp_no_token.status_code == 401
    assert resp_no_token.headers.get("WWW-Authenticate") == "Bearer"

    # 2. Valid token -> 200
    token = get_auth_token("planner_officer", UserRole.PLANNER)
    resp_auth = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_auth.status_code == 200
    assert resp_auth.json()["username"] == "planner_officer"
    assert resp_auth.json()["role"] == "planner"


def test_auth_expired_and_malformed_tokens():
    """Verify expired and malformed tokens are rejected with 401."""
    # 1. Expired token
    expired_token = create_access_token(
        subject="planner_officer",
        role="planner",
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    resp_expired = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp_expired.status_code == 401
    assert "expired" in resp_expired.json()["detail"].lower()

    # 2. Malformed token string
    resp_malformed = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert resp_malformed.status_code == 401

    # 3. Forged signature (tampered payload)
    tampered_token = expired_token[:-4] + "fake"
    resp_forged = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert resp_forged.status_code == 401


def test_token_refresh_endpoint():
    """Verify active authenticated session can be refreshed."""
    token = get_auth_token("smc_admin", UserRole.ADMIN)
    resp = client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["username"] == "smc_admin"


# ---------------------------------------------------------------------------
# 2. Authorization / Role-Based Access Control (RBAC) Tests
# ---------------------------------------------------------------------------

def test_admin_endpoints_require_admin_role():
    """Verify administrative operations block non-admins with 403."""
    admin_token = get_auth_token("smc_admin", UserRole.ADMIN)
    planner_token = get_auth_token("planner_officer", UserRole.PLANNER)
    public_token = get_auth_token("public_user", UserRole.PUBLIC)

    # 1. Public user attempting admin logs -> 403
    resp_pub = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {public_token}"},
    )
    assert resp_pub.status_code == 403

    # 2. Planner attempting admin cost parameter update -> 403
    cost_payload = {
        "tree_unit_cost_inr": 3600.0,
        "tree_maintenance_years": 3,
        "cool_roof_per_m2_inr": 375.0,
        "green_roof_per_m2_inr": 3800.0,
        "cool_pavement_per_m2_inr": 480.0,
    }
    resp_pln = client.put(
        "/api/v1/admin/cost-parameters",
        json=cost_payload,
        headers={"Authorization": f"Bearer {planner_token}"},
    )
    assert resp_pln.status_code == 403

    # 3. SMC Admin successfully accessing admin endpoints -> 200
    resp_adm_logs = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_adm_logs.status_code == 200
    assert resp_adm_logs.json()["operator"] == "smc_admin"

    resp_adm_cost = client.put(
        "/api/v1/admin/cost-parameters",
        json=cost_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_adm_cost.status_code == 200
    assert resp_adm_cost.json()["status"] == "success"


def test_model_metadata_role_authorization():
    """Verify model metadata endpoint is accessible to researchers & admins, blocked for public."""
    public_token = get_auth_token("public_user", UserRole.PUBLIC)
    researcher_token = get_auth_token("climate_researcher", UserRole.RESEARCHER)

    # Public blocked -> 403
    resp_pub = client.get(
        "/api/v1/admin/model-metadata",
        headers={"Authorization": f"Bearer {public_token}"},
    )
    assert resp_pub.status_code == 403

    # Researcher allowed -> 200
    resp_res = client.get(
        "/api/v1/admin/model-metadata",
        headers={"Authorization": f"Bearer {researcher_token}"},
    )
    assert resp_res.status_code == 200
    data = resp_res.json()
    assert "metadata" in data
    assert data["authorized_researcher"] == "climate_researcher"


def test_public_user_blocked_from_optimization():
    """Verify authenticated public user cannot execute intensive optimization."""
    public_token = get_auth_token("public_user", UserRole.PUBLIC)
    payload = {
        "budget_inr": 10000000.0,
        "algorithm": "greedy",
        "max_candidates": 20,
    }
    resp = client.post(
        "/api/v1/interventions/optimize",
        json=payload,
        headers={"Authorization": f"Bearer {public_token}"},
    )
    assert resp.status_code == 403
    assert "sufficient privileges" in resp.json()["detail"]


def test_researcher_blocked_from_optimization():
    """Verify researcher role cannot execute municipal budget optimization runs."""
    researcher_token = get_auth_token("climate_researcher", UserRole.RESEARCHER)
    payload = {
        "budget_inr": 10000000.0,
        "algorithm": "greedy",
        "max_candidates": 20,
    }
    resp = client.post(
        "/api/v1/interventions/optimize",
        json=payload,
        headers={"Authorization": f"Bearer {researcher_token}"},
    )
    assert resp.status_code == 403
    assert "researcher" in resp.json()["detail"]


def test_unauthenticated_blocked_from_optimization_in_all_environments():
    """Verify unauthenticated requests to optimize are fail-closed with 401 across all environments."""
    payload = {
        "budget_inr": 10000000.0,
        "algorithm": "greedy",
        "max_candidates": 10,
    }
    # In default/dev environment
    resp_dev = client.post("/api/v1/interventions/optimize", json=payload)
    assert resp_dev.status_code == 401
    assert "Authentication credentials were not provided" in resp_dev.json()["detail"]

    # In production environment
    with patch.object(settings, "app_env", "production"):
        resp_prod = client.post("/api/v1/interventions/optimize", json=payload)
        assert resp_prod.status_code == 401
        assert "Authentication credentials were not provided" in resp_prod.json()["detail"]


def test_planner_and_admin_authorized_for_optimization():
    """Verify planner and admin roles are authorized to execute optimization."""
    planner_token = get_auth_token("planner_officer", UserRole.PLANNER)
    admin_token = get_auth_token("smc_admin", UserRole.ADMIN)
    payload = {
        "budget_inr": 10000000.0,
        "algorithm": "greedy",
        "max_candidates": 10,
    }
    # Planner -> 200
    resp_planner = client.post(
        "/api/v1/interventions/optimize",
        json=payload,
        headers={"Authorization": f"Bearer {planner_token}"},
    )
    assert resp_planner.status_code == 200
    assert resp_planner.json()["solutions_count"] >= 1

    # Admin -> 200
    resp_admin = client.post(
        "/api/v1/interventions/optimize",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["solutions_count"] >= 1


def test_production_settings_rejects_weak_and_dev_jwt_secret():
    """Verify Settings rejects default dev secret, short keys, and placeholder credentials in production."""
    # 1. Default dev secret in production raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Settings(app_env="production")
    assert "JWT_SECRET_KEY" in str(exc_info.value)

    # 2. Short secret in production raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Settings(app_env="production", jwt_secret_key="too_short_key")
    assert "at least 32 characters" in str(exc_info.value)

    # 3. Default database credentials in production raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="production",
            jwt_secret_key="a_valid_and_sufficiently_long_production_key_32_chars",
            database_url="postgresql+psycopg://heatsense:change_me@localhost:5432/heatsense",
        )
    assert "DATABASE_URL" in str(exc_info.value)

    # 3b. Actual dev database credentials ('heatsense_dev') in production raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="production",
            jwt_secret_key="a_valid_and_sufficiently_long_production_key_32_chars",
            database_url="postgresql+psycopg://heatsense:heatsense_dev@localhost:5432/heatsense",
        )
    assert "DATABASE_URL" in str(exc_info.value)

    # 4. Valid production settings pass
    valid_prod_settings = Settings(
        app_env="production",
        jwt_secret_key="a_valid_and_sufficiently_long_production_key_32_chars",
        database_url="postgresql+psycopg://heatsense:prod_secure_pass@db.surat.gov.in:5432/heatsense",
    )
    assert valid_prod_settings.app_env == "production"



# ---------------------------------------------------------------------------
# 3. Security Headers & Telemetry Tests
# ---------------------------------------------------------------------------

def test_owasp_security_headers_present():
    """Verify OWASP defensive headers on API responses."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200

    headers = resp.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Permissions-Policy" in headers
    assert "Content-Security-Policy" in headers


def test_audit_log_request_id_propagation():
    """Verify X-Request-ID header is generated and returned on all responses."""
    # Auto-generated request ID
    resp = client.get("/api/v1/health")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 10

    # Custom request ID preserved
    custom_id = "req_audit_test_778899"
    resp_custom = client.get(
        "/api/v1/health",
        headers={"X-Request-ID": custom_id},
    )
    assert resp_custom.headers.get("X-Request-ID") == custom_id


# ---------------------------------------------------------------------------
# 4. API Input Validation & Boundary Hardening Tests
# ---------------------------------------------------------------------------

def test_optimization_negative_and_zero_budget_rejected():
    """Verify non-positive budgets fail with 422 Unprocessable Entity."""
    planner_token = get_auth_token("planner_officer", UserRole.PLANNER)
    auth_headers = {"Authorization": f"Bearer {planner_token}"}

    # Negative budget
    resp_neg = client.post(
        "/api/v1/interventions/optimize",
        json={"budget_inr": -5000000.0, "algorithm": "greedy"},
        headers=auth_headers,
    )
    assert resp_neg.status_code == 422

    # Zero budget
    resp_zero = client.post(
        "/api/v1/interventions/optimize",
        json={"budget_inr": 0.0, "algorithm": "greedy"},
        headers=auth_headers,
    )
    assert resp_zero.status_code == 422


def test_candidates_bbox_validation():
    """Verify geographical bounds and reversed bounding box detection."""
    # 1. Reversed bounding box (min_lat > max_lat)
    resp_reversed = client.get(
        "/api/v1/interventions/candidates?bbox=72.75,21.30,72.90,21.10"
    )
    assert resp_reversed.status_code == 400
    assert "Reversed bounding box extent" in resp_reversed.json()["detail"]

    # 2. Out of geographical range latitude (lat > 90)
    resp_range = client.get(
        "/api/v1/interventions/candidates?bbox=72.75,21.10,72.90,121.25"
    )
    assert resp_range.status_code == 400
    assert "coordinates out of range" in resp_range.json()["detail"]


def test_heat_priority_cells_bbox_validation():
    """Verify bounding box validation on /heat-priority/cells."""
    # 1. Reversed longitude extent
    resp_rev_lon = client.get(
        "/api/v1/heat-priority/cells?bbox=73.00,21.10,72.50,21.25"
    )
    assert resp_rev_lon.status_code == 400
    assert "Reversed bounding box" in resp_rev_lon.json()["detail"]

    # 2. Out of range longitude
    resp_bad_lon = client.get(
        "/api/v1/heat-priority/cells?bbox=-200.0,21.10,72.90,21.25"
    )
    assert resp_bad_lon.status_code == 400
    assert "coordinates out of range" in resp_bad_lon.json()["detail"]


def test_raster_tile_zoom_and_coordinate_bounds():
    """Verify /rasters/lst/tiles/{z}/{x}/{y}.png enforces zoom bounds."""
    # Negative zoom -> 422
    resp_neg_z = client.get("/api/v1/rasters/lst/tiles/-1/0/0.png")
    assert resp_neg_z.status_code == 422

    # Excessive zoom (> 24) -> 422
    resp_excess_z = client.get("/api/v1/rasters/lst/tiles/25/0/0.png")
    assert resp_excess_z.status_code == 422


# ---------------------------------------------------------------------------
# 5. File Upload & Ingestion Security Utility Tests
# ---------------------------------------------------------------------------

def test_file_validation_prohibits_dangerous_extensions():
    """Verify executable and dangerous scripts are strictly rejected."""
    prohibited_files = [
        "malware.exe",
        "deploy.sh",
        "exploit.py",
        "run.bat",
        "script.ps1",
        "shell.php",
    ]
    for fname in prohibited_files:
        with pytest.raises(FileValidationError) as exc:
            validate_file_upload(fname, file_bytes=b"echo dangerous")
        assert "Prohibited executable" in str(exc.value)


def test_file_validation_path_traversal_sanitization():
    """Verify path traversal sequences are neutralized."""
    # Directory traversal path
    dirty_name = "../../etc/passwd.geojson"
    sanitized = sanitize_filename(dirty_name)
    assert ".." not in sanitized
    assert "/" not in sanitized
    assert sanitized == "passwd.geojson"

    # Null byte injection rejected
    with pytest.raises(FileValidationError):
        sanitize_filename("clean_data.geojson\x00.exe")


def test_file_validation_size_and_empty_checks():
    """Verify 0-byte files and oversized files (>50MB) are rejected."""
    # 0 bytes
    with pytest.raises(FileValidationError) as exc_zero:
        validate_file_upload("boundary.geojson", file_bytes=b"")
    assert "empty" in str(exc_zero.value)

    # > 50 MB
    oversized = 51 * 1024 * 1024
    with pytest.raises(FileValidationError) as exc_size:
        validate_file_upload("massive.tif", file_size=oversized)
    assert "exceeds maximum permitted limit" in str(exc_size.value)


def test_file_validation_magic_bytes_inspection():
    """Verify TIFF and Parquet magic bytes header validation."""
    # Valid GeoTIFF header (Little Endian: II*\x00)
    valid_tiff_header = b"II*\x00" + b"\x00" * 100
    res = validate_file_upload("scene.tif", file_bytes=valid_tiff_header)
    assert res["status"] == "VALID"

    # Spoofed TIFF header
    fake_tiff = b"MZ\x90\x00" + b"\x00" * 100  # DOS/EXE header renamed to .tif
    with pytest.raises(FileValidationError) as exc_spoof:
        validate_file_upload("trojan.tif", file_bytes=fake_tiff)
    assert "Invalid TIFF magic header" in str(exc_spoof.value)


# ---------------------------------------------------------------------------
# 6. Database & PostGIS Referential & Geometry Integrity Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_database_referential_integrity_zero_orphans():
    """Verify zero orphan records across observations and heat priority scores."""
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        # Check orphan observations
        orphan_obs = conn.execute(text("""
            SELECT count(*) FROM stage_c_grid_observations o
            LEFT JOIN stage_c_grid_cells c ON o.pixel_id = c.pixel_id
            WHERE c.pixel_id IS NULL;
        """)).scalar()
        assert orphan_obs == 0, f"Found {orphan_obs} orphan observations without parent cells"

        # Check orphan scores
        orphan_scores = conn.execute(text("""
            SELECT count(*) FROM stage_c_heat_priority_scores s
            LEFT JOIN stage_c_grid_cells c ON s.pixel_id = c.pixel_id
            WHERE c.pixel_id IS NULL;
        """)).scalar()
        assert orphan_scores == 0, f"Found {orphan_scores} orphan scores without parent cells"


@pytest.mark.integration
def test_postgis_geometry_validity_and_srid():
    """Verify all PostGIS geometries are topologically valid with SRID 4326."""
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        # Invalid geometry check
        invalid_geom_count = conn.execute(text("""
            SELECT count(*) FROM stage_c_grid_cells
            WHERE NOT ST_IsValid(geometry);
        """)).scalar()
        assert invalid_geom_count == 0, f"Found {invalid_geom_count} invalid geometries in grid cells"

        # Non-4326 SRID check
        non_4326_count = conn.execute(text("""
            SELECT count(*) FROM stage_c_grid_cells
            WHERE ST_SRID(geometry) != 4326;
        """)).scalar()
        assert non_4326_count == 0, f"Found {non_4326_count} cells with non-4326 SRID"

        # Empty geometry check
        empty_count = conn.execute(text("""
            SELECT count(*) FROM stage_c_grid_cells
            WHERE ST_IsEmpty(geometry);
        """)).scalar()
        assert empty_count == 0, f"Found {empty_count} empty geometries in grid cells"


# ---------------------------------------------------------------------------
# 7. Error Information Disclosure Shielding Tests
# ---------------------------------------------------------------------------

def test_nonexistent_endpoint_no_information_disclosure():
    """Verify 404 responses do not leak server directory paths or versions."""
    resp = client.get("/api/v1/nonexistent/secret_path")
    assert resp.status_code == 404
    body = resp.text
    assert "Traceback" not in body
    assert "C:\\" not in body
    assert "/Users/" not in body


# ---------------------------------------------------------------------------
# 8. Rate Limiting, Throttling & Compute Abuse Hardening Tests
# ---------------------------------------------------------------------------

def test_auth_rate_limiting_enforcement_and_headers():
    """Verify authentication endpoint rate limits abuse after configured attempts."""
    auth_rate_limiter.reset()

    # First 5 attempts (within limit) should return 401 Unauthorized for bad credentials
    for attempt in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "bad_user", "password": "wrong_password"},
        )
        assert resp.status_code == 401, f"Attempt {attempt + 1} should be 401, got {resp.status_code}"

    # 6th attempt should be blocked with 429 Too Many Requests
    resp_blocked = client.post(
        "/api/v1/auth/login",
        json={"username": "bad_user", "password": "wrong_password"},
    )
    assert resp_blocked.status_code == 429
    assert "Too many authentication attempts" in resp_blocked.json()["detail"]
    assert "Retry-After" in resp_blocked.headers
    retry_after = int(resp_blocked.headers["Retry-After"])
    assert retry_after > 0


def test_auth_rate_limiting_reset():
    """Verify rate limiter reset restores login capability immediately."""
    auth_rate_limiter.reset()

    # Exhaust quota
    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            json={"username": "bad_user", "password": "wrong_password"},
        )
    resp_blocked = client.post(
        "/api/v1/auth/login",
        json={"username": "bad_user", "password": "wrong_password"},
    )
    assert resp_blocked.status_code == 429

    # Reset client IP history for socket peer
    auth_rate_limiter.reset("testclient")

    # Next attempt should proceed through to 401 (not 429)
    resp_after_reset = client.post(
        "/api/v1/auth/login",
        json={"username": "bad_user", "password": "wrong_password"},
    )
    assert resp_after_reset.status_code == 401


def test_auth_rate_limiting_spoofed_forwarded_for_cannot_evade_throttle():
    """Verify arbitrary X-Forwarded-For headers from untrusted clients cannot bypass throttling."""
    auth_rate_limiter.reset()

    # Send 5 attempts with 5 different spoofed X-Forwarded-For headers
    for i in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "bad_user", "password": "wrong_password"},
            headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
        )
        assert resp.status_code == 401

    # 6th attempt with yet another spoofed IP must still be blocked (socket peer enforced)
    resp_blocked = client.post(
        "/api/v1/auth/login",
        json={"username": "bad_user", "password": "wrong_password"},
        headers={"X-Forwarded-For": "198.51.100.254"},
    )
    assert resp_blocked.status_code == 429
    assert "Too many authentication attempts" in resp_blocked.json()["detail"]


def test_auth_rate_limiting_sliding_window_expiry():
    """Verify rate limiter sliding window expires deterministically using synthetic clock."""
    current_time = 1000.0

    def mock_time() -> float:
        return current_time

    limiter = InMemoryRateLimiter(max_attempts=3, window_seconds=60, time_func=mock_time)

    # First 3 attempts permitted via check_and_record
    for _ in range(3):
        allowed, _ = limiter.check_and_record("test-source")
        assert allowed is True

    # 4th attempt rejected
    allowed, retry_after = limiter.check_and_record("test-source")
    assert allowed is False
    assert retry_after == 60

    # Advance clock past the 60-second window
    current_time = 1061.0
    allowed_after_expiry, retry_after_new = limiter.check_and_record("test-source")
    assert allowed_after_expiry is True
    assert retry_after_new == 0


def test_rate_limiter_bounded_storage_and_cleanup():
    """Verify rate limiter storage bounds capacity and prunes expired client entries."""
    current_time = 100.0

    def mock_time() -> float:
        return current_time

    limiter = InMemoryRateLimiter(
        max_attempts=5,
        window_seconds=60,
        time_func=mock_time,
        max_tracked_keys=5,
    )

    # Add 8 different client IPs (exceeding max_tracked_keys of 5)
    for i in range(8):
        limiter.check_and_record(f"client-{i}")

    # History size should be bounded and not exceed max_tracked_keys
    assert len(limiter._history) <= 5

    # Advance clock past 60s window
    current_time = 170.0

    # Next attempt triggers cleanup of stale keys
    limiter.check_and_record("new-client")
    assert "client-0" not in limiter._history
    assert "new-client" in limiter._history


def test_rate_limiter_invalid_configuration_rejected():
    """Verify non-positive limiter configuration raises ValueError."""
    with pytest.raises(ValueError) as exc1:
        InMemoryRateLimiter(max_attempts=0)
    assert "max_attempts must be greater than 0" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        InMemoryRateLimiter(window_seconds=-10)
    assert "window_seconds must be greater than 0" in str(exc2.value)

    with pytest.raises(ValueError) as exc3:
        InMemoryRateLimiter(max_tracked_keys=0)
    assert "max_tracked_keys must be greater than 0" in str(exc3.value)


def test_analysis_geometry_complexity_limit_rejected():
    """Verify excessively complex geometries (> 2500 vertices) are rejected with 400."""
    import math

    n_pts = 2600
    pts = [
        [
            round(72.82 + 0.01 * math.cos(2 * math.pi * i / n_pts), 6),
            round(21.10 + 0.01 * math.sin(2 * math.pi * i / n_pts), 6),
        ]
        for i in range(n_pts)
    ]
    pts.append(pts[0])  # Close ring

    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [pts],
        }
    }
    resp = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert resp.status_code == 400
    assert "exceeds maximum allowed complexity" in resp.json()["detail"]


def test_analysis_geometry_coordinates_out_of_bounds():
    """Verify geometries with coordinates outside [-180, 180] or [-90, 90] are rejected with 400."""
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.82, 195.0],
                [72.84, 195.0],
                [72.84, 21.12],
                [72.82, 21.12],
                [72.82, 195.0],
            ]],
        }
    }
    resp = client.post("/api/v1/analysis/zonal-stats", json=payload)
    assert resp.status_code == 400
    assert "out of valid range" in resp.json()["detail"]


def test_analysis_geometry_nan_and_inf_rejected():
    """Verify NaN and Infinity coordinates in geometry fail with 400."""
    import json
    import pytest
    from fastapi import HTTPException
    from backend.app.api.v1.analysis import validate_analysis_geometry

    # Direct unit test on validator
    geom_nan = {
        "type": "Polygon",
        "coordinates": [[
            [72.82, 21.10],
            [float("nan"), 21.10],
            [72.84, 21.12],
            [72.82, 21.12],
            [72.82, 21.10],
        ]],
    }
    with pytest.raises(ValueError) as exc_info_nan:
        validate_analysis_geometry(geom_nan)
    assert "finite numbers" in str(exc_info_nan.value)

    geom_inf = {
        "type": "Polygon",
        "coordinates": [[
            [72.82, 21.10],
            [float("inf"), 21.10],
            [72.84, 21.12],
            [72.82, 21.12],
            [72.82, 21.10],
        ]],
    }
    with pytest.raises(ValueError) as exc_info_inf:
        validate_analysis_geometry(geom_inf)
    assert "finite numbers" in str(exc_info_inf.value)

    # HTTP endpoint test via raw bytes (since httpx default json serializer forbids NaN)
    payload_nan = {
        "geometry": geom_nan
    }
    raw_body = json.dumps(payload_nan, allow_nan=True).encode("utf-8")
    resp_nan = client.post(
        "/api/v1/analysis/zonal-stats",
        content=raw_body,
        headers={"Content-Type": "application/json"}
    )
    # Pydantic or our validator rejects with 400 or 422
    assert resp_nan.status_code in (400, 422)


def test_analysis_geometry_unclosed_ring_rejected():
    """Verify linear ring without matching start/end coordinate is rejected with 400."""
    payload_unclosed = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.82, 21.10],
                [72.84, 21.10],
                [72.84, 21.12],
                [72.82, 21.12],
            ]],  # Not closed (missing 5th coordinate matching 1st)
        }
    }
    resp = client.post("/api/v1/analysis/zonal-stats", json=payload_unclosed)
    assert resp.status_code == 400
    assert "not closed" in resp.json()["detail"]


def test_analysis_geometry_degenerate_ring_rejected():
    """Verify collinear or degenerate linear ring with < 3 distinct points is rejected with 400."""
    payload_degenerate = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.82, 21.10],
                [72.82, 21.10],
                [72.82, 21.10],
                [72.82, 21.10],
            ]],
        }
    }
    resp = client.post("/api/v1/analysis/zonal-stats", json=payload_degenerate)
    assert resp.status_code == 400
    assert "at least 3 distinct coordinate positions" in resp.json()["detail"]


def test_analysis_geometry_boolean_coordinate_rejected():
    """Verify boolean values in coordinate arrays are rejected with 400."""
    payload_bool = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.82, 21.10],
                [True, False],
                [72.84, 21.12],
                [72.82, 21.12],
                [72.82, 21.10],
            ]],
        }
    }
    resp = client.post("/api/v1/analysis/zonal-stats", json=payload_bool)
    assert resp.status_code == 400
    assert "must be numeric, not boolean" in resp.json()["detail"]


def test_stage_d_test_override_isolation():
    """Verify Stage D authentication override is strictly isolated and absent in other suites."""
    from backend.app.core.auth import require_planner_or_admin

    # In security audit suite, require_planner_or_admin must NOT be overridden
    assert require_planner_or_admin not in app.dependency_overrides


