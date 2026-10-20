"""Defensive file validation utilities for spatial, raster, and tabular dataset ingestion.

Enforces:
- File size ceilings (default: 50 MB)
- Extension allowlist (.geojson, .json, .tif, .tiff, .parquet, .csv)
- MIME / Magic byte inspection
- Directory traversal & path sanitization
- Executable script rejection (.exe, .sh, .py, .bat, .cmd, .ps1, etc.)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import BinaryIO

# Maximum permitted file size in bytes (50 MB)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Allowed file extensions for geospatial and scientific datasets
ALLOWED_EXTENSIONS = {
    ".geojson",
    ".json",
    ".tif",
    ".tiff",
    ".parquet",
    ".csv",
}

# Known executable or dangerous script extensions that are strictly prohibited
PROHIBITED_EXTENSIONS = {
    ".exe",
    ".sh",
    ".bat",
    ".cmd",
    ".ps1",
    ".py",
    ".js",
    ".ts",
    ".php",
    ".pl",
    ".rb",
    ".jar",
    ".vbs",
    ".dll",
    ".so",
    ".dylib",
}

# Magic bytes signatures for validated formats
MAGIC_SIGNATURES = {
    "TIFF_LITTLE_ENDIAN": b"II*\x00",
    "TIFF_BIG_ENDIAN": b"MM\x00*",
    "PARQUET": b"PAR1",
}


class FileValidationError(ValueError):
    """Raised when a file fails defensive security or integrity validation."""
    pass


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or filesystem corruption."""
    if not filename:
        raise FileValidationError("Filename cannot be empty.")
    
    # Strip null bytes
    if "\x00" in filename:
        raise FileValidationError("Null bytes are prohibited in filenames.")
        
    # Extract only the base name (rejects ../ or / paths)
    base_name = os.path.basename(filename.replace("\\", "/"))
    
    # Remove any dangerous characters, allowing only alphanumeric, dash, underscore, dot
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base_name)
    
    if not sanitized or sanitized.startswith("."):
        raise FileValidationError("Filename must be a valid alphanumeric identifier.")
        
    return sanitized


def validate_file_upload(
    filename: str,
    file_bytes: bytes | None = None,
    file_size: int | None = None,
) -> dict[str, str | int]:
    """Defensively validate an incoming file before processing or storage."""
    clean_name = sanitize_filename(filename)
    suffix = Path(clean_name).suffix.lower()

    if suffix in PROHIBITED_EXTENSIONS:
        raise FileValidationError(
            f"Prohibited executable or script file extension '{suffix}'. Ingestion rejected."
        )

    if suffix not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file extension '{suffix}'. Allowed: {sorted(list(ALLOWED_EXTENSIONS))}."
        )

    effective_size = file_size
    if file_bytes is not None:
        effective_size = len(file_bytes)

    if effective_size is not None:
        if effective_size <= 0:
            raise FileValidationError("Uploaded file is empty (0 bytes).")
        if effective_size > MAX_FILE_SIZE_BYTES:
            raise FileValidationError(
                f"File size {effective_size} bytes exceeds maximum permitted limit of {MAX_FILE_SIZE_BYTES} bytes (50 MB)."
            )

    # Magic byte inspection for binary rasters & parquet
    if file_bytes is not None and len(file_bytes) >= 4:
        header = file_bytes[:4]
        if suffix in (".tif", ".tiff"):
            if not (header.startswith(MAGIC_SIGNATURES["TIFF_LITTLE_ENDIAN"]) or header.startswith(MAGIC_SIGNATURES["TIFF_BIG_ENDIAN"])):
                raise FileValidationError("Invalid TIFF magic header signature. File is corrupted or spoofed.")
        elif suffix == ".parquet":
            if not header.startswith(MAGIC_SIGNATURES["PARQUET"]):
                raise FileValidationError("Invalid Parquet magic header signature. File is corrupted or spoofed.")

    return {
        "status": "VALID",
        "sanitized_filename": clean_name,
        "extension": suffix,
        "size_bytes": effective_size or 0,
    }
