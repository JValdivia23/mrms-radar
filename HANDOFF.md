# HANDOFF.md — MRMS Radar CLI + Web App

**Date:** 2026-06-09
**Status:** Phase 1, 6 complete. Basemap integration done. Phase 3 (animation), 7 (PWA) partial.

## What this project is

A CLI + web app that fetches rendered radar imagery from NOAA/NSSL MRMS
Operational Product Viewer. No S3, no GRIB2 parsing — just HTTP GET to a
render endpoint that returns PNGs.

The long-term plan: CLI → web app → Android app via PWA.
See `PLAN.md` for the full roadmap and product catalog.

## Architecture

```
mrms_core.py     ← shared library (NO HTTP framework deps)
                    RadarImage dataclass, round_to_mrms_window(),
                    fetch_radar(), disk cache (cache/),
                    fetch_legend() (SVG colorbar)
                    Imported by BOTH CLI and server.

mrms_cli.py      ← click CLI
                    mrms fetch [--product] [--lat] [--lon] [--zoom]
                    [--width] [--height] [--time] [--output]

server.py        ← FastAPI web server
                    /api/radar         → PNG or JSON (meta=true)
                    /api/legend        → SVG colorbar (proxied from NOAA)
                    /api/products      → hierarchical category list
                    /                  → static/index.html

static/
  index.html     ← Windy-style PWA frontend (~970 lines inline)
                     Leaflet basemap (Dark/Satellite/OSM) at 920x630,
                     L.imageOverlay for radar PNG (perfect geo-alignment),
                     CSS-scaled to fill viewport, pinch-zoom + drag,
                     hierarchical product selector, altitude slider,
                     time scrubber, auto-refresh, Play/Pause animation,
                     pre-fetch + cached frame playback, SVG colorbar,
                     opacity slider, basemap picker
  manifest.json  ← PWA manifest (for Android "Add to Home Screen")
  sw.js          ← Service worker (caches shell + radar images)
```

## How to run

```bash
cd radar_app

# CLI
python mrms_cli.py fetch                           # live, Denver, M3DL13
python mrms_cli.py fetch --product BREF --lat 35 --lon -97
python mrms_cli.py fetch --time 2026-01-15T08:30

# Web app
python server.py                                   # → http://127.0.0.1:8000
```

## Current state by phase

### Phase 1: CLI MVP ✅ DONE
- `mrms_core.py` — fetch_radar(), RadarImage, time rounding, disk cache
- `mrms_cli.py` — all flags working, tested with real NOAA endpoint
- 24 tests (23 unit + 1 integration), all passing

### Phase 2: Product catalog ⬜ PENDING
- Server `/api/products` returns static hierarchical catalog (10 categories, 100+ products)
- Real NOAA menu config endpoint documented in PLAN.md but not consumed yet

### Phase 3: Animation 🟡 PARTIAL (frontend only)
- Frontend animation: 18 frames x 4-min step = 72 min history, 5-sec loop
- Pre-fetch Promise.all loads all frames before playback
- Sliding window refresh re-fetches 3 newest frames every 2 min
- Three modes: live (auto-refresh + red dot), playing (loop), paused (frozen)
- Play/Pause toggle, single-step arrows, UTC time labels
- CLI animation (--animate) and GIF assembly not yet implemented

### Phase 4: Terminal display ⬜ PENDING
- Not started.

### Phase 5: S3 data integration ⬜ PENDING
- Not started.

### Phase 6: Web API + frontend ✅ DONE
- FastAPI server with /api/radar, /api/legend, /api/products
- Leaflet basemap with 3 tile layers (CartoDB Dark Matter default, Esri Satellite, OSM Mapnik)
- L.imageOverlay for radar PNG with exact EPSG:3857 geographic bounds
- #leafletMap at fixed 920x630, CSS-scaled to fill viewport (no compositor conflicts)
- Hierarchical product selector, altitude slider, zoom slider (NOAA zoom 3–12)
- Time scrubber with 48 slots (96 min history, 2-min steps)
- Auto-refresh every 2 min in live mode, Play/Pause animation
- Pinch-zoom, drag-to-pan, mouse wheel zoom
- Per-product SVG colorbar legend on right edge
- Radar opacity slider (10–100%)
- Basemap picker in side panel
- Keyboard shortcuts: Escape, +/-, arrows, 0 (reset)

