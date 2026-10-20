# 09 — File Upload & Ingestion Security Audit

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Ingestion File Validation, Directory Traversal Defense, Executable Code Blocking, and MIME/Magic Header Verification  
**Date:** October 2026  
**Auditor Classification:** Senior Application Security Engineer  
**Component:** `backend/app/core/file_validation.py`, `backend/tests/test_security_audit.py`  
**Status:** **NOT APPLICABLE IN LIVE HTTP API / FULL DEFENSIVE ENGINE IMPLEMENTED & VERIFIED**  

---

## 1. Attack Surface Analysis

A comprehensive scan of the active FastAPI routing surface (`backend/app/api/v1`) confirms that:
- **Zero multipart file upload endpoints are exposed on the public HTTP interface.**
- File-based inputs currently ingest via local filesystem pipelines and authenticated batch scripts (`scripts/run_stage_c_pipeline.py`).
- Therefore, external file upload vulnerabilities are **NOT APPLICABLE** on the current live HTTP API.

However, to support planned administrative dataset ingestion (`POST /admin/ingest`) and prevent future upload vulnerabilities, a robust defensive validation engine was built and verified in [backend/app/core/file_validation.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/app/core/file_validation.py).

---

## 2. Defensive Validation Architecture

```text
Incoming File Stream / Upload
             │
             ├─► [1. Filename Sanitization] ── Fail (.. or \0) ──► FileValidationError
             │     - Strips directory paths
             │     - Eliminates traversal (../)
             │     - Rejects null bytes
             │
             ├─► [2. Extension Allowlist] ─── Prohibited (.exe/.sh) ──► FileValidationError
             │     - Allowed: .geojson, .tif, .tiff, .parquet, .csv
             │     - Prohibited: .exe, .sh, .bat, .cmd, .ps1, .py, .php
             │
             ├─► [3. File Size Validation] ── Oversized (>50MB) ──► FileValidationError
             │     - Max limit: 50 MB
             │     - Min limit: > 0 bytes (no empty files)
             │
             ├─► [4. Magic Bytes Inspection] ── Spoofed Signature ──► FileValidationError
             │     - TIFF: II*\0 or MM\0*
             │     - Parquet: PAR1
             │
             └─► Validated Safe File for Ingestion
```

---

## 3. Detailed Defensive Controls Implemented

| Defensive Control | Implementation | Enforced Boundary |
| :--- | :--- | :--- |
| **Directory Traversal Defense** | `sanitize_filename()` | Neutralizes `../`, `..\\`, absolute paths, and null bytes (`\x00`), extracting only safe alphanumeric filenames. |
| **Executable Extension Blocking** | `PROHIBITED_EXTENSIONS` | Rejects executable and script extensions (`.exe`, `.sh`, `.bat`, `.cmd`, `.ps1`, `.py`, `.js`, `.php`, etc.). |
| **Geospatial Extension Allowlist** | `ALLOWED_EXTENSIONS` | Restricts uploads to verified formats: `.geojson`, `.json`, `.tif`, `.tiff`, `.parquet`, `.csv`. |
| **File Size Ceiling** | `MAX_FILE_SIZE_BYTES` | Enforces a strict 50 MB (52,428,800 bytes) ceiling to prevent memory exhaustion and DoS. |
| **Zero-Byte File Rejection** | Empty check | Rejects 0-byte corrupt files before parsing. |
| **Magic Byte Inspection** | `MAGIC_SIGNATURES` | Reads raw binary headers to confirm genuine GeoTIFF (`II*\x00` or `MM\x00*`) and Parquet (`PAR1`) structures, preventing file extension spoofing. |

---

## 4. Empirical Test Scenarios & Observed Results

Automated tests in [backend/tests/test_security_audit.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_security_audit.py#L343-L377) confirm the defensive engine:

| Test Case | Scenario / Attack Vector | Target Input | Expected Outcome | Observed Result | Evidence |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **FILE-01** | Executable script extension | `malware.exe`, `exploit.py` | Raised `FileValidationError` | Blocked, detail: `"Prohibited executable"`. | `test_file_validation_prohibits_dangerous_extensions` |
| **FILE-02** | Path traversal attempt | `../../etc/passwd.geojson` | Sanitized to base name | Traversal stripped: `"passwd.geojson"`. | `test_file_validation_path_traversal_sanitization` |
| **FILE-03** | Null byte injection | `data.geojson\x00.exe` | Raised `FileValidationError` | Blocked, detail: `"Null bytes are prohibited"`. | `test_file_validation_path_traversal_sanitization` |
| **FILE-04** | Empty file upload | `boundary.geojson` (0 bytes) | Raised `FileValidationError` | Blocked, detail: `"Uploaded file is empty"`. | `test_file_validation_size_and_empty_checks` |
| **FILE-05** | Oversized file upload | `massive.tif` (51 MB) | Raised `FileValidationError` | Blocked, detail: `"exceeds maximum permitted limit"`. | `test_file_validation_size_and_empty_checks` |
| **FILE-06** | Spoofed TIFF header | Binary EXE header with `.tif` | Raised `FileValidationError` | Blocked, detail: `"Invalid TIFF magic header"`. | `test_file_validation_magic_bytes_inspection` |

---

## 5. Conclusion & Status

- **Status:** **VERIFIED (PASS)**.
- While the active public API exposes zero upload endpoints, the file validation engine provides robust defense-in-depth for future dataset ingestion pipelines.
