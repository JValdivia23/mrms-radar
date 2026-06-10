"""MRMS Radar — FastAPI web server.

Serves the Windy-style PWA frontend and a JSON API that wraps mrms_core.
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import Response, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from mrms_core import fetch_legend, fetch_radar, round_to_mrms_window

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="MRMS Radar", version="0.1.0")

STATIC = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# API: products (hierarchical — category → products)
# ---------------------------------------------------------------------------

CATEGORIES = [
    {
        "code": "level",
        "name": "3D Reflectivity",
        "default_product": "M3DL13",
        "products": [
            {"code": "M3DL1",  "name": "0.5 km"},
            {"code": "M3DL2",  "name": "0.75 km"},
            {"code": "M3DL3",  "name": "1.0 km"},
            {"code": "M3DL4",  "name": "1.25 km"},
            {"code": "M3DL5",  "name": "1.5 km"},
            {"code": "M3DL6",  "name": "1.75 km"},
            {"code": "M3DL7",  "name": "2.0 km"},
            {"code": "M3DL8",  "name": "2.25 km"},
            {"code": "M3DL9",  "name": "2.5 km"},
            {"code": "M3DL10", "name": "2.75 km"},
            {"code": "M3DL11", "name": "3.0 km"},
            {"code": "M3DL12", "name": "3.5 km"},
            {"code": "M3DL13", "name": "4.0 km"},
            {"code": "M3DL14", "name": "4.5 km"},
            {"code": "M3DL15", "name": "5.0 km"},
            {"code": "M3DL16", "name": "5.5 km"},
            {"code": "M3DL17", "name": "6.0 km"},
            {"code": "M3DL18", "name": "6.5 km"},
            {"code": "M3DL19", "name": "7.0 km"},
            {"code": "M3DL20", "name": "7.5 km"},
            {"code": "M3DL21", "name": "8.0 km"},
            {"code": "M3DL22", "name": "8.5 km"},
            {"code": "M3DL23", "name": "9.0 km"},
            {"code": "M3DL24", "name": "11 km"},
            {"code": "M3DL25", "name": "12 km"},
            {"code": "M3DL26", "name": "13 km"},
            {"code": "M3DL27", "name": "14 km"},
            {"code": "M3DL28", "name": "15 km"},
            {"code": "M3DL29", "name": "16 km"},
            {"code": "M3DL30", "name": "17 km"},
            {"code": "M3DL31", "name": "18 km"},
            {"code": "M3DL32", "name": "19 km"},
            {"code": "M3DL33", "name": "19+ km"},
        ],
        "has_levels": True,
        "level_suffix": "km",
    },
    {
        "code": "zdr",
        "name": "Differential Reflectivity (ZDR)",
        "default_product": "MZDRL13",
        "products": [
            {"code": "MZDRL1",  "name": "0.5 km"},
            {"code": "MZDRL3",  "name": "1.0 km"},
            {"code": "MZDRL5",  "name": "1.5 km"},
            {"code": "MZDRL7",  "name": "2.0 km"},
            {"code": "MZDRL9",  "name": "2.5 km"},
            {"code": "MZDRL11", "name": "3.0 km"},
            {"code": "MZDRL13", "name": "4.0 km"},
            {"code": "MZDRL15", "name": "5.0 km"},
            {"code": "MZDRL17", "name": "6.0 km"},
            {"code": "MZDRL19", "name": "7.0 km"},
            {"code": "MZDRL21", "name": "8.0 km"},
            {"code": "MZDRL23", "name": "9.0 km"},
            {"code": "MZDRL25", "name": "12 km"},
            {"code": "MZDRL27", "name": "14 km"},
            {"code": "MZDRL29", "name": "16 km"},
            {"code": "MZDRL31", "name": "18 km"},
            {"code": "MZDRL33", "name": "19+ km"},
        ],
        "has_levels": True,
        "level_suffix": "km",
    },
    {
        "code": "rhohv",
        "name": "Correlation Coefficient (RhoHV)",
        "default_product": "MRHOL13",
        "products": [
            {"code": "MRHOL1",  "name": "0.5 km"},
            {"code": "MRHOL3",  "name": "1.0 km"},
            {"code": "MRHOL5",  "name": "1.5 km"},
            {"code": "MRHOL7",  "name": "2.0 km"},
            {"code": "MRHOL9",  "name": "2.5 km"},
            {"code": "MRHOL11", "name": "3.0 km"},
            {"code": "MRHOL13", "name": "4.0 km"},
            {"code": "MRHOL15", "name": "5.0 km"},
            {"code": "MRHOL17", "name": "6.0 km"},
            {"code": "MRHOL19", "name": "7.0 km"},
            {"code": "MRHOL21", "name": "8.0 km"},
            {"code": "MRHOL23", "name": "9.0 km"},
            {"code": "MRHOL25", "name": "12 km"},
            {"code": "MRHOL27", "name": "14 km"},
            {"code": "MRHOL29", "name": "16 km"},
            {"code": "MRHOL31", "name": "18 km"},
            {"code": "MRHOL33", "name": "19+ km"},
        ],
        "has_levels": True,
        "level_suffix": "km",
    },
    {
        "code": "brefls",
        "name": "Base Reflectivity",
        "default_product": "BREF",
        "products": [
            {"code": "BREF", "name": "Base Reflectivity"},
        ],
        "has_levels": False,
    },
    {
        "code": "crefls",
        "name": "Composite Reflectivity",
        "default_product": "CREF",
        "products": [
            {"code": "CREF", "name": "Composite Reflectivity"},
        ],
        "has_levels": False,
    },
    {
        "code": "shsrs",
        "name": "Seamless Hybrid Scan",
        "default_product": "SHSR",
        "products": [
            {"code": "SHSR", "name": "SHSR Reflectivity"},
        ],
        "has_levels": False,
    },
    {
        "code": "ralas",
        "name": "Refl at Lowest Altitude",
        "default_product": "RALA",
        "products": [
            {"code": "RALA", "name": "RALA Reflectivity"},
        ],
        "has_levels": False,
    },
    {
        "code": "hails",
        "name": "Hail Products",
        "default_product": "MESH",
        "products": [
            {"code": "SHI",  "name": "Severe Hail Index"},
            {"code": "POSH", "name": "Prob of Severe Hail"},
            {"code": "MESH", "name": "Max Est Size of Hail"},
        ],
        "has_levels": False,
    },
    {
        "code": "waters",
        "name": "Vert Integrated Water",
        "default_product": "VIL",
        "products": [
            {"code": "VIL",  "name": "Vert Integrated Liquid"},
            {"code": "VII",  "name": "Vert Integrated Ice"},
        ],
        "has_levels": False,
    },
    {
        "code": "rads",
        "name": "Echo Tops",
        "default_product": "ET18",
        "products": [
            {"code": "ET18", "name": "Echo Top 18 dBZ"},
            {"code": "ET30", "name": "Echo Top 30 dBZ"},
            {"code": "ET50", "name": "Echo Top 50 dBZ"},
        ],
        "has_levels": False,
    },
]


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
        dt = round_to_mrms_window(dt)
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
