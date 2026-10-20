"""Authoritative SHA-256 Checksum Verifier for HeatSense AI Freeze Manifests.

This script independently validates repository files against an authoritative
SHA-256 manifest (default: artifacts/ml_freeze/checksums.sha256).

Security and Integrity Invariants:
- Validates every non-comment manifest line; malformed entries are strictly reported as failures.
- Requires valid 64-character hexadecimal SHA-256 digests.
- Rejects absolute paths and path traversal attempts outside the repository root.
- Detects missing files, content hash mismatches, duplicate entries, and empty manifests.
- Handles filenames with spaces correctly.
- Operates read-only: never modifies the manifest or any target file.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path


HEX_64_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class ChecksumVerificationResult:
    """Encapsulates the structured results of manifest verification."""

    def __init__(self) -> None:
        self.total_lines: int = 0
        self.comment_or_empty_lines: int = 0
        self.valid_entries: int = 0
        self.matches: int = 0
        self.malformed_entries: list[tuple[int, str, str]] = []  # (line_no, raw_line, reason)
        self.duplicate_paths: list[tuple[int, str]] = []  # (line_no, path)
        self.missing_files: list[str] = []  # path
        self.mismatches: list[tuple[str, str, str]] = []  # (path, expected, actual)
        self.empty_manifest: bool = False

    @property
    def is_success(self) -> bool:
        """Success requires non-empty manifest, zero malformed lines, zero duplicates, zero missing, zero mismatches."""
        return (
            not self.empty_manifest
            and len(self.malformed_entries) == 0
            and len(self.duplicate_paths) == 0
            and len(self.missing_files) == 0
            and len(self.mismatches) == 0
            and self.valid_entries > 0
            and self.matches == self.valid_entries
        )


def verify_manifest(
    manifest_path: Path,
    repo_root: Path | None = None,
) -> ChecksumVerificationResult:
    """Verifies all entries in a checksum manifest against files on disk.

    Args:
        manifest_path: Path to the SHA-256 manifest file.
        repo_root: Repository root against which relative paths are resolved.
                   Defaults to the parent directory of this script or cwd.

    Returns:
        ChecksumVerificationResult with detailed failure breakdowns.
    """
    result = ChecksumVerificationResult()

    if repo_root is None:
        repo_root = Path(__file__).resolve().parent
    repo_root = repo_root.resolve()

    if not manifest_path.exists() or not manifest_path.is_file():
        result.empty_manifest = True
        result.malformed_entries.append((0, str(manifest_path), "Manifest file not found or not a regular file"))
        return result

    seen_paths: set[str] = set()

    with open(manifest_path, "r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            result.total_lines += 1
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                result.comment_or_empty_lines += 1
                continue

            # Standard sha256sum format: 64 hex characters followed by 2 spaces/flags and the path
            # Or whitespace-separated digest and path
            if len(line) >= 66 and HEX_64_PATTERN.match(line[:64]) and line[64:66] in ("  ", " *"):
                expected_sha256 = line[:64]
                rel_path = line[66:]
            else:
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    result.malformed_entries.append(
                        (line_no, line, "Malformed line: expected '<sha256>  <path>' format")
                    )
                    continue
                expected_sha256, rel_path = parts
                if rel_path.startswith("*"):
                    rel_path = rel_path[1:]

            # 1. Validate 64-char hexadecimal digest
            if not HEX_64_PATTERN.match(expected_sha256):
                result.malformed_entries.append(
                    (line_no, line, f"Invalid SHA-256 digest: '{expected_sha256}' is not a 64-character hex string")
                )
                continue

            # 2. Validate path format (reject empty, absolute, or traversal paths)
            if not rel_path or not rel_path.strip():
                result.malformed_entries.append(
                    (line_no, line, "Empty file path specified")
                )
                continue

            rel_path_obj = Path(rel_path)

            if rel_path_obj.is_absolute() or rel_path.startswith(("/", "\\")):
                result.malformed_entries.append(
                    (line_no, line, f"Absolute path rejected: '{rel_path}'")
                )
                continue

            # Check drive letter on Windows (e.g. C:file)
            if len(rel_path) > 1 and rel_path[1] == ":":
                result.malformed_entries.append(
                    (line_no, line, f"Absolute drive path rejected: '{rel_path}'")
                )
                continue

            # Resolve target path and verify it stays within repo_root
            try:
                target_path = (repo_root / rel_path_obj).resolve()
                target_path.relative_to(repo_root)
            except (ValueError, RuntimeError):
                result.malformed_entries.append(
                    (line_no, line, f"Path traversal rejected: '{rel_path}' resolves outside repository root")
                )
                continue

            # 3. Detect duplicate paths in manifest (normalized)
            norm_path = rel_path.replace("\\", "/").strip()
            if norm_path in seen_paths:
                result.duplicate_paths.append((line_no, rel_path))
                continue
            seen_paths.add(norm_path)

            result.valid_entries += 1

            # 4. Check file existence
            if not target_path.exists() or not target_path.is_file():
                result.missing_files.append(rel_path)
                continue

            # 5. Compute SHA-256 and compare
            hasher = hashlib.sha256()
            try:
                with open(target_path, "rb") as bf:
                    while chunk := bf.read(65536):
                        hasher.update(chunk)
                actual_sha256 = hasher.hexdigest()
            except OSError as e:
                result.malformed_entries.append(
                    (line_no, line, f"I/O error reading '{rel_path}': {e}")
                )
                continue

            if actual_sha256.lower() == expected_sha256.lower():
                result.matches += 1
            else:
                result.mismatches.append((rel_path, expected_sha256, actual_sha256))

    if result.valid_entries == 0 and len(result.malformed_entries) == 0:
        result.empty_manifest = True

    return result


def print_report(result: ChecksumVerificationResult, manifest_path: Path) -> None:
    """Prints a clear, categorized diagnostic report."""
    print("=" * 70)
    print("HeatSense AI — SHA-256 Checksum Manifest Verification Report")
    print("=" * 70)
    print(f"Manifest File: {manifest_path}")
    print(f"Total Lines Processed: {result.total_lines}")
    print(f"Comment/Blank Lines:   {result.comment_or_empty_lines}")
    print(f"Valid Entries:         {result.valid_entries}")
    print(f"Verified Matches:      {result.matches}")
    print(f"Missing Files:         {len(result.missing_files)}")
    print(f"Checksum Mismatches:   {len(result.mismatches)}")
    print(f"Duplicate Paths:       {len(result.duplicate_paths)}")
    print(f"Malformed Lines:       {len(result.malformed_entries)}")
    print(f"Empty Manifest:        {result.empty_manifest}")
    print("-" * 70)

    if result.empty_manifest:
        print("[FAIL] Manifest contains zero valid entries.")

    if result.malformed_entries:
        print(f"\n[FAIL] Malformed Manifest Entries ({len(result.malformed_entries)}):")
        for line_no, raw, reason in result.malformed_entries:
            print(f"  - Line {line_no}: {reason}")
            print(f"    Content: '{raw}'")

    if result.duplicate_paths:
        print(f"\n[FAIL] Duplicate Manifest Paths ({len(result.duplicate_paths)}):")
        for line_no, path in result.duplicate_paths:
            print(f"  - Line {line_no}: Duplicate entry for '{path}'")

    if result.missing_files:
        print(f"\n[FAIL] Missing Protected Files ({len(result.missing_files)}):")
        for path in result.missing_files:
            print(f"  - {path}")

    if result.mismatches:
        print(f"\n[FAIL] Checksum Mismatches ({len(result.mismatches)}):")
        for path, exp, act in result.mismatches:
            print(f"  - {path}")
            print(f"    Expected: {exp}")
            print(f"    Actual:   {act}")

    if result.is_success:
        print("\n[PASS] ALL CHECKSUMS VERIFIED OK (100% MATCH)!")
        print("All protected artifacts match authoritative freeze digests exactly.")
    else:
        print("\n[FAIL] CHECKSUM VERIFICATION FAILED.")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify HeatSense AI freeze artifacts against SHA-256 manifest."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to checksums.sha256 (default: artifacts/ml_freeze/checksums.sha256)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Path to repository root (default: directory containing this script)",
    )

    args = parser.parse_args()

    repo_root = args.repo_root or Path(__file__).resolve().parent
    manifest_path = args.manifest or (repo_root / "artifacts" / "ml_freeze" / "checksums.sha256")

    result = verify_manifest(manifest_path, repo_root)
    print_report(result, manifest_path)

    return 0 if result.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
