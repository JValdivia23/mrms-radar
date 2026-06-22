# AGENTS.md

## Project

MRMS Radar — CLI + web app that fetches rendered radar PNGs from NOAA/NSSL MRMS Operational Product Viewer. No GRIB2, no S3 — just HTTP GET to a render endpoint.

## Quick reference

```bash
python -m pytest tests/ -v                   # all 25 tests
python -m pytest tests/ -v -m "not integration"  # unit tests only (no network)
python mrms_cli.py fetch                     # CLI: latest Denver M3DL13
python mrms_cli.py fetch --product BREF --lat 35 --lon -97 --zoom 5
python mrms_cli.py products                  # CLI: list all categories
python server.py                             # web app → http://127.0.0.1:8000
```

**Always use `python`** (not `python3`). Both currently resolve to the same 3.12.2, but this is not guaranteed.

## Architecture

```
mrms_products.json ← centralized product configuration database
mrms_core.py   ← shared library (imported by CLI + server)
mrms_cli.py    ← click CLI (thin wrapper around mrms_core)
server.py      ← FastAPI web server + dynamic JSON API
static/        ← Leaflet PWA frontend (index.html ~1030 lines inline)
tests/         ← 25 tests (24 unit + 1 integration)
```

## Critical NOAA constraints

- **Headers required**: `User-Agent` and `Referer` headers — without them, NOAA returns 410 Gone.
- **SSL disabled**: `verify=False` on all NOAA requests. NOAA doesn't send the intermediate CA cert (Sectigo). `InsecureRequestWarning` is suppressed in `mrms_core.py`.
- **Fixed dimensions**: NOAA only renders at **920x630** pixels. Other sizes fail with "Fatal Error in Reading Product Blank File".
- **Variable data cycles**: Products cycle at 2, 5, or 60 minutes (defined in `mrms_products.json`). `fetch_radar()` automatically detects product resolution to round time windows and shifts back latency (max of 4 min or 2x resolution). Retries step back by resolution duration.
- **Blank PNG detection**: Images <1KB are treated as empty and trigger retry.

## Frontend gotchas

- `const $` must be defined before any top-level code that uses it (line 408 in `static/index.html`).
- DOM element IDs create implicit globals — avoid `const` name collisions.
- `roundSlot()` must use UTC getters with `Date.UTC()` — local time causes timezone offsets.
- Leaflet CDN (`leaflet@1.9.4`) **must load before** the inline script — `L` global used at script parse.
- The map container is fixed at 920x630 internal pixels, CSS-scaled to fill the viewport.

## Testing

- Unit tests mock `requests.get` — no network needed.
- Integration test (`test_real_noaa_fetch`) hits real NOAA — marked `integration`.
- Run `pytest tests/ -v -m "not integration"` for fast offline checks.
- No lint/typecheck command configured.

## Dependencies

`requirements.txt`: `requests`, `click`, `timezonefinder` — installed via `pip install -e .` or `pip install -r requirements.txt`.

FastAPI/uvicorn/leaflet are server + frontend dependencies, not in `requirements.txt`.
