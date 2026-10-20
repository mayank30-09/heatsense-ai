# 12 — Security & Data Integrity Remediation Error Log

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Issue Identification, Root Cause Analysis, Remediation Actions, and Post-Fix Verification  
**Date:** October 2026  
**Auditor Classification:** Senior Application Security & Reliability Engineer  
**Status:** **ALL JUSTIFIED ISSUES REMEDIATED & VERIFIED**  

---

## 1. Remediation Action Log

### SEC-ERR-01: Missing Authentication Subsystem & Session Verification
- **Severity:** HIGH
- **Component:** `backend/app/api/v1/`
- **Initial Finding:** All API endpoints were exposed without authentication. No password verification, JWT issuance, or session validation existed in the codebase.
- **Root Cause:** Day 1 initial skeleton lacked authentication modules, deferred during scientific freeze.
- **Remediation Action:**
  1. Built [backend/app/core/security.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/core/security.py) implementing salted bcrypt hashing and PyJWT HS256 token creation and decoding with `exp`, `iat`, `sub`, and `role` claims.
  2. Implemented [backend/app/core/auth.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/core/auth.py) with `get_current_user` and `get_current_user_optional` dependencies.
  3. Built [backend/app/api/v1/auth.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/api/v1/auth.py) exposing `/auth/login`, `/auth/me`, and `/auth/refresh`.
- **Verification Result:** PASS (`test_login_endpoint_success_and_failure`, `test_auth_me_endpoint_with_valid_and_missing_token`).

---

### SEC-ERR-02: Absence of Server-Side Role-Based Access Control (RBAC)
- **Severity:** HIGH
- **Component:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/interventions.py`
- **Initial Finding:** No role enforcement existed. Public web users could trigger computationally intensive optimization runs (`/interventions/optimize`) or potentially tamper with administrative parameters.
- **Root Cause:** Role checking was not implemented on backend route handlers.
- **Remediation Action:**
  1. Created `RoleChecker` dependency enforcing the 4 authoritative SRS roles (`public`, `planner`, `researcher`, `admin`).
  2. Created [backend/app/api/v1/admin.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/api/v1/admin.py) with `/admin/audit-logs`, `/admin/cost-parameters`, `/admin/ingest` restricted to `admin`, and `/admin/model-metadata` restricted to `researcher` and `admin`.
  3. Added role check to [backend/app/api/v1/interventions.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/api/v1/interventions.py#L280-L289) blocking `public` users from running `/optimize`.
- **Verification Result:** PASS (`test_admin_endpoints_require_admin_role`, `test_public_user_blocked_from_optimization`).

---

### SEC-ERR-03: Missing OWASP Security Response Headers
- **Severity:** MEDIUM
- **Component:** `backend/app/main.py`
- **Initial Finding:** HTTP responses lacked defensive headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`), leaving the client vulnerable to MIME-sniffing, clickjacking, and cross-site framing.
- **Root Cause:** Standard FastAPI boilerplate did not configure security header middleware.
- **Remediation Action:**
  1. Built `SecurityHeadersMiddleware` in [backend/app/core/middleware.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/core/middleware.py#L17-L35).
  2. Injected into [backend/app/main.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/main.py#L18) via `setup_security_and_audit(app)`.
- **Verification Result:** PASS (`test_owasp_security_headers_present`).

---

### SEC-ERR-04: Lack of Distributed Request ID & Audit Logging
- **Severity:** MEDIUM
- **Component:** `backend/app/main.py`
- **Initial Finding:** Incoming HTTP requests did not have an authoritative correlation ID (`X-Request-ID`) or centralized telemetry logging request latency and status.
- **Root Cause:** Standard logging lacked middleware-level telemetry.
- **Remediation Action:**
  1. Implemented `AuditLogMiddleware` in [backend/app/core/middleware.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/core/middleware.py#L38-L70).
  2. Attached `X-Request-ID` (UUID4) to all responses and recorded client IP, path, status, and duration in ms while strictly redacting authorization tokens.
- **Verification Result:** PASS (`test_audit_log_request_id_propagation`).

---

### SEC-ERR-05: Unbounded Intervention Budget in Optimization Schema
- **Severity:** MEDIUM
- **Component:** `backend/app/api/v1/interventions.py`
- **Initial Finding:** `OptimizeRequest` accepted negative or zero budgets (`budget_inr = -5000000.0`), allowing invalid mathematical state in greedy and NSGA-II knapsack optimizers.
- **Root Cause:** Pydantic schema lacked `gt=0.0` constraint.
- **Remediation Action:**
  1. Hardened [backend/app/api/v1/interventions.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/api/v1/interventions.py#L84-L89) with `gt=0.0` and `le=10_000_000_000.0`.
- **Verification Result:** PASS (`test_optimization_negative_and_zero_budget_rejected`).

---

### SEC-ERR-06: Unvalidated Viewport Bounding Box Coordinates
- **Severity:** LOW
- **Component:** `backend/app/api/v1/interventions.py`, `backend/app/api/v1/heat_priority.py`
- **Initial Finding:** Reversed bounding box extents (`min_lat > max_lat`) or coordinates outside valid ranges (`[-180, 180]`, `[-90, 90]`) were not validated, leading to unhandled empty queries.
- **Root Cause:** Parsing logic only checked for 4 split tokens without coordinate range validation.
- **Remediation Action:**
  1. Added geographic range checks and reversed extent validation in `interventions.py` and `heat_priority.py`.
  2. Returns clean `400 Bad Request` with descriptive error details.
- **Verification Result:** PASS (`test_candidates_bbox_validation`, `test_heat_priority_cells_bbox_validation`).

---

### SEC-ERR-07: Unbounded Tile Pyramid Zoom Levels
- **Severity:** LOW
- **Component:** `backend/app/api/v1/rasters.py`
- **Initial Finding:** Endpoint `/rasters/lst/tiles/{z}/{x}/{y}.png` accepted negative zoom levels (`z = -1`) and excessive zoom levels (`z = 99`), attempting invalid Rio-tiler window slices.
- **Root Cause:** Parameters declared as unconstrained `int`.
- **Remediation Action:**
  1. Enforced `Path(..., ge=0, le=24)` on `z` and `Path(..., ge=0)` on `x` and `y`.
- **Verification Result:** PASS (`test_raster_tile_zoom_and_coordinate_bounds`).

---

## 2. Summary of Residual Risk

All 7 identified issues have been remediated, verified by automated unit and integration tests, and confirmed to have zero negative impact on existing system functionality. Zero known high-severity vulnerabilities remain.
