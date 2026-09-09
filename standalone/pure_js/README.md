# Google Apps Script CORS Proxy Setup (Lightweight Mode)

To run the Lightweight Pure JS standalone page, you need to configure your own Google Apps Script to act as a private CORS proxy. This requires no servers, is completely free, and will bypass CORS restrictions safely.

---

### Step 1: Create the Google Apps Script

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

### Step 2: Deploy the Script

1. Click the blue **Deploy** button in the top right and select **New deployment**.
2. Click the gear icon next to "Select type" and choose **Web app**.
3. Fill out the configuration fields:
   * **Description**: `MRMS Standalone Radar Proxy`
   * **Execute as**: `Me (your-email@gmail.com)`
   * **Who has access**: **`Anyone`** (This is crucial so the browser can contact it).
4. Click **Deploy**.
5. Copy the generated **Web app URL** (it should look like `https://script.google.com/macros/s/XXXXXX/exec`).

---

### Step 3: Insert Your URL

Open your compiled `standalone/pure_js/index.html` file, locate line 2616 (or search for `GOOGLE_SCRIPT_PROXY`):

```javascript
const GOOGLE_SCRIPT_PROXY = "https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec";
```

Replace `https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec` with your copied web app URL, save the file, and you are ready to go!

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
node --test standalone/pure_js/tests/retrieval.test.cjs
```

The tests mock proxy responses and image decoding, including 90 scheduled refreshes over three simulated hours across midnight. Every refresh checks all 18 timestamps and their corresponding image data, guarding against a frozen history with only the newest frame updating. Real image decoding and the proxy connection should also be checked by opening `index.html` in a browser and playing a loop.
