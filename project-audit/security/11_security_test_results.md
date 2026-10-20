# 11 — Security & Data Integrity Automated Test Execution Results

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Automated Regression & Security Test Suite Execution  
**Date:** October 2026  
**Auditor Classification:** Senior Application Security & Test Automation Engineer  
**Execution Environment:** Windows 11, Python 3.12.10, pytest 8.4.2, Vitest 5.0.3, PostgreSQL 16.3 + PostGIS 3.4  
**Total Platform Tests:** **255 / 255 PASSING (100% Success Rate)**  

---

## 1. Executive Test Execution Summary

The complete HeatSense AI platform test suite was executed to verify security hardening, checksum verification robustness, and zero functional regression:

| Test Domain | Test Suite / Runner | Test Count | Passing | Failing | Execution Time |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Dedicated Security & Integrity Suite** | `pytest backend/tests/test_security_audit.py` + `test_checksum_verifier.py` | 46 | 46 | 0 | 3.02s |
| **Complete Backend Platform Suite** | `pytest backend/tests/` | 242 | 242 | 0 | 50.46s |
| **Frontend Unit & Component Suite** | `npm test` (Vitest in `frontend/`) | 13 | 13 | 0 | 0.28s |
| **Frontend Production Build** | `npm run build` (`tsc -b && vite build`) | — | PASS | 0 errors | 3.48s |
| **Total Automated Platform Suite** | **Comprehensive Regression** | **255** | **255** | **0** | **54.22s** |


---

## 2. Security Test Matrix

