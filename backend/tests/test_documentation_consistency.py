"""Automated Documentation Consistency & Evidence Register Tests for HEATSENSE AI (Stage D).

Covers T6 Requirements:
1. Verifies that docs/EVIDENCE_REGISTER.md exists and enforces the four explicit evidential statuses.
2. Verifies that README.md documents critical invariants (checksum verifier, dual R2, 100m grid domain).
3. Verifies that no active docs claim the production code is a PDE or CFD continuum solver.
4. Verifies that key referenced evidence paths in docs/EVIDENCE_REGISTER.md exist on disk.
"""

from __future__ import annotations

from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_evidence_register_exists_and_covers_required_categories():
    """Verify that docs/EVIDENCE_REGISTER.md exists and implements all four required evidential statuses."""
    ev_path = REPO_ROOT / "docs" / "EVIDENCE_REGISTER.md"
    assert ev_path.is_file(), f"Missing evidence register: {ev_path}"

    content = ev_path.read_text(encoding="utf-8")

    # The four required evidential statuses
    required_statuses = [
        "Verified by a reproducible command or committed artifact",
        "Supported by source metadata or documented methodology",
        "Assumption or heuristic",
        "Unverified or unavailable",
    ]
    for status in required_statuses:
        assert status in content, f"Evidence register missing status category: '{status}'"

    # Core platform claims must be cataloged
    assert "Landsat 8/9 LST Radiometric Conversion" in content
    assert "SMC Municipal Domain Boundary" in content
    assert "Canonical 100m Analytical Grid" in content
    assert "Cryptographic Freeze Checksums" in content
    assert "2km Block-Disjoint Spatial Holdout Split" in content
    assert "Pooled Random-Split Holdout Performance" in content
    assert "Geographically Blocked Spatial-Split Performance" in content
    assert "Baseline HPI Formulation" in content
    assert "Linearized Microclimate Heat Dissipation Model" in content
    assert "Itemized Engineering Markup Structure" in content
    assert "CPWD DSR 2023 & SMC Annual Rate Contract Alignment" in content
    assert "Legal Municipal Land Ownership & Confirmed Vacancy" in content


def test_readme_documents_critical_invariants():
    """Verify that README.md reflects production reality and documents critical invariants."""
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.is_file(), f"Missing README: {readme_path}"

    content = readme_path.read_text(encoding="utf-8")

    # Invariants that must be documented
    assert "verify_checksums.py" in content
    assert "41/41" in content or "41 Verified" in content
    assert "461.63" in content
    assert "49,747" in content
    assert "0.9006" in content
    assert "0.7119" in content
    assert "Linearized" in content

    # Key documentation links
    assert "EVIDENCE_REGISTER.md" in content
    assert "VALIDATION_STATUS.md" in content
    assert "KNOWN_LIMITATIONS.md" in content


def test_no_claims_of_pde_or_cfd_continuum_solvers_in_active_docs():
    """Verify that active production UI and documentation do not claim the active code is a PDE or CFD solver."""
    scan_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "frontend" / "src" / "components" / "interventions" / "ScenarioLab.tsx",
        REPO_ROOT / "frontend" / "src" / "components" / "interventions" / "InterventionExplorer.tsx",
        REPO_ROOT / "frontend" / "src" / "components" / "common" / "ScienceGlossaryModal.tsx",
    ]

    disallowed_claims = [
        "continuum pde solver",
        "surface energy balance pde",
        "cfd solver deployed",
        "is a pde solver",
        "uses a pde solver",
    ]

    for fpath in scan_files:
        assert fpath.is_file(), f"Target file missing: {fpath}"
        content = fpath.read_text(encoding="utf-8").lower()
        for phrase in disallowed_claims:
            assert phrase not in content, f"Disallowed '{phrase}' claim in {fpath.name}"


def test_referenced_evidence_paths_exist():
    """Verify that file paths referenced in the Evidence Register physically exist in the repository."""
    key_evidence_paths = [
        "data/raw/boundaries/surat_smc_boundary.geojson",
        "docs/audits/stage-c-baseline-inspection.md",
        "artifacts/ml_freeze/checksums.sha256",
        "artifacts/ml_freeze/holdout_split.json",
        "artifacts/ml_freeze/feature_schema.json",
        "artifacts/ml_freeze/holdout_performance.json",
        "artifacts/ml_freeze/holdout_spatial_residuals.geojson",
        "artifacts/ml_experiments/ml_experimental_evaluation.json",
        "docs/provenance/seasonal_scene_manifest.json",
        "docs/validation/scenario_summary.json",
        "gis/interventions/cooling_effects.py",
        "gis/interventions/costs.py",
        "gis/interventions/landuse.py",
        "gis/interventions/config/landuse_interventions.json",
        "reports/INTERVENTION_REALISM_REPORT.md",
        "reports/hpi_sensitivity_analysis.json",
        "reports/hpi_sensitivity_analysis.md",
    ]

    for rel_path in key_evidence_paths:
        target = REPO_ROOT / rel_path
        assert target.is_file(), f"Referenced evidence artifact missing: {rel_path}"


def test_all_documentation_paths_exist():
    """Verify that every file path referenced in key documentation exists on disk via check_doc_paths."""
    import sys
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from scripts.check_doc_paths import check_doc_paths

    doc_found, doc_missing = check_doc_paths()
    all_missing = {doc: paths for doc, paths in doc_missing.items() if paths}
    assert not all_missing, f"Missing documentation paths found: {all_missing}"
