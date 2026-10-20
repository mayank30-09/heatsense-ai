# 02 — Authentication Subsystem Audit & Empirical Verification

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Login Flow, Password Hashing, JWT Token Issuance, Expiration, Malformed Tokens, and Session Refresh  
**Date:** October 2026  
**Auditor Classification:** Senior Application Security Engineer  
**Component:** `backend/app/core/security.py`, `backend/app/core/auth.py`, `backend/app/api/v1/auth.py`  
**Status:** **VERIFIED & REMEDIATED**  

---

## 1. Authentication Architecture & Design

In accordance with IEEE SRS Section 12 (User Classes) and Section 59 (Authentication and Authorization), the HeatSense AI platform implements a cryptographic authentication engine using **salted bcrypt password hashing** and **signed JSON Web Tokens (PyJWT HS256)**.

```text
User Credentials (username, password)
                 │
                 ▼
  [ POST /api/v1/auth/login ]
                 │
       (bcrypt.checkpw)
                 │
       Valid? ───┴─── No ──► HTTP 401 Unauthorized
                 │
                Yes
                 │
                 ▼
     [ Generate JWT (HS256) ]
      - sub: username
      - role: user_role
      - exp: now + 60 minutes
      - iat: now
      - iss: heatsense-api
                 │
                 ▼
   Return Access Token & Profile
```

---

## 2. Password Handling & Cryptographic Security

