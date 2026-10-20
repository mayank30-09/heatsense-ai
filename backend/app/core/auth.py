"""Authentication, user models, and role-based access control (RBAC) engine."""

from __future__ import annotations

import os
from enum import Enum
from typing import Annotated, Any
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
import jwt

from backend.app.core.security import decode_access_token, get_password_hash, verify_password

load_dotenv()

bearer_scheme = HTTPBearer(auto_error=False)


class UserRole(str, Enum):
    """Authoritative user classes defined in SRS Section 12 & Section 59."""
    PUBLIC = "public"
    PLANNER = "planner"
    RESEARCHER = "researcher"
    ADMIN = "admin"


class User(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    is_active: bool = True
    department: str | None = None


class UserInDB(User):
    hashed_password: str


# Pre-hashed passwords for development and testing environments (bcrypt salt 12)
# Password for all default accounts is read from environment variable DEV_USER_PASSWORD
_DEV_USER_PASSWORD = os.environ.get("DEV_USER_PASSWORD", "")
_DEFAULT_HASH = get_password_hash(_DEV_USER_PASSWORD) if _DEV_USER_PASSWORD else ""

DEV_USERS_DB: dict[str, UserInDB] = {
    "public_user": UserInDB(
        id="usr_pub_001",
        username="public_user",
        email="citizen@surat.gov.in",
        role=UserRole.PUBLIC,
        is_active=True,
        department="Surat Citizen",
        hashed_password=_DEFAULT_HASH,
    ),
    "planner_officer": UserInDB(
        id="usr_pln_002",
        username="planner_officer",
        email="planner@surat.gov.in",
        role=UserRole.PLANNER,
        is_active=True,
        department="Town Planning Department, SMC",
        hashed_password=_DEFAULT_HASH,
    ),
    "climate_researcher": UserInDB(
        id="usr_res_003",
        username="climate_researcher",
        email="researcher@svnit.ac.in",
        role=UserRole.RESEARCHER,
        is_active=True,
        department="Urban Microclimate Lab",
        hashed_password=_DEFAULT_HASH,
    ),
    "smc_admin": UserInDB(
        id="usr_adm_004",
        username="smc_admin",
        email="admin@surat.gov.in",
        role=UserRole.ADMIN,
        is_active=True,
        department="Smart City Center, SMC",
        hashed_password=_DEFAULT_HASH,
    ),
}


def authenticate_user(username: str, password: str) -> UserInDB | None:
    """Validate username and password against user records."""
    # Refuse to authenticate development accounts in production mode
    if os.environ.get("APP_ENV", "").lower() == "production":
        return None
    user = DEV_USERS_DB.get(username)
    if not user:
        return None
    dev_password = os.environ.get("DEV_USER_PASSWORD", "")
    if user.hashed_password and verify_password(password, user.hashed_password):
        return user
    if dev_password and verify_password(password, get_password_hash(dev_password)):
        return user
    return None


async def get_current_user_optional(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    """Optionally resolve the current authenticated user from Bearer token."""
    if not creds or not creds.credentials:
        return None
    try:
        payload = decode_access_token(creds.credentials)
        username = payload.get("sub")
        if not username:
            return None
        user = DEV_USERS_DB.get(username)
        if user and user.is_active:
            return User(**user.model_dump())
        return None
    except Exception:
        return None


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Resolve and enforce authenticated user from Bearer token.
    
    Raises:
        HTTPException(401): If token is missing, expired, or invalid.
    """
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = creds.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or malformed authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing user identifier claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = DEV_USERS_DB.get(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return User(**user.model_dump())


class RoleChecker:
    """Dependency that enforces role-based access control (RBAC)."""

    def __init__(self, allowed_roles: list[UserRole]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: User role '{current_user.role.value}' does not have "
                    f"sufficient privileges. Required roles: {[r.value for r in self.allowed_roles]}."
                ),
            )
        return current_user


# Predefined RBAC dependencies
require_planner_or_admin = RoleChecker([UserRole.PLANNER, UserRole.ADMIN])
require_researcher_or_admin = RoleChecker([UserRole.RESEARCHER, UserRole.ADMIN])
require_admin = RoleChecker([UserRole.ADMIN])
