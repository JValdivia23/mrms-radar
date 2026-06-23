"""MRMS radar data fetching — shared core library.

Fetches rendered radar PNGs from NOAA/NSSL MRMS Operational Product Viewer.
No S3, no GRIB2 — just HTTP GET → PNG bytes.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

# NOAA MRMS server does not send the intermediate CA certificate in its
# TLS handshake (Sectigo Public Server Authentication CA DV R36).
# This is a known server-side issue; suppress the InsecureRequestWarning.
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RENDER_URL = (
    "https://mrms.nssl.noaa.gov/qvs/product_viewer/local/"
    "render_multi_domain_product_layer.php"
)
LEGEND_URL = (
    "https://mrms.nssl.noaa.gov/qvs/product_viewer/shared/"
    "fetch_svg_legend_via_config.php"
)
CPP_EXEC_DIR = "/home/metop/web/specific/opv/"
WEB_RESOURCES_DIR = "/var/www/html/qvs/product_viewer/resources/"
REFERER = "https://mrms.nssl.noaa.gov/qvs/product_viewer/index.php"

# Cache directory — relative to this file, gitignored
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

import json

# Product Catalog
PRODUCTS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mrms_products.json")

def _load_products_catalog() -> list:
    try:
        with open(PRODUCTS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

PRODUCT_CATALOG = _load_products_catalog()

def get_product_metadata(product_code: str) -> dict | None:
    """Find a product by its code in the catalog and return its details."""
    for category in PRODUCT_CATALOG:
        for product in category.get("products", []):
            if product.get("code") == product_code:
                return {
                    "code": product.get("code"),
                    "name": product.get("name"),
                    "min_res_minutes": product.get("min_res_minutes", 2),
                    "category_code": category.get("code"),
                    "category_name": category.get("name"),
                    "has_levels": category.get("has_levels", False),
                }
    return None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RadarImage:
    """A fetched MRMS radar image with metadata."""

    png_bytes: bytes
    product: str
    lat: float
    lon: float
    product_name: str = ""
    zoom: int = 7
    timestamp: str = ""
    fetch_time: str = ""
    source_url: str = ""
    width: int = 920
    height: int = 630
    from_cache: bool = False

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Return the geographic bounding box (min_lat, max_lat, min_lon, max_lon) for this image."""
        return get_mercator_bounds(self.lat, self.lon, self.zoom, self.width, self.height)


# ---------------------------------------------------------------------------
# Time utilities
# ---------------------------------------------------------------------------


