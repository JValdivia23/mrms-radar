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
