"""Tests for mrms_core.py."""
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mrms_core import (
    RadarImage,
    fetch_radar,
    round_to_mrms_window,
    _cache_key,
    _cache_load,
    _cache_save,
    CACHE_DIR,
)


# ============================================================================
# RadarImage dataclass
# ============================================================================


def test_radar_image_creation():
    img = RadarImage(
        png_bytes=b"fake_png",
        product="M3DL13",
        product_name="3D Reflectivity at 4.0 km",
        lat=40.55,
        lon=-104.68,
        zoom=7,
        timestamp="2026-06-06T16:30:00",
        fetch_time="2026-06-06T16:30:05",
        source_url="https://...",
        width=920,
        height=630,
        from_cache=False,
    )
    assert img.product == "M3DL13"
    assert img.width == 920
    assert img.from_cache is False
    assert img.png_bytes == b"fake_png"
    assert img.product_name == "3D Reflectivity at 4.0 km"


def test_radar_image_defaults():
    img = RadarImage(
        png_bytes=b"x",
        product="BREF",
        lat=0.0,
        lon=0.0,
    )
    assert img.product_name == ""
    assert img.zoom == 7
    assert img.width == 920
    assert img.height == 630
    assert img.from_cache is False
    assert img.source_url == ""
    assert img.timestamp == ""
    assert img.fetch_time == ""


# ============================================================================
# Time rounding
# ============================================================================


def test_round_to_mrms_window_exact():
    dt = datetime(2026, 6, 6, 16, 30, 0, tzinfo=timezone.utc)
    result = round_to_mrms_window(dt)
    assert result == datetime(2026, 6, 6, 16, 30, 0, tzinfo=timezone.utc)


def test_round_to_mrms_window_odd_minute():
    dt = datetime(2026, 6, 6, 16, 31, 0, tzinfo=timezone.utc)
    result = round_to_mrms_window(dt)
    assert result == datetime(2026, 6, 6, 16, 30, 0, tzinfo=timezone.utc)


def test_round_to_mrms_window_odd_second():
    dt = datetime(2026, 6, 6, 16, 33, 45, tzinfo=timezone.utc)
    result = round_to_mrms_window(dt)
    assert result == datetime(2026, 6, 6, 16, 32, 0, tzinfo=timezone.utc)


def test_round_to_mrms_window_hour_boundary():
    dt = datetime(2026, 6, 6, 17, 1, 0, tzinfo=timezone.utc)
    result = round_to_mrms_window(dt)
    assert result == datetime(2026, 6, 6, 17, 0, 0, tzinfo=timezone.utc)


def test_round_to_mrms_window_midnight():
    dt = datetime(2026, 6, 7, 0, 1, 30, tzinfo=timezone.utc)
    result = round_to_mrms_window(dt)
    assert result == datetime(2026, 6, 7, 0, 0, 0, tzinfo=timezone.utc)


# ============================================================================
# Spatial utilities
# ============================================================================


def test_get_mercator_bounds_zoom0():
    """Verify that at zoom 0, a 256x256 image centered at (0, 0) covers the whole Earth projection bounds."""
    from mrms_core import get_mercator_bounds
    min_lat, max_lat, min_lon, max_lon = get_mercator_bounds(0, 0, 0, 256, 256)
    
    assert abs(min_lon - (-180.0)) < 1e-7
    assert abs(max_lon - 180.0) < 1e-7
    assert abs(min_lat - (-85.05112878)) < 1e-6
    assert abs(max_lat - 85.05112878) < 1e-6


def test_radar_image_get_bounds():
    """RadarImage get_bounds method successfully forwards to get_mercator_bounds."""
    img = RadarImage(
        png_bytes=b"png",
        product="M3DL13",
        lat=40.55,
        lon=-104.68,
        zoom=7,
        width=920,
        height=630,
    )
    min_lat, max_lat, min_lon, max_lon = img.get_bounds()
    assert 37.86 < min_lat < 37.87
    assert 43.12 < max_lat < 43.13
    assert -109.74 < min_lon < -109.73
    assert -99.63 < max_lon < -99.62


# ============================================================================
# Cache utilities
# ============================================================================


def test_cache_key_format():
    key = _cache_key(
        product="M3DL13",
        year=2026, month=6, day=6, hour=16, minute=30,
        lat=40.55, lon=-104.68, zoom=7, width=920, height=630,
    )
    assert key == "M3DL13_20260606_1630_40.55_-104.68_7_920x630.png"


def test_cache_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mrms_core.CACHE_DIR", tmpdir):
            key = "test_product_20260606_1200_35.0_-97.0_5_920x630.png"
            _cache_save(key, b"cached_png_bytes")
            result = _cache_load(key)
            assert result == b"cached_png_bytes"


