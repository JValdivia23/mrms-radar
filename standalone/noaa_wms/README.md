# Direct NOAA radar experiment

Open `index.html` in a browser. It is a single runnable HTML file: Leaflet
1.9.4, its CSS/images/license, and the Natural Earth basemap are embedded.
Copying the HTML alone is sufficient. No Python server, Google Apps Script
deployment, sign-in, API key, or build step is required.

Live radar and legends require internet access. The default Natural Earth map
does not; optional Mapnik and Satellite maps use their own public tile services.
The original `../pure_js/` and `../wasm_console/` experiments are unchanged.

## Radar source and coverage

The page requests PNGs directly from NOAA's public GeoServer WMS:

- [Base reflectivity](https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_qcd/ows?service=WMS&version=1.3.0&request=GetCapabilities)
- [Composite reflectivity](https://opengeo.ncep.noaa.gov/geoserver/conus/conus_cref_qcd/ows?service=WMS&version=1.3.0&request=GetCapabilities)

Both layers cover the contiguous U.S. The product selector deliberately contains
only these two supported products; altitude selection and the broader MRMS
Operational Product Viewer catalog remain in `pure_js`.
See the [NOAA service directory](https://opengeo.ncep.noaa.gov/geoserver/www/index.html).

`GetCapabilities` supplies recent observation times, including their actual
seconds. The live image loads immediately from this fast path; older time
coverage is discovered in the background. `GetMap` requests an explicit timestamp and a 920×630 image in
EPSG:3857. WMS 1.1.1 keeps the bounding-box axis order unambiguous, and Leaflet
displays the result over the identical projected rectangle. The legend comes
directly from `GetLegendGraphic`.

The services were checked with an anonymous `Origin: null` request and returned
`Access-Control-Allow-Origin: *`, permitting browser access from `file://`.
No fetch interception, local JSON API, proxy, or base64 image transport is used.

### Three-hour history and past dates

The WMS feed currently exposes roughly two hours. For older scans the page uses
the same two quality-controlled MRMS products from the public
[NOAA archive](https://registry.opendata.aws/noaa-mrms-pds/), without AWS
credentials:

```text
CONUS/MergedBaseReflectivityQC_00.50/YYYYMMDD/
CONUS/MergedReflectivityQCComposite_00.50/YYYYMMDD/
```

The archive's XML listing provides actual object timestamps. Requests spanning
UTC midnight read both dates, and recent GIS/archive observations within the
same minute are deduplicated with preference for the fast WMS image. Missing
observations are never invented. Availability depends on NOAA's archive; an
empty date reports that no scans are available.

Archive files are gzip-compressed GRIB2 with PNG-packed unsigned 16-bit values.
A source-specific decoder validates the product, observation timestamp, grid,
scales, PNG checksums, and supported profile. A disposable Web Worker inflates
and filters the source, then samples only the requested viewport onto the same
EPSG:3857 rectangle used by the map. Archive decoding is serialized, and cancelled
views terminate their worker. Compressed and inflated inputs are limited to
64 MiB; only the small viewport becomes an RGBA image. The decoder supports the
7000×3500 CONUS grid and GRIB packing template 5.41, not arbitrary GRIB formats.

Archived images use the NOAA/NSSL viewer's published 5 dBZ reflectivity bins
from −35 to 75 dBZ, with a matching embedded legend; the live WMS image keeps
its provider legend. Missing/no-coverage values are transparent. This path needs
a modern browser supporting Web Workers and `DecompressionStream` (gzip/deflate).
It remains a single HTML file with no backend or extra downloads of decoder code.

## Controls and performance

- **Play** loops the newest 18 advertised scans, or scans ending at a paused
  selection, and starts once three images
  have loaded (or fewer if the service offers fewer scans). Pausing retains the
  observation actually displayed. Arrow buttons and the time slider select
  individual real scans within the three-hour window. Historical playback stays
  on its selected date rather than refreshing back to the present.
- **NOW** returns to the latest advertised scan. Live view and playing loops
  check for new scans every 30 seconds while the page is visible. Published
  cadence and retained history are controlled by NOAA.
- **Slider** has a fixed three-hour elapsed-time scale (−3 h, −2 h, −1 h,
  NOW), with a live `time ago` readout. Positions reflect elapsed seconds rather
  than the number of available scans. Dragging previews the selected scan's
  offset; releasing fetches it. The hour labels are clickable jump buttons and
  also support keyboard activation. Both dragging and hour jumps pause live
  updates and explicitly load the requested time, even if background archive
  discovery is still running. Gaps snap to a real nearby scan; if no scan
  is available within three minutes, an explicit error preserves the current
  image. The displayed image timestamp changes only once a new image has loaded.
- **Go to date** in the menu accepts a UTC date and time, plus previous/next-day
  buttons. It opens the nearest available prior observation and a three-hour
  window ending at the requested time. The full UTC date is always displayed;
  the offset is relative to that window's end. NOW exits this fixed historical
  window. Future/invalid dates and missing dates show explicit messages.
- **Pan/zoom** select the image viewport. The basemap picker and radar-opacity
  slider follow the original interface. Startup requests browser location access
  in parallel with radar loading. If allowed, a pulsing red dot with a white
  outline marks your actual location above the radar. The view centers there
  unless you have already navigated elsewhere. The home button refreshes your
  location and recenters the map. Denying location leaves radar fully usable.
- **Keyboard:** Space plays/pauses, left/right arrows step scans, `+`/`-` zoom,
  Escape closes settings, and `0` requests location.
- The small timing label reports the PNG's fetch/decode time, including any
  request-queue wait, and its size. It excludes initial service discovery and
  legend loading. `From memory` means the exact image was reused from cache.

At most three PNG requests run concurrently. Exact requests and in-flight work
are shared; the memory cache holds at most 72 images or 32 MiB. Refreshing a
warm loop normally downloads only newly advertised scans. Changing views or
pausing aborts obsolete downloads, and late responses cannot replace the current
view. Each network request has a 15-second deadline. Refresh failures retain the
previous image or loop and show a status message.
Archive discovery retains at most eight product/day listings. Each archive
decode has a 30-second deadline in addition to its download deadline.

Small, transparent PNGs are valid clear-weather images here. The old renderer's
4 KB blank-image heuristic does not apply. PNG signatures, dimensions, and image
decoding are checked before a frame enters the cache.

## Validation

From the project root, run the offline Node.js checks:

```bash
node --test standalone/noaa_wms/tests/*.test.cjs
```

These cover exact timestamps and projection, transparent images, response
validation, request sharing, cache budgets, concurrency, deadlines, cancellation,
stale replies, three-hour boundaries, UTC dates, history navigation, archive/WMS
routing, and 90 scheduled loop refreshes across UTC midnight. Synthetic archive
tests cover 16-bit values, all five PNG row filters, geographic sampling,
transparency, and corrupt/mismatched data. They use
mocked network/image decoding; real decoding and live NOAA access require a
browser check.

During implementation, both real archived products were also compared pixel for
pixel against an independent Pillow/NumPy decode and projection; the viewport
RGBA hashes matched. Source data and generated rasters stay outside git.

For an optional local HTTP preview:

```bash
python -m http.server 8766 --bind 127.0.0.1 --directory standalone/noaa_wms
```

Then open `http://127.0.0.1:8766/`. Browser validation during development used
this preview because the automated browser disallows `file://` navigation.
Live base/composite PNG decoding, legends, 18-frame playback, historical
scrubbing, switching products, and a previous-day archive image were checked. Direct `file://` navigation
still needs a manual browser check.

`build_standalone.py` builds the older experiments and does not regenerate this
page. Application code is in the HTML's `<script id="radar-app">` block, separate
from the embedded Leaflet and Natural Earth scripts. Natural Earth data is
public domain; Leaflet's BSD-2-Clause license is included in the HTML.
