const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const source = html.match(/<script id="radar-app">([\s\S]*?)<\/script>/)[1]
  .replace(/\ninit\(\)\.catch\(showError\);/, '\n');
const bbox = [-12000000, 4500000, -11000000, 5200000];
const product = 'conus_bref_qcd';
const stamp = '2026-11-02T18:25:57.000Z';
function png(time = stamp, size = 1000) {
  const bytes = Buffer.alloc(size);
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(bytes);
  bytes.writeUInt32BE(920, 16); bytes.writeUInt32BE(630, 20);
  bytes.write(time, 32);
  return bytes;
}
function harness(network = async () => new Response(png())) {
  const elements = new Map(), timers = new Map(); let timerId = 0;
  function element(id) {
    if (!elements.has(id)) elements.set(id, {value: 100, src: '', style: {},
      children: [{}, {}, {}], setAttribute() {},
      classList: {add() {}, remove() {}},
    });
    return elements.get(id);
  }
  const context = {console, URL, URLSearchParams, Response, Blob, AbortController, DOMException,
    Uint8Array, DataView, performance, navigator: {},
    fetch: network, localStorage: {getItem() {return null;}, setItem() {}},
    document: {getElementById: element},
    L: {tileLayer() {return {}; }},
    createImageBitmap: async () => ({close() {}}),
    setTimeout(fn, ms) {const id = ++timerId; timers.set(id, {fn, ms}); return id;},
    clearTimeout(id) {timers.delete(id);},
  };
  context.window = context;
  vm.createContext(context); vm.runInContext(source, context);
  return {context, timers, element, run: code => vm.runInContext(code, context)};
}
test('the runnable page has no external scripts, styles, Google proxy, or backend requests', () => {
  assert.doesNotMatch(html, /<script[^>]+src=|<link[^>]+stylesheet|GOOGLE_SCRIPT_PROXY|script\.google\.com|\/api\/|serviceWorker/);
  for (const match of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
  assert.match(html, /Redistribution and use/); // Leaflet's embedded license.
});
test('actual scan seconds survive sorting, deduplication, and UTC midnight', () => {
  const h = harness();
  assert.deepEqual([...h.run("advertisedTimes('2026-11-03T00:00:13Z,2026-11-02T23:58:07Z,2026-11-03T00:00:13Z')")],
    ['2026-11-02T23:58:07.000Z', '2026-11-03T00:00:13.000Z']);
  assert.deepEqual([...h.run("advertisedTimes('2026-11-02T23:58:07Z/2026-11-03T00:02:07Z/PT2M')")],
    ['2026-11-02T23:58:07.000Z', '2026-11-03T00:00:07.000Z', '2026-11-03T00:02:07.000Z']);
  for (const times of ['bad', '2026-11-02T12:00Z/2026-11-02T12:10Z/PT0S',
    '2026-11-02T12:00Z/2027-11-02T12:10Z/PT1S']) {
    assert.throws(() => h.run(`advertisedTimes(${JSON.stringify(times)})`));
  }
});
test('image requests use the exact timestamp and viewport in Web Mercator', () => {
  const h = harness();
  const bounds = [...h.run('projectedBounds(40, -104, 7)')];
  assert.ok(Math.abs((bounds[2] - bounds[0]) / (bounds[3] - bounds[1]) - 920 / 630) < 1e-10);
  const url = new URL(h.run(`mapUrl('${product}', '${stamp}', projectedBounds(40, -104, 7))`));
  assert.equal(url.hostname, 'opengeo.ncep.noaa.gov');
  assert.equal(url.searchParams.get('version'), '1.1.1');
  assert.equal(url.searchParams.get('srs'), 'EPSG:3857');
  assert.equal(url.searchParams.get('time'), stamp);
  assert.equal(url.searchParams.get('width'), '920');
  assert.equal(url.searchParams.get('height'), '630');
});
test('one PNG request supplies concurrent consumers and subsequent playback', async () => {
  let calls = 0;
  const h = harness(async (url, options) => {
    calls++; assert.equal(options.credentials, 'omit');
    assert.equal(options.mode, 'cors'); return new Response(png());
  });
  const frame = () => h.run(`client.frame('${product}', '${stamp}', ${JSON.stringify(bbox)})`);
  const result = await Promise.all([frame(), frame()]);
  assert.equal(calls, 1); assert.equal(result[0].blob.size, 1000);
  assert.equal((await frame()).cached, true); assert.equal(calls, 1);
  await h.run(`client.frame('conus_cref_qcd', '${stamp}', ${JSON.stringify(bbox)})`);
  assert.equal(calls, 2);
});
test('clear-weather PNGs smaller than the old 4 KB threshold remain valid', async () => {
  const h = harness();
  const frame = await h.run(`client.frame('${product}', '${stamp}', ${JSON.stringify(bbox)})`);
  assert.equal(frame.blob.size, 1000);
  assert.equal(h.run('client.frames.size'), 1);
});
test('HTTP, XML, dimension, and decode failures never enter the frame cache', async () => {
  const wrong = png(); wrong.writeUInt32BE(7000, 16);
  for (const response of [() => new Response('unavailable', {status: 503}),
    () => new Response('<ServiceException>bad time</ServiceException>'), () => new Response(wrong)]) {
    const h = harness(async () => response());
    await assert.rejects(h.run(`client.frame('${product}', '${stamp}', ${JSON.stringify(bbox)})`));
    assert.equal(h.run('client.frames.size'), 0); assert.equal(h.run('client.active'), 0);
  }
  const h = harness(); h.context.createImageBitmap = async () => {throw Error('corrupt PNG');};
  await assert.rejects(h.run(`client.frame('${product}', '${stamp}', ${JSON.stringify(bbox)})`));
  assert.equal(h.run('client.frames.size'), 0);
});
test('network concurrency is bounded and a timed-out download releases its slot', async () => {
  let active = 0, max = 0; const releases = [];
  const h = harness(async () => {
    active++; max = Math.max(max, active);
    await new Promise(resolve => releases.push(resolve)); active--; return new Response(png());
  });
  const jobs = Array.from({length: 9}, (_, i) => h.run(`client.frame('${product}', new Date(${Date.parse(stamp)}+${i}*120000).toISOString(), ${JSON.stringify(bbox)})`));
  for (let i = 0; i < 12; i++) {await new Promise(setImmediate); releases.splice(0).forEach(resolve => resolve());}
  await Promise.all(jobs); assert.equal(max, 3);
  const stalled = harness((url, {signal}) => new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Timed out', 'AbortError')))));
  const job = stalled.run(`client.frame('${product}', '${stamp}', ${JSON.stringify(bbox)})`);
  const rejected = assert.rejects(job, {name: 'AbortError'});
  [...stalled.timers.values()].find(timer => timer.ms === 15000).fn();
  await rejected; assert.equal(stalled.run('client.active'), 0);
});
test('changing views cancels active and queued downloads without caching stale results', async () => {
  let calls = 0;
  const h = harness((url, {signal}) => {
    calls++;
    return new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('View changed', 'AbortError'))));
  });
  const jobs = Array.from({length: 8}, (_, i) => h.run(`client.frame('${product}', new Date(${Date.parse(stamp)}+${i}*120000).toISOString(), ${JSON.stringify(bbox)})`));
  const finished = Promise.allSettled(jobs);
  h.run('client.cancelFrames()');
  assert.ok((await finished).every(result => result.status === 'rejected'));
  assert.equal(calls, 3); assert.equal(h.run('client.frames.size'), 0);
  assert.equal(h.run('client.active'), 0); assert.equal(h.run('client.pending.size'), 0);
});
test('decoded-frame storage obeys both entry and byte budgets', async () => {
  const h = harness();
  for (let i = 0; i < 75; i++) await h.run(`client.frame('${product}', new Date(${Date.parse(stamp)}+${i}*120000).toISOString(), ${JSON.stringify(bbox)})`);
  assert.equal(h.run('client.frames.size'), 72); assert.equal(h.run('client.bytes'), 72000);
  const large = harness(async () => new Response(png(stamp, 2 * 1024 * 1024)));
  for (let i = 0; i < 18; i++) await large.run(`client.frame('${product}', new Date(${Date.parse(stamp)}+${i}*120000).toISOString(), ${JSON.stringify(bbox)})`);
  assert.equal(large.run('client.frames.size'), 16); assert.equal(large.run('client.bytes'), 32 * 1024 * 1024);
});
test('a stale still-image response cannot overwrite the selected view or its timestamp', async () => {
  const h = harness(); const releases = [];
  h.run(`client.catalog = async () => ['${stamp}']; displayFrame = frame => {S.selected = frame.time; window.displayed = frame;};`);
  h.context.deferFrame = () => new Promise(resolve => releases.push(resolve));
  h.run('client.frame = () => window.deferFrame()');
  const oldJob = h.run('fetchImage()'); await new Promise(setImmediate);
  h.run('S.lon = -97');
  const newJob = h.run('fetchImage()'); await new Promise(setImmediate);
  releases[1]({time: stamp, label: 'new'}); await newJob;
  releases[0]({time: stamp, label: 'old'}); await oldJob;
  assert.equal(h.context.displayed.label, 'new');
});
test('loop refresh advances every image across midnight and downloads only new scans', async () => {
  let anchor = Date.parse('2026-11-02T23:58:07Z'), downloads = 0;
  const h = harness(async url => {
    downloads++; const time = new URL(url).searchParams.get('time'); return new Response(png(time));
  });
  h.context.times = () => Array.from({length: 30}, (_, i) => new Date(anchor - (29 - i) * 120000).toISOString());
  h.run("client.catalog = async () => window.times(); S.mode = 'playing'; displayFrame = frame => { S.selected = frame.time; };");
  await h.run('loadLoop()'); assert.equal(downloads, 18);
  for (let refresh = 1; refresh <= 90; refresh++) {
    anchor += 120000;
    await h.run('loadLoop(true)');
    const frames = h.run('S.loop'); assert.equal(frames.length, 18);
    assert.equal(frames.at(-1).time, new Date(anchor).toISOString());
    for (let i = 0; i < frames.length; i++) {
      const expected = new Date(anchor - (17 - i) * 120000).toISOString();
      assert.equal(frames[i].time, expected);
      const bytes = Buffer.from(await frames[i].blob.arrayBuffer());
      assert.equal(bytes.toString('utf8', 32, 32 + expected.length), expected);
    }
    assert.equal(downloads, 18 + refresh);
  }
});
test('pausing during loop loading prevents late playback and further history requests', async () => {
  const releases = [], h = harness(async () => {
    await new Promise(resolve => releases.push(resolve)); return new Response(png());
  });
  h.run(`client.catalog = async () => ['2026-11-02T18:21:39.000Z','2026-11-02T18:23:41.000Z','${stamp}']; S.mode = 'playing';`);
  const job = h.run('loadLoop()'); await new Promise(setImmediate);
  h.run('pause()'); releases.forEach(resolve => resolve()); await job;
  assert.equal(h.run('S.mode'), 'paused'); assert.equal(h.run('S.timer'), null);
  assert.equal(h.run('S.loop.length'), 0);
});