def test_cache_load_miss():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mrms_core.CACHE_DIR", tmpdir):
            result = _cache_load("nonexistent_key.png")
            assert result is None


# ============================================================================
# fetch_radar
# ============================================================================


def test_fetch_radar_builds_correct_url():
    """fetch_radar constructs the URL and headers correctly without network."""
    mock_response = MagicMock()
    mock_response.content = b"fake_png_data" + b"x" * 4000

    with patch("mrms_core.requests.get", return_value=mock_response) as mock_get:
        with patch("mrms_core._cache_load", return_value=None):  # bypass cache
            fetch_radar(
                product="M3DL13",
                lat=40.55,
                lon=-104.68,
                zoom=7,
                year=2026, month=6, day=6, hour=16, minute=30,
            )

    call_args = mock_get.call_args
    assert call_args[0][0] == (
        "https://mrms.nssl.noaa.gov/qvs/product_viewer/local/"
        "render_multi_domain_product_layer.php"
    )

    params = call_args[1]["params"]
    assert params["prod_root"] == "M3DL13"
    assert params["clat"] == 40.55
    assert params["clon"] == -104.68
    assert params["zoom"] == 7
    assert params["mode"] == "run"
    assert params["year"] == 2026
    assert params["month"] == 6
    assert params["day"] == 6
    assert params["hour"] == 16
    assert params["minute"] == 30

    headers = call_args[1]["headers"]
    assert "User-Agent" in headers
    assert "Referer" in headers
    assert "mrms.nssl.noaa.gov" in headers["Referer"]


def test_fetch_radar_returns_radar_image():
    """fetch_radar returns a RadarImage with correct metadata."""
    mock_response = MagicMock()
    mock_response.content = b"radar_png_bytes" + b"x" * 4000

    with patch("mrms_core.requests.get", return_value=mock_response):
        with patch("mrms_core._cache_load", return_value=None):
            result = fetch_radar(
                product="BREF",
                lat=35.0,
                lon=-97.0,
                zoom=5,
                year=2026, month=6, day=6, hour=12, minute=0,
            )

    assert isinstance(result, RadarImage)
    assert result.png_bytes == b"radar_png_bytes" + b"x" * 4000
    assert result.product == "BREF"
    assert result.lat == 35.0
    assert result.lon == -97.0
    assert result.zoom == 5
    assert result.from_cache is False
    assert result.width == 920
    assert result.height == 630


def test_fetch_radar_defaults():
    """fetch_radar with only required params uses sensible defaults."""
    mock_response = MagicMock()
    mock_response.content = b"data" + b"x" * 4000

    with patch("mrms_core.requests.get", return_value=mock_response) as mock_get:
        with patch("mrms_core._cache_load", return_value=None):
            fetch_radar(product="M3DL13", lat=40.55, lon=-104.68,
                        year=2026, month=6, day=6, hour=12, minute=0)

    params = mock_get.call_args[1]["params"]
    assert params["width"] == 920
    assert params["height"] == 630
    assert params["zoom"] == 7


def test_fetch_radar_uses_cache():
    """fetch_radar returns cached image when available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mrms_core.CACHE_DIR", tmpdir):
            # First call — no cache, should hit network
            mock_response = MagicMock()
            mock_response.content = b"fresh_data" + b"x" * 4000

            with patch("mrms_core.requests.get", return_value=mock_response) as mock_get:
                result1 = fetch_radar(
                    product="BREF", lat=35.0, lon=-97.0,
                    year=2026, month=6, day=6, hour=12, minute=0,
                )
                assert result1.from_cache is False
                assert mock_get.call_count == 1

                # Second call — should hit cache, no network call
                result2 = fetch_radar(
                    product="BREF", lat=35.0, lon=-97.0,
                    year=2026, month=6, day=6, hour=12, minute=0,
                )
                assert result2.from_cache is True
                assert result2.png_bytes == b"fresh_data" + b"x" * 4000
                assert mock_get.call_count == 1  # still 1, no extra call


# ============================================================================
# Integration test
# ============================================================================


@pytest.mark.integration
def test_real_noaa_fetch():
    """Real end-to-end fetch from NOAA MRMS. Skipped if unreachable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mrms_core.CACHE_DIR", tmpdir):
            try:
                img = fetch_radar(product="M3DL13", lat=40.55, lon=-104.68, zoom=7)
            except Exception as e:
                pytest.skip(f"NOAA MRMS unreachable: {e}")

            assert len(img.png_bytes) > 100, "PNG too small — likely an error page"
            assert img.png_bytes[:4] == b"\x89PNG", "Not a valid PNG"
            assert img.product == "M3DL13"
            assert img.width == 920
            assert img.height == 630
            assert img.from_cache is False  # fresh fetch with clean cache
