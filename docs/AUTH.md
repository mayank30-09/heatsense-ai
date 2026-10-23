# HeatSense AI — Authentication & Role-Based Access Control (RBAC) Specification

This document details the authentication architecture, user classes, credential workflows, token lifetimes, rate-limiting policies, and server-side role-to-route mappings implemented in HeatSense AI.

---

## 1. Seeded Development Accounts

HeatSense AI provides pre-seeded municipal role profiles in development and testing environments (`DEV_USERS_DB` in `backend/app/core/auth.py`).

| Username | Role | Department / Affiliation | Default Privileges |
|:---|:---|:---|:---|
| `public_user` | `public` | Surat Citizen | Public dashboard, map viewing, zonal stats, area recommendations, candidate browsing |
| `planner_officer` | `planner` | Town Planning Department, SMC | All public capabilities + multi-objective budget optimization (`/optimize`) and diminishing returns curves (`/diminishing-returns`) |
| `climate_researcher` | `researcher` | Urban Microclimate Lab, SVNIT | All public capabilities + model validation metadata, feature schema verification (`/admin/model-metadata`) |
| `smc_admin` | `admin` | Smart City Center, SMC | Full administrative access: audit logs (`/admin/audit-logs`), cost parameter adjustments (`/admin/cost-parameters`), ingestion triggers (`/admin/ingest`), optimization, and researcher endpoints |

> [!IMPORTANT]
> **Password Source:**  
> Passwords for all seeded accounts are **never** hardcoded into the source code, version control, or static fixtures. The password is dynamically derived from the `DEV_USER_PASSWORD` environment variable when the backend process boots:
> ```python
> _DEV_USER_PASSWORD = os.environ.get("DEV_USER_PASSWORD", "")
> _DEFAULT_HASH = get_password_hash(_DEV_USER_PASSWORD) if _DEV_USER_PASSWORD else ""
> ```
> Users and developers must set `DEV_USER_PASSWORD` in their local `.env` or execution shell prior to launching the API server. Never commit passwords or credentials to repository files.

---

## 2. Production Security & Development Account Refusal

When the platform runs in production mode (`APP_ENV=production`), development accounts are unconditionally refused:

```python
def authenticate_user(username: str, password: str) -> UserInDB | None:
    """Validate username and password against user records."""
    # Refuse to authenticate development accounts in production mode
    if os.environ.get("APP_ENV", "").lower() == "production":
        return None
    ...
```

### Production Invariants:
1. **Refusal of Seeded Users:** Any login attempt against `public_user`, `planner_officer`, `climate_researcher`, or `smc_admin` immediately returns `None` (resulting in HTTP 401 Unauthorized). Production deployments require integration with an authoritative identity provider (e.g., SMC Keycloak, SAML 2.0 / OpenID Connect, or LDAP directory).
2. **Strict Configuration Validation:** The Pydantic application settings (`Settings.validate_production_configuration` in `backend/app/config.py`) validate that:
   - `JWT_SECRET_KEY` is not a placeholder, contains no `"dev"` substring, and is at least 32 cryptographically random bytes.
   - `DATABASE_URL` does not contain default development credentials.
   - Failure to meet these criteria halts startup immediately with a `ValueError`.

---

## 3. Token Lifetime, Claims, and Storage

HeatSense AI issues digitally signed JSON Web Tokens (JWT) adhering to RFC 7519:

- **Algorithm:** `HS256` (HMAC SHA-256)
- **Default Lifetime:** 60 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Issuer (`iss`):** `heatsense-api`
- **Standard Claims:**
  - `sub`: Authenticated username (e.g., `planner_officer`)
  - `role`: Role string (`public`, `planner`, `researcher`, or `admin`)
  - `exp`: Expiration Unix timestamp (`datetime.now(timezone.utc) + timedelta(minutes=60)`)
  - `iat`: Issued-at Unix timestamp
- **Custom Claims:**
  - `email`: Municipal email address
  - `dept`: Departmental designation
- **Client-Side Storage Invariant:**  
  Authentication tokens are stored **strictly in-memory** within the React state runtime (`AuthContext.tsx`). Tokens are **never written** to `localStorage`, `sessionStorage`, browser cookies, or URL query parameters, protecting against cross-site scripting (XSS) credential exfiltration.

---

## 4. Authentication Rate Limiting

To prevent brute-force credential stuffing and denial-of-service attempts, `/api/v1/auth/login` is governed by a dedicated in-memory sliding-window rate limiter (`auth_rate_limiter`):

- **Window Size:** 60 seconds (configurable via `AUTH_RATE_LIMIT_WINDOW_SECONDS`)
- **Max Attempts:** 5 attempts per IP address per window (configurable via `AUTH_RATE_LIMIT_MAX_ATTEMPTS`)
- **Behavior on Violation:**
  - Response Status: `HTTP 429 Too Many Requests`
  - Response Header: `Retry-After: <seconds>` indicating exact cooldown seconds remaining
  - Response Body:
    ```json
    {
      "detail": "Too many authentication attempts. Please try again in 58 seconds."
    }
    ```

---

## 5. Route-to-Role Access Control Matrix

The table below reflects the actual runtime routes registered in `backend.app.main:app` and enforced by FastAPI dependency injection (`RoleChecker` and `get_current_user`):

