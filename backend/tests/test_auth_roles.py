"""Role-based access control (RBAC), authentication mechanics, and security boundary tests."""

from __future__ import annotations

import os
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.core.auth import (
    DEV_USERS_DB,
    UserRole,
    authenticate_user,
)
from backend.app.core.rate_limit import auth_rate_limiter
from backend.app.core.security import create_access_token
from backend.app.main import app

settings = get_settings()
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_auth_rate_limiter():
    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()


def make_token(username: str, role: UserRole, expired: bool = False) -> str:
    """Generate a test token for a given user role."""
    delta = timedelta(seconds=-10) if expired else timedelta(minutes=60)
    return create_access_token(subject=username, role=role.value, expires_delta=delta)


# ---------------------------------------------------------------------------
# 1. Seeded Accounts & Password Source
# ---------------------------------------------------------------------------

def test_seeded_accounts_presence():
    """Verify standard seeded accounts are present in development database."""
    expected_accounts = ["public_user", "planner_officer", "climate_researcher", "smc_admin"]
    for uname in expected_accounts:
        assert uname in DEV_USERS_DB
        user = DEV_USERS_DB[uname]
        assert user.is_active is True
        assert user.role in (UserRole.PUBLIC, UserRole.PLANNER, UserRole.RESEARCHER, UserRole.ADMIN)


def test_password_comes_from_dev_user_password():
    """Verify that seeded accounts only authenticate with DEV_USER_PASSWORD."""
    dev_password = os.environ.get("DEV_USER_PASSWORD", "")
    assert dev_password != "", "DEV_USER_PASSWORD must be configured in environment"

    for uname in ["public_user", "planner_officer", "smc_admin"]:
        user = authenticate_user(uname, dev_password)
        assert user is not None
        assert user.username == uname

    # Random password must fail
    assert authenticate_user("planner_officer", "definitely_wrong_password_999") is None
    assert authenticate_user("unknown_user", dev_password) is None


def test_dev_accounts_refused_in_production(monkeypatch):
    """Verify dev accounts are rejected when APP_ENV=production."""
    dev_password = os.environ.get("DEV_USER_PASSWORD", "")
    monkeypatch.setenv("APP_ENV", "production")

    for uname in ["public_user", "planner_officer", "smc_admin"]:
        assert authenticate_user(uname, dev_password) is None

    # Login endpoint also fails with 401 in production
    resp = client.post("/api/v1/auth/login", json={"username": "planner_officer", "password": dev_password})
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Token Lifetime & JWT Behavior
# ---------------------------------------------------------------------------

def test_token_lifetime_and_claims():
    """Verify login issues a JWT with 60-minute default lifetime and required claims."""
    dev_password = os.environ.get("DEV_USER_PASSWORD", "")
    resp = client.post("/api/v1/auth/login", json={"username": "planner_officer", "password": dev_password})
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "Bearer"
    assert data["expires_in_minutes"] == 60
    assert data["user"]["role"] == "planner"


def test_expired_token_rejected_distinctly():
    """Verify expired token yields 401 with explicit expired message."""
    expired_token = make_token("planner_officer", UserRole.PLANNER, expired=True)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Rate Limiting on Auth Endpoints
# ---------------------------------------------------------------------------

def test_login_rate_limit_and_retry_after():
    """Verify that exceeding rate limit on /auth/login returns 429 with Retry-After header."""
    auth_rate_limiter.reset()

    # Default is 5 attempts per 60 seconds
    for _ in range(5):
        resp = client.post("/api/v1/auth/login", json={"username": "public_user", "password": "wrong_password"})
        assert resp.status_code == 401

    # 6th attempt must be throttled
    resp_blocked = client.post("/api/v1/auth/login", json={"username": "public_user", "password": "wrong_password"})
    assert resp_blocked.status_code == 429
    assert "Retry-After" in resp_blocked.headers
    retry_seconds = int(resp_blocked.headers["Retry-After"])
    assert 1 <= retry_seconds <= 60
    assert "Too many authentication attempts" in resp_blocked.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Comprehensive Role-to-Route Authorization Matrix
# ---------------------------------------------------------------------------