1. **Algorithm:** bcrypt with work factor (salt rounds) = 12.
2. **Storage:** Plaintext passwords are never stored in memory or persisted. All user hashes derive from `bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))`.
3. **Verification:** Constant-time hash verification via `bcrypt.checkpw` prevents timing attack side channels.
4. **Implementation:** [backend/app/core/security.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/core/security.py#L13-L34)

---

## 3. JWT Token Architecture & Specification

| Token Claim | Claim Value / Format | Security Purpose |
| :--- | :--- | :--- |
| `sub` | String (e.g. `"planner_officer"`) | Identifies the authenticated municipal actor. |
| `role` | String (`"public"`, `"planner"`, `"researcher"`, `"admin"`) | Carries authorized role for RBAC evaluation. |
| `exp` | NumericDate (UTC timestamp) | Enforces strict token expiration window (default: 60 minutes). |
| `iat` | NumericDate (UTC timestamp) | Token issuance timestamp; prevents future-dated tokens. |
| `iss` | String (`"heatsense-api"`) | Guarantees token origin; prevents cross-issuer token reuse. |
| `dept` | String (e.g. `"Town Planning Department, SMC"`) | Municipal organizational context. |

Tokens are signed using HMAC-SHA256 (`HS256`) with a cryptographically secure key managed via Pydantic `BaseSettings` (`JWT_SECRET_KEY`).

---

## 4. Empirical Test Scenarios & Observed Results

All authentication workflows are verified through automated regression tests in [backend/tests/test_security_audit.py](file:///e:/FINAL%20YEAR PROJECT/heatsense-ai/backend/tests/test_security_audit.py#L42-L170).

### Test Matrix:

| Test Case | Scenario / Payload | Expected Status | Observed Result | Evidence |
| :--- | :--- | :---: | :---: | :--- |
| **AUTH-01** | `POST /auth/login` with valid credentials (`planner_officer` / `[REDACTED_DEV_PASSWORD]`) | `200 OK` | `200 OK`, signed Bearer JWT returned with 60-min expiration. | `test_login_endpoint_success_and_failure` |
| **AUTH-02** | `POST /auth/login` with incorrect password | `401 Unauthorized` | `401 Unauthorized`, detail: `"Invalid username or password."` | `test_login_endpoint_success_and_failure` |
| **AUTH-03** | `POST /auth/login` with nonexistent username | `401 Unauthorized` | `401 Unauthorized`, zero username enumeration disclosure. | `test_login_endpoint_success_and_failure` |
| **AUTH-04** | `GET /auth/me` with no credentials | `401 Unauthorized` | `401 Unauthorized`, header `WWW-Authenticate: Bearer`. | `test_auth_me_endpoint_with_valid_and_missing_token` |
| **AUTH-05** | `GET /auth/me` with valid planner Bearer token | `200 OK` | `200 OK`, user profile, department, and planner role returned. | `test_auth_me_endpoint_with_valid_and_missing_token` |
| **AUTH-06** | `GET /auth/me` with expired JWT (`exp` in past) | `401 Unauthorized` | `401 Unauthorized`, detail: `"Authentication token has expired."` | `test_auth_expired_and_malformed_tokens` |
| **AUTH-07** | `GET /auth/me` with malformed token string | `401 Unauthorized` | `401 Unauthorized`, detail: `"Invalid or malformed authentication token."` | `test_auth_expired_and_malformed_tokens` |
| **AUTH-08** | `GET /auth/me` with forged / tampered token signature | `401 Unauthorized` | `401 Unauthorized`, signature verification failure caught. | `test_auth_expired_and_malformed_tokens` |
| **AUTH-09** | `POST /auth/refresh` with active session | `200 OK` | `200 OK`, renewed JWT issued with reset expiration. | `test_token_refresh_endpoint` |

---

## 5. Account Store Architecture & Implementation Status

- **Account Store Type:** Pre-seeded in-memory dictionary (`DEV_USERS_DB` in [backend/app/core/auth.py](file:///e:/FINAL%20YEAR PROJECT/heatsense-ai/backend/app/core/auth.py#L42-L79)).
- **Persistence Assessment:** **NOT PERSISTED IN DATABASE**. Users and salted hashes are loaded in-memory on application launch rather than querying a PostgreSQL `users` table.
- **Enterprise Requirement:** For multi-node production deployment, a dedicated `users` and `audit_sessions` table with migration and Admin user management API must be implemented.

---

## 6. Rate Limiting & Abuse Controls

- **Active Engine:** `InMemoryRateLimiter` ([backend/app/core/rate_limit.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/core/rate_limit.py)) provides process-local sliding-window rate limiting on `/auth/login` (default: 5 attempts per 60 seconds).
- **Client Identity Source:** The rate limiter resolves client identity strictly via `request.client.host` (the immediate TCP socket peer address).
- **Forwarded Header Handling:** All forwarded headers (`X-Forwarded-For`, `X-Real-IP`) are intentionally ignored by `get_client_ip()` to eliminate client-spoofed header rotation attacks.
- **Trusted-Proxy Configuration Status (NOT IMPLEMENTED):** There is currently no trusted-proxy CIDR configuration or proxy-aware middleware in `backend/app`. The application does NOT assume or parse upstream proxy headers.
- **Reverse Proxy Deployment Behavior (Shared-IP Throttling Risk):**
  - *Direct Connection:* Rate limiting operates per client machine IP address.
  - *Behind a Reverse Proxy (e.g. NGINX, ALB, Envoy):* Because forwarded headers are not trusted, all requests arriving through a reverse proxy carry the proxy's own IP address as `request.client.host`. Consequently, all clients behind that proxy share a single rate-limit counter (**shared-IP throttling collapse**). If 5 failed attempts occur across any combination of users behind the proxy within 60s, the entire proxy IP is throttled.
  - *Deployment Requirement:* In a production environment using a reverse proxy, rate limiting should either be enforced directly at the reverse proxy layer (e.g., NGINX `limit_req_zone`), or a verified trusted-proxy middleware with explicit CIDR whitelist must be integrated.
- **Concurrency & TOCTOU Elimination:** The `check_and_record()` method atomically evaluates the sliding window and appends the attempt timestamp inside a thread lock (`threading.Lock`), preventing parallel request bursts from bypassing the limit.
- **Bounded Storage & Memory Leak Defense:** The tracking store caps capacity at `max_tracked_keys` (10,000 keys) and prunes stale keys whose timestamps fall entirely outside the sliding window.
- **Accurate Retry-After:** Remaining duration is computed using `math.ceil` to guarantee that callers waiting `Retry-After` seconds encounter an expired window.
- **Configuration Validation:** Limits are validated via Pydantic (`ge=1, le=1000` for attempts, `ge=1, le=86400` for window duration) and in constructor validation.
- **Zero Secret Disclosure:** Rate limit logging records solely IP addresses and throttle status; passwords, tokens, and credentials are never logged.
- **Process-Local Scope Limitation:** Tracks request timestamps per worker process in memory. If Uvicorn runs with multiple worker processes or in a multi-pod cluster, each worker process maintains an independent in-memory window. Distributed rate limiting across workers requires external Redis storage.

---

## 7. Refresh Token Semantics & Unsupported Controls

- **Active Behavior:** The `POST /api/v1/auth/refresh` endpoint operates as a **session renewal mechanism**. An authenticated client holding a valid, non-expired Bearer access token can request a refreshed token.
- **Unsupported Controls (Documented Architecture Limitations):**
  1. *Separate Long-Lived Refresh Token Entity:* Not implemented. There is no dual access/refresh token pair.
  2. *Token Revocation List / Blacklist:* Not implemented. Tokens remain valid until their 60-minute expiration timestamp (`exp`) passes; premature logout does not invalidate tokens server-side without a Redis or DB blocklist.
  3. *Refresh Token Rotation & Replay Detection:* Not implemented.

---

## 8. Verification Summary

| Component | Status | Notes |
| :--- | :---: | :--- |
| **Bcrypt Hashing & Constant-Time Check** | **VERIFIED** | Salt rounds = 12, timing attack defense active. |
| **JWT Creation, Signatures, Expiration** | **VERIFIED** | Enforces HS256, `exp`, `iat`, `sub`, `role`, and `iss`. |
| **Login / Me / Refresh Handlers** | **VERIFIED** | Validated via automated tests in `test_security_audit.py`. |
| **Rate Limiting & Abuse Controls** | **VERIFIED** | 5 attempts/60s sliding window on login, returns 429 and `Retry-After`. |
| **Database-Backed Persistent Accounts** | **NOT IMPLEMENTED** | In-memory seeded development store (`DEV_USERS_DB`). |
| **Token Revocation & Replay Protection** | **NOT IMPLEMENTED** | Explicit architectural limitation documented in Section 7. |