| Method | Endpoint Path | Authorization / RBAC | Failure Code | Description / Scope |
|:---|:---|:---|:---|:---|
| `POST` | `/api/v1/auth/login` | Public (Rate limited: 5/min) | 401, 429 | Authenticate credentials and receive signed Bearer token |
| `GET` | `/api/v1/auth/me` | Authenticated (Any Role) | 401 | Retrieve currently authenticated user profile |
| `POST` | `/api/v1/auth/refresh` | Authenticated (Any Role) | 401 | Renew active session token before expiration |
| `GET` | `/api/v1/admin/audit-logs` | Role: `['admin']` | 401, 403 | Municipal security audit events and operator logging |
| `PUT` | `/api/v1/admin/cost-parameters` | Role: `['admin']` | 401, 403 | Update municipal intervention unit cost parameters |
| `POST` | `/api/v1/admin/ingest` | Role: `['admin']` | 401, 403 | Trigger GIS raster or tabular data ingestion jobs |
| `GET` | `/api/v1/admin/model-metadata` | Role: `['researcher', 'admin']` | 401, 403 | Inspect ML model metadata, feature schemas, and freeze manifests |
| `POST` | `/api/v1/interventions/optimize` | Role: `['planner', 'admin']` | 401, 403 | Execute multi-objective budget optimization (Knapsack / NSGA-II) |
| `POST` | `/api/v1/interventions/diminishing-returns` | Role: `['planner', 'admin']` | 401, 403 | Compute cooling diminishing-returns curve across budget tiers |
| `GET` | `/api/v1/interventions/candidates` | Public | None | Viewport-bounded candidate grid queries |
| `GET` | `/api/v1/interventions/candidates/{candidate_id}` | Public | 404 | Specific intervention candidate details and cost breakdown |
| `GET` | `/api/v1/interventions/scenarios` | Public | None | Reference municipal planning scenario benchmarks |
| `GET` | `/api/v1/heat-priority/summary` | Public | None | City-wide Heat Priority Index summary |
| `GET` | `/api/v1/heat-priority/lst-stats` | Public | None | Seasonal Land Surface Temperature statistics |
| `GET` | `/api/v1/heat-priority/cells` | Public | None | Spatial grid cells and priority scoring |
| `GET` | `/api/v1/heat-priority/cell/{pixel_id}` | Public | 404 | Single cell inspection, environmental indicators, and HPI |
| `GET` | `/api/v1/heat-priority/model-validation` | Public | None | ML model cross-validation and conformal bounds metrics |
| `POST` | `/api/v1/analysis/zonal-stats` | Public | 400 | Calculate Landsat zonal statistics for drawn polygon |
| `POST` | `/api/v1/analysis/recommendations` | Public (Rate limited: 30/min) | 400, 429 | Multi-criteria intervention recommendations for polygon |
| `POST` | `/api/v1/analysis/resolve-area-name` | Public (Deprecated) | 400, 502 | Legacy Nominatim reverse geocode |
| `POST` | `/api/v1/analysis/resolve-area-name-postgis` | Public | 400 | PostGIS spatial reverse geocode |
| `GET` | `/api/v1/rasters/lst/tiles/{z}/{x}/{y}.png` | Public | None | Dynamic XYZ Landsat thermal raster tiles |
| `GET` | `/api/v1/scenes` | Public | None | Near-real-time Landsat Level-2 scene catalog |
| `GET` | `/api/v1/health` | Public | 503 | System health and PostGIS database connectivity check |

---

## 6. Distinct Error Categorization

Both backend responses and frontend API handlers strictly distinguish between error conditions:

1. **HTTP 401 Unauthorized (Invalid Credentials):**
   - Trigger: Unknown username or password mismatch in `authenticate_user`.
   - Message: `"Invalid username or password."`
   - Header: `WWW-Authenticate: Bearer`
2. **HTTP 401 Unauthorized (Expired Token):**
   - Trigger: Token `exp` timestamp is in the past (`jwt.ExpiredSignatureError`).
   - Message: `"Authentication token has expired. Please log in again."`
   - Action: Frontend clears in-memory credentials and prompts re-login.
3. **HTTP 401 Unauthorized (Missing / Malformed Token):**
   - Trigger: Missing `Authorization` header, invalid signature, or corrupted base64 payload.
   - Message: `"Authentication credentials were not provided."` or `"Invalid or malformed authentication token: <reason>"`
4. **HTTP 403 Forbidden (Insufficient Privileges):**
   - Trigger: Authenticated user role does not match endpoint's `RoleChecker` whitelist (e.g. `public` accessing `/optimize`).
   - Message: `"Access forbidden: User role '<role>' does not have sufficient privileges. Required roles: [<allowed_roles>]."`
5. **HTTP 403 Forbidden (Account Inactive):**
   - Trigger: User record has `is_active=False`.
   - Message: `"Account is inactive. Contact the SMC system administrator."`
6. **HTTP 429 Too Many Requests (Rate Throttling):**
   - Trigger: Exceeding 5 login attempts per 60 seconds from client IP.
   - Message: `"Too many authentication attempts. Please try again in <seconds> seconds."`
   - Header: `Retry-After: <seconds>`
7. **Client Network Error:**
   - Trigger: Inability of frontend to establish TCP / HTTP connection with the API server.
   - Message: `"Network error: Unable to connect to authentication server."`
