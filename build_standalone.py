#!/usr/bin/env python3
import os
import shutil
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_PATH = os.path.join(SCRIPT_DIR, "mrms_core.py")
CLI_PATH = os.path.join(SCRIPT_DIR, "mrms_cli.py")
PRODUCTS_PATH = os.path.join(SCRIPT_DIR, "mrms_products.json")
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "static", "index.template.html")
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "static", "manifest.json")

STANDALONE_DIR = os.path.join(SCRIPT_DIR, "standalone")
WASM_DIR = os.path.join(STANDALONE_DIR, "wasm_console")
PURE_JS_DIR = os.path.join(STANDALONE_DIR, "pure_js")

def load_source_files():
    with open(CORE_PATH, "r", encoding="utf-8") as f:
        core_code = f.read()
    with open(CLI_PATH, "r", encoding="utf-8") as f:
        cli_code = f.read()
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        products_json = f.read()
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template_html = f.read()
    return core_code, cli_code, products_json, template_html

def build_wasm_console(core_code, cli_code, products_json, template_html):
    # CSS Injection
    css_injection = """
  /* ── Terminal Panel ── */
  .terminal-panel {
    position: fixed;
    bottom: calc(max(16px, env(safe-area-inset-bottom)) + 120px);
    right: 12px;
    width: min(500px, 90vw);
    height: 300px;
    background: rgba(10, 12, 16, 0.72);
    border: 1px solid var(--panel-border);
    border-radius: var(--radius);
    backdrop-filter: blur(var(--blur));
    -webkit-backdrop-filter: blur(var(--blur));
    z-index: 100;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transform: translateY(20px);
    opacity: 0;
    pointer-events: none;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  }
  .terminal-panel.open {
    transform: translateY(0);
    opacity: 1;
    pointer-events: auto;
  }
  .terminal-header {
    background: rgba(255, 255, 255, 0.03);
    border-bottom: 1px solid var(--panel-border);
    padding: 8px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
  .terminal-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .terminal-title .status-dot {
    width: 6px;
    height: 6px;
    background-color: var(--danger);
    border-radius: 50%;
  }
  .terminal-title .status-dot.ready {
    background-color: #58a6ff;
    box-shadow: 0 0 8px rgba(88, 166, 255, 0.6);
  }
  .terminal-title .status-dot.loading {
    background-color: #f0c674;
    animation: pulse 1.5s ease-in-out infinite;
  }
  .terminal-close {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.15s;
  }
  .terminal-close:hover {
    color: var(--text);
  }
  #terminal-body {
    flex: 1;
    padding: 8px;
    overflow: hidden;
  }
  .terminal-toggle-btn {
    position: fixed;
    right: 12px;
    bottom: calc(max(16px, env(safe-area-inset-bottom)) + 70px);
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: 1px solid var(--panel-border);
    background: var(--panel-bg);
    backdrop-filter: blur(var(--blur));
    -webkit-backdrop-filter: blur(var(--blur));
    color: var(--text);
    font-size: 15px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    transition: background 0.15s;
  }
  .terminal-toggle-btn:hover {
    background: rgba(255, 255, 255, 0.08);
  }
</style>"""

    # HTML Injection
    html_injection = """
<!-- Terminal Panel Overlay -->
<button class="terminal-toggle-btn" id="terminalToggleBtn" onclick="toggleTerminal()" title="Toggle Console">>_</button>
<div class="terminal-panel" id="terminalPanel">
  <div class="terminal-header">
    <div class="terminal-title">
      <div class="status-dot" id="terminalStatusDot"></div>
      <span id="terminalStatusText">Console</span>
    </div>
    <button class="terminal-close" onclick="toggleTerminal()">✕</button>
  </div>
  <div id="terminal-body"></div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>"""

    # Javascript / Pyodide Injection
    js_injection = """
// ═══════════════════════════════════════════════════════════════════════════
// Standalone CORS Proxy & API Interceptors (Serverless Mode)
// ═══════════════════════════════════════════════════════════════════════════
const categoriesCatalog = __PRODUCTS_JSON__;

const fileCatalog = {
  "mrms_products.json": __PRODUCTS_JSON_REPR__,
  "mrms_core.py": __CORE_CODE_REPR__,
  "mrms_cli.py": __CLI_CODE_REPR__
};

function resolveCorsProxyUrl() {
  const select = document.getElementById('proxy-select') ? document.getElementById('proxy-select').value : 'allorigins';
  if (select === 'none') return '';
  return document.getElementById('cors-proxy') ? document.getElementById('cors-proxy').value : 'https://api.allorigins.win/raw?url=';
}

function getProductMetadata(productCode) {
  for (const cat of categoriesCatalog) {
    for (const prod of cat.products) {
      if (prod.code === productCode) {
        return {
          code: prod.code,
          name: prod.name,
          min_res_minutes: prod.min_res_minutes || 2,
          category_code: cat.code,
          category_name: cat.name,
          has_levels: cat.has_levels
        };
      }
    }
  }
  return null;
}

function roundToMrmsWindow(date, resMins) {
  const roundedMinutes = Math.floor(date.getUTCMinutes() / resMins) * resMins;
  return new Date(Date.UTC(
    date.getUTCFullYear(),
    date.getUTCMonth(),
    date.getUTCDate(),
    date.getUTCHours(),
    roundedMinutes,
    0, 0
  ));
}

function resolveUrl(url) {
  const proxy = resolveCorsProxyUrl();
  
  if (url.startsWith('/api/legend')) {
    const params = new URLSearchParams(url.split('?')[1]);
    const product = params.get('product') || 'M3DL13';
    const noaaUrl = `https://mrms.nssl.noaa.gov/qvs/product_viewer/shared/fetch_svg_legend_via_config.php?web_resources_dir=/var/www/html/qvs/product_viewer/resources/&config_name=title_and_legend_config.txt&product=${product}`;
    return proxy ? proxy + encodeURIComponent(noaaUrl) : noaaUrl;
  }
  
  return url;
}

async function handleRadarFetch(path, init) {
  const params = new URLSearchParams(path.split('?')[1]);
  const productCode = params.get('product') || 'M3DL13';
  const meta = getProductMetadata(productCode);
  const resMins = meta ? meta.min_res_minutes : 2;
  
  // Resolve base time
  let targetDate;
  const timeVal = params.get('time');
  if (timeVal) {
    targetDate = roundToMrmsWindow(new Date(timeVal + 'Z'), resMins);
  } else {
    // Default to now, round, and apply latency offset
    let now = new Date();
    let rounded = roundToMrmsWindow(now, resMins);
    const latencyMins = Math.max(4, resMins * 2);
    rounded.setMinutes(rounded.getMinutes() - latencyMins);
    targetDate = rounded;
  }
  
  const clon = params.get('lon') || S.lon;
  const clat = params.get('lat') || S.lat;
  const zoom = params.get('zoom') || S.zoom;
  const width = params.get('width') || 920;
  const height = params.get('height') || 630;
  
  const proxy = resolveCorsProxyUrl();
  let lastResponse = null;
  let finalDate = new Date(targetDate);
  
  // Try up to 6 times, stepping back by 2 minutes and retrying
  for (let attempt = 0; attempt < 6; attempt++) {
    const p = new URLSearchParams({
      mode: "run",
      cpp_exec_dir: "/home/metop/web/specific/opv/",
      web_resources_dir: "/var/www/html/qvs/product_viewer/resources/",
      prod_root: productCode,
      qperate_pal_option: 0,
      qpe_pal_option: 0,
      clon: clon,
      clat: clat,
      zoom: zoom,
      width: width,
      height: height,
      year: finalDate.getUTCFullYear(),
      month: finalDate.getUTCMonth() + 1,
      day: finalDate.getUTCDate(),
      hour: finalDate.getUTCHours(),
      minute: finalDate.getUTCMinutes()
    });
    
    const noaaUrl = 'https://mrms.nssl.noaa.gov/qvs/product_viewer/local/render_multi_domain_product_layer.php?' + p;
    const requestUrl = proxy ? proxy + encodeURIComponent(noaaUrl) : noaaUrl;
    
    try {
      const response = await originalFetch(requestUrl, init);
      if (response.ok) {
        const blob = await response.blob();
        if (blob.size >= 4000 || attempt === 5) {
          const timestampStr = `${finalDate.getUTCFullYear()}-${String(finalDate.getUTCMonth() + 1).padStart(2,'0')}-${String(finalDate.getUTCDate()).padStart(2,'0')}T${String(finalDate.getUTCHours()).padStart(2,'0')}:${String(finalDate.getUTCMinutes()).padStart(2,'0')}:00`;
          
          const headers = new Headers(response.headers);
          headers.set('X-MRMS-Timestamp', timestampStr);
          headers.set('Access-Control-Expose-Headers', 'X-MRMS-Timestamp');
          
          return new Response(blob, {
            status: response.status,
            statusText: response.statusText,
            headers: headers
          });
        }
      }
      lastResponse = response;
    } catch (err) {
      console.warn(`Attempt ${attempt} failed:`, err);
    }
    
    finalDate.setMinutes(finalDate.getMinutes() - 2);
  }
  
  if (lastResponse) return lastResponse;
  throw new Error("Failed to fetch radar image after 6 attempts");
}

// Hijack fetch globally to intercept local API requests and redirect via CORS proxy
let isStandalone = true;
const originalFetch = window.fetch.bind(window);
const detectPromise = (async () => {
  if (window.location.protocol === 'file:') {
    isStandalone = true;
    return;
  }
  try {
    const r = await originalFetch('/api/products');
    if (r.ok) {
      isStandalone = false;
    }
  } catch (e) {
    isStandalone = true;
  }
})();

window.fetch = async function(input, init) {
  await detectPromise;
  if (!isStandalone) {
    return originalFetch(input, init);
  }
  let url = '';
  if (typeof input === 'string') {
    url = input;
  } else if (input instanceof URL) {
    url = input.href;
  } else if (input && typeof input === 'object') {
    url = input.url || '';
  }
  
  if (url) {
    let path = '';
    try {
      const parsed = new URL(url, window.location.origin);
      path = parsed.pathname + parsed.search;
    } catch(e) {
      path = url;
    }
    
    if (path.startsWith('/api/products')) {
      return Promise.resolve(new Response(JSON.stringify(categoriesCatalog), {
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    
    if (path.startsWith('/api/timezone')) {
      const tzName = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      const now = new Date();
      const abbr = now.toLocaleDateString('en-US', { day: 'numeric', timeZoneName: 'short' }).split(', ')[1] || 'UTC';
      const offset = -now.getTimezoneOffset() / 60;
      const localTime = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
      
      return Promise.resolve(new Response(JSON.stringify({
        tz: tzName,
        abbr: abbr,
        offset_hours: offset,
        local_time: localTime
      }), {
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    
    if (path.startsWith('/api/radar')) {
      return handleRadarFetch(path, init);
    }
    
    if (path.startsWith('/api/legend')) {
      const resolved = resolveUrl(path);
      if (typeof input === 'string') {
        input = resolved;
      } else if (input instanceof URL) {
        input = new URL(resolved);
      } else if (input && typeof input === 'object') {
        return originalFetch(resolved, init);
      }
    }
  }
  
  return originalFetch(input, init);
};

// ═══════════════════════════════════════════════════════════════════════════
// Terminal & Pyodide WASM Integration
// ═══════════════════════════════════════════════════════════════════════════
let termInstance = null;
let pyodideInstance = null;
let terminalOpen = false;
let pyodideLoading = false;
let currentTermLine = '';

// Expose handlers globally for Python bindings
window.termWrite = (data) => {
  if (termInstance) termInstance.write(data.replace(/\\n/g, '\\r\\n'));
};

window.getCorsProxy = resolveCorsProxyUrl;

window.onPyodideFileGenerated = (filename, bytes) => {
  if (filename.startsWith('radar_') && filename.endsWith('.png')) {
    const blob = new Blob([bytes], { type: 'image/png' });
    const localUrl = URL.createObjectURL(blob);
    
    updateRadarOverlay(localUrl);
    
    try {
      const metaJson = window.pyodideInstance.runPython(`
import json
from mrms_core import get_product_metadata
meta = get_product_metadata(img.product) if 'img' in globals() else None
json.dumps({
    "product": img.product if 'img' in globals() else "",
    "timestamp": img.timestamp if 'img' in globals() else "",
    "lat": img.lat if 'img' in globals() else 0.0,
    "lon": img.lon if 'img' in globals() else 0.0,
    "zoom": img.zoom if 'img' in globals() else 7,
    "product_name": meta["name"] if meta else ""
})
      `);
      const meta = JSON.parse(metaJson);
      if (meta.product) {
        S.zoom = meta.zoom;
        S.lat = meta.lat;
        S.lon = meta.lon;
        
        if (leafletMap) {
          leafletMap.setView([S.lat, S.lon], S.zoom);
        }
        
        if ($('productBadge')) {
          $('productBadge').innerHTML = `<strong>${meta.product_name || meta.product}</strong> (CLI)`;
        }
        
        updateTimeDisplay(meta.timestamp);
      }
    } catch (e) {
      console.error("Failed to sync CLI metadata to Leaflet UI:", e);
    }
    
    if (termInstance) {
      termInstance.write('\\r\\n\\x1b[1;32m[Info] Map dynamically updated from CLI output file: ' + filename + '\\x1b[0m\\r\\n');
    }
  } else {
    const blob = new Blob([bytes], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
  }
};

function toggleTerminal() {
  terminalOpen = !terminalOpen;
  const panel = $('terminalPanel');
  if (terminalOpen) {
    panel.classList.add('open');
    if (!termInstance) {
      initTerminal();
    } else {
      termInstance.focus();
    }
  } else {
    panel.classList.remove('open');
  }
}

function initTerminal() {
  if (pyodideLoading) return;
  pyodideLoading = true;
  
  const dot = $('terminalStatusDot');
  const text = $('terminalStatusText');
  dot.className = 'status-dot loading';
  text.innerText = "Loading WASM...";
  
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css';
  document.head.appendChild(link);
  
  const scriptXterm = document.createElement('script');
  scriptXterm.src = 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js';
  document.head.appendChild(scriptXterm);
  
  const scriptPyodide = document.createElement('script');
  scriptPyodide.src = 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js';
  document.head.appendChild(scriptPyodide);
  
  scriptPyodide.onload = async () => {
    if (typeof Terminal === 'undefined') {
      await new Promise(resolve => scriptXterm.onload = resolve);
    }
    
    termInstance = new Terminal({
      cursorBlink: true,
      fontFamily: 'Fira Code, Courier New, monospace',
      fontSize: 12,
      theme: {
        background: '#0d1117',
        foreground: '#c9d1d9',
        cursor: '#58a6ff'
      }
    });
    termInstance.open(document.getElementById('terminal-body'));
    termInstance.writeln("=== MRMS Browser Console ===");
    termInstance.writeln("Loading Python WebAssembly runtime...");
    
    try {
      window.pyodideInstance = await loadPyodide();
      
      text.innerText = "Installing Packages...";
      termInstance.writeln("Installing dependencies (click, requests, pyodide-http)...");
      
      await window.pyodideInstance.loadPackage(["requests", "micropip"]);
      const micropip = window.pyodideInstance.pyimport("micropip");
      await micropip.install("click");
      await micropip.install("pyodide-http");
      
      text.innerText = "Syncing Codebase...";
      termInstance.writeln("Mounting application files in virtual FS...");
      
      for (const [filename, content] of Object.entries(fileCatalog)) {
        window.pyodideInstance.FS.writeFile(filename, content);
      }
      
      termInstance.writeln("Setting up network bridges...");
      
      await window.pyodideInstance.runPythonAsync(`
import pyodide_http
pyodide_http.patch_all()

import requests
original_get = requests.get

def local_proxy_get(url, *args, **kwargs):
    import js
    proxy = js.getCorsProxy()
    if proxy and "mrms.nssl.noaa.gov" in url:
        url = proxy + url
    kwargs['verify'] = False
    return original_get(url, *args, **kwargs)

requests.get = local_proxy_get
      `);
      
      dot.className = 'status-dot ready';
      text.innerText = "Console Ready";
      
      termInstance.clear();
      termInstance.writeln("=== MRMS Interactive Web Console ===");
      termInstance.writeln("Type CLI commands directly. Image outputs will update the Leaflet map!");
      termInstance.writeln("Type \\x1b[1;33mmrms fetch --help\\x1b[0m or \\x1b[1;33mmrms products\\x1b[0m to list options.");
      showTermPrompt();
      
      termInstance.onData(data => {
        const code = data.charCodeAt(0);
        if (code === 13) {
          termInstance.write('\\r\\n');
          handleTermCommand(currentTermLine);
          currentTermLine = '';
        } else if (code === 127 || code === 8) {
          if (currentTermLine.length > 0) {
            currentTermLine = currentTermLine.slice(0, -1);
            termInstance.write('\b \b');
          }
        } else if (code === 3) {
          termInstance.write('^C\\r\\n');
          currentTermLine = '';
          showTermPrompt();
        } else if (code >= 32) {
          currentTermLine += data;
          termInstance.write(data);
        }
      });
      termInstance.focus();
      
    } catch (e) {
      dot.className = 'status-dot';
      text.innerText = "Load Failed";
      termInstance.writeln("\\x1b[1;31mInitialization Error: " + e.message + "\\x1b[0m");
    }
  };
}

function showTermPrompt() {
  if (termInstance) termInstance.write('\\r\\nmrms> ');
}

async function handleTermCommand(cmdLine) {
  const trimmed = cmdLine.trim();
  if (!trimmed) {
    showTermPrompt();
    return;
  }
  
  const args = trimmed.split(/\\s+/);
  const cmdName = args[0];
  
  if (cmdName === 'mrms' || (cmdName === 'python' && args[1] === 'mrms_cli.py')) {
    const finalArgs = cmdName === 'mrms' ? args.slice(1) : args.slice(2);
    window.pyodideInstance.globals.set("cli_args", finalArgs);
    
    try {
      termInstance.write('\\x1b[1;30mRunning CLI command...\\x1b[0m\\r\\n');
      
      await window.pyodideInstance.runPythonAsync(`
import sys
from mrms_cli import cli

old_stdout = sys.stdout
old_stderr = sys.stderr

class JSWriter:
    def write(self, data):
        import js
        js.termWrite(data)
    def flush(self):
        pass

sys.stdout = JSWriter()
sys.stderr = JSWriter()

try:
    args_list = list(cli_args)
    global img
    cli.main(args=args_list, standalone_mode=False)
except Exception as e:
    sys.stderr.write(f"Error: {e}\\\\n")
finally:
    sys.stdout = old_stdout
    sys.stderr = old_stderr
      `);
      
      await window.pyodideInstance.runPythonAsync(`
import os
import js
files = os.listdir('.')
for f in files:
    if f.startswith('radar_') and f.endswith('.png'):
        try:
            with open(f, 'rb') as file_obj:
                data = file_obj.read()
                js.onPyodideFileGenerated(f, bytes(data))
            os.remove(f)
        except Exception as e:
            js.termWrite(f"Map Redraw Error: {e}\\\\n")
      `);
      
    } catch (e) {
      termInstance.writeln("\\x1b[1;31mException: " + e.message + "\\x1b[0m");
    }
  } else if (cmdName === 'clear') {
    termInstance.clear();
  } else if (cmdName === 'help') {
    termInstance.writeln("Available commands:");
    termInstance.writeln("  \\x1b[1;33mmrms fetch [options]\\x1b[0m         - Fetch a radar image (updates the Leaflet map)");
    termInstance.writeln("  \\x1b[1;33mmrms products [options]\\x1b[0m      - List categories and products");
    termInstance.writeln("  \\x1b[1;33mclear\\x1b[0m                        - Clear terminal screen");
    termInstance.writeln("  \\x1b[1;33mhelp\\x1b[0m                         - Show this help message");
  } else {
    termInstance.writeln(`command not found: ${cmdName}`);
  }
  showTermPrompt();
}

// ═══════════════════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════════════════
window.addEventListener('resize', scaleLeafletMap);"""

    # Replace variables in JS
    js_resolved = js_injection.replace("__PRODUCTS_JSON__", products_json)
    js_resolved = js_resolved.replace("__PRODUCTS_JSON_REPR__", repr(products_json))
    js_resolved = js_resolved.replace("__CORE_CODE_REPR__", repr(core_code))
    js_resolved = js_resolved.replace("__CLI_CODE_REPR__", repr(cli_code))

    # Compile HTML
    output_html = template_html.replace("</style>", css_injection)
    output_html = output_html.replace('<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>', html_injection)
    output_html = output_html.replace("window.addEventListener('resize', scaleLeafletMap);", js_resolved)
    
    os.makedirs(WASM_DIR, exist_ok=True)
    out_path = os.path.join(WASM_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output_html)
    print(f"Generated: {out_path}")

