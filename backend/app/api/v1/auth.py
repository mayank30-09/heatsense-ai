"""Authentication API endpoints for login, token verification, and session refresh."""

from __future__ import annotations

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.config import get_settings
from backend.app.core.auth import (
    DEV_USERS_DB,
    User,
    UserRole,
    authenticate_user,
    get_current_user,
)
from backend.app.core.rate_limit import auth_rate_limiter, get_client_ip
from backend.app.core.security import create_access_token

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Municipal username")
    password: str = Field(..., min_length=6, max_length=128, description="Account password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_minutes: int
    user: User


class RefreshTokenRequest(BaseModel):
    token: str = Field(..., description="Active access token to refresh")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate with username and password, returning a signed JWT access token."""
    client_ip = get_client_ip(request)
    allowed, retry_after = auth_rate_limiter.check_and_record(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many authentication attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact the SMC system administrator.",
        )

    token = create_access_token(
        subject=user.username,
        role=user.role.value,
        additional_claims={"email": user.email, "dept": user.department},
    )

    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in_minutes=settings.access_token_expire_minutes,
        user=User(**user.model_dump()),
    )


@router.get("/me", response_model=User)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the currently authenticated user's profile and active role."""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    """Issue a renewed JWT access token for an authenticated active session."""
    token = create_access_token(
        subject=current_user.username,
        role=current_user.role.value,
        additional_claims={"email": current_user.email, "dept": current_user.department},
    )
    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in_minutes=settings.access_token_expire_minutes,
        user=current_user,
    )


@router.post("/dev-token", response_model=TokenResponse)
def get_development_token(role: str = "planner") -> TokenResponse:
    """Issue a development JWT access token when running in non-production environments."""
    if settings.app_env.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development token generation is prohibited in production.",
        )
    username = "smc_admin" if role == "admin" else "planner_officer"
    user = DEV_USERS_DB.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="Default dev user not found.")
    token = create_access_token(
        subject=user.username,
        role=user.role.value,
        additional_claims={"email": user.email, "dept": user.department},
    )
    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in_minutes=settings.access_token_expire_minutes,
        user=User(**user.model_dump()),
    )

