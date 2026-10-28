"""Unit and guardrail tests for experimental candidate retraining scripts.

Verifies:
- scripts/experimental/retrain_candidate.py imports cleanly and exhibits EXPERIMENTAL notice.
- Refuses to run without an explicit --output-dir argument (ValueError).
- Refuses to run if --output-dir is inside or targets artifacts/ml_freeze (PermissionError).
- Refuses to run if --output-dir is inside or targets data/ (PermissionError).
- Strictly asserts that the 33 locked test blocks are NEVER loaded or contaminated.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import pandas as pd

from scripts.experimental import retrain_candidate as rc

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_experimental_retrain_candidate_notice_and_header():
    """Verify that retrain_candidate exhibits the explicit EXPERIMENTAL header."""
    assert rc.EXPERIMENTAL_NOTICE == "EXPERIMENTAL - does not modify frozen artifacts"
    assert "EXPERIMENTAL" in rc.__doc__


def test_retrain_candidate_refuses_without_explicit_output_dir():
    """Verify that retrain_candidate raises ValueError when output_dir is None."""
    with pytest.raises(ValueError, match="CRITICAL GUARDRAIL VIOLATION: Experimental candidate retraining refuses to run without an explicit --output-dir"):
        rc.validate_output_directory(None, REPO_ROOT)

    with pytest.raises(ValueError):
        rc.retrain_candidate(output_dir=None)


def test_retrain_candidate_refuses_output_in_ml_freeze(tmp_path: Path):
    """Verify that retrain_candidate raises PermissionError when targeting artifacts/ml_freeze."""
    freeze_dir = REPO_ROOT / "artifacts" / "ml_freeze"
    with pytest.raises(PermissionError, match="CRITICAL GUARDRAIL VIOLATION.*artifacts/ml_freeze"):
        rc.validate_output_directory(freeze_dir, REPO_ROOT)

    sub_freeze = freeze_dir / "candidate_trial"
    with pytest.raises(PermissionError, match="CRITICAL GUARDRAIL VIOLATION.*artifacts/ml_freeze"):
        rc.validate_output_directory(sub_freeze, REPO_ROOT)


def test_retrain_candidate_refuses_output_in_data_directory():
    """Verify that retrain_candidate raises PermissionError when targeting data/."""
    data_dir = REPO_ROOT / "data"
    with pytest.raises(PermissionError, match="CRITICAL GUARDRAIL VIOLATION.*data/"):
        rc.validate_output_directory(data_dir, REPO_ROOT)

    sub_data = data_dir / "processed" / "candidate"
    with pytest.raises(PermissionError, match="CRITICAL GUARDRAIL VIOLATION.*data/"):
        rc.validate_output_directory(sub_data, REPO_ROOT)


def test_retrain_candidate_accepts_valid_external_output_dir(tmp_path: Path):
    """Verify that a directory outside artifacts/ml_freeze and data/ is permitted."""
    valid_out = tmp_path / "experimental_candidate_out"
    resolved = rc.validate_output_directory(valid_out, REPO_ROOT)
    assert resolved == valid_out.resolve()
    assert resolved.exists()


def test_assert_test_blocks_never_loaded_guard():
    """Verify that assert_test_blocks_never_loaded strictly catches test block contamination."""
    test_blocks = {f"test_blk_{i}" for i in range(33)}
    
    # 1. Clean dev-only dataframe passes
    df_clean = pd.DataFrame({"block_id": ["dev_blk_1", "dev_blk_2", "dev_blk_3"]})
    rc.assert_test_blocks_never_loaded(df_clean, test_blocks)

    # 2. Contaminated dataframe fails with AssertionError
    df_contaminated = pd.DataFrame({"block_id": ["dev_blk_1", "test_blk_5", "dev_blk_2"]})
    with pytest.raises(AssertionError, match="CRITICAL GUARDRAIL VIOLATION.*locked test blocks detected"):
        rc.assert_test_blocks_never_loaded(df_contaminated, test_blocks)
