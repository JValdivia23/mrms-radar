# Direct NOAA WMS experiment

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

`GetCapabilities` supplies the available observation times, including their
actual seconds. The slider uses this list without rounding or guessing scan
availability. `GetMap` requests an explicit timestamp and a 920×630 image in
EPSG:3857. WMS 1.1.1 keeps the bounding-box axis order unambiguous, and Leaflet
displays the result over the identical projected rectangle. The legend comes
directly from `GetLegendGraphic`.

The services were checked with an anonymous `Origin: null` request and returned
`Access-Control-Allow-Origin: *`, permitting browser access from `file://`.
No fetch interception, local JSON API, proxy, GRIB decoding, or base64 image
transport is used.

## Controls and performance

- **Play** loops the newest 18 advertised scans and starts once three images
  have loaded (or fewer if the service offers fewer scans). Pausing retains the
  observation actually displayed. Arrow buttons and the time slider select
  individual scans from all available history.
- **NOW** returns to the latest advertised scan. Live view and playing loops
  check for new scans every 30 seconds while the page is visible. Published
  cadence and retained history are controlled by NOAA.
- **Pan/zoom** select the image viewport. The basemap picker, radar-opacity
  slider, and location marker follow the original interface. The home button
  requests browser location permission when clicked; startup uses the remembered
  view or northern Colorado without waiting for geolocation.
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
stale replies, and 90 scheduled loop refreshes across UTC midnight. They use
mocked network/image decoding; real decoding and live NOAA access require a
browser check.

For an optional local HTTP preview:

```bash
python -m http.server 8766 --bind 127.0.0.1 --directory standalone/noaa_wms
```

Then open `http://127.0.0.1:8766/`. Browser validation during development used
this preview because the automated browser disallows `file://` navigation.
Live base/composite PNG decoding, legends, 18-frame playback, historical
scrubbing, and switching products were checked. Direct `file://` navigation
still needs a manual browser check.

`build_standalone.py` builds the older experiments and does not regenerate this
page. Application code is in the HTML's `<script id="radar-app">` block, separate
from the embedded Leaflet and Natural Earth scripts. Natural Earth data is
public domain; Leaflet's BSD-2-Clause license is included in the HTML.
