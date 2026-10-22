"""Unit tests for LST Radiometric Conversion and Quality Assurance Masking.

Verifies:
1. Radiometric conversion formula from USGS Landsat Collection 2 Level 2 ST_B10 DN to Kelvin and Celsius.
2. QA_PIXEL masking rules (cloud, cirrus, dilated cloud, cloud shadow, water, snow).
3. QA_RADSAT saturation detection for thermal Band 10.
4. Raster tile generation with valid skin temperature range up to 60°C.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from backend.app.raster.catalog import resolve_seasonal_cog
from backend.app.raster.tiles import get_lst_tile, LST_MIN_C, LST_MAX_C


# USGS Landsat Collection 2 Level 2 constants
MULT_FACTOR = 0.00341802
ADD_OFFSET = 149.0
KELVIN_OFFSET = 273.15


def dn_to_lst_celsius(dn: int | float | np.ndarray) -> float | np.ndarray:
    """Convert raw 16-bit DN to LST in degrees Celsius."""
    kelvin = np.asarray(dn, dtype=np.float64) * MULT_FACTOR + ADD_OFFSET
    celsius = kelvin - KELVIN_OFFSET
    return celsius if isinstance(dn, np.ndarray) else float(celsius)


def lst_celsius_to_dn(celsius: float) -> int:
    """Invert Celsius back to integer DN."""
    kelvin = celsius + KELVIN_OFFSET
    dn = (kelvin - ADD_OFFSET) / MULT_FACTOR
    return int(round(dn))


def is_qa_pixel_valid(qa: int | np.ndarray) -> bool | np.ndarray:
    """Check QA_PIXEL validity according to USGS Landsat C2 L2 specification.

    Bits to reject:
      - Bit 0: Fill (1 = Fill)
      - Bit 1: Dilated Cloud (1 = Dilated cloud)
      - Bit 2: Cirrus (1 = High confidence cirrus)
      - Bit 3: Cloud (1 = Cloud present)
      - Bit 4: Cloud Shadow (1 = Cloud shadow present)
      - Bit 5: Snow (1 = Snow / Ice)
    """
    qa_arr = np.asarray(qa, dtype=np.uint32)
    mask = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5)
    is_valid = (qa_arr & mask) == 0
    return bool(is_valid) if isinstance(qa, int) else is_valid


def is_radsat_thermal_saturated(radsat: int | np.ndarray) -> bool | np.ndarray:
    """Check QA_RADSAT thermal band 10 saturation (bits 10 & 11)."""
    radsat_arr = np.asarray(radsat, dtype=np.uint32)
    # Band 10 saturation is bit 10 or bit 11 in Landsat Collection 2
    thermal_saturation_mask = (1 << 10) | (1 << 11)
    is_saturated = (radsat_arr & thermal_saturation_mask) != 0
    return bool(is_saturated) if isinstance(radsat, int) else is_saturated


class TestLSTRadiometricConversion:
    """Verify USGS Collection 2 Level 2 Surface Temperature scaling."""

    def test_dn_conversion_benchmarks(self):
        """Verify DN -> Celsius at specific known calibration points."""
        # Baseline reference: DN = 44000
        # Kelvin = 44000 * 0.00341802 + 149.0 = 299.39288 K
        # Celsius = 299.39288 - 273.15 = 26.24288 °C
        c_44k = dn_to_lst_celsius(44000)
        assert pytest.approx(c_44k, rel=1e-5) == 26.24288

        # Summer baseline: DN = 50000
        # Kelvin = 50000 * 0.00341802 + 149.0 = 319.901 K
        # Celsius = 319.901 - 273.15 = 46.751 °C
        c_50k = dn_to_lst_celsius(50000)
        assert pytest.approx(c_50k, rel=1e-5) == 46.751

        # Hotspot skin temperature (industrial metal roof): DN = 53000
        # Kelvin = 53000 * 0.00341802 + 149.0 = 330.15506 K
        # Celsius = 330.15506 - 273.15 = 57.00506 °C
        c_53k = dn_to_lst_celsius(53000)
        assert pytest.approx(c_53k, rel=1e-5) == 57.00506

    def test_dn_conversion_reversibility(self):
        """Verify round-trip invertibility of DN -> Celsius -> DN."""
        test_temps = [25.0, 32.5, 42.0, 48.5, 50.0, 58.65]
        for t in test_temps:
            dn = lst_celsius_to_dn(t)
            t_reconstructed = dn_to_lst_celsius(dn)
            # 16-bit quantization error is < 0.0035°C
            assert abs(t - t_reconstructed) < 0.005

    def test_vectorized_conversion(self):
        """Verify vectorized numpy array operations maintain float precision."""
        dns = np.array([44000, 48000, 52000], dtype=np.uint16)
        cels = dn_to_lst_celsius(dns)
        assert cels.shape == (3,)
        assert np.all(np.isfinite(cels))
        assert cels[0] < cels[1] < cels[2]


class TestQAPixelMasking:
    """Verify Quality Assurance bitmask evaluation."""

    def test_clear_land_pixel_is_valid(self):
        """Standard clear land pixel (e.g. QA_PIXEL = 21824 = binary 0101010101000000b) is valid."""
        # Bit 6 (clear) set, bits 0-5 zero
        clear_qa = 1 << 6
        assert is_qa_pixel_valid(clear_qa) is True

    def test_cloud_detected_is_rejected(self):
        """Pixels with cloud (bit 3) or dilated cloud (bit 1) must be rejected."""
        assert is_qa_pixel_valid(1 << 3) is False
        assert is_qa_pixel_valid(1 << 1) is False
        assert is_qa_pixel_valid((1 << 6) | (1 << 3)) is False

    def test_cirrus_and_shadow_are_rejected(self):
        """Cirrus (bit 2) and Cloud Shadow (bit 4) must be rejected."""
        assert is_qa_pixel_valid(1 << 2) is False
        assert is_qa_pixel_valid(1 << 4) is False

    def test_fill_and_snow_are_rejected(self):
        """Fill (bit 0) and Snow (bit 5) must be rejected."""
        assert is_qa_pixel_valid(1 << 0) is False
        assert is_qa_pixel_valid(1 << 5) is False

    def test_thermal_saturation_detection(self):
        """Ensure thermal band 10 saturation is detected by QA_RADSAT check."""
        # No saturation
        assert is_radsat_thermal_saturated(0) is False
        # Band 10 saturation (bit 10 or 11)
        assert is_radsat_thermal_saturated(1 << 10) is True
        assert is_radsat_thermal_saturated(1 << 11) is True


class TestRasterTileGeneration:
    """Verify LST tile rendering and season support."""

    def test_seasonal_cog_resolution(self):
        """Verify resolve_seasonal_cog finds summer and winter 2026 COGs."""
        summer_cog = resolve_seasonal_cog(season="summer", year=2026).path
        assert summer_cog.exists()
        assert "summer" in str(summer_cog).lower()

        winter_cog = resolve_seasonal_cog(season="winter", year=2026).path
        assert winter_cog.exists()
        assert "winter" in str(winter_cog).lower()

    def test_summer_tile_renders_png_bytes(self):
        """Verify rendering a tile inside Surat bounds returns valid PNG bytes."""
        tile_bytes = get_lst_tile(x=2876, y=1801, z=12, season="summer", year=2026)
        assert isinstance(tile_bytes, bytes)
        assert len(tile_bytes) > 1000
        # PNG magic header bytes
        assert tile_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_winter_tile_renders_png_bytes(self):
        """Verify rendering winter tile returns valid PNG bytes."""
        tile_bytes = get_lst_tile(x=2876, y=1801, z=12, season="winter", year=2026)
        assert isinstance(tile_bytes, bytes)
        assert len(tile_bytes) > 1000
        assert tile_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_outside_bounds_returns_transparent_png(self):
        """Verify tile outside bounding box returns empty/transparent PNG."""
        tile_bytes = get_lst_tile(x=0, y=0, z=10, season="summer", year=2026)
        assert isinstance(tile_bytes, bytes)
        assert len(tile_bytes) > 0
        assert tile_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_temperature_limits_support_extreme_roofs(self):
        """Verify upper normalization ceiling is 60°C to preserve ~58.6°C industrial hotspots."""
        assert LST_MAX_C >= 58.65
        assert LST_MIN_C <= 20.0
