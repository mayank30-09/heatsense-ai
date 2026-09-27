"""Unit tests for analyze_lst_extremes.py module."""

import subprocess
import sys
import numpy as np
import pytest

from scripts.analyze_lst_extremes import build_arg_parser, compute_neighborhood_stats


def test_cli_help():
    """Verify that python scripts/analyze_lst_extremes.py --help exits with code 0 without executing."""
    result = subprocess.run(
        [sys.executable, "scripts/analyze_lst_extremes.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower() or "options:" in result.stdout.lower()
    assert "--top-percentile" in result.stdout
    assert "--bottom-percentile" in result.stdout


def test_cli_argument_parsing():
    """Verify CLI parser options."""
    parser = build_arg_parser()
    args = parser.parse_args(["--year", "2023", "--season", "monsoon", "--top-percentile", "1.5", "--skip-gee"])
    assert args.year == 2023
    assert args.season == "monsoon"
    assert args.top_percentile == 1.5
    assert args.skip_gee is True


def test_compute_neighborhood_stats():
    """Verify 3x3 neighborhood calculation excluding center pixel and handling NoData."""
    # Create a 5x5 grid with known values
    # Center pixel at (2, 2) has value 100.0
    # Neighbors: 8 values around it all equal to 20.0
    grid = np.full((5, 5), -9999.0, dtype=np.float32)
    grid[1:4, 1:4] = 20.0
    grid[2, 2] = 100.0  # Center

    stats = compute_neighborhood_stats(grid, row=2, col=2)
    assert stats["valid_neighbor_count"] == 8
    assert np.isclose(stats["neighborhood_median"], 20.0)
    assert np.isclose(stats["neighborhood_mean"], 20.0)
    assert np.isclose(stats["neighborhood_std"], 0.0)
    assert np.isclose(stats["pixel_minus_neighborhood_median"], 80.0)
    assert np.isclose(stats["absolute_pixel_minus_neighborhood_median"], 80.0)


def test_compute_neighborhood_stats_edge():
    """Verify edge handling where some neighbors are outside the raster bounds."""
    grid = np.full((3, 3), 10.0, dtype=np.float32)
    grid[0, 0] = 50.0  # Corner pixel

    stats = compute_neighborhood_stats(grid, row=0, col=0)
    # A corner pixel in 3x3 only has 3 neighbors: (0,1), (1,0), (1,1)
    assert stats["valid_neighbor_count"] == 3
    assert np.isclose(stats["neighborhood_median"], 10.0)
    assert np.isclose(stats["pixel_minus_neighborhood_median"], 40.0)
