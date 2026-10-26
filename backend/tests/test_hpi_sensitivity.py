"""Tests for Controlled HPI Sensitivity Analysis (T4).

Verifies:
1. Scenario weight normalization (sum to 1.0, valid bounds).
2. Read-only baseline preservation (invariants, score reproduction).
3. Metric calculations (Pearson r, Spearman rho, Jaccard overlaps, rank shifts).
4. FastAPI endpoint GET /api/v1/heat-priority/sensitivity-analysis.
5. Missing-evidence and error handling.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from scripts.analyze_hpi_sensitivity import (
    BASELINE_CONFIG,
    SCENARIOS,
    compute_ranks_descending,
    jaccard_overlap,
    run_sensitivity_analysis,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestHPISensitivityScenarios:
    """Validate sensitivity scenario definitions and mathematical properties."""

    def test_baseline_config_invariants(self) -> None:
        """Verify locked baseline weights sum to 1.0 and match Stage C spec."""
        w = BASELINE_CONFIG["weights"]
        total_w = sum(w.values())
        assert abs(total_w - 1.0) < 1e-9
        assert w["w_thermal"] == 0.40
        assert w["w_persistence"] == 0.30
        assert w["w_vegetation"] == 0.15
        assert w["w_builtup"] == 0.15
        assert BASELINE_CONFIG["cell_count"] == 49747

    def test_all_scenario_weights_normalize_to_one(self) -> None:
        """Every sensitivity scenario must have weights summing to 1.0 and each weight > 0."""
        assert len(SCENARIOS) == 4
        for sc in SCENARIOS:
            w = sc["weights"]
            assert set(w.keys()) == {"w_thermal", "w_persistence", "w_vegetation", "w_builtup"}
            total_w = sum(w.values())
            assert abs(total_w - 1.0) < 1e-9, f"Scenario {sc['name']} weights sum to {total_w}, expected 1.0"
            for k, val in w.items():
                assert val > 0.0, f"Scenario {sc['name']} weight {k} must be positive, got {val}"
                assert val < 1.0, f"Scenario {sc['name']} weight {k} must be < 1.0, got {val}"

    def test_rank_computation_descending(self) -> None:
        """Highest score must receive rank 1 (top priority)."""
        values = np.array([10.0, 50.0, 90.0, 30.0])
        ranks = compute_ranks_descending(values)
        assert ranks[2] == 1.0  # 90.0 is highest -> rank 1
        assert ranks[1] == 2.0  # 50.0 is 2nd -> rank 2
        assert ranks[3] == 3.0  # 30.0 is 3rd -> rank 3
        assert ranks[0] == 4.0  # 10.0 is lowest -> rank 4

    def test_jaccard_overlap_bounds(self) -> None:
        """Jaccard similarity must be in [0, 100] with identity giving 100% and disjoint 0%."""
        s1 = {"a", "b", "c"}
        s2 = {"a", "b", "c"}
        assert jaccard_overlap(s1, s2) == 100.0

        s3 = {"x", "y"}
        assert jaccard_overlap(s1, s3) == 0.0

        s4 = {"b", "c", "d"}
        # Intersection = {b, c} (2), Union = {a, b, c, d} (4) -> 50.0%
        assert jaccard_overlap(s1, s4) == 50.0


class TestHPISensitivityExecution:
    """Validate full analysis engine execution against database and report generation."""

    def test_run_sensitivity_analysis_reproduces_canonical_baseline(self) -> None:
        """Verify analysis reproduces known baseline metrics without mutating database."""
        result = run_sensitivity_analysis()
        assert result["status"] == "COMPLETED"

        base = result["baseline"]
        assert base["total_cells"] == 49747
        assert base["mean_hpi"] == 42.14
        assert base["min_hpi"] == 4.83
        assert base["max_hpi"] == 96.39
        assert base["chronic_hotspots_count"] == 223
        assert base["max_recomputation_discrepancy"] < 1e-5

        # Check scenarios output
        scenarios = result["scenarios"]
        assert len(scenarios) == 4

        scenario_map = {s["id"]: s for s in scenarios}

        # Thermal dominant
        td = scenario_map["thermal_dominant"]
        assert td["metrics"]["mean_hpi"] == 51.06
        assert td["metrics"]["score_diff_mean"] == 8.92
        assert td["metrics"]["spearman_rho"] >= 0.98
        assert td["metrics"]["top_500_jaccard_pct"] >= 85.0

        # Persistence dominant
        pd = scenario_map["persistence_dominant"]
        assert pd["metrics"]["mean_hpi"] == 29.48
        assert pd["metrics"]["score_diff_mean"] == -12.65
        assert pd["metrics"]["spearman_rho"] >= 0.99
        assert pd["metrics"]["top_500_jaccard_pct"] >= 88.0

        # Nature deficit
        nd = scenario_map["nature_deficit"]
        assert nd["metrics"]["mean_hpi"] == 44.41
        assert nd["metrics"]["score_diff_mean"] == 2.27
        assert nd["metrics"]["spearman_rho"] >= 0.96

        # Equal weighting
        eq = scenario_map["equal_weighting"]
        assert eq["metrics"]["mean_hpi"] == 41.28
        assert abs(eq["metrics"]["score_diff_mean"]) < 1.0
        assert eq["metrics"]["spearman_rho"] >= 0.97

    def test_reports_exist_and_match(self) -> None:
        """Verify reports/hpi_sensitivity_analysis.json and .md exist on disk."""
        json_path = PROJECT_ROOT / "reports" / "hpi_sensitivity_analysis.json"
        md_path = PROJECT_ROOT / "reports" / "hpi_sensitivity_analysis.md"

        assert json_path.exists(), f"Missing {json_path}"
        assert md_path.exists(), f"Missing {md_path}"

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["baseline"]["total_cells"] == 49747
        assert "SENSITIVITY ANALYSIS IS NOT MODEL VALIDATION" in md_path.read_text(encoding="utf-8")


class TestHPISensitivityEndpoint:
    """Validate FastAPI endpoint /api/v1/heat-priority/sensitivity-analysis."""

    def test_get_sensitivity_analysis_success(self) -> None:
        """Endpoint must return 200 with proper schema, cache headers, and ETag."""
        client = TestClient(app)
        resp = client.get("/api/v1/heat-priority/sensitivity-analysis")
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["baseline"]["total_cells"] == 49747
        assert len(data["scenarios"]) == 4
        assert "scientific_caveats" in data
        assert "evidence_paths" in data

        # HTTP headers
        assert "ETag" in resp.headers
        assert "Cache-Control" in resp.headers
        assert "max-age=86400" in resp.headers["Cache-Control"]

    def test_missing_evidence_fallback(self) -> None:
        """If reports JSON is temporarily missing, endpoint dynamically recomputes."""
        client = TestClient(app)
        with patch.object(Path, "exists", return_value=False):
            resp = client.get("/api/v1/heat-priority/sensitivity-analysis")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "COMPLETED"
            assert data["baseline"]["total_cells"] == 49747

    def test_empty_database_error_handling(self) -> None:
        """When database returns zero rows, run_sensitivity_analysis raises ValueError."""
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        with pytest.raises(ValueError, match="No baseline HPI scores found"):
            run_sensitivity_analysis(db=mock_db)
