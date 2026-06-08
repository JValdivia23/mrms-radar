# HANDOFF.md — MRMS Radar CLI + Web App

**Date:** 2026-06-06
**Status:** Phase 1 (CLI) complete. Phase 6 (web app) functional. Phase 2–5, 7 pending.

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
                    fetch_radar(), disk cache (cache/)
                    Imported by BOTH CLI and server.

mrms_cli.py      ← click CLI
                    mrms fetch [--product] [--lat] [--lon] [--zoom]
                    [--width] [--height] [--time] [--output]

server.py        ← FastAPI web server
                    /api/radar         → PNG or JSON (meta=true)
                    /api/products      → hierarchical category list
                    /                  → static/index.html

static/
  index.html     ← Windy-style PWA frontend (~750 lines inline)
                    Full-screen map, CSS-transformed PNG,
                    pinch-zoom + drag, category dropdown +
                    altitude slider, time scrubber, auto-refresh
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
- `--list-products` flag not yet wired to the CLI
- The server's `/api/products` returns a static hierarchical catalog (10 categories, 100+ products)
- The real NOAA menu config endpoint is documented in PLAN.md but not consumed yet:
  `GET https://mrms.nssl.noaa.gov/qvs/product_viewer/shared/fetch_menu_json_from_config.php?...`

### Phase 3: Animation ⬜ PENDING
- Not started. Plan mentions `--animate N --step M` and GIF assembly.

### Phase 4: Terminal display ⬜ PENDING
- Not started. ASCII art / kitty inline protocol / rich.

### Phase 5: S3 data integration ⬜ PENDING
- Not started. GRIB2 access, point extraction, regional subsetting.

### Phase 6: Web API + frontend ✅ DONE
- FastAPI server with `/api/radar` (PNG + JSON metadata) and `/api/products` (hierarchical)
- Windy-style frontend: full-screen map, floating controls, auto-hiding top bar
- Hierarchical product selector: category dropdown + altitude slider for 3D products
- Default: 3D Reflectivity at 4.0 km (M3DL13) over Denver
- Time scrubber with 48 slots (96 min history, 2-min steps)
- Auto-refresh every 2 minutes in live mode
- Pinch-zoom, drag-to-pan, mouse wheel zoom
- Error state + loading spinner
- Keyboard shortcuts: Escape (close panel), +/- (zoom), arrows (time scrub), 0 (reset)

### Phase 7: PWA + Android install ⬜ PARTIAL
- `manifest.json` and `sw.js` exist, not tested on Android
- No app icons yet
- Need to test "Add to Home Screen" on Chrome for Android
- Optional: TWA wrapper for Play Store

## Critical implementation details

### NOAA endpoint
```
GET https://mrms.nssl.noaa.gov/qvs/product_viewer/local/render_multi_domain_product_layer.php
```
- **REQUIRES** `User-Agent` and `Referer` headers, otherwise 410 Gone
- SSL verification DISABLED (`verify=False`) because NOAA's server doesn't send
  the intermediate CA certificate (Sectigo). This is a known server-side issue.
- urllib3 InsecureRequestWarning suppressed in mrms_core.py

### 2-minute latency
- NOAA data is generated every 2 minutes with ~2 min processing delay
- `fetch_radar()` automatically subtracts 2 minutes for live requests
- Past timestamps (explicit `--time`) are NOT adjusted

### Python environment
- `python` = anaconda3 Python 3.12 at `/Users/java1127/anaconda3/bin/python`
- `python3` = system Python 3.13 — does NOT have requests/click
- ALWAYS use `python` (not `python3`) for this project
- Packages: requests 2.32.2, click 8.1.8, fastapi 0.128.6, uvicorn 0.49.0

### Cache
- Disk cache in `cache/` directory (gitignored)
- Cache key: `{product}_{YYYYMMDD_HHMM}_{lat}_{lon}_{zoom}_{W}x{H}.png`
- No expiry — MRMS data is immutable once generated

### Tests
- Run: `python -m pytest tests/ -v`
- Integration test: `test_real_noaa_fetch` hits real NOAA (marked `integration`)
- CLI tests use `click.testing.CliRunner` with mocked `requests.get`
- All tests patch `CACHE_DIR` to `tempfile.TemporaryDirectory()` for isolation

### Frontend gotchas
- `const $` must be defined BEFORE any top-level code that uses it
- DOM element IDs create implicit global variables — avoid `const` name collisions
  (e.g., renamed `toggleAutoRefresh` DOM id to `toggleAutoRefreshEl` in JS ref)
- Service workers don't work in headless browsers (Browserbase) — harmless error
- NOAA PNGs are RGBA with transparency — map-container background should be dark

### Sketches
- `sketches/001-windy-floating/` — the chosen design direction
- `sketches/002-google-maps-bottom/` — alternative (rejected)
- Open with: `open sketches/001-windy-floating/index.html`

## What to work on next

1. **Priority: Add PNG basemap layer** — the NOAA radar PNG is just the radar
   data (no terrain/borders). The native NOAA viewer has base map options.
   Need to either fetch a separate basemap or toggle overlays.
   
2. **PWA icons** — generate 192px and 512px PNGs, add to `manifest.json`

3. **Phase 2: Product catalog** — wire `mrms --list-products` and
   `--list-products --category brefls` flags to the CLI

4. **Geolocation** — use the browser Geolocation API for "radar near me"
   button on the frontend

5. **Better error recovery** — if the NOAA endpoint is down, show cached
   last-known-good image with a "stale data" indicator

## Git history (most recent first)

```
d0f2110 fix: subtract 2-min NOAA latency from live requests
3a1e390 feat: hierarchical product selector — category dropdown + level slider
03cc265 fix: add image error state, explicit dimensions, darker background
a81e319 docs: mark Phase 6 complete in PLAN.md
66fdb41 feat: Phase 6 — FastAPI server + Windy-style PWA frontend
01fb141 docs: mark Phase 1 complete in PLAN.md
6c5b762 docs: add README with usage, options, architecture
e616a0e feat: complete Phase 1 — working CLI with real NOAA fetch
886355b chore: remove test artifacts, ignore *.png in root
3e31283 feat: CLI with all flags + full test suite
0be1c37 feat: core library — RadarImage, time rounding, fetch_radar, disk cache
5a41570 scaffold: project structure for mrms core + cli
30f7ce6 init: MRMS radar CLI project plan
```
