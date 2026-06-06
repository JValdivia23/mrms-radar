# MRMS CLI → Web App → Android — Plan

## Goal

Wrap the NOAA/NSSL MRMS Operational Product Viewer into a CLI that fetches rendered radar imagery for any product, location, and time — no browser, no S3, no GRIB2 parsing. Then evolve the same codebase into a web app and Android app via PWA.

## Platform Roadmap

```
Phase 1–2: CLI (Python + click)        ← single binary, terminal users
Phase 6:   Web API + frontend (FastAPI) ← browser access
Phase 7:   PWA (manifest + service worker) → Android installable app
```

All three share a single `mrms_core.py` library. The CLI and web server are thin wrappers around it. The PWA is static HTML/JS served by the same web server — no separate Android codebase.

## Data Source

### Render endpoint (primary — visual images only)

```
GET https://mrms.nssl.noaa.gov/qvs/product_viewer/local/render_multi_domain_product_layer.php
```

**Required headers:**
| Header | Value |
|--------|-------|
| `User-Agent` | `Mozilla/5.0` (any browser-like string) |
| `Referer` | `https://mrms.nssl.noaa.gov/qvs/product_viewer/index.php` |

Without these → 410 Gone. With them → 200 OK, PNG.

**Query parameters:**

| Param | Example | Description |
|-------|---------|-------------|
| `mode` | `run` | Always `run` |
| `cpp_exec_dir` | `/home/metop/web/specific/opv/` | Server-side render binary path (constant) |
| `web_resources_dir` | `/var/www/html/qvs/product_viewer/resources/` | Server config path (constant) |
| `prod_root` | `M3DL13` | Product code (see catalog below) |
| `qperate_pal_option` | `0` | Palette option (usually 0) |
| `qpe_pal_option` | `0` | QPE palette option (usually 0) |
| `year` | `2026` | 4-digit year |
| `month` | `6` | 1-12 |
| `day` | `6` | 1-31 |
| `hour` | `16` | 0-23 UTC |
| `minute` | `30` | 0-59 UTC (data available every 2 min) |
| `clon` | `-104.68` | Map center longitude |
| `clat` | `40.55` | Map center latitude |
| `zoom` | `7` | Leaflet zoom level (3=continent, 7=state, 10=city) |
| `width` | `920` | Image width in px |
| `height` | `630` | Image height in px |

**Response:** PNG image, RGBA 8-bit. ~14 KB for 920×630. ~200 ms response time.

### S3 archive (data access — for future numerical analysis)

```
s3://noaa-mrms-pds/CONUS/MergedReflectivityQC_04.00/YYYYMMDD/
```

- Public HTTPS, no auth
- GRIB2 format, gzipped (~1.3 MB per file)
- New file every 2 minutes, ~2 min latency
- Full CONUS grid: 3500 × 7000 points, 93.5 MB in memory
- Product mapping: viewer `M3DL13` → S3 `MergedReflectivityQC_04.00`

## Product Catalog

20 categories, ~200 individual products. Full catalog available at:

```
GET https://mrms.nssl.noaa.gov/qvs/product_viewer/shared/fetch_menu_json_from_config.php
  ?menu=/var/www/html/qvs/product_viewer/resources/menu_config.txt
```

### Top-level categories

| # | Code | Name | Products |
|---|------|------|----------|
| 1 | `brefls` | Base Reflectivity | BREF, 1hr Max, Un-QC'ed |
| 2 | `crefls` | Composite Reflectivity | CREF, Max Method, 1hr Max, Un-QC'ed, Height |
| 3 | `shsrs` | Seamless Hybrid Scan | SHSR, SHSR Height |
| 4 | `ralas` | Refl At Lowest Altitude | RALA, Un-QC'ed |
| 5 | `layer` | Layer Reflectivity | ANC, Low, High, Super, Constant-Temp levels |
| 6 | `rads` | Echo Top | 18/30/50/60 dBZ (m and kft) |
| 7 | `thick` | Layer Thickness | 50/60 dBZ above 0°C/-20°C |
| 8 | `level` | **3D Mosaic Levels** | **M3DL1–M3DL33** (0.5 km – 19 km) |
| 9 | `zdr` | ZDR - 3D Mosaic | MZDRL1–MZDRL33 (same levels) |
| 10 | `rhohv` | RhoHV - 3D Mosaic | MRHOL1–MRHOL33 (same levels) |
| 11 | `rqis` | Radar Quality Index | RQI, QPE RQI (1h–72h) |
| 12 | `azsh` | Rotation | AzShear low/mid, tracks 30m–24h |
| 13 | `hails` | Hail/Lightning | SHI, POSH, MESH, hail swaths, lightning prob |
| 14 | `precips` | Gauge Influence Index | Pass1/Pass2 (1h–72h) |
| 15 | `flash` | FLASH | CREST/SAC/HP flow, ARI, FFG |
| 16 | `q3rads` | Q3 Radar Only | Rate, 15m–72h accumulations |
| 17 | `q3mss` | Q3 Multi-Sensor | Pass1/Pass2 (1h–72h) |
| 18 | `waters` | Vert Integrated Water | VIL, VIL Density, VII, VIL Swaths |
| 19 | `pcpflag_bb` | Precip Flag/Bright Band | PrecipFlag, BB Top/Bottom |
| 20 | `models` | Model | Surface Temp, Wet Bulb, Freezing Height, Tropical Rain Prob |

