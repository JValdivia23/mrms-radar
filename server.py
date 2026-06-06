"""MRMS Radar — FastAPI web server.

Serves the Windy-style PWA frontend and a JSON API that wraps mrms_core.
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import Response, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from mrms_core import fetch_radar, round_to_mrms_window

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="MRMS Radar", version="0.1.0")

STATIC = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# API: products
# ---------------------------------------------------------------------------

PRODUCTS = [
    {"code": "M3DL13", "name": "3D Reflectivity at 4.0 km", "category": "level"},
    {"code": "M3DL11", "name": "3D Reflectivity at 3.0 km", "category": "level"},
    {"code": "M3DL7",  "name": "3D Reflectivity at 2.0 km",  "category": "level"},
    {"code": "M3DL5",  "name": "3D Reflectivity at 1.5 km",  "category": "level"},
    {"code": "M3DL3",  "name": "3D Reflectivity at 1.0 km",  "category": "level"},
    {"code": "M3DL1",  "name": "3D Reflectivity at 0.5 km",  "category": "level"},
    {"code": "BREF",   "name": "Base Reflectivity",          "category": "brefls"},
    {"code": "CREF",   "name": "Composite Reflectivity",     "category": "crefls"},
    {"code": "SHSR",   "name": "Seamless Hybrid Scan",       "category": "shsrs"},
    {"code": "RALA",   "name": "Refl at Lowest Altitude",    "category": "ralas"},
]


@app.get("/api/products")
async def list_products():
    return PRODUCTS


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
        dt = round_to_mrms_window(dt)
        year, month, day = dt.year, dt.month, dt.day
        hour, minute = dt.hour, dt.minute
    else:
        now = round_to_mrms_window(datetime.now(timezone.utc))
        year, month, day = now.year, now.month, now.day
        hour, minute = now.hour, now.minute

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