| ID | Requirement | Component | Test Name | Expected | Actual | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **SEC-01** | Password Hashing | `core/security.py` | `test_password_hashing_and_verification` | Salted bcrypt hash verified in constant time. | Hash verified; wrong password rejected. | **PASS** | `test_security_audit.py` |
| **SEC-02** | JWT Token Structure | `core/security.py` | `test_jwt_token_creation_and_decoding` | HS256 signed JWT with sub, role, exp, iat, iss. | Valid payload claims extracted. | **PASS** | `test_security_audit.py` |
| **SEC-03** | Login Flow | `api/v1/auth.py` | `test_login_endpoint_success_and_failure` | 200 on valid credentials; 401 on invalid/unknown. | 200 with Bearer token; 401 on bad password. | **PASS** | `test_security_audit.py` |
| **SEC-04** | Session Inspection | `api/v1/auth.py` | `test_auth_me_endpoint_with_valid_and_missing_token`| 401 without token; 200 with active Bearer token. | 401 on missing token; 200 on valid Bearer. | **PASS** | `test_security_audit.py` |
| **SEC-05** | Token Expiration | `core/auth.py` | `test_auth_expired_and_malformed_tokens` | 401 when token `exp` timestamp has elapsed. | 401 Unauthorized with expired message. | **PASS** | `test_security_audit.py` |
| **SEC-06** | Malformed Token | `core/auth.py` | `test_auth_expired_and_malformed_tokens` | 401 when token string is corrupted or invalid. | 401 Unauthorized caught. | **PASS** | `test_security_audit.py` |
| **SEC-07** | Signature Tampering| `core/auth.py` | `test_auth_expired_and_malformed_tokens` | 401 when cryptographic signature is altered. | 401 Signature verification failed. | **PASS** | `test_security_audit.py` |
| **SEC-08** | Token Refresh | `api/v1/auth.py` | `test_token_refresh_endpoint` | 200 returning renewed token for active user. | 200 with renewed 60-min access token. | **PASS** | `test_security_audit.py` |
| **SEC-09** | Admin Audit Logs | `api/v1/admin.py` | `test_admin_endpoints_require_admin_role` | 403 for public; 200 for municipal administrator. | 403 on public; 200 on admin. | **PASS** | `test_security_audit.py` |
| **SEC-10** | Admin Cost Update | `api/v1/admin.py` | `test_admin_endpoints_require_admin_role` | 403 for planner; 200 for municipal administrator.| 403 on planner; 200 on admin. | **PASS** | `test_security_audit.py` |
| **SEC-11** | Model Metadata | `api/v1/admin.py` | `test_model_metadata_role_authorization` | 403 for public; 200 for climate researchers. | 403 on public; 200 on researcher. | **PASS** | `test_security_audit.py` |
| **SEC-12** | Optimization Guard | `api/v1/interventions.py` | `test_public_user_blocked_from_optimization` | 403 when public user calls `/optimize`. | 403 Forbidden with role explanation. | **PASS** | `test_security_audit.py` |
| **SEC-13** | OWASP Headers | `core/middleware.py` | `test_owasp_security_headers_present` | Headers nosniff, DENY, strict-origin, CSP present.| All 5 OWASP defensive headers verified. | **PASS** | `test_security_audit.py` |
| **SEC-14** | Request Telemetry | `core/middleware.py` | `test_audit_log_request_id_propagation` | `X-Request-ID` attached and propagated. | Unique UUID4 generated; custom ID preserved. | **PASS** | `test_security_audit.py` |
| **SEC-15** | Budget Validation | `api/v1/interventions.py` | `test_optimization_negative_and_zero_budget_rejected`| 422 on negative or zero intervention budget. | 422 Unprocessable Entity returned. | **PASS** | `test_security_audit.py` |
| **SEC-16** | Reversed Bbox | `api/v1/interventions.py` | `test_candidates_bbox_validation` | 400 when min coordinates exceed max coordinates. | 400 Bad Request returned. | **PASS** | `test_security_audit.py` |
| **SEC-17** | Coordinates Range | `api/v1/interventions.py` | `test_candidates_bbox_validation` | 400 when coordinates exceed [-180, 180] / [-90, 90]| 400 Bad Request returned. | **PASS** | `test_security_audit.py` |
| **SEC-18** | HPI Bbox Check | `api/v1/heat_priority.py` | `test_heat_priority_cells_bbox_validation` | 400 on reversed or out-of-range bbox on HPI cells.| 400 Bad Request returned. | **PASS** | `test_security_audit.py` |
| **SEC-19** | Tile Zoom Bounds | `api/v1/rasters.py` | `test_raster_tile_zoom_and_coordinate_bounds` | 422 on negative zoom or zoom > 24. | 422 Unprocessable Entity returned. | **PASS** | `test_security_audit.py` |
| **SEC-20** | Ingestion Scripts | `core/file_validation.py` | `test_file_validation_prohibits_dangerous_extensions`| FileValidationError on .exe, .sh, .py uploads. | Prohibited executable rejected. | **PASS** | `test_security_audit.py` |
| **SEC-21** | Path Traversal | `core/file_validation.py` | `test_file_validation_path_traversal_sanitization`| Path traversal (../) stripped; null bytes blocked.| Traversal eliminated; null byte raised error.| **PASS** | `test_security_audit.py` |
| **SEC-22** | Magic Bytes Check | `core/file_validation.py` | `test_file_validation_magic_bytes_inspection` | Spoofed GeoTIFF binary rejected. | Genuine TIFF passed; spoofed EXE rejected. | **PASS** | `test_security_audit.py` |
| **SEC-23** | DB Zero Orphans | PostgreSQL / PostGIS | `test_database_referential_integrity_zero_orphans`| 0 orphan observations and 0 orphan scores. | Exactly 0 orphan rows in live DB. | **PASS** | `test_security_audit.py` |
| **SEC-24** | Geometry Validity | PostGIS | `test_postgis_geometry_validity_and_srid` | 100% valid geometries with SRID 4326. | 0 invalid, 0 non-4326, 0 empty geoms. | **PASS** | `test_security_audit.py` |
| **SEC-25** | Error Shielding | FastAPI Exception Shield | `test_nonexistent_endpoint_no_information_disclosure`| Zero stack trace or filesystem path leakage. | Clean 404 response without internal paths. | **PASS** | `test_security_audit.py` |
| **SEC-26** | Researcher Optimize Denial | `api/v1/interventions.py` | `test_researcher_blocked_from_optimization` | 403 when researcher calls `/optimize`. | 403 Forbidden with role explanation. | **PASS** | `test_security_audit.py` |
| **SEC-27** | Fail-Closed Unauth Optimize| `api/v1/interventions.py` | `test_unauthenticated_blocked_from_optimization_in_all_environments` | 401 unauthenticated across dev, prod, and test. | 401 Unauthorized in all environments. | **PASS** | `test_security_audit.py` |
| **SEC-28** | Planner & Admin Optimize   | `api/v1/interventions.py` | `test_planner_and_admin_authorized_for_optimization` | 200 OK for planner and admin roles. | 200 OK with solutions returned. | **PASS** | `test_security_audit.py` |
| **SEC-29** | Production Secret Validator| `core/config.py` | `test_production_settings_rejects_weak_and_dev_jwt_secret` | ValidationError on dev JWT secrets or short keys. | Startup rejected with critical error. | **PASS** | `test_security_audit.py` |
| **SEC-30** | Auth Rate Limiting Throttling | `core/rate_limit.py` | `test_auth_rate_limiting_enforcement_and_headers` | 429 Too Many Requests after 5 failed attempts with `Retry-After`. | 429 returned with safe message and header. | **PASS** | `test_security_audit.py` |
| **SEC-31** | Auth Rate Limiting Reset   | `core/rate_limit.py` | `test_auth_rate_limiting_reset` | Quota restored upon administrative/test reset. | 401 returns immediately upon reset. | **PASS** | `test_security_audit.py` |
| **SEC-32** | Sliding Window Expiry      | `core/rate_limit.py` | `test_auth_rate_limiting_sliding_window_expiry` | Quota restored after window elapses. | Allowed after synthetic clock advance. | **PASS** | `test_security_audit.py` |
| **SEC-33** | Analysis Geometry Complexity| `api/v1/analysis.py` | `test_analysis_geometry_complexity_limit_rejected` | 400 on polygon exceeding 2500 vertices. | 400 Bad Request returned. | **PASS** | `test_security_audit.py` |
| **SEC-34** | Analysis Geometry Bounds    | `api/v1/analysis.py` | `test_analysis_geometry_coordinates_out_of_bounds` | 400 on coordinates exceeding valid range. | 400 Bad Request returned. | **PASS** | `test_security_audit.py` |
| **SEC-35** | Spoofed Forwarded-For Evasion Defense | `core/rate_limit.py` | `test_auth_rate_limiting_spoofed_forwarded_for_cannot_evade_throttle` | Rotating `X-Forwarded-For` header cannot evade peer throttling. | 429 enforced on peer socket address. | **PASS** | `test_security_audit.py` |
| **SEC-36** | Bounded Store & Stale Pruning | `core/rate_limit.py` | `test_rate_limiter_bounded_storage_and_cleanup` | Tracking dictionary does not grow unbounded; prunes stale keys. | Bounded memory capacity maintained. | **PASS** | `test_security_audit.py` |
| **SEC-37** | Invalid Rate Limit Config  | `core/rate_limit.py` | `test_rate_limiter_invalid_configuration_rejected` | Zero or negative limits rejected with ValueError / Pydantic error. | ValueError raised on invalid limits. | **PASS** | `test_security_audit.py` |
| **SEC-38** | Non-Finite Coordinate Check| `api/v1/analysis.py` | `test_analysis_geometry_nan_and_inf_rejected` | NaN and Inf float coordinates rejected with 400/ValueError. | Rejection prevents GIS engine crashes. | **PASS** | `test_security_audit.py` |
| **SEC-39** | Geometry Ring Closure Check| `api/v1/analysis.py` | `test_analysis_geometry_unclosed_ring_rejected` | Unclosed polygon linear ring rejected with 400. | RFC 7946 ring closure enforced. | **PASS** | `test_security_audit.py` |
| **SEC-40** | Degenerate Linear Ring Check| `api/v1/analysis.py` | `test_analysis_geometry_degenerate_ring_rejected` | Polygon ring with < 3 distinct points rejected with 400. | Degenerate line/point polygon rejected. | **PASS** | `test_security_audit.py` |
| **SEC-41** | Boolean Coordinate Injection| `api/v1/analysis.py` | `test_analysis_geometry_boolean_coordinate_rejected` | Boolean coordinate literals rejected with 400. | Python int-coercion bypass blocked. | **PASS** | `test_security_audit.py` |
| **SEC-42** | Stage D Test Override Isolation| `backend/tests/conftest.py`| `test_stage_d_test_override_isolation` | Test client override confined strictly to Stage D tests. | Application defaults to fail-closed unauth. | **PASS** | `test_security_audit.py` |
| **SEC-43** | Checksum Manifest Normal Verification | `verify_checksums.py` | `test_verifier_valid_manifest_and_files` | Valid manifest with space-containing files passes 100%. | All files verified, zero failures reported. | **PASS** | `test_checksum_verifier.py` |
| **SEC-44** | Checksum Content Tamper Detection | `verify_checksums.py` | `test_verifier_detects_mismatch` | Tampered content flagged under mismatches category. | Content mismatch detected and reported. | **PASS** | `test_checksum_verifier.py` |
| **SEC-45** | Checksum Missing File Detection | `verify_checksums.py` | `test_verifier_detects_missing_file` | Absent files flagged under missing files category. | Missing file caught and non-zero exit code set. | **PASS** | `test_checksum_verifier.py` |
| **SEC-46** | Checksum Malformed Entry Rejection | `verify_checksums.py` | `test_verifier_rejects_malformed_lines` | Non-hex digests or incomplete lines rejected. | Malformed entries caught without silent skip. | **PASS** | `test_checksum_verifier.py` |
| **SEC-47** | Checksum Path Traversal Defense | `verify_checksums.py` | `test_verifier_rejects_absolute_and_traversal_paths` | Absolute paths & `..` traversals rejected. | Paths resolving outside repo root rejected. | **PASS** | `test_checksum_verifier.py` |
| **SEC-48** | Checksum Duplicate Path Detection | `verify_checksums.py` | `test_verifier_detects_duplicates` | Duplicate manifest entries flagged and rejected. | Duplicate entries identified with line numbers. | **PASS** | `test_checksum_verifier.py` |
| **SEC-49** | Checksum Empty Manifest Detection | `verify_checksums.py` | `test_verifier_detects_empty_manifest` | Manifest with zero valid entries rejected. | Empty manifest detected, exit code non-zero. | **PASS** | `test_checksum_verifier.py` |

