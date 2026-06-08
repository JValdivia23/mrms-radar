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
CPP_EXEC_DIR = "/home/metop/web/specific/opv/"
WEB_RESOURCES_DIR = "/var/www/html/qvs/product_viewer/resources/"
REFERER = "https://mrms.nssl.noaa.gov/qvs/product_viewer/index.php"

# Cache directory — relative to this file, gitignored
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

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


# ---------------------------------------------------------------------------
# Time utilities
# ---------------------------------------------------------------------------


def round_to_mrms_window(dt: datetime) -> datetime:
    """Round a datetime down to the nearest 2-minute MRMS window.

    MRMS data is generated every 2 minutes (:00, :02, :04, ..., :58).
    """
    minute = (dt.minute // 2) * 2
    return dt.replace(minute=minute, second=0, microsecond=0)


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
        now = round_to_mrms_window(datetime.now(timezone.utc))
        # NOAA MRMS has ~2 min processing latency — the current 2-min
        # window is usually blank because the data hasn't been generated
        # yet.  Subtract 2 min to get the latest *available* tile.
        from datetime import timedelta
        now = now - timedelta(minutes=2)
        year, month, day = now.year, now.month, now.day
        hour, minute = now.hour, now.minute

    # --- check cache --------------------------------------------------------
    # (year/month/day/hour/minute are guaranteed ints after the block above;
    #  help the type checker see that.)
    assert year is not None
    assert month is not None
    assert day is not None
    assert hour is not None
    assert minute is not None
    key = _cache_key(product, year, month, day, hour, minute,
                     lat, lon, zoom, width, height)
    cached = _cache_load(key)
    if cached is not None:
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

    # --- fetch from NOAA ----------------------------------------------------
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

    # Save to cache
    _cache_save(key, r.content)

    # Resolve the actual URL that was fetched (for debugging).
    # r.request may be None (e.g. redirects); fall back to empty string.
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