def build_pure_js(products_json, template_html):
    # Javascript fetch interceptor pointing to Google Apps Script CORS Proxy
    js_interceptor = """
// ═══════════════════════════════════════════════════════════════════════════
// Standalone Google Apps Script CORS Proxy Interceptor
// ═══════════════════════════════════════════════════════════════════════════
const categoriesCatalog = __PRODUCTS_JSON__;
const GOOGLE_SCRIPT_PROXY = "https://script.google.com/macros/s/AKfycbw_v3dfB0B5U2OiAPrKcBMy-2k2FsM9tfEK7XWR3lp4MXKbbhNEVxzPo4cY0oUlXTTM/exec";

function getProductMetadata(productCode) {
  for (const cat of categoriesCatalog) {
    for (const prod of cat.products) {
      if (prod.code === productCode) {
        return {
          code: prod.code,
          name: prod.name,
          min_res_minutes: prod.min_res_minutes || 2,
          category_code: cat.code,
          category_name: cat.name,
          has_levels: cat.has_levels
        };
      }
    }
  }
  return null;
}

function roundToMrmsWindow(date, resMins) {
  const roundedMinutes = Math.floor(date.getUTCMinutes() / resMins) * resMins;
  return new Date(Date.UTC(
    date.getUTCFullYear(),
    date.getUTCMonth(),
    date.getUTCDate(),
    date.getUTCHours(),
    roundedMinutes,
    0, 0
  ));
}

async function handleRadarFetch(path, init) {
  const params = new URLSearchParams(path.split('?')[1]);
  const productCode = params.get('product') || 'M3DL13';
  const meta = getProductMetadata(productCode);
  const resMins = meta ? meta.min_res_minutes : 2;
  
  let targetDate;
  const timeVal = params.get('time');
  if (timeVal) {
    targetDate = roundToMrmsWindow(new Date(timeVal + 'Z'), resMins);
  } else {
    let now = new Date();
    let rounded = roundToMrmsWindow(now, resMins);
    const latencyMins = Math.max(4, resMins * 2);
    rounded.setMinutes(rounded.getMinutes() - latencyMins);
    targetDate = rounded;
  }
  
  const clon = params.get('lon') || S.lon;
  const clat = params.get('lat') || S.lat;
  const zoom = params.get('zoom') || S.zoom;
  const width = params.get('width') || 920;
  const height = params.get('height') || 630;
  
  let lastResponse = null;
  let finalDate = new Date(targetDate);
  
  // Try up to 6 times, stepping back by 2 minutes and retrying
  for (let attempt = 0; attempt < 6; attempt++) {
    const p = new URLSearchParams({
      mode: "run",
      cpp_exec_dir: "/home/metop/web/specific/opv/",
      web_resources_dir: "/var/www/html/qvs/product_viewer/resources/",
      prod_root: productCode,
      qperate_pal_option: 0,
      qpe_pal_option: 0,
      clon: clon,
      clat: clat,
      zoom: zoom,
      width: width,
      height: height,
      year: finalDate.getUTCFullYear(),
      month: finalDate.getUTCMonth() + 1,
      day: finalDate.getUTCDate(),
      hour: finalDate.getUTCHours(),
      minute: finalDate.getUTCMinutes()
    });
    
    const noaaUrl = 'https://mrms.nssl.noaa.gov/qvs/product_viewer/local/render_multi_domain_product_layer.php?' + p;
    
    // Redirect through Google Apps Script Proxy
    const requestUrl = GOOGLE_SCRIPT_PROXY + '?url=' + encodeURIComponent(noaaUrl);
    
    try {
      const response = await originalFetch(requestUrl, init);
      if (response.ok) {
        const base64Text = await response.text();
        
        // Convert Base64 back to Blob so it integrates cleanly with native fetch API
        const binaryString = window.atob(base64Text);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], {type: "image/png"});
        
        if (blob.size >= 4000 || attempt === 5) {
          const timestampStr = `${finalDate.getUTCFullYear()}-${String(finalDate.getUTCMonth() + 1).padStart(2,'0')}-${String(finalDate.getUTCDate()).padStart(2,'0')}T${String(finalDate.getUTCHours()).padStart(2,'0')}:${String(finalDate.getUTCMinutes()).padStart(2,'0')}:00`;
          
          const headers = new Headers();
          headers.set('Content-Type', 'image/png');
          headers.set('X-MRMS-Timestamp', timestampStr);
          headers.set('Access-Control-Expose-Headers', 'X-MRMS-Timestamp');
          
          return new Response(blob, {
            status: 200,
            headers: headers
          });
        }
      }
      lastResponse = response;
    } catch (err) {
      console.warn(`Attempt ${attempt} failed:`, err);
    }
    
    finalDate.setMinutes(finalDate.getMinutes() - 2);
  }
  
  if (lastResponse) return lastResponse;
  throw new Error("Failed to fetch radar image after 6 attempts");
}

// Hijack fetch globally to intercept local API requests and redirect via Google Apps Script CORS proxy
let isStandalone = true;
const originalFetch = window.fetch.bind(window);
const detectPromise = (async () => {
  if (window.location.protocol === 'file:') {
    isStandalone = true;
    return;
  }
  try {
    const r = await originalFetch('/api/products');
    if (r.ok) {
      isStandalone = false;
    }
  } catch (e) {
    isStandalone = true;
  }
})();

window.fetch = async function(input, init) {
  await detectPromise;
  if (!isStandalone) {
    return originalFetch(input, init);
  }
  let url = '';
  if (typeof input === 'string') {
    url = input;
  } else if (input instanceof URL) {
    url = input.href;
  } else if (input && typeof input === 'object') {
    url = input.url || '';
  }
  
  if (url) {
    let path = '';
    try {
      const parsed = new URL(url, window.location.origin);
      path = parsed.pathname + parsed.search;
    } catch(e) {
      path = url;
    }
    
    if (path.startsWith('/api/products')) {
      return Promise.resolve(new Response(JSON.stringify(categoriesCatalog), {
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    
    if (path.startsWith('/api/timezone')) {
      const tzName = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      const now = new Date();
      const abbr = now.toLocaleDateString('en-US', { day: 'numeric', timeZoneName: 'short' }).split(', ')[1] || 'UTC';
      const offset = -now.getTimezoneOffset() / 60;
      const localTime = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
      
      return Promise.resolve(new Response(JSON.stringify({
        tz: tzName,
        abbr: abbr,
        offset_hours: offset,
        local_time: localTime
      }), {
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    
    if (path.startsWith('/api/radar')) {
      return handleRadarFetch(path, init);
    }
    
    if (path.startsWith('/api/legend')) {
      const params = new URLSearchParams(path.split('?')[1]);
      const product = params.get('product') || 'M3DL13';
      const noaaUrl = `https://mrms.nssl.noaa.gov/qvs/product_viewer/shared/fetch_svg_legend_via_config.php?web_resources_dir=/var/www/html/qvs/product_viewer/resources/&config_name=title_and_legend_config.txt&product=${product}`;
      const requestUrl = GOOGLE_SCRIPT_PROXY + '?url=' + encodeURIComponent(noaaUrl);
      return originalFetch(requestUrl, init).then(async response => {
        if (!response.ok) return response;
        try {
          const base64Text = await response.text();
          const decodedSvg = window.atob(base64Text);
          return new Response(decodedSvg, {
            status: 200,
            headers: { 'Content-Type': 'image/svg+xml' }
          });
        } catch (err) {
          console.error("Failed to decode legend SVG:", err);
          return response;
        }
      });
    }
  }
  
  return originalFetch(input, init);
};

window.addEventListener('resize', scaleLeafletMap);"""

    js_resolved = js_interceptor.replace("__PRODUCTS_JSON__", products_json)
    
    # Inject fetch hijack
    output_html = template_html.replace("window.addEventListener('resize', scaleLeafletMap);", js_resolved)
    
    os.makedirs(PURE_JS_DIR, exist_ok=True)
    out_path = os.path.join(PURE_JS_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output_html)
    print(f"Generated: {out_path}")

def main():
    print("Loading source files...")
    core_code, cli_code, products_json, template_html = load_source_files()
    
    print("Compiling WASM Console version...")
    build_wasm_console(core_code, cli_code, products_json, template_html)
    
    print("Compiling Lightweight Pure JS version...")
    build_pure_js(products_json, template_html)
    
    print("Copying manifest files...")
    shutil.copy(MANIFEST_PATH, os.path.join(WASM_DIR, "manifest.json"))
    shutil.copy(MANIFEST_PATH, os.path.join(PURE_JS_DIR, "manifest.json"))
    
    print("\\nStandalone files successfully compiled under: standalone/")

if __name__ == "__main__":
    main()