def round_to_mrms_window(dt: datetime, resolution_mins: int = 2) -> datetime:
    """Round a datetime down to the nearest MRMS window for the given resolution."""
    minute = (dt.minute // resolution_mins) * resolution_mins
    return dt.replace(minute=minute, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Spatial utilities
# ---------------------------------------------------------------------------


def get_mercator_bounds(
    clat: float, clon: float, zoom: int, width: int, height: int
) -> tuple[float, float, float, float]:
    """Calculate the geographic bounding box (min_lat, max_lat, min_lon, max_lon)
    for a viewport with center (clat, clon), Leaflet zoom level, and pixel dimensions.
    Uses standard Web Mercator (EPSG:3857) formulas.
    """
    import math
    clat_rad = math.radians(clat)
    
    center_x = (clon + 180.0) / 360.0
    center_y = (1.0 - math.log(math.tan(clat_rad) + 1.0 / math.cos(clat_rad)) / math.pi) / 2.0
    
    map_size = 256.0 * (2.0 ** zoom)
    
    left_x = (center_x * map_size - (width / 2.0)) / map_size
    right_x = (center_x * map_size + (width / 2.0)) / map_size
    top_y = (center_y * map_size - (height / 2.0)) / map_size
    bottom_y = (center_y * map_size + (height / 2.0)) / map_size
    
    def x_to_lon(x):
        return x * 360.0 - 180.0
        
    def y_to_lat(y):
        val = math.pi * (1.0 - 2.0 * y)
        lat_rad = 2.0 * math.atan(math.exp(val)) - math.pi / 2.0
        return math.degrees(lat_rad)
        
    return y_to_lat(bottom_y), y_to_lat(top_y), x_to_lon(left_x), x_to_lon(right_x)



# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------


def _cache_key(
    product: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    lat: float,
    lon: float,
    zoom: int,
    width: int,
    height: int,
) -> str:
    """Build a deterministic cache filename from request parameters."""
    return (
        f"{product}_{year:04d}{month:02d}{day:02d}_"
        f"{hour:02d}{minute:02d}_"
        f"{lat}_{lon}_{zoom}_"
        f"{width}x{height}.png"
    )


def _cache_save(key: str, png_bytes: bytes) -> None:
    """Save PNG bytes to the cache directory."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, key)
    with open(path, "wb") as f:
        f.write(png_bytes)


def _cache_load(key: str) -> bytes | None:
    """Load PNG bytes from cache, or None if not cached."""
    path = os.path.join(CACHE_DIR, key)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_radar(
    product: str = "M3DL13",
    lat: float = 40.55,
    lon: float = -104.68,
    zoom: int = 7,
    width: int = 920,
    height: int = 630,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    hour: int | None = None,
    minute: int | None = None,
) -> RadarImage:
    """Fetch a rendered MRMS radar image from NOAA.

    If *year* is ``None``, the current UTC time (rounded to the nearest
    2-minute MRMS window) is used.
    """
    # --- resolve time -------------------------------------------------------
    if year is None:
        meta = get_product_metadata(product)
        res_mins = meta["min_res_minutes"] if meta else 2
        now = round_to_mrms_window(datetime.now(timezone.utc), res_mins)
        # NOAA MRMS has processing latency — adjust back by at least one cycle
        from datetime import timedelta
        latency_mins = max(4, res_mins * 2)
        now = now - timedelta(minutes=latency_mins)
        year, month, day = now.year, now.month, now.day
        hour, minute = now.hour, now.minute


    # --- fetch from NOAA ----------------------------------------------------
    from datetime import timedelta

    for attempt in range(6):
        # Check cache for current timestamp
        assert year is not None
        assert month is not None
        assert day is not None
        assert hour is not None
        assert minute is not None
        key = _cache_key(product, year, month, day, hour, minute,
                         lat, lon, zoom, width, height)
        cached = _cache_load(key)
        if cached is not None:
            # Check if cached image is blank
            if len(cached) >= 4000:
                return RadarImage(
                    png_bytes=cached,
                    product=product,
                    lat=lat,
                    lon=lon,
                    zoom=zoom,
                    width=width,
                    height=height,
                    timestamp=f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00",
                    fetch_time=datetime.now(timezone.utc).isoformat(),
                    from_cache=True,
                )

        # Fetch from NOAA
        params = {
            "mode": "run",
            "cpp_exec_dir": CPP_EXEC_DIR,
            "web_resources_dir": WEB_RESOURCES_DIR,
            "prod_root": product,
            "qperate_pal_option": 0,
            "qpe_pal_option": 0,
            "year": year,
            "month": month,
            "day": day,
            "hour": hour,
            "minute": minute,
            "clon": lon,
            "clat": lat,
            "zoom": zoom,
            "width": width,
            "height": height,
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": REFERER,
        }

        fetch_time = datetime.now(timezone.utc)

        r = requests.get(
            RENDER_URL, params=params, headers=headers, timeout=30, verify=False
        )
        r.raise_for_status()

        # Check if PNG is blank (transparent PNGs <4KB are typically empty)
        if len(r.content) >= 4000:
            # Save to cache and return
            _cache_save(key, r.content)

            # Resolve the actual URL that was fetched (for debugging).
            req = getattr(r, "request", None)
            source_url = req.url if req is not None else ""

            return RadarImage(
                png_bytes=r.content,
                product=product,
                lat=lat,
                lon=lon,
                zoom=zoom,
                width=width,
                height=height,
                timestamp=f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00",
                fetch_time=fetch_time.isoformat(),
                source_url=source_url,
                from_cache=False,
            )

        # Step back 2 minutes and retry
        dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        dt = dt - timedelta(minutes=2)
        year, month, day = dt.year, dt.month, dt.day
        hour, minute = dt.hour, dt.minute

    # All attempts failed — return the last (blank) image
    _cache_save(key, r.content)
    req = getattr(r, "request", None)
    source_url = req.url if req is not None else ""
    return RadarImage(
        png_bytes=r.content,
        product=product,
        lat=lat,
        lon=lon,
        zoom=zoom,
        width=width,
        height=height,
        timestamp=f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00",
        fetch_time=fetch_time.isoformat(),
        source_url=source_url,
        from_cache=False,
    )


def fetch_legend(product: str) -> str | None:
    """Fetch the SVG colorbar legend for a given MRMS product.

    Returns the raw SVG string, or ``None`` if the legend is unavailable.
    Legends are cached on disk since they never change per product.
    """
    cache_key = f"legend_{product}.svg"
    cached = _cache_load(cache_key)
    if cached is not None:
        return cached.decode("utf-8")

    params = {
        "web_resources_dir": WEB_RESOURCES_DIR,
        "config_name": "title_and_legend_config.txt",
        "product": product,
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": REFERER,
    }

    try:
        r = requests.get(
            LEGEND_URL, params=params, headers=headers, timeout=15, verify=False
        )
        r.raise_for_status()
    except Exception:
        return None

    svg = r.text
    if not svg or "<svg" not in svg:
        return None

    _cache_save(cache_key, svg.encode("utf-8"))
    return svg
