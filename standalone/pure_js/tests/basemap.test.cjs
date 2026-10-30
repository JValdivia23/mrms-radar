const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../..');

test('every entry point ships local basemap scripts and removes the keyed provider', () => {
  for (const page of ['static/index.html', 'static/index.template.html',
    'standalone/pure_js/index.html', 'standalone/wasm_console/index.html']) {
    const html = fs.readFileSync(path.join(root, page), 'utf8');
    assert.doesNotMatch(html, /cartocdn/);
    for (const asset of ['natural-earth.js', 'natural-earth-data.js']) {
      const src = html.match(new RegExp('<script src="([^"]*' + asset.replaceAll('.', '\\.') + ')"'))[1];
      const resolved = src.startsWith('/static/') ? path.join(root, src) : path.join(root, path.dirname(page), src);
      assert.equal(fs.existsSync(resolved), true, resolved);
      assert.equal(fs.readFileSync(resolved, 'utf8'), fs.readFileSync(path.join(root, 'static', asset), 'utf8'));
    }
    for (const script of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(script[1]);
  }
});

test('bundled geography renders without network and cleans up when switching maps', () => {
  const context = {window: {}, document: {createElement: () => ({})}};
  vm.createContext(context);
  for (const asset of ['natural-earth-data.js', 'natural-earth.js']) {
    vm.runInContext(fs.readFileSync(path.join(root, 'static', asset), 'utf8'), context);
  }
  const data = context.window.MRMSNaturalEarthData;
  assert.equal(data.countries.features.length, 177);
  assert.ok(data.states.features.length > 250);
  assert.ok(data.places.some(p => p[0] === 'Denver'));
  const layers = new Set(), listeners = new Map(), classes = new Set();
  const map = {
    getPane: () => null, createPane: () => ({style: {}}),
    getContainer: () => ({classList: {add: c => classes.add(c), remove: c => classes.delete(c)}}),
    getZoom: () => 7,
    getBounds: () => ({contains: ([lat, lon]) => lat > 38 && lat < 42 && lon > -107 && lon < -103}),
    latLngToContainerPoint: ([lat, lon]) => ({x: (lon + 107) * 200, y: (42 - lat) * 200}),
    on: (event, handler) => listeners.set(event, handler),
    off: (event, handler) => {assert.equal(listeners.get(event), handler); listeners.delete(event);},
    removeLayer: layer => layers.delete(layer),
  };
  const L = {
    Layer: {extend: methods => function() {Object.assign(this, methods);}},
    layerGroup: () => ({items: [], addTo() {layers.add(this); return this;}, clearLayers() {this.items = [];}}),
    geoJSON: (data, options) => {assert.equal(options.pane, 'naturalEarth'); return {data, options};},
    divIcon: options => options,
    marker: (position, options) => ({addTo(group) {group.items.push({position, options});}}),
  };
  const layer = context.window.MRMSNaturalEarth.createLayer(L);
  for (let i = 0; i < 3; i++) {
    layer.onAdd(map);
    assert.equal(layers.size, 2);
    assert.equal(listeners.size, 1);
    assert.ok(classes.has('natural-earth-map'));
    assert.ok(layer.labels.items.some(m => m.options.icon.html.textContent.includes('Denver')));
    const count = layer.labels.items.length;
    listeners.get('moveend')();
    assert.equal(layer.labels.items.length, count);
    layer.onRemove(map);
    assert.equal(layers.size, 0);
    assert.equal(listeners.size, 0);
    assert.equal(classes.size, 0);
  }
});