def test_admin_only_endpoints():
    """Verify /api/v1/admin/audit-logs and /cost-parameters allow ONLY admin role."""
    tokens = {
        "none": None,
        "public": make_token("public_user", UserRole.PUBLIC),
        "planner": make_token("planner_officer", UserRole.PLANNER),
        "researcher": make_token("climate_researcher", UserRole.RESEARCHER),
        "admin": make_token("smc_admin", UserRole.ADMIN),
    }

    # 1. /api/v1/admin/audit-logs
    for role, tok in tokens.items():
        headers = {"Authorization": f"Bearer {tok}"} if tok else {}
        resp = client.get("/api/v1/admin/audit-logs", headers=headers)
        if role == "none":
            assert resp.status_code == 401, f"Expected 401 for unauthenticated on audit-logs, got {resp.status_code}"
        elif role == "admin":
            assert resp.status_code == 200, f"Expected 200 for admin on audit-logs, got {resp.status_code}"
        else:
            assert resp.status_code == 403, f"Expected 403 for {role} on audit-logs, got {resp.status_code}"

    # 2. /api/v1/admin/cost-parameters
    cost_payload = {
        "tree_unit_cost_inr": 3600.0,
        "tree_maintenance_years": 3,
        "cool_roof_per_m2_inr": 375.0,
        "green_roof_per_m2_inr": 3800.0,
        "cool_pavement_per_m2_inr": 480.0,
    }
    for role, tok in tokens.items():
        headers = {"Authorization": f"Bearer {tok}"} if tok else {}
        resp = client.put("/api/v1/admin/cost-parameters", json=cost_payload, headers=headers)
        if role == "none":
            assert resp.status_code == 401
        elif role == "admin":
            assert resp.status_code == 200
        else:
            assert resp.status_code == 403


def test_model_metadata_endpoint_roles():
    """Verify /api/v1/admin/model-metadata allows Researcher and Admin, blocks Public and Planner."""
    tokens = {
        "none": None,
        "public": make_token("public_user", UserRole.PUBLIC),
        "planner": make_token("planner_officer", UserRole.PLANNER),
        "researcher": make_token("climate_researcher", UserRole.RESEARCHER),
        "admin": make_token("smc_admin", UserRole.ADMIN),
    }

    for role, tok in tokens.items():
        headers = {"Authorization": f"Bearer {tok}"} if tok else {}
        resp = client.get("/api/v1/admin/model-metadata", headers=headers)
        if role == "none":
            assert resp.status_code == 401
        elif role in ("researcher", "admin"):
            assert resp.status_code == 200
        else:
            assert resp.status_code == 403


def test_interventions_optimization_roles():
    """Verify /api/v1/interventions/optimize allows Planner and Admin, blocks Public and Researcher."""
    tokens = {
        "none": None,
        "public": make_token("public_user", UserRole.PUBLIC),
        "researcher": make_token("climate_researcher", UserRole.RESEARCHER),
        "planner": make_token("planner_officer", UserRole.PLANNER),
        "admin": make_token("smc_admin", UserRole.ADMIN),
    }
    opt_payload = {
        "budget_inr": 10000000.0,
        "algorithm": "greedy",
        "max_candidates": 10,
    }

    for role, tok in tokens.items():
        headers = {"Authorization": f"Bearer {tok}"} if tok else {}
        resp = client.post("/api/v1/interventions/optimize", json=opt_payload, headers=headers)
        if role == "none":
            assert resp.status_code == 401
        elif role in ("planner", "admin"):
            assert resp.status_code == 200
        else:
            assert resp.status_code == 403


def test_diminishing_returns_roles():
    """Verify /api/v1/interventions/diminishing-returns allows Planner and Admin, blocks Public and Researcher."""
    tokens = {
        "none": None,
        "public": make_token("public_user", UserRole.PUBLIC),
        "researcher": make_token("climate_researcher", UserRole.RESEARCHER),
        "planner": make_token("planner_officer", UserRole.PLANNER),
        "admin": make_token("smc_admin", UserRole.ADMIN),
    }
    dr_payload = {
        "budgets_inr": [5000000.0, 25000000.0],
        "max_candidates": 10,
    }

    for role, tok in tokens.items():
        headers = {"Authorization": f"Bearer {tok}"} if tok else {}
        resp = client.post("/api/v1/interventions/diminishing-returns", json=dr_payload, headers=headers)
        if role == "none":
            assert resp.status_code == 401
        elif role in ("planner", "admin"):
            assert resp.status_code == 200
        else:
            assert resp.status_code == 403


def test_user_profile_and_refresh_roles():
    """Verify /api/v1/auth/me and /api/v1/auth/refresh allow all authenticated active roles."""
    for role, uname in [
        (UserRole.PUBLIC, "public_user"),
        (UserRole.PLANNER, "planner_officer"),
        (UserRole.RESEARCHER, "climate_researcher"),
        (UserRole.ADMIN, "smc_admin"),
    ]:
        token = make_token(uname, role)
        headers = {"Authorization": f"Bearer {token}"}

        # Profile /me
        resp_me = client.get("/api/v1/auth/me", headers=headers)
        assert resp_me.status_code == 200
        assert resp_me.json()["username"] == uname
        assert resp_me.json()["role"] == role.value

        # Refresh
        resp_ref = client.post("/api/v1/auth/refresh", headers=headers)
        assert resp_ref.status_code == 200
        assert "access_token" in resp_ref.json()
