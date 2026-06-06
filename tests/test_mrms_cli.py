"""Tests for mrms_cli.py."""
import os
import tempfile
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from mrms_cli import cli


# ============================================================================
# Help
# ============================================================================


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "MRMS" in result.output


def test_fetch_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["fetch", "--help"])
    assert result.exit_code == 0
    assert "--product" in result.output
    assert "--lat" in result.output
    assert "--time" in result.output


# ============================================================================
# Default fetch
# ============================================================================


def test_fetch_defaults():
    """mrms fetch without flags uses defaults and saves a PNG."""
    mock_response = MagicMock()
    mock_response.content = b"test_png"

    with tempfile.TemporaryDirectory() as tmpdir:
        cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            with patch("mrms_core.CACHE_DIR", tmpdir):
                with patch("mrms_core.requests.get", return_value=mock_response):
                    with patch("mrms_core._cache_load", return_value=None):
                        runner = CliRunner()
                        result = runner.invoke(cli, ["fetch"])
                        assert result.exit_code == 0

            # Should have created a PNG file in cwd
            pngs = [f for f in os.listdir(tmpdir) if f.startswith("radar_")]
            assert len(pngs) == 1
            assert pngs[0].startswith("radar_")

            # File should have content
            with open(os.path.join(tmpdir, pngs[0]), "rb") as f:
                assert f.read() == b"test_png"

            assert "Saved" in result.output
        finally:
            os.chdir(cwd)


# ============================================================================
# Flag passthrough
# ============================================================================


def test_fetch_with_product_and_location():
    """--product, --lat, --lon, --zoom are passed to fetch_radar."""
    mock_response = MagicMock()
    mock_response.content = b"custom_png"

    with tempfile.TemporaryDirectory() as tmpdir:
        outpath = os.path.join(tmpdir, "my_radar.png")
        with patch("mrms_core.CACHE_DIR", tmpdir):
            with patch("mrms_core.requests.get", return_value=mock_response):
                with patch("mrms_core._cache_load", return_value=None):
                    runner = CliRunner()
                    result = runner.invoke(cli, [
                        "fetch",
                        "--product", "BREF",
                        "--lat", "35.0",
                        "--lon", "-97.0",
                        "--zoom", "5",
                        "--output", outpath,
                    ])
                    assert result.exit_code == 0
                    assert os.path.exists(outpath)
                    assert "my_radar.png" in result.output


def test_fetch_with_size_flags():
    """--width and --height pass through correctly."""
    mock_response = MagicMock()
    mock_response.content = b"big_png"

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mrms_core.CACHE_DIR", tmpdir):
            with patch("mrms_core.requests.get", return_value=mock_response) as mock_get:
                with patch("mrms_core._cache_load", return_value=None):
                    runner = CliRunner()
                    result = runner.invoke(cli, [
                        "fetch", "--width", "1200", "--height", "800",
                    ])
                    assert result.exit_code == 0

                    params = mock_get.call_args[1]["params"]
                    assert params["width"] == 1200
                    assert params["height"] == 800


# ============================================================================
# --time flag
# ============================================================================


def test_fetch_with_time_flag():
    """--time ISO 8601 is parsed and passed to fetch_radar."""
    mock_response = MagicMock()
    mock_response.content = b"historical_png"

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mrms_core.CACHE_DIR", tmpdir):
            with patch("mrms_core.requests.get", return_value=mock_response) as mock_get:
                with patch("mrms_core._cache_load", return_value=None):
                    runner = CliRunner()
                    result = runner.invoke(cli, [
                        "fetch",
                        "--time", "2026-01-15T08:31",
                    ])
                    assert result.exit_code == 0

                    params = mock_get.call_args[1]["params"]
                    assert params["year"] == 2026
                    assert params["month"] == 1
                    assert params["day"] == 15
                    assert params["hour"] == 8
                    assert params["minute"] == 30  # rounded down


def test_fetch_with_exact_time():
    """--time at exact MRMS window is not shifted."""
    mock_response = MagicMock()
    mock_response.content = b"data"

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mrms_core.CACHE_DIR", tmpdir):
            with patch("mrms_core.requests.get", return_value=mock_response) as mock_get:
                with patch("mrms_core._cache_load", return_value=None):
                    runner = CliRunner()
                    result = runner.invoke(cli, [
                        "fetch", "--time", "2026-06-06T16:30",
                    ])
                    assert result.exit_code == 0
                    params = mock_get.call_args[1]["params"]
                    assert params["minute"] == 30


# ============================================================================
# Cache display
# ============================================================================


def test_fetch_shows_cached_when_from_cache():
    """Output includes '(cached)' when image comes from cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mrms_core.CACHE_DIR", tmpdir):
            with patch("mrms_core.requests.get") as mock_get:
                mock_get.return_value = MagicMock()
                mock_get.return_value.content = b"data"

                # First call — not cached
                with patch("mrms_core._cache_load", return_value=None):
                    runner = CliRunner()
                    result = runner.invoke(cli, ["fetch", "--time", "2026-01-15T08:30"])
                    assert "(cached)" not in result.output

                # Second call — cached
                with patch("mrms_core._cache_load", return_value=b"data"):
                    result = runner.invoke(cli, ["fetch", "--time", "2026-01-15T08:30"])
                    assert "(cached)" in result.output


# ============================================================================
# Error handling
# ============================================================================


def test_fetch_invalid_time():
    """Invalid --time format produces a friendly error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["fetch", "--time", "not-a-date"])
    assert result.exit_code != 0
