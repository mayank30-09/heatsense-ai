"""Deterministic unit tests for the hardened SHA-256 checksum verifier.

Tests use temporary directory fixtures (tmp_path) and never touch or mutate
the protected production/scientific freeze manifest or artifacts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from verify_checksums import verify_manifest, ChecksumVerificationResult


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_verifier_valid_manifest_and_files(tmp_path: Path):
    """Test standard verification when all files match their digests."""
    file1 = tmp_path / "data" / "file1.txt"
    file1.parent.mkdir(parents=True, exist_ok=True)
    file1.write_bytes(b"hello world")

    file2 = tmp_path / "models" / "file with space.bin"
    file2.parent.mkdir(parents=True, exist_ok=True)
    file2.write_bytes(b"model weights 12345")

    h1 = compute_hash(b"hello world")
    h2 = compute_hash(b"model weights 12345")

    manifest = tmp_path / "checksums.sha256"
    manifest.write_text(
        f"# Authoritative checksum manifest\n"
        f"\n"
        f"{h1}  data/file1.txt\n"
        f"{h2}  models/file with space.bin\n",
        encoding="utf-8",
    )

    result = verify_manifest(manifest, tmp_path)
    assert result.is_success
    assert result.valid_entries == 2
    assert result.matches == 2
    assert len(result.missing_files) == 0
    assert len(result.mismatches) == 0
    assert len(result.malformed_entries) == 0
    assert len(result.duplicate_paths) == 0


def test_verifier_detects_mismatch(tmp_path: Path):
    """Test that altered file content is reported under mismatches."""
    file1 = tmp_path / "artifact.dat"
    file1.write_bytes(b"tampered content")

    wrong_hash = compute_hash(b"original content")
    manifest = tmp_path / "checksums.sha256"
    manifest.write_text(f"{wrong_hash}  artifact.dat\n", encoding="utf-8")

    result = verify_manifest(manifest, tmp_path)
    assert not result.is_success
    assert len(result.mismatches) == 1
    path, exp, act = result.mismatches[0]
    assert path == "artifact.dat"
    assert exp == wrong_hash
    assert act == compute_hash(b"tampered content")


def test_verifier_detects_missing_file(tmp_path: Path):
    """Test that non-existent target files are flagged as missing."""
    h = "a" * 64
    manifest = tmp_path / "checksums.sha256"
    manifest.write_text(f"{h}  non_existent_file.json\n", encoding="utf-8")

    result = verify_manifest(manifest, tmp_path)
    assert not result.is_success
    assert len(result.missing_files) == 1
    assert result.missing_files[0] == "non_existent_file.json"


def test_verifier_rejects_malformed_lines(tmp_path: Path):
    """Test that malformed digests or lines without path are caught."""
    manifest = tmp_path / "checksums.sha256"
    manifest.write_text(
        "short_digest data.txt\n"
        + ("g" * 64) + " bad_hex.txt\n"
        + "only_one_token\n",
        encoding="utf-8",
    )

    result = verify_manifest(manifest, tmp_path)
    assert not result.is_success
    assert len(result.malformed_entries) == 3


def test_verifier_rejects_absolute_and_traversal_paths(tmp_path: Path):
    """Test that absolute paths and path traversals are rejected."""
    h = "b" * 64
    manifest = tmp_path / "checksums.sha256"
    manifest.write_text(
        f"{h}  /etc/passwd\n"
        f"{h}  C:\\secret.txt\n"
        f"{h}  ../../outside_repo.txt\n",
        encoding="utf-8",
    )

    result = verify_manifest(manifest, tmp_path)
    assert not result.is_success
    assert len(result.malformed_entries) == 3
    for _, _, reason in result.malformed_entries:
        assert "rejected" in reason.lower()


def test_verifier_detects_duplicates(tmp_path: Path):
    """Test that duplicate manifest entries for the same path are flagged."""
    f = tmp_path / "file.txt"
    f.write_bytes(b"content")
    h = compute_hash(b"content")

    manifest = tmp_path / "checksums.sha256"
    manifest.write_text(
        f"{h}  file.txt\n"
        f"{h}  file.txt\n",
        encoding="utf-8",
    )

    result = verify_manifest(manifest, tmp_path)
    assert not result.is_success
    assert len(result.duplicate_paths) == 1
    assert result.duplicate_paths[0][1] == "file.txt"


def test_verifier_detects_empty_manifest(tmp_path: Path):
    """Test that manifest with zero entries is flagged."""
    manifest = tmp_path / "empty_checksums.sha256"
    manifest.write_text("# only comments\n\n", encoding="utf-8")

    result = verify_manifest(manifest, tmp_path)
    assert not result.is_success
    assert result.empty_manifest
    assert result.valid_entries == 0