### 3D Reflectivity levels (most commonly used)

| Code | Altitude | Code | Altitude | Code | Altitude |
|------|----------|------|----------|------|----------|
| M3DL1 | 0.5 km | M3DL13 | 4.0 km | M3DL24 | 11 km |
| M3DL2 | 0.75 km | M3DL14 | 4.5 km | M3DL25 | 12 km |
| M3DL3 | 1.0 km | M3DL15 | 5.0 km | M3DL26 | 13 km |
| M3DL4 | 1.25 km | M3DL16 | 5.5 km | M3DL27 | 14 km |
| M3DL5 | 1.5 km | M3DL17 | 6.0 km | M3DL28 | 15 km |
| M3DL6 | 1.75 km | M3DL18 | 6.5 km | M3DL29 | 16 km |
| M3DL7 | 2.0 km | M3DL19 | 7.0 km | M3DL30 | 17 km |
| M3DL8 | 2.25 km | M3DL20 | 7.5 km | M3DL31 | 18 km |
| M3DL9 | 2.5 km | M3DL21 | 8.0 km | M3DL32 | 19 km |
| M3DL10 | 2.75 km | M3DL22 | 8.5 km | M3DL33 | 19+ km |
| M3DL11 | 3.0 km | M3DL23 | 9.0 km | | |
| M3DL12 | 3.5 km | | | | |

## Architecture

### Shared core library

The entire data-fetching logic lives in `mrms_core.py` — a pure Python module with zero UI dependencies. Both the CLI and the web server import it. This avoids duplication and keeps platform-specific code minimal.

```
radar_app/
├── PLAN.md
├── requirements.txt
├── README.md
│
├── mrms_core.py          ← shared library (fetch, catalog, cache, models)
├── mrms_cli.py           ← click CLI (thin wrapper)
│
├── server.py             ← FastAPI web server
├── static/               ← PWA frontend (served by FastAPI)
│   ├── index.html
│   ├── manifest.json
│   ├── sw.js
│   └── app.js
│
└── cache/                ← disk cache for fetched images (gitignored)
```

### Data flow (all platforms)

```
User input (CLI flags / URL params / PWA form)
        │
        ▼
  mrms_core.fetch_radar(product, lat, lon, zoom, time, ...)
        │
        ├─ Check disk cache → return cached PNG if fresh
        │
        ├─ GET NOAA render endpoint (with User-Agent + Referer)
        │
        ├─ Cache PNG to disk
        │
        └─ Return RadarImage object (PNG bytes + metadata)
                │
                ▼
        CLI: write to file       Web: return as HTTP response
        PWA: display in <img>    Android: same PWA, same <img>
```

### Response model

`fetch_radar()` returns a `RadarImage` dataclass, not raw bytes:

```python
@dataclass
class RadarImage:
    png_bytes: bytes          # raw PNG
    product: str              # e.g., "M3DL13"
    product_name: str         # e.g., "3D Reflectivity at 4.0 km"
    lat: float
    lon: float
    zoom: int
    timestamp: datetime       # actual data time (UTC)
    fetch_time: datetime      # when we fetched it
    source_url: str           # the exact NOAA URL used
    width: int
    height: int
    from_cache: bool          # was this a cache hit?
```

### Caching strategy

MRMS data is immutable once generated (a given product+time never changes). Cache key: `{product}_{YYYYMMDD_HHMM}_{lat}_{lon}_{zoom}_{w}x{h}.png`.

- Disk cache in `cache/` directory (gitignored)
- CLI: caches every fetch automatically
- Web server: adds `Cache-Control: public, max-age=3600` header so browsers and CDNs cache too
- PWA service worker: can cache recent images for offline viewing
- No cache expiry needed — old tiles are tiny (~14 KB) and the total is self-limiting if someone fetches 1000 unique tiles that's only ~14 MB

## CLI Architecture

### Tech stack
- **Python** (already installed: 3.12 via anaconda3)
- **requests** (already installed: 2.32.2) — HTTP calls
- **click** (already installed: 8.1.8) — CLI framework
- **No additional installs needed for Phase 1–5**

### CLI interface

```bash
# Default: latest reflectivity for Denver area
mrms

# Specific product
mrms --product M3DL13

# Specific location
mrms --lat 40.55 --lon -104.68 --zoom 7

# Specific time
mrms --time 2026-06-06T16:30

# Custom image size
mrms --width 1200 --height 800

# Save to specific path
mrms --output ~/Desktop/radar.png

# List all products
mrms --list-products

# Download animation frames
mrms --animate 18 --step 4
```

