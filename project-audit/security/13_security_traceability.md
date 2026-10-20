# 13 — Security & Data Integrity Requirements Traceability Matrix

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** End-to-End Traceability from IEEE SRS v1.0 to Code Implementation and Test Verification  
**Date:** October 2026  
**Auditor Classification:** Senior Application Security & Systems Assurance Engineer  
**Reference Document:** `HEATSENSE_AI_SRS_v1.0.md`  
**Status:** **FULLY TRACEABLE & VERIFIED**  

---

## 1. Traceability Overview

This matrix maps each security, authentication, authorization, data integrity, and provenance requirement from the authoritative **HeatSense AI Software Requirements Specification (SRS v1.0)** to the exact source files, architectural components, and automated test cases that prove compliance.

---

## 2. Requirements Traceability Matrix

| SRS Req ID | SRS Reference | Requirement Description | Architectural Design | Implementation Component | Test Verification Function | Status |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **REQ-SEC-01** | Section 60 | Salted password hashing for all user accounts | bcrypt with work factor 12 | `backend/app/core/security.py` | `test_password_hashing_and_verification` | **PASS** |
| **REQ-SEC-02** | Section 59, 60 | Cryptographic JWT token handling & expiration | PyJWT HS256 with sub, role, exp, iat | `backend/app/core/security.py` | `test_jwt_token_creation_and_decoding`<br>`test_auth_expired_and_malformed_tokens` | **PASS** |
| **REQ-SEC-03** | Section 59 | User login and session refresh endpoints | REST API endpoints for login & refresh | `backend/app/api/v1/auth.py` | `test_login_endpoint_success_and_failure`<br>`test_token_refresh_endpoint` | **PASS** |
| **REQ-SEC-04** | Section 12, 59 | 4-tier Role-Based Access Control (RBAC) | Server-side `RoleChecker` dependency | `backend/app/core/auth.py` | `test_admin_endpoints_require_admin_role`<br>`test_public_user_blocked_from_optimization` | **PASS** |
| **REQ-SEC-05** | Section 60 | Administrative endpoints access control | Strict `require_admin` dependency | `backend/app/api/v1/admin.py` | `test_admin_endpoints_require_admin_role` | **PASS** |
| **REQ-SEC-06** | Section 60 | Model metadata and freeze access control | `require_researcher_or_admin` guard | `backend/app/api/v1/admin.py` | `test_model_metadata_role_authorization` | **PASS** |
| **REQ-SEC-07** | Section 60 | OWASP defensive security response headers | `SecurityHeadersMiddleware` injection | `backend/app/core/middleware.py` | `test_owasp_security_headers_present` | **PASS** |
| **REQ-SEC-08** | Section 60 | Centralized audit logging telemetry & tracing | `AuditLogMiddleware` with `X-Request-ID`| `backend/app/core/middleware.py` | `test_audit_log_request_id_propagation` | **PASS** |
| **REQ-SEC-09** | Section 60 | Error information disclosure prevention | Global exception shielding handler | `backend/app/core/middleware.py` | `test_nonexistent_endpoint_no_information_disclosure` | **PASS** |
| **REQ-SEC-10** | Section 60 | Intervention budget range validation | Pydantic `gt=0.0, le=10_000_000_000.0` | `backend/app/api/v1/interventions.py` | `test_optimization_negative_and_zero_budget_rejected` | **PASS** |
| **REQ-SEC-11** | Section 60 | Geospatial bounding box extent validation | Coordinate range & reversed extent check | `backend/app/api/v1/interventions.py`<br>`backend/app/api/v1/heat_priority.py` | `test_candidates_bbox_validation`<br>`test_heat_priority_cells_bbox_validation` | **PASS** |
| **REQ-SEC-12** | Section 60 | Raster tile pyramid coordinate limits | Path parameter constraints (`0 <= z <= 24`)| `backend/app/api/v1/rasters.py` | `test_raster_tile_zoom_and_coordinate_bounds` | **PASS** |
| **REQ-SEC-13** | Section 60 | Defensive file upload security & validation | Sanitization, extension allowlist, magic | `backend/app/core/file_validation.py` | `test_file_validation_prohibits_dangerous_extensions`<br>`test_file_validation_path_traversal_sanitization`<br>`test_file_validation_magic_bytes_inspection` | **PASS** |
| **REQ-SEC-14** | Section 38, 60 | SQL injection defense via parameterized queries | SQLAlchemy 2.0 select and bind variables | `backend/app/db/session.py`<br>`backend/app/api/v1/*` | `test_database_referential_integrity_zero_orphans` | **PASS** |
| **REQ-SEC-15** | Section 38 | Referential integrity and foreign key constraints| PostgreSQL schema CASCADE and SET NULL | `backend/app/db/models/stage_c.py` | `test_database_referential_integrity_zero_orphans` | **PASS** |
| **REQ-SEC-16** | Section 38 | Domain CHECK constraints on analytical scores | Database engine CHECK constraints | `backend/app/db/models/stage_c.py` | `backend/tests/test_stage_c_db.py` | **PASS** |
| **REQ-SEC-17** | Section 29 | PostGIS geometry validity and CRS consistency | Valid geometries with SRID 4326 | `backend/app/db/models/stage_c.py` | `test_postgis_geometry_validity_and_srid` | **PASS** |
| **REQ-SEC-18** | Section 29 | SMC municipal boundary area reconciliation | Authoritative area 461.630791 km² | `gis/spatial/grid.py` | `test_t01_boundary_area_reconciliation` | **PASS** |
| **REQ-SEC-19** | Section 29 | Area conservation across fishnet grid cells | 50,871 touching cells reconstruct SMC | `gis/spatial/grid.py` | `test_t02_area_conservation` | **PASS** |
| **REQ-SEC-20** | Section 31 | Optical sentinel value (-9999) isolation | Dev partition isolation, median impute | `gis/quality/imputation.py` | `backend/tests/test_optical_sentinel_audit.py` | **PASS** |
| **REQ-SEC-21** | Section 32 | Zero data leakage in spatial holdout ML split | 33 test blocks strictly locked | `artifacts/ml_freeze/holdout_split.json`| `backend/tests/test_holdout_protocol.py` | **PASS** |
| **REQ-SEC-22** | Section 32 | Spatially calibrated conformal uncertainty | 90% nominal coverage achieved | `gis/ml/conformal.py` | `backend/tests/test_ml_experiments_and_conformal.py` | **PASS** |
| **REQ-SEC-23** | Section 60 | Secure CORS configuration without wildcards | Explicit origin whitelist in Pydantic | `backend/app/config.py`<br>`backend/app/main.py` | `backend/tests/test_security_audit.py` | **PASS** |
| **REQ-SEC-24** | Section 60 | Secret management without hardcoded keys | Pydantic `BaseSettings` & `.env` | `backend/app/config.py` | `project-audit/security/10_secret_configuration_audit.md` | **PASS** |
