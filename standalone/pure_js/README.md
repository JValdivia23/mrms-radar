# Pure JavaScript standalone experiment

`index.html` is the current browser-only radar experiment. Open it directly via
`file://` without running the Python server. It includes the product catalog,
radar controls, and animation player, and uses a Google Apps Script CORS proxy
for NOAA radar images and legends.

The goal is a single HTML file. The current build still needs
`natural-earth.js` and `natural-earth-data.js` beside it and loads Leaflet JS/CSS
from a CDN. Live radar requires an internet connection and the configured proxy.

## Google authorization and credentials

**Known setup limitation:** the standalone experiment depends on a Google Apps
Script deployment authorized by its owner. Opening or copying the HTML does not
create that deployment or grant its Google permissions. The checked-in
`GOOGLE_SCRIPT_PROXY` value points to an existing deployment; configure your own
deployment for an independent copy.

- **Proxy owner:** sign in with a Google Account, create/deploy the script, and
  approve its permission to make external requests. `UrlFetchApp` requires the
  `https://www.googleapis.com/auth/script.external_request` OAuth scope, normally
  detected automatically by Apps Script. See Google's [URL Fetch documentation](https://developers.google.com/apps-script/reference/url-fetch).
- **Radar viewer:** with **Execute as: Me** and **Who has access: Anyone**
  (anonymous access), requests run with the owner's authorization. Viewers should
  not need their own Google login. **Anyone with Google account**, domain-only
  access, or executing as the accessing user introduces a sign-in dependency.
  See Google's [web app permissions](https://developers.google.com/apps-script/guides/web#permissions)
  and [access settings](https://developers.google.com/apps-script/manifest/web-app-api-executable#webapp).
- **HTML configuration:** only the deployed `/exec` URL is stored in the page.
  Google account credentials and authorization stay with Google. No Google Maps
  API key is needed for the bundled Natural Earth basemap.

The page uses background `fetch()` requests and has no interactive Google sign-in
flow. If the proxy redirects to a login or consent page, the map shell can load
while radar and legends fail. This dependency remains even when the HTML is
opened locally or hosted on a static website.

## Background maps

The default **Natural Earth (Dark)** map is bundled with the app. It needs no
API key or tile server and works when opened via `file://`. Keep
`natural-earth.js` and `natural-earth-data.js` beside `index.html` when copying
the standalone app. Mapnik and Satellite remain available in the map selector.

The map includes country/state borders and city labels, with fewer details at
city zoom than a street map. Data is Natural Earth v5.1.2, public domain:
https://www.naturalearthdata.com/about/terms-of-use/ . Regenerate the data with
`python tools/build_natural_earth.py` from the project root. The standalone
builder copies the bundled map assets automatically.

The proxy runs on Google's infrastructure, so no local server is needed. Requests
use the deploying account's [Apps Script quotas](https://developers.google.com/apps-script/guides/services/quotas).
With anonymous access enabled, the endpoint is publicly callable.

---

## Step 1: Create the Google Apps Script

1. Go to **[script.google.com](https://script.google.com/)** and sign in with your Google Account.
2. Click **New Project** in the upper left corner.
3. Replace any code in the editor with the following script:

```javascript
function doGet(e) {
  const url = e.parameter.url;
  if (!url) {
    return ContentService.createTextOutput("Error: url parameter is required").setMimeType(ContentService.MimeType.TEXT);
  }
  
  try {
    const response = UrlFetchApp.fetch(url, {
      method: "get",
      headers: {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://mrms.nssl.noaa.gov/qvs/product_viewer/index.php"
      },
      muteHttpExceptions: true
    });
    
    const bytes = response.getContent();
    // Return base64 encoded bytes (standard way to handle binary images in Apps Script)
    return ContentService.createTextOutput(Utilities.base64Encode(bytes))
      .setMimeType(ContentService.MimeType.TEXT);
  } catch (err) {
    return ContentService.createTextOutput("Error: " + err.toString()).setMimeType(ContentService.MimeType.TEXT);
  }
}
```
4. Click the **Save** icon (floppy disk) or press `Cmd+S` / `Ctrl+S`.

---

## Step 2: Deploy and authorize the script

1. Click the blue **Deploy** button in the top right and select **New deployment**.
2. Click the gear icon next to "Select type" and choose **Web app**.
3. Fill out the configuration fields:
   * **Description**: `MRMS Standalone Radar Proxy`
   * **Execute as**: `Me (your-email@gmail.com)`
   * **Who has access**: **`Anyone`** (anonymous access, not `Anyone with Google account`).
4. Click **Deploy**.
5. If prompted, select **Authorize access**, choose the deploying account, and
   review and approve the external-request permission. Google may show an
   unverified-app notice for a personal script; see the [authorization guide](https://developers.google.com/apps-script/guides/services/authorization).
6. Copy the generated **Web app URL** (it should look like `https://script.google.com/macros/s/XXXXXX/exec`).
   Use the deployed `/exec` URL, not the editor-only `/dev` test URL.

If your managed Google Workspace account does not offer anonymous access, this
deployment cannot provide the intended login-free proxy. Check the account's
deployment policy with its administrator.

---

## Step 3: Insert your URL

Open `standalone/pure_js/index.html` and search for `GOOGLE_SCRIPT_PROXY`:

```javascript
const GOOGLE_SCRIPT_PROXY = "https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec";
```

Replace `https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec` with your copied web app URL, save the file, and you are ready to go!

## Check access and troubleshoot authorization

1. Open your deployment's `/exec` URL in a signed-out/private browser window.
   Without a `url` parameter, the sample script should return
   `Error: url parameter is required`. This confirms anonymous access to the
   handler, but does not yet test its outbound-request permission.
2. Test a legend through the proxy by appending the following query to your
   `/exec` URL:

   ```text
   ?url=https%3A%2F%2Fmrms.nssl.noaa.gov%2Fqvs%2Fproduct_viewer%2Fshared%2Ffetch_svg_legend_via_config.php%3Fweb_resources_dir%3D%2Fvar%2Fwww%2Fhtml%2Fqvs%2Fproduct_viewer%2Fresources%2F%26config_name%3Dtitle_and_legend_config.txt%26product%3DM3DL13
   ```

   The expected result is base64 text that decodes to SVG, rather than a Google
   login/consent page or `Error: ...`. The proxy returns base64 for both SVG
   legends and PNG radar frames.
3. Open `index.html`, confirm radar and the legend load, and play a loop. In
   browser developer tools, inspect requests to `script.google.com` and the
   redirected `script.googleusercontent.com` response if loading fails.

- **Google sign-in, consent, or access-denied page:** check **Execute as: Me**,
  anonymous **Anyone** access, and the `/exec` URL. A successful owner-only test
  does not establish anonymous access. Signing in in another tab is not a
  substitute for configuring the deployed endpoint for background requests.
- **Authorization required or revoked:** the owner must authorize the script
  again in Apps Script. Changes that add scopes can require new consent; see
  Google's [authorization guide](https://developers.google.com/apps-script/guides/services/authorization).
  After changing script code, publish a new version through **Deploy → Manage
  deployments**; saving in the editor alone does not update the deployed version.
- **Base64/decode errors, non-PNG responses, or `Radar proxy request failed`:**
  inspect the response body. The HTML expects base64 bytes, so a Google HTML
  error page or the sample proxy's plain-text error cannot be rendered as radar.
- **Quota errors:** review the deployment's Apps Script execution log and account
  quotas. Loop playback shares the same owner's request allowance.

## Retrieval and loops

The standalone page keeps using the configured Apps Script proxy; no Python server or additional availability service is required.

- Historical requests fetch exactly the selected UTC timestamp. Blank frames return unavailable instead of silently substituting earlier images.
- Live requests start at the existing product latency allowance and search at most six product intervals backward. Products retain their configured 2-, 5-, or 60-minute resolution.
- Each successful request supplies both availability and the playback image. Exact renders and in-flight requests are shared across still images and loops, keyed by the full render URL (including product, time, map center, and zoom).
- The in-memory cache holds up to 80 results or 32 MB of image data. Blank results expire after 20 seconds; transport and invalid-image failures are not cached. Reloading the page clears the cache.
- Radar requests have a 20-second timeout and a shared concurrency limit of three. PNG signature, decoding, fixed 920×630 dimensions, and the existing 4 KB minimum are checked before displaying a frame.
- The 18-frame loop begins after three available frames load, then fills in older frames. Historical frames use a stable four-minute grid for two-minute products, or the product interval for slower products. The newest frame can be between grid points.
- Refresh replaces the entire rolling window while reusing cached images. The slider and navigation buttons follow actual loaded timestamps during playback and after pausing. Missing frames are skipped and counted separately from failed requests.
- Legends are cached per product. Stale view requests cannot overwrite a newer selection.

Run the standalone regression checks from the project root with Node.js (no additional packages or network required):

```bash
node --test standalone/pure_js/tests/*.test.cjs
```

The tests mock proxy responses and image decoding, including 90 scheduled refreshes over three simulated hours across midnight. Every refresh checks all 18 timestamps and their corresponding image data, guarding against a frozen history with only the newest frame updating. Real image decoding and the proxy connection should also be checked by opening `index.html` in a browser and playing a loop.