### Defaults
| Parameter | Default | Reason |
|-----------|---------|--------|
| Product | `M3DL13` | 3D Reflectivity at 4.0 km — good mid-level view |
| Lat | 40.55 | Denver, CO area |
| Lon | -104.68 | Denver, CO area |
| Zoom | 7 | State-level view |
| Width | 920 | Matches viewer default |
| Height | 630 | Matches viewer default |
| Time | now (rounded to nearest 2 min) | Real-time |
| Output | `./radar_YYYYMMDD_HHMM.png` | Auto-named by timestamp |

### Time rounding
MRMS data is generated every 2 minutes. The CLI should round down to the nearest even minute (e.g., 16:31 → 16:30) to hit an existing tile.

## Web App Architecture (Phase 6)

### Backend: FastAPI

Single-file server (`server.py`) with three endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/radar` | Fetch radar image (same params as CLI) → returns PNG |
| `GET` | `/api/products` | List all products as JSON |
| `GET` | `/api/products/{code}` | Product details (name, category, levels) |

Also serves `static/` directory for the PWA frontend.

### Frontend: vanilla HTML/CSS/JS PWA

Single-page app with:
- Product selector dropdown (loaded from `/api/products`)
- Location picker (lat/lon inputs or geolocation API)
- Zoom slider (3–12)
- Time scrubber (last 24h, 2-min steps)
- Image display (`<img>` pointing at `/api/radar?...`)
- Auto-refresh toggle (polls `/api/radar` every 2 min)

### PWA → Android install

Three files enable Android installation with zero native code:

1. **`manifest.json`** — app name, icon, fullscreen mode, background color
2. **`sw.js`** — service worker caching the app shell and recent radar images
3. **`index.html`** — links to both, has `<meta name="viewport">` for mobile

When a user opens the web app in Chrome on Android, Chrome detects the manifest and shows an "Install" banner. The installed app:
- Gets a home-screen icon (separate from the browser)
- Runs fullscreen (no browser chrome)
- Works offline for cached images
- Appears in the Android app drawer

If a Play Store listing is desired later, wrap the same PWA in a **Trusted Web Activity (TWA)** using Google's Bubblewrap tool — generates an APK from the PWA URL in minutes, no code changes.

### Why PWA over React Native / Flutter

| Factor | PWA | React Native / Flutter |
|--------|-----|----------------------|
| Codebases | 1 (web = Android) | 2+ (web + Android + iOS) |
| Build toolchain | None | Android Studio, Gradle, Xcode |
| App complexity | ~300 lines HTML/JS | Thousands of lines + state management |
| NOAA endpoint access | Direct HTTP (no CORS issue if same-origin) | Same via fetch |
| Image display | `<img>` tag | `<Image>` component |
| Offline support | Service worker (built-in) | Manual SQLite/cache |
| This app's needs | 100% covered | Overkill |

The app is a data-fetch + image-display tool. PWA handles this perfectly with a fraction of the complexity.

## Milestones

### Phase 1: Core library + Single-image CLI (MVP)
- [ ] `mrms_core.py` — `fetch_radar()`, `RadarImage` dataclass, time rounding, disk cache
- [ ] `mrms_cli.py` — click CLI with default product + location + current time
- [ ] `--product`, `--lat`, `--lon`, `--zoom`, `--output` flags
- [ ] `--time` flag with ISO parsing

### Phase 2: Product catalog
- [ ] `mrms_core.list_products()` — fetch and parse menu config endpoint
- [ ] `--list-products` flag (all products)
- [ ] `--list-products --category brefls` — filter by category
- [ ] `--info M3DL13` — show product details (name, resolution, category)

### Phase 3: Animation
- [ ] `mrms_core.fetch_animation()` — download N frames, step M minutes
- [ ] `--animate N --step M` flags
- [ ] Assemble into GIF (Pillow) or save frame sequence

### Phase 4: Terminal display (optional)
- [ ] ASCII art rendering for terminal preview
- [ ] Or kitty/iTerm2 inline image protocol
- [ ] Color output with rich/textual

### Phase 5: S3 data integration (future)
- [ ] Direct GRIB2 access for numerical analysis
- [ ] Point extraction (`--extract lat lon` → reflectivity value)
- [ ] Regional subsetting with grib_copy

### Phase 6: Web API + frontend
- [ ] `server.py` — FastAPI serving `/api/radar`, `/api/products`, static files
- [ ] `static/index.html` — product selector, map preview, time scrubber
- [ ] `static/app.js` — fetch API calls, auto-refresh, image display
- [ ] CORS and caching headers

### Phase 7: PWA + Android install
- [ ] `static/manifest.json` — app name, icons, display mode
- [ ] `static/sw.js` — cache shell + recent images for offline use
- [ ] Test "Add to Home Screen" on Android Chrome
- [ ] (Optional) TWA wrapper for Play Store distribution
