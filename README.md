# MRMS Radar CLI

Fetch rendered radar imagery from NOAA/NSSL MRMS — no browser, no S3, no GRIB2.

## Install

```bash
git clone <this-repo>
cd radar_app
pip install -e .
```

Requirements: Python 3.12+, requests, click (all pre-installed on this machine).

## Usage

```bash
# Latest reflectivity for Denver (default: M3DL13 at 4.0 km)
mrms fetch

# Specific product and location
mrms fetch --product BREF --lat 35.0 --lon -97.0 --zoom 5

# Historical data
mrms fetch --time 2026-01-15T08:30

# Custom output and size
mrms fetch --output ~/Desktop/storm.png --width 1200 --height 800
```

Output is saved as `radar_YYYYMMDD_HHMMSS.png` (or your chosen path). Repeated requests for the same product+time hit the disk cache — instant.

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--product`, `-p` | `M3DL13` | MRMS product code |
| `--lat` | `40.55` | Center latitude |
| `--lon` | `-104.68` | Center longitude |
| `--zoom`, `-z` | `7` | Leaflet zoom (3=continent, 7=state, 10=city) |
| `--width`, `-W` | `920` | Image width (px) |
| `--height`, `-H` | `630` | Image height (px) |
| `--time`, `-t` | now | ISO 8601 timestamp (rounded to 2-min MRMS window) |
| `--output`, `-o` | auto | Output file path |

## Products

~200 products across 20 categories. Common ones:

| Code | Description |
|------|-------------|
| `M3DL13` | 3D Reflectivity at 4.0 km (default) |
| `BREF` | Base Reflectivity |
| `CREF` | Composite Reflectivity |
| `SHSR` | Seamless Hybrid Scan Reflectivity |
| `RALA` | Reflectivity at Lowest Altitude |

See `PLAN.md` for the full product catalog.

## How it works

Fetches rendered PNGs from NOAA's MRMS Operational Product Viewer render endpoint
(`render_multi_domain_product_layer.php`). Images are cached locally in `cache/`
— repeated requests for the same product, location, and time are instant.

MRMS data is generated every 2 minutes. The CLI rounds timestamps down to the
nearest even minute to hit existing tiles (:00, :02, :04, ...).

## Architecture

```
mrms_core.py    ← shared library: fetch_radar(), cache, data model
mrms_cli.py     ← click CLI (thin wrapper around mrms_core)
```

Both the CLI and future web app import `mrms_core` — no code duplication.

## Tests

```bash
# All tests (unit + integration)
pytest tests/ -v

# Unit tests only (no network)
pytest tests/ -v -m "not integration"
```