### Phase 7: PWA + Android install ⬜ PARTIAL
- manifest.json and sw.js exist, not tested on Android
- No app icons yet

## Basemap integration (recently completed)

**Layering:**
```
.map-container (position:fixed; inset:0)
  └── #leafletMap (920x630, centered, CSS-scaled to fill viewport)
        ├── .leaflet-tile-pane    → basemap tiles (CartoDB Dark default)
        └── .leaflet-overlay-pane → radar PNG (L.imageOverlay)
```

**Why this works:**
- Both tile layer and image overlay live inside Leaflet's internal pane system
- Same 920x630 internal coordinate space, same center, same zoom, same projection (EPSG:3857)
- No sibling CSS elements → no GPU compositor layer conflicts
- Uniform CSS `transform: scale()` on the entire `#leafletMap` div
- Geographic alignment is exact — `getRadarBounds()` uses `leafletMap.project()/unproject()`

**Key functions in `static/index.html`:**
| Function | Purpose |
|---|---|
| `initLeaflet()` | Creates L.map at 920x630, all interactions disabled, pointer-events:none |
| `syncMap()` | Calls `leafletMap.setView()` after pan/zoom/fetch |
| `scaleLeafletMap()` | Computes CSS scale factor (`max(vw/920, vh/630)`) and sets transform |
| `getRadarBounds()` | Projects center point, offsets ±460/±315, unprojects to LatLngBounds |
| `updateRadarOverlay(url)` | Creates or updates L.imageOverlay with blob URL and bounds |
| `switchBaseMap(key)` | Swaps tile layer (dark/satellite/osm) |

**Base maps:**
- `dark` (default): CartoDB Dark Matter — `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`
- `satellite`: Esri World Imagery — `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
- `osm`: OpenStreetMap Mapnik — `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`

## Critical implementation details

### NOAA endpoint
```
GET https://mrms.nssl.noaa.gov/qvs/product_viewer/local/render_multi_domain_product_layer.php
```
- **REQUIRES** `User-Agent` and `Referer` headers, otherwise 410 Gone
- SSL verification DISABLED (`verify=False`) — NOAA's server doesn't send the intermediate CA cert (Sectigo)
- Only renders at **fixed 920x630** pixels (other dimensions fail with "Fatal Error in Reading Product Blank File")
- urllib3 InsecureRequestWarning suppressed in mrms_core.py

### NOAA legend endpoint
```
GET https://mrms.nssl.noaa.gov/qvs/product_viewer/shared/fetch_svg_legend_via_config.php
```
- Per-product SVG colorbars (~80x600px) with colored rectangles and tick labels
- Same User-Agent/Referer headers and verify=False as the render endpoint
- Disk-cached: `legend_{product}.svg` — legends are immutable, no expiry
- SVG text is black — frontend container uses light gray background

### 2-minute latency
- NOAA data generated every 2 minutes with variable processing delay
- `fetch_radar()` starts 4 min behind, steps back 2 min up to 6x (12 min total)
- Blank-PNG detection: images <1KB are treated as empty and trigger retry
- Past timestamps (explicit `--time`) are NOT adjusted or retried

### Leaflet map constraints
- `#leafletMap` must be exactly 920x630 (NOAA's only supported dimensions)
- Map interactions disabled: `dragging:false, scrollWheelZoom:false, touchZoom:false, doubleClickZoom:false, boxZoom:false, keyboard:false, zoomControl:false, attributionControl:false`
- `pointer-events: none` on `#leafletMap` — all pan/zoom handled by custom handlers on `.map-container`
- Pan/zoom: custom drag+touch+wheel handlers update `S.lat/S.lon/S.zoom`, call `syncMap()` + `fetchImage()`
- CSS scaling: `transform: translate(-50%,-50%) scale(s)` fills viewport; both tiles and overlay scale together
- Resize handler calls `scaleLeafletMap()` to recalculate scale

