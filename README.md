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
| `--time`, `-t` | now | ISO 8601 timestamp (rounded to product-specific resolution, e.g. 2, 5, or 60 min) |
| `--output`, `-o` | auto | Output file path |

~200 products across 20 categories. You can query all available categories and product codes directly using the CLI:

```bash
# List all 20 categories
mrms products

# List all specific product codes under a category (e.g. brefls or level)
mrms products --category brefls
```

The catalog metadata is loaded dynamically from [mrms_products.json](file:///Users/java1127/onedrive/Projects/radar_app/mrms_products.json). Common ones include:

| Code | Description | Time Cycle |
|------|-------------|------------|
| `M3DL13` | 3D Reflectivity at 4.0 km (default) | 2 min |
| `BREF` | Base Reflectivity (Alias for `BASE_REFL`) | 2 min |
| `CREF` | Composite Reflectivity | 2 min |
| `SHSR` | Seamless Hybrid Scan Reflectivity | 2 min |
| `RALA` | Reflectivity at Lowest Altitude | 2 min |
| `MZDRL13` | ZDR 3D Mosaic at 4.0 km | 5 min |
| `MRHOL13` | RhoHV 3D Mosaic at 4.0 km | 5 min |

## How it works

Fetches rendered PNGs from NOAA's MRMS Operational Product Viewer render endpoint
(`render_multi_domain_product_layer.php`). Images are cached locally in `cache/`
— repeated requests for the same product, location, and time are instant.

Product cycles vary (e.g. 2, 5, or 60 minutes). The CLI queries [mrms_products.json](file:///Users/java1127/onedrive/Projects/radar_app/mrms_products.json) to dynamically round the requested time to the correct resolution boundary for that specific product.

### Geographic Bounds Extraction
Because the NOAA renderer operates in standard Web Mercator (`EPSG:3857`), the exact coordinate limits (min/max latitude and longitude bounds) of any fetched figure can be computed programmatically.

The core library exposes a spatial utility function for this. You can call `.get_bounds()` on any fetched `RadarImage` to retrieve its geographic bounding box:

```python
from mrms_core import fetch_radar

# Fetch default Denver image (zoom level 7, 920x630 pixels)
img = fetch_radar()

# Retrieve limits: (min_lat, max_lat, min_lon, max_lon)
min_lat, max_lat, min_lon, max_lon = img.get_bounds()
print(f"Latitude bounds : {min_lat:.5f}° to {max_lat:.5f}°")
print(f"Longitude bounds: {min_lon:.5f}° to {max_lon:.5f}°")
```

## Architecture

```
mrms_products.json ← centralized product categories and resolution database
mrms_core.py       ← shared library: loads catalog, fetch_radar(), cache, data model
mrms_cli.py        ← click CLI (thin wrapper around mrms_core, validation & listing)
server.py          ← FastAPI web server + dynamically populated JSON API
static/            ← Leaflet PWA frontend (index.html, responsive layout, loop player)
```

All components load and resolve products dynamically using the catalog registry in `mrms_core.py` to prevent duplicate structures.

## Tests

```bash
# All tests (unit + integration)
pytest tests/ -v

# Unit tests only (no network)
pytest tests/ -v -m "not integration"
```
