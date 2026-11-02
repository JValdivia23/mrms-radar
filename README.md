# MRMS Radar

A browser radar viewer with live imagery, playback, and archived observations,
plus the original Python CLI and web server.

## Latest standalone version — start here

**[standalone/noaa_wms/index.html](standalone/noaa_wms/index.html) is the latest
standalone version.** It includes the compact controls, red location dot,
three-hour history slider, and UTC date/time picker for earlier days.

It is a single HTML file with Leaflet and the default basemap embedded. No
Python server, Google authorization, proxy, API key, or build step is required.
Live base/composite reflectivity comes directly from NOAA WMS; older scans come
from NOAA's public archive and are decoded in the browser. Coverage is the
contiguous United States.

1. **[Download the latest HTML](https://raw.githubusercontent.com/JValdivia23/mrms-radar/main/standalone/noaa_wms/index.html)**
   and save it as `index.html` (use Save link as if the browser displays its source).
2. Open the saved file in a modern browser. Internet access is needed for radar
   observations and legends; the default basemap is embedded.
3. To put it on a personal website, upload that same HTML file to static hosting.
   HTTPS allows browser location access when permission is granted.

See the **[standalone guide](standalone/noaa_wms/README.md)** for controls,
archive decoding, browser requirements, and validation details. The older
experiments and Python tools below remain available for their broader product
catalog and alternative workflows.

---

## Original CLI and web app features

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
git clone https://github.com/JValdivia23/mrms-radar.git
cd mrms-radar
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

## Standalone versions

| Version | Status and purpose |
| --- | --- |
| **[noaa_wms](standalone/noaa_wms/README.md)** | **Latest standalone version.** One self-contained HTML file; direct NOAA access, compact controls, three-hour history, and past-date selection. |
| [pure_js](standalone/pure_js/README.md) | Earlier Google Apps Script proxy experiment, retaining the broader MRMS product catalog. Requires a configured, authorized proxy. |
| [wasm_console](standalone/wasm_console/index.html) | Earlier WebAssembly console experiment. |
| [static](static/index.html) | Original frontend used by the Python web server. |

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