---

## 3. Backend Regression Verification Command Output

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: E:\FINAL YEAR PROJECT\heatsense-ai
configfile: pyproject.toml
testpaths: backend/tests
plugins: anyio-4.15.1
collected 242 items

backend\tests\test_analysis.py ...                                       [  1%]
backend\tests\test_analysis_dataset.py .....                             [  3%]
backend\tests\test_analysis_dataset_quality.py ......                    [  5%]
backend\tests\test_checksum_verifier.py .......                          [  8%]
backend\tests\test_eligibility.py .....                                  [ 10%]
backend\tests\test_final_holdout.py ...                                  [ 11%]
backend\tests\test_health.py .                                           [ 11%]
backend\tests\test_heat_priority.py .........                            [ 15%]
backend\tests\test_holdout_protocol.py .............                     [ 21%]
backend\tests\test_hotspot_definitions.py ......                         [ 23%]
backend\tests\test_hotspot_persistence.py ...                            [ 24%]
backend\tests\test_lst_extremes_analysis.py ....                         [ 26%]
backend\tests\test_ml_experiments_and_conformal.py ....                  [ 28%]
backend\tests\test_ml_sensitivity.py ...                                 [ 29%]
backend\tests\test_optical_sentinel_audit.py ..............              [ 35%]
backend\tests\test_pixel_quality.py .......                              [ 37%]
backend\tests\test_policy_comparison.py .......                          [ 40%]
backend\tests\test_policy_d_spec.py ....                                 [ 42%]
backend\tests\test_rasters.py ..                                         [ 43%]
backend\tests\test_rf_model.py ....                                      [ 45%]
backend\tests\test_scientific_freeze_audit.py ........                   [ 48%]
backend\tests\test_security_audit.py ................................... [ 62%]
backend\tests\test_spatial_validation.py ...                             [ 63%]
backend\tests\test_stage_c_api.py .........                              [ 67%]
backend\tests\test_stage_c_confidence.py ......                          [ 70%]
backend\tests\test_stage_c_db.py ........                                [ 73%]
backend\tests\test_stage_c_freeze.py .                                   [ 73%]
backend\tests\test_stage_c_imputation.py ......                          [ 76%]
backend\tests\test_stage_c_persistence.py .....                          [ 78%]
backend\tests\test_stage_c_scoring.py ........                           [ 81%]
backend\tests\test_stage_c_sensitivity.py .                              [ 81%]
backend\tests\test_stage_c_spatial.py ....                               [ 83%]
backend\tests\test_stage_d_api.py .......                                [ 86%]
backend\tests\test_stage_d_candidates.py .....                           [ 88%]
backend\tests\test_stage_d_cooling_metrics.py .........                  [ 92%]
backend\tests\test_stage_d_optimizer.py ...                              [ 93%]
backend\tests\test_xgb_model.py ....                                     [ 95%]
backend\tests\test_xgb_tuning.py ......                                  [100%]

====================== 242 passed, 25 warnings in 50.46s ======================
```


