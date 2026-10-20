# 03 — Role-Based Access Control (RBAC) & Authorization Audit

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Server-Side Authorization, Privilege Escalation Defense, and Role-Level Endpoint Enforcement  
**Date:** October 2026  
**Auditor Classification:** Senior Application Security Engineer  
**Component:** `backend/app/core/auth.py`, `backend/app/api/v1/admin.py`, `backend/app/api/v1/interventions.py`  
**Status:** **VERIFIED & REMEDIATED**  

---

## 1. Role Definitions & Permissions Matrix

In compliance with IEEE SRS Section 12 (User Classes) and Section 59 (Authentication and Authorization), the HeatSense AI platform implements a four-tier server-side RBAC hierarchy. Role checking is enforced in the FastAPI dependency graph via [RoleChecker](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/core/auth.py#L136-L154).

### Authoritative Permissions Matrix Across All Actors:

| Category | Endpoint | Unauthenticated | Public User (`public`) | Municipal Planner (`planner`) | Climate Researcher (`researcher`) | System Admin (`admin`) | Effective Policy / Guard |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Admin** | `GET /admin/audit-logs` | `401 Unauthorized` | `403 Forbidden` | `403 Forbidden` | `403 Forbidden` | `200 OK` | `require_admin` |
| **Admin** | `PUT /admin/cost-parameters` | `401 Unauthorized` | `403 Forbidden` | `403 Forbidden` | `403 Forbidden` | `200 OK` | `require_admin` |
| **Admin** | `POST /admin/ingest` | `401 Unauthorized` | `403 Forbidden` | `403 Forbidden` | `403 Forbidden` | `200 OK` | `require_admin` |
| **Admin** | `GET /admin/model-metadata` | `401 Unauthorized` | `403 Forbidden` | `403 Forbidden` | `200 OK` | `200 OK` | `require_researcher_or_admin` |
| **Auth** | `POST /auth/login` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Credential Exchange |
| **Auth** | `GET /auth/me` | `401 Unauthorized` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `get_current_user` |
| **Auth** | `POST /auth/refresh` | `401 Unauthorized` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `get_current_user` |
| **Optimization** | `POST /interventions/optimize` | `401 Unauthorized` | `403 Forbidden` | `200 OK` | `403 Forbidden` | `200 OK` | `require_planner_or_admin` (fail-closed in all envs) |
| **Interventions** | `GET /interventions/candidates` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Interventions** | `GET /interventions/candidates/{id}` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Interventions** | `GET /interventions/scenarios` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Heat Priority** | `GET /heat-priority/summary` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Heat Priority** | `GET /heat-priority/cells` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Heat Priority** | `GET /heat-priority/cell/{pixel_id}`| `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Rasters** | `GET /rasters/lst/tiles/{z}/{x}/{y}.png` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Analysis** | `POST /analysis/zonal-stats` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read / Compute |
| **Analysis** | `POST /analysis/resolve-area-name` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Analysis** | `POST /analysis/resolve-area-name-postgis` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Read |
| **Health** | `GET /health` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | `200 OK` | Public Health Check |

---

## 2. Server-Side Privilege Escalation Defense

Authorization is strictly validated on the FastAPI backend and does not rely on frontend UI hiding:

1. **Token Role Extraction:** When an HTTP request reaches a protected route, `RoleChecker` extracts the `role` claim from the cryptographically verified JWT.
2. **Rejection with HTTP 403:** If the caller's role is not in the endpoint's `allowed_roles` list, FastAPI raises `HTTPException(403, detail="Access forbidden: User role ... does not have sufficient privileges")`.
3. **Defense Against Unauthenticated Optimization:** Callers without valid Bearer credentials cannot trigger optimization runs, failing closed with `401 Unauthorized` across all environments (`development`, `staging`, `production`, and unconfigured test environments).
4. **Denial by Default:** Any newly registered route without explicit public access declaration defaults to authenticated verification.

---

## 3. Empirical Test Matrix & Observed Evidence

Automated tests in [backend/tests/test_security_audit.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_security_audit.py#L170-L315) verify each permission boundary:

| Test Case | Actor Role | Target Route | Expected Status | Observed Result | Evidence |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **RBAC-01** | `public` | `GET /admin/audit-logs` | `403 Forbidden` | `403 Forbidden`, access rejected. | `test_admin_endpoints_require_admin_role` |
| **RBAC-02** | `planner` | `PUT /admin/cost-parameters` | `403 Forbidden` | `403 Forbidden`, cost tampering blocked. | `test_admin_endpoints_require_admin_role` |
| **RBAC-03** | `admin` | `GET /admin/audit-logs` | `200 OK` | `200 OK`, audit records returned. | `test_admin_endpoints_require_admin_role` |
| **RBAC-04** | `admin` | `PUT /admin/cost-parameters` | `200 OK` | `200 OK`, parameters updated. | `test_admin_endpoints_require_admin_role` |
| **RBAC-05** | `public` | `GET /admin/model-metadata` | `403 Forbidden` | `403 Forbidden`, model details hidden. | `test_model_metadata_role_authorization` |
| **RBAC-06** | `researcher` | `GET /admin/model-metadata` | `200 OK` | `200 OK`, feature schema & freeze info returned. | `test_model_metadata_role_authorization` |
| **RBAC-07** | `public` | `POST /interventions/optimize` | `403 Forbidden` | `403 Forbidden`, compute resource abuse blocked. | `test_public_user_blocked_from_optimization` |
| **RBAC-08** | `researcher` | `POST /interventions/optimize` | `403 Forbidden` | `403 Forbidden`, researcher blocked from municipal budgets. | `test_researcher_blocked_from_optimization` |
| **RBAC-09** | `unauthenticated` | `POST /interventions/optimize` (all envs) | `401 Unauthorized` | `401 Unauthorized`, fails closed in all environments (dev, prod, test). | `test_unauthenticated_blocked_from_optimization_in_all_environments` |
| **RBAC-10** | `planner` | `POST /interventions/optimize` | `200 OK` | `200 OK`, municipal planner authorized to execute optimization. | `test_planner_and_admin_authorized_for_optimization` |
| **RBAC-11** | `admin` | `POST /interventions/optimize` | `200 OK` | `200 OK`, smart city admin authorized to execute optimization. | `test_planner_and_admin_authorized_for_optimization` |

---

## 4. Conclusion & Status

- **Initial State:** Compute-heavy optimization allowed unauthenticated execution in non-production environments due to an environment-dependent check (`if settings.app_env.lower() == "production"`).
- **Remediation:** Enforced fail-closed authorization via `current_user: User = Depends(require_planner_or_admin)` directly in [backend/app/api/v1/interventions.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/api/v1/interventions.py#L280-L285). Stage D mathematical test compatibility is preserved through explicit test dependency overrides in [backend/tests/conftest.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/conftest.py), not by weakening runtime application authorization.
- **Final Status:** **VERIFIED (FAIL-CLOSED IN ALL ENVIRONMENTS)**.


