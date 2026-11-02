# MRMS Radar — CLI, Web Server, & Standalone PWA

MRMS Radar is a powerful command-line interface (CLI) and responsive Windy-style web application designed to fetch and render raw radar imagery directly from the NOAA/NSSL Multi-Radar Multi-Sensor (MRMS) Operational Product Viewer. 

There are no heavy GRIB2 parsers or AWS S3 requirements—just direct, cached, geo-aligned HTTP rendering.

---

## Key Features

*   **Python CLI**: Fetch, cache, and save radar images for any location, zoom level, and product directly from your terminal.
*   **FastAPI Web Server**: Serves a dynamic JSON API mapping geographic timezones and proxying NOAA rendering endpoints.
*   **Interactive Leaflet Map (PWA)**:
    *   **Windy-Style Interface**: Floating translucent control panels, colorbar legends, and basemap selectors (Dark, Satellite, OpenStreetMap).
    *   **Smooth Navigation**: Pinch-to-zoom, click-and-drag panning, and mousewheel zoom.
    *   **Persistent Settings**: Saves zoom level, position, basemap choice, and last selected product to browser local storage.
*   **Animation Loop Player**:
    *   Preloads and caches 18 frames of history.
    *   Features smart resolution alignment (automatically meshes 2-min and 4-min slots depending on product to guarantee zero-latency playback without requesting future blank images).
*   **Pyodide WebAssembly Console**:
    *   Includes a client-side command-line shell running inside the browser.
    *   Mounts the core python scripts (`mrms_core.py`, `mrms_cli.py`) in a virtual filesystem.
    *   Executing `mrms fetch` inside the in-browser terminal immediately updates the interactive Leaflet map!
*   **Standalone Serverless Mode**:
    *   The compiled `static/index.html` runs entirely serverless (via `file://` or static CDNs like GitHub Pages) by dynamically probing the backend and falling back to a CORS proxy.

---

## Architecture

```
mrms_products.json ← Centralized product configuration database (resolution, levels, categories)
mrms_core.py       ← Core library: fetch_radar(), get_mercator_bounds(), and disk cache
mrms_cli.py        ← Click command-line wrapper around mrms_core
server.py          ← FastAPI backend (API endpoints, timezone solver, static index.html router)
static/
  ├── index.html   ← Standalone web application with embedded console & fetch interceptor
  ├── sw.js        ← Service worker (caches app shell and recent radar frames)
  └── manifest.json← PWA configuration for mobile installation
```

---

## Installation

### Prerequisites
*   Python 3.11+
*   Conda (optional, but recommended)

### Setup
Clone the repository and install core dependencies:
```bash
git clone <this-repo>
cd radar_app
pip install -r requirements.txt
```

To run the FastAPI server, you can activate the provided conda environment (if available) or install server dependencies:
```bash
pip install fastapi uvicorn watchfiles
```

---

## Command Line Usage

### Basic Fetch
Save the latest reflectivity for Denver (default: M3DL13 at 4.0 km) to your current directory:
```bash
python mrms_cli.py fetch
```

### Specific Location and Product
Fetch Base Reflectivity (`BREF`) at zoom level 5 centered on Oklahoma:
```bash
python mrms_cli.py fetch --product BREF --lat 35.0 --lon -97.0 --zoom 5
```

### Querying the Catalog
You can browse all categories and product codes directly using the CLI:
```bash
# List all categories
python mrms_cli.py products

# List all products under a specific category
python mrms_cli.py products --category brefls
```

---

## Web Server Usage

Start the FastAPI web server locally:
```bash
python server.py
```
Open **`http://127.0.0.1:8000`** in your browser to view the interactive map and console.

### Key API Endpoints
*   `/api/products` — Returns the full category structure and product attributes.
*   `/api/radar` — Fetches a rendered PNG from NOAA or cache. Accepts `?lat=`, `?lon=`, `?zoom=`, `?product=`, and optional `?time=`.
*   `/api/timezone` — Geographically maps coordinates to an IANA timezone and local offset.
*   `/api/legend` — Returns the SVG colorbar configuration proxy for the selected product.

---

## Standalone HTML experiment

The new [direct NOAA WMS experiment](standalone/noaa_wms/README.md) runs from a
single [HTML file](standalone/noaa_wms/index.html), with its map assets embedded.
It retrieves base/composite reflectivity PNGs and real scan timestamps directly
from NOAA, without Google authorization or a proxy. It includes historical
scrubbing, animation, image caching, and compact playback controls. This
experiment covers the contiguous U.S.; the broader product catalog remains in `pure_js`.
Its three-hour slider shows elapsed time, and the menu's UTC date/time picker
opens earlier days using NOAA's public archive. Older images are decoded in a
background worker, preserving the fast WMS path for recent observations.

The Google-proxy experiment is [standalone/pure_js/index.html](standalone/pure_js/index.html).
Open it directly with `file://`; no local Python server is required. The
`standalone/` directory also contains a WebAssembly console experiment in
`wasm_console/`.

**Google-proxy setup dependency: authorization.** In `pure_js` standalone mode, radar
images and legends go through the Google Apps Script web app configured by
`GOOGLE_SCRIPT_PROXY` in the HTML. Its owner must sign in to Google and authorize
outbound requests. The intended deployment runs as the owner and allows anonymous
access; a deployment requiring viewer sign-in cannot complete that sign-in through
the page's background requests. See the [proxy setup and troubleshooting guide](standalone/pure_js/README.md#google-authorization-and-credentials)
and Google's [web app permissions documentation](https://developers.google.com/apps-script/guides/web#permissions).

The `pure_js` build still loads
`natural-earth.js` and `natural-earth-data.js` from beside the HTML and Leaflet
from a CDN. The default Natural Earth basemap needs no API key; live radar still
requires the proxy and an internet connection.

---

## Spatial Utilities & Bounds

Because the NOAA renderer processes coordinates in standard Web Mercator (`EPSG:3857`), the exact geographic bounding box for any rendered image can be computed. You can call `.get_bounds()` on any `RadarImage` dataclass:

```python
from mrms_core import fetch_radar

# Fetch Denver radar image
img = fetch_radar()

# Retrieve bounding box boundaries
min_lat, max_lat, min_lon, max_lon = img.get_bounds()
print(f"Viewport limits: {min_lat:.4f}° to {max_lat:.4f}° Latitude")
```

---

## Caching and Performance

*   **Local Disk Caching**: Images are stored in the local `cache/` directory. If you query the same parameters (product, time, coordinates, dimensions, zoom), the server returns the cached file instantly.
*   **PWA Cache**: The Service Worker (`sw.js`) caches the application shell (Network-First strategy) and radar images, enabling offline performance and fast load times.

---

## Development & Testing

All unit and integration tests are located in `tests/`.

```bash
# Run all tests
python -m pytest tests/ -v

# Run unit tests only (no network requests)
python -m pytest tests/ -v -m "not integration"
```
