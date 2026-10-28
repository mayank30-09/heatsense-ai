#!/usr/bin/env python3
"""
scripts/check_doc_paths.py

Extracts every file path mentioned in:
  - docs/EVIDENCE_REGISTER.md
  - docs/VALIDATION_STATUS.md
  - README.md
  - docs/KNOWN_LIMITATIONS.md
  - docs/RUN_GUIDE.md
and reports which paths do not exist (relative to repo root, ignoring HTTP links).
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

TARGET_DOCS = [
    "docs/EVIDENCE_REGISTER.md",
    "docs/VALIDATION_STATUS.md",
    "README.md",
    "docs/KNOWN_LIMITATIONS.md",
    "docs/RUN_GUIDE.md",
]

# Common extensions indicating candidate file paths
FILE_EXTENSIONS = (
    ".py", ".json", ".csv", ".md", ".tif", ".tiff", ".geojson",
    ".parquet", ".sh", ".ps1", ".yaml", ".yml", ".png", ".jpg",
    ".html", ".sha256", ".ts", ".tsx", ".sql", ".patch", ".env",
    ".toml", ".txt"
)

# Known repository root directories
KNOWN_TOP_DIRS = (
    "artifacts/", "backend/", "data/", "docs/", "frontend/",
    "gis/", "migrations/", "reports/", "scripts/", "tests/",
    "config/", ".github/"
)

# Words or ratios that look like paths because they contain slashes, but are not files
FALSE_POSITIVE_TOKENS = {
    "8/9", "148/045", "148/45", "14/14", "14/18", "18/18", "17/25", "16/21", "25/25", "8/25", "17/17", "41/41", "33/33",
    "w/m", "w/m²", "kg/m", "kg/m³", "120/kl", "a/500", "000/m²", "300/m²", "400/m²",
    "usgs/ee", "linux/macos", "design/supervision", "pde/cfd", "pdf/csv", "pdfs/csvs",
    "typescript/vite", "geojson/tiff/json", "mae/rmse", "ward/slum", "comment/blank",
    "ai/ml", "c/d", "n/a", "oli/oli-2", "spectral/site-type", "structural/demographic",
    "measured/modelled/assumption/unverified", "bounding-box/heuristic", "3-year/10-year",
    "services/deep", "tcp", "activate.ps1",
}


def normalize_candidate(raw: str) -> str | None:
    """Clean and normalize a raw candidate string into a relative repo path."""
    if not raw:
        return None
        
    s = raw.strip().strip("'\"`")
    
    # Ignore HTTP/HTTPS/mailto/ftp links
    if re.match(r"^(https?|mailto|ftp):", s, re.IGNORECASE):
        return None
        
    # Ignore network host/port patterns like //localhost, //127.0.0.1, 8000/docs, 5433/heatsense
    if s.startswith("//") or re.match(r"^\d{4,5}/", s) or re.match(r"^localhost:\d+", s):
        return None

    # Handle file:/// URLs (unquote fully first)
    s = urllib.parse.unquote(s)
    if s.lower().startswith("file:///"):
        s = s[8:]
        # Remove leading drive slash if /e:/...
        if re.match(r"^/[a-zA-Z]:", s):
            s = s[1:]
            
    norm_s = s.replace("\\", "/")
    norm_root = str(REPO_ROOT).replace("\\", "/")
    if norm_s.lower().startswith(norm_root.lower()):
        s = norm_s[len(norm_root):].lstrip("/")
    elif re.match(r"^[a-zA-Z]:/", norm_s):
        # Absolute path outside repo root
        return None

    # Strip anchor fragments (#...)
    if "#" in s:
        s = s.split("#")[0]
        
    # Strip line numbers or function references (:65, :check_scene_provenance, :75-85)
    # But preserve Windows drive letters like C:
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2 and len(parts[0]) == 1 and parts[0].isalpha():
            pass
        else:
            s = parts[0]
            
    s = s.strip().rstrip(".,;:!?)")
    s = s.replace("\\", "/")
    
    # Remove leading ./
    if s.startswith("./"):
        s = s[2:]
        
    if not s or s.startswith("#"):
        return None
        
    # Check false positives
    if s.lower() in FALSE_POSITIVE_TOKENS:
        return None
        
    return s


def is_candidate_path(token: str) -> bool:
    """Determine if a token represents a candidate filesystem path."""
    if not token or len(token) < 2:
        return False
        
    lower = token.lower()
    if lower in FALSE_POSITIVE_TOKENS:
        return False
        
    # Ignore command line tokens, code keywords, or template variables
    if token in (
        "python", "pytest", "npm", "git", "cd", "run", "add", "commit", "push",
        "true", "false", "null", "HEAD", "origin", "main", "master",
    ) or "<" in token or ">" in token:
        return False
        
    # Ignore REST API paths (like /api/v1/...)
    if lower.startswith("/api/") or lower.startswith("api/"):
        return False
        
    # Ignore Linux system paths like /opt/..., /var/...
    if lower.startswith("/opt/") or lower.startswith("/var/") or lower.startswith("/etc/"):
        return False
        
    # Starts with known repo dir
    if any(lower.startswith(d.lower()) for d in KNOWN_TOP_DIRS):
        return True
        
    # Has known file extension
    if any(lower.endswith(ext) for ext in FILE_EXTENSIONS):
        return True
        
    # File in repo root like verify_checksums.py, README.md, etc.
    if "/" not in token and any(lower.endswith(ext) for ext in FILE_EXTENSIONS):
        return True
            
    return False


def extract_paths_from_text(content: str) -> Set[str]:
    """Extract all candidate paths from markdown content, strictly ignoring HTTP links."""
    candidates: Set[str] = set()

    # 1. Markdown links: [text](target) - ignore http/https/mailto
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
        target = match.group(2).strip()
        norm = normalize_candidate(target)
        if norm and is_candidate_path(norm):
            candidates.add(norm)

    # Strip out HTTP/HTTPS/mailto URLs so their path components are not falsely extracted
    clean_content = re.sub(r"https?://\S+", " ", content, flags=re.IGNORECASE)
    clean_content = re.sub(r"mailto:\S+", " ", clean_content, flags=re.IGNORECASE)

    # 2. Backticks: `token`
    for match in re.finditer(r"`([^`\n]+)`", clean_content):
        raw = match.group(1).strip()
        # Might contain multiple paths separated by semicolons, commas, or spaces
        sub_tokens = re.split(r"[;\s]+", raw)
        for sub in sub_tokens:
            norm = normalize_candidate(sub)
            if norm and is_candidate_path(norm):
                candidates.add(norm)
        norm_whole = normalize_candidate(raw)
        if norm_whole and is_candidate_path(norm_whole):
            candidates.add(norm_whole)

    # 3. Path patterns in table cells or text starting with known directories
    for top_dir in KNOWN_TOP_DIRS:
        # Match tokens like data/cogs/foo.tif or docs/foo.md, avoiding parts of URLs
        pattern = re.compile(rf"(?<!/)\b{re.escape(top_dir)}[\w\.\-/]+", re.IGNORECASE)
        for match in pattern.finditer(clean_content):
            norm = normalize_candidate(match.group(0))
            if norm and is_candidate_path(norm):
                candidates.add(norm)

    # 4. Known standalone root files mentioned in text
    root_file_pattern = re.compile(r"\b(verify_checksums\.py|README\.md|CLAUDE\.md)\b")
    for match in root_file_pattern.finditer(clean_content):
        candidates.add(match.group(1))

    return candidates


def check_doc_paths(docs: list[str] = TARGET_DOCS) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Check extracted paths across specified documents."""
    doc_missing: Dict[str, List[str]] = {}
    doc_found: Dict[str, List[str]] = {}

    for rel_doc in docs:
        doc_file = REPO_ROOT / rel_doc
        if not doc_file.exists():
            print(f"[WARNING] Document not found: {rel_doc}", file=sys.stderr)
            continue

        text = doc_file.read_text(encoding="utf-8")
        extracted = extract_paths_from_text(text)

        missing: List[str] = []
        found: List[str] = []

        for p_str in sorted(extracted):
            target = REPO_ROOT / p_str
            if target.exists():
                found.append(p_str)
            else:
                missing.append(p_str)

        doc_missing[rel_doc] = missing
        doc_found[rel_doc] = found

    return doc_found, doc_missing


