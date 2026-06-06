"""MRMS Radar CLI — fetch NOAA radar imagery from the terminal.

Usage:
    mrms fetch                              # defaults: M3DL13, Denver, now
    mrms fetch --product BREF --lat 35 -lon -97 --zoom 5
    mrms fetch --time 2026-01-15T08:30
    mrms fetch --width 1200 --height 800 -o ~/Desktop/storm.png
"""

import click
from datetime import datetime

from mrms_core import fetch_radar, round_to_mrms_window


@click.group()
def cli():
    """MRMS Radar — fetch rendered radar imagery from NOAA/NSSL MRMS.

    Default product is M3DL13 (3D Reflectivity at 4.0 km) centered on
    Denver, CO (40.55, -104.68) at zoom level 7.
    """
    pass


@cli.command()
@click.option(
    "--product", "-p",
    default="M3DL13",
    help="MRMS product code (e.g., M3DL13, BREF, CREF, SHSR).",
)
@click.option(
    "--lat",
    default=40.55,
    type=float,
    help="Center latitude (default: 40.55 — Denver, CO).",
)
@click.option(
    "--lon",
    default=-104.68,
    type=float,
    help="Center longitude (default: -104.68 — Denver, CO).",
)
@click.option(
    "--zoom", "-z",
    default=7,
    type=int,
    help="Leaflet zoom level: 3=continent, 7=state, 10=city (default: 7).",
)
@click.option(
    "--width", "-W",
    default=920,
    type=int,
    help="Image width in pixels (default: 920).",
)
@click.option(
    "--height", "-H",
    default=630,
    type=int,
    help="Image height in pixels (default: 630).",
)
@click.option(
    "--time", "-t",
    default=None,
    help="Timestamp in ISO 8601 format (e.g., 2026-06-06T16:30). "
         "Defaults to current UTC time rounded to 2-min MRMS window.",
)
@click.option(
    "--output", "-o",
    default=None,
    type=click.Path(dir_okay=False, writable=True),
    help="Output file path. Defaults to radar_YYYYMMDD_HHMM.png.",
)
def fetch(product, lat, lon, zoom, width, height, time, output):
    """Fetch a radar image from NOAA MRMS and save it to disk.

    Examples:\n
      \b
      mrms fetch
      mrms fetch --product BREF --lat 35.0 --lon -97.0
      mrms fetch --time 2026-01-15T08:30 -o storm.png
      mrms fetch --width 1200 --height 800
    """
    # Resolve time
    if time is not None:
        dt = datetime.fromisoformat(time)
        dt = round_to_mrms_window(dt)
        year, month, day = dt.year, dt.month, dt.day
        hour, minute = dt.hour, dt.minute
        img = fetch_radar(
            product=product, lat=lat, lon=lon, zoom=zoom,
            width=width, height=height,
            year=year, month=month, day=day, hour=hour, minute=minute,
        )
    else:
        img = fetch_radar(
            product=product, lat=lat, lon=lon, zoom=zoom,
            width=width, height=height,
        )

    # Determine output path
    if output is None:
        output = (
            f"radar_"
            f"{img.timestamp.replace('-', '').replace(':', '').replace('T', '_')}"
            f".png"
        )

    # Save
    with open(output, "wb") as f:
        f.write(img.png_bytes)

    cache_tag = " (cached)" if img.from_cache else ""
    click.echo(
        f"Saved {output}  "
        f"({len(img.png_bytes):,} bytes, {img.width}\u00d7{img.height})"
        f"{cache_tag}"
    )


if __name__ == "__main__":
    cli()
