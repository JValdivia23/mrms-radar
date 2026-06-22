"""MRMS Radar — FastAPI web server.

Serves the Windy-style PWA frontend and a JSON API that wraps mrms_core.
"""

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Query
from fastapi.responses import Response, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from timezonefinder import TimezoneFinder

from mrms_core import fetch_legend, fetch_radar, round_to_mrms_window, PRODUCT_CATALOG, get_product_metadata

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="MRMS Radar", version="0.1.0")

STATIC = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# API: products (hierarchical — category → products)
# ---------------------------------------------------------------------------

CATEGORIES = PRODUCT_CATALOG


@app.get("/api/products")
async def list_products():
    return CATEGORIES


# ---------------------------------------------------------------------------
# API: radar image
# ---------------------------------------------------------------------------


@app.get("/api/radar")
async def get_radar(
    product: str = Query("M3DL13", description="MRMS product code"),
    lat: float = Query(40.55, description="Center latitude"),
    lon: float = Query(-104.68, description="Center longitude"),
    zoom: int = Query(7, ge=3, le=12, description="Zoom level"),
    width: int = Query(920, ge=100, le=2000, description="Image width"),
    height: int = Query(630, ge=100, le=2000, description="Image height"),
    time: str | None = Query(None, description="ISO 8601 timestamp"),
    meta: bool = Query(False, description="Return JSON metadata instead of PNG"),
):
    """Fetch a rendered MRMS radar image.

    Returns PNG by default.  Set ``?meta=true`` to get JSON metadata
    (useful for the frontend to show timestamp info).
    """
    # Resolve time
    if time is not None:
        dt = datetime.fromisoformat(time)
        meta = get_product_metadata(product)
        res_mins = meta["min_res_minutes"] if meta else 2
        dt = round_to_mrms_window(dt, res_mins)
        year, month, day = dt.year, dt.month, dt.day
        hour, minute = dt.hour, dt.minute
    else:
        year = month = day = hour = minute = None

    img = fetch_radar(
        product=product, lat=lat, lon=lon, zoom=zoom,
        width=width, height=height,
        year=year, month=month, day=day, hour=hour, minute=minute,
    )

    if meta:
        return {
            "product": img.product,
            "timestamp": img.timestamp,
            "lat": img.lat,
            "lon": img.lon,
            "zoom": img.zoom,
            "width": img.width,
            "height": img.height,
            "size_bytes": len(img.png_bytes),
            "from_cache": img.from_cache,
        }

    return Response(
        content=img.png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=120",
            "X-MRMS-Timestamp": img.timestamp,
            "X-MRMS-Cache": "hit" if img.from_cache else "miss",
        },
    )


# ---------------------------------------------------------------------------
# API: legend / colorbar
# ---------------------------------------------------------------------------


@app.get("/api/legend")
async def get_legend(
    product: str = Query("M3DL13", description="MRMS product code"),
):
    """Fetch the SVG colorbar legend for a product.

    Returns ``image/svg+xml`` with a long cache lifetime.
    """
    svg = fetch_legend(product)
    if svg is None:
        return Response(status_code=404)

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
        },
    )


# ---------------------------------------------------------------------------
# API: timezone from geographic coordinates
# ---------------------------------------------------------------------------

_tf = TimezoneFinder()


@app.get("/api/timezone")
async def get_timezone(
    lat: float = Query(..., description="Center latitude"),
    lon: float = Query(..., description="Center longitude"),
):
    """Return the IANA timezone and current local time for a geographic point.

    Uses timezonefinder to map lat/lon to an IANA timezone name, then
    ``zoneinfo`` to compute the UTC offset, abbreviation, and local HH:MM.
    """
    tz_name = _tf.timezone_at(lat=lat, lng=lon)
    if tz_name is None:
        tz_name = _tf.timezone_at(lat=lat, lng=lon + 0.5) or _tf.timezone_at(lat=lat, lng=lon - 0.5)
    if tz_name is None:
        return JSONResponse(status_code=404, content={"error": "No timezone found for coordinates"})

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        return JSONResponse(status_code=404, content={"error": f"Invalid timezone: {tz_name}"})

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    offset_hours = now_local.utcoffset().total_seconds() / 3600

    return {
        "tz": tz_name,
        "abbr": now_local.strftime("%Z"),
        "offset_hours": offset_hours,
        "local_time": now_local.strftime("%H:%M"),
    }


# ---------------------------------------------------------------------------
# Static files / frontend
# ---------------------------------------------------------------------------


@app.get("/")
async def index():
    return HTMLResponse((STATIC / "index.html").read_text())


# Mount remaining static files (manifest, sw.js, icons)
if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