def main() -> int:
    print("=" * 72)
    print("HEATSENSE AI — Documentation Path Verification Check")
    print(f"Repository Root: {REPO_ROOT}")
    print("=" * 72)

    doc_found, doc_missing = check_doc_paths()

    total_checked = 0
    total_missing = 0
    all_missing_paths: Set[str] = set()

    for doc, missing in doc_missing.items():
        found = doc_found[doc]
        total_checked += len(found) + len(missing)
        total_missing += len(missing)
        for m in missing:
            all_missing_paths.add(m)

        print(f"\nDocument: {doc}")
        print(f"  Total paths extracted: {len(found) + len(missing)}")
        print(f"  Valid paths found:     {len(found)}")
        print(f"  Missing paths:         {len(missing)}")
        if missing:
            for m in missing:
                print(f"    [MISSING] {m}")

    print("\n" + "-" * 72)
    print(f"Total Unique Missing Paths: {len(all_missing_paths)}")
    print(f"Total Extracted Path Occurrences: {total_checked}")
    print(f"Total Missing Path Occurrences:   {total_missing}")
    print("-" * 72)

    if all_missing_paths:
        print("\nALL UNIQUE MISSING PATHS:")
        for idx, p in enumerate(sorted(all_missing_paths), start=1):
            print(f"  {idx:2d}. {p}")
        return 1
    else:
        print("\n[PASS] All documentation file and directory references exist on disk!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