### Python environment
- `python` = anaconda3 Python 3.12
- `python3` = system Python 3.13 — does NOT have requests/click
- ALWAYS use `python` (not `python3`) for this project
- Packages: requests 2.32.2, click 8.1.8, fastapi 0.128.6, uvicorn 0.49.0

### Cache
- Disk cache in `cache/` directory (gitignored)
- Cache key: `{product}_{YYYYMMDD_HHMM}_{lat}_{lon}_{zoom}_{W}x{H}.png`
- Legend cache key: `legend_{product}.svg`
- No expiry — MRMS data is immutable once generated

### Tests
- Run: `python -m pytest tests/ -v`
- 24 tests (23 unit + 1 integration), all passing
- Integration test: `test_real_noaa_fetch` hits real NOAA (marked `integration`)
- CLI tests use `click.testing.CliRunner` with mocked `requests.get`

### Frontend gotchas
- `const $` must be defined BEFORE any top-level code that uses it
- DOM element IDs create implicit global variables — avoid `const` name collisions
- NOAA PNGs are RGBA with transparency — map background shows through
- `roundSlot()` MUST use UTC getters with `Date.UTC()` — local time causes timezone offsets
- Time state uses `S.mode: 'live'|'playing'|'paused'` (not isLive+paused booleans)
- Animation pre-fetch: `radarUrlForSlot(slot)` bypasses current mode for explicit timestamps
- Blob URLs: `updateRadarOverlay()` creates blob URL, Leaflet's internal `<img>` manages lifecycle
- Leaflet CDN (leaflet@1.9.4) **must load before** our inline script — `L` global used at script parse
- **`originalFetch` context binding**: Unbound copies of browser native APIs (like `const originalFetch = window.fetch;`) throw `TypeError: Illegal invocation` when called. Always bind it to `window` (e.g., `window.fetch.bind(window)`).
- **Dynamic Standalone Detection**: The standalone fetch hijacker probes `/api/products` using native `fetch` on startup. If a Python server is active, it disables the hijack to let the app communicate directly with `server.py` instead of the public CORS proxy.
- **Python WASM script escaping**: Newlines in Python strings executed via Pyodide `runPythonAsync` inside JS template literals must be triple-escaped (`\\\\n`) in generator scripts to avoid JS parsing them as literal newlines, which causes Python syntax errors.

### Sketches
- `sketches/001-windy-floating/` — the chosen design direction
- `sketches/002-google-maps-bottom/` — alternative (rejected)
- Open with: `open sketches/001-windy-floating/index.html`

## What to work on next

1. **PWA icons** — generate 192px and 512px PNGs, add to `manifest.json`
2. **Phase 2: Product catalog** — wire `mrms --list-products` and `--list-products --category` flags
3. **Geolocation** — browser Geolocation API for "radar near me" button
4. **Better error recovery** — show cached last-known-good image with "stale data" indicator
5. **NOAA overlay API** — fetch borders/highways from overlay endpoint for additional basemap layers
6. **Mobile testing** — test "Add to Home Screen" on Chrome for Android

## Git status (2026-06-09)

```
On branch main
Changes not staged for commit:
  modified:   HANDOFF.md
  modified:   mrms_core.py
  modified:   server.py
  modified:   static/index.html
  modified:   tests/test_mrms_cli.py
  modified:   tests/test_mrms_core.py

Untracked files:
  .DS_Store
```

**Git log (most recent first):**
```
fe51ab3 docs: add HANDOFF.md
d0f2110 fix: subtract 2-min NOAA latency from live requests
3a1e390 feat: hierarchical product selector — category dropdown + level slider
03cc265 fix: add image error state, explicit dimensions, darker background
a81e319 docs: mark Phase 6 complete in PLAN.md
66fdb41 feat: Phase 6 — FastAPI server + Windy-style PWA frontend
01fb141 docs: mark Phase 1 complete in PLAN.md
6c5b762 docs: add README with usage, options, architecture
e616a0e feat: complete Phase 1 — working CLI with real NOAA fetch
886355b chore: remove test artifacts, ignore *.png in root
```

**Current state of working tree:** `static/index.html` is the main file with changes — basemap integration (Leaflet + L.imageOverlay + CSS scaling), Dark basemap default, opacity slider, basemap picker. Other modified files have minor changes or are carry-over from prior work.
