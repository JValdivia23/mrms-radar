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
    if (!elements.has(id)) elements.set(id, {value: 100, src: '', style: {}, dataset: {},
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
test('three-hour windows span midnight and avoid duplicate GIS/archive cycles', () => {
  const h = harness();
  assert.deepEqual([...h.run(`historyTimes(['2026-11-02T21:59:59.000Z', '2026-11-02T22:00:00.000Z',
    '2026-11-03T00:30:12.000Z', '2026-11-03T01:00:01.000Z'], Date.parse('2026-11-03T01:00:00Z'))`)],
    ['2026-11-02T22:00:00.000Z', '2026-11-03T00:30:12.000Z']);
  assert.deepEqual([...h.run(`mergeRecentTimes(['2026-11-03T00:30:42.000Z'],
    ['2026-11-03T00:30:40.000Z', '2026-11-02T23:00:04.000Z'], Date.parse('2026-11-03T01:00:00Z'))`)],
    ['2026-11-02T23:00:04.000Z', '2026-11-03T00:30:42.000Z']);
});
test('slider positions measure elapsed time rather than the number of scans', () => {
  const h = harness();
  h.run(`S.windowEnd='2026-11-03T01:00:00.000Z'; S.times=['2026-11-02T22:00:10.000Z',
    '2026-11-03T00:00:00.000Z','2026-11-03T00:58:42.000Z']; S.selected=S.times[1]; renderTime();`);
  assert.equal(h.element('timeSlider').max, 10800);
  assert.equal(h.element('timeSlider').value, 7200);
  assert.equal(h.element('timeOffset').textContent, '1 h before 01:00 UTC');
  assert.equal(h.run('sliderTime(7200)'), '2026-11-03T00:00:00.000Z');
  assert.equal(h.element('labelStart').textContent, '−3 h');
});
test('archive discovery requests both UTC days and only returns observations inside the window', async () => {
  const h = harness(); const days = [];
  h.context.records = day => {
    days.push(day);
    return day === '2026-11-02'
      ? [{time:'2026-11-02T21:58:00.000Z'}, {time:'2026-11-02T23:58:07.000Z'}]
      : [{time:'2026-11-03T00:00:13.000Z'}, {time:'2026-11-03T01:02:00.000Z'}];
  };
  h.run('client.day = async (product, day) => window.records(day)');
  const times = await h.run("client.history('conus_bref_qcd','2026-11-03T01:00:00.000Z')");
  assert.deepEqual(days, ['2026-11-02','2026-11-03']);
  assert.deepEqual([...times], ['2026-11-02T23:58:07.000Z','2026-11-03T00:00:13.000Z']);
});
test('older scans use public archive objects while recent scans keep the fast PNG path', async () => {
  const calls = [], h = harness(async url => {calls.push(url); return new Response(png());});
  h.run(`client.catalogs.set('${product}', {times:['${stamp}']});
    client.archiveObjects.set('${product}|${stamp}', {time:'${stamp}',key:'recent.grib2.gz'});
    client.archiveObjects.set('${product}|2026-11-01T12:00:04.000Z', {time:'2026-11-01T12:00:04.000Z',key:'old.grib2.gz'});
    decodeArchive = async blob => blob;`);
  const recent = await h.run(`client.frame('${product}','${stamp}',${JSON.stringify(bbox)})`);
  const old = await h.run(`client.frame('${product}','2026-11-01T12:00:04.000Z',${JSON.stringify(bbox)})`);
  assert.equal(recent.source, 'wms'); assert.equal(old.source, 'archive');
  assert.equal(new URL(calls[0]).hostname, 'opengeo.ncep.noaa.gov');
  assert.equal(calls[1], 'https://noaa-mrms-pds.s3.amazonaws.com/old.grib2.gz');
});
test('UTC date input rejects invalid and future dates', () => {
  const h = harness();
  h.context.Date = class extends Date {static now() {return Date.parse('2026-11-02T18:00:00Z');}};
  h.element('goDate').value='2026-11-01'; h.element('goTime').value='15:30';
  assert.equal(h.run('requestedDate()'), '2026-11-01T15:30:00.000Z');
  h.element('goDate').value='2026-11-03'; assert.throws(() => h.run('requestedDate()'), /past/);
  h.element('goDate').value='2026-02-30'; assert.throws(() => h.run('requestedDate()'), /valid/);
});
test('missing historical data preserves the displayed scan and reports a useful message', async () => {
  const h = harness();
  h.element('goDate').value='2026-11-01'; h.element('goTime').value='15:30';
  h.run(`S.selected='${stamp}'; client.history=async()=>[];`);
  await h.run('goToDate()');
  assert.equal(h.run('S.selected'), stamp); assert.equal(h.run('S.windowEnd'), null);
  assert.match(h.element('dateStatus').textContent, /No scans are available/);
  assert.equal(h.element('dateGo').disabled, false);
});
test('date navigation selects a real prior observation and fixes the historical playback window', async () => {
  const h = harness();
  h.element('goDate').value='2026-11-01'; h.element('goTime').value='15:30';
  h.run(`client.history=async()=>['2026-11-01T15:26:04.000Z','2026-11-01T15:28:40.000Z'];
    fetchImage=async(force,time)=>{S.revision++;window.requested=time;return true;};`);
  await h.run('goToDate()');
  assert.equal(h.run('S.windowEnd'), '2026-11-01T15:30:00.000Z');
  assert.equal(h.context.requested, '2026-11-01T15:28:40.000Z');
  assert.equal(h.run('S.mode'), 'paused');
  assert.match(h.element('dateStatus').textContent, /Showing 2026-11-01 15:28:40 UTC/);
  h.run('goLive()'); assert.equal(h.run('S.windowEnd'), null);
});
test('a failed archived image restores the previous timeline and reports its error', async () => {
  const h = harness();
  h.element('goDate').value='2026-11-01'; h.element('goTime').value='15:30';
  h.run(`S.selected='${stamp}'; S.times=['${stamp}'];
    client.history=async()=>['2026-11-01T15:28:40.000Z'];
    client.frame=async()=>{throw Error('Unsupported archive packing');};`);
  await h.run('goToDate()');
  assert.equal(h.run('S.selected'), stamp); assert.equal(h.run('S.windowEnd'), null);
  assert.deepEqual([...h.run('S.times')], [stamp]);
  assert.match(h.element('dateStatus').textContent, /Unsupported archive packing/);
});

function timeJumpHarness() {
  const h = harness();
  h.context.Date = class extends Date {static now() {return Date.parse('2026-11-02T18:30:00Z');}};
  h.run(`S.selected='2026-11-02T18:28:40.000Z';
    S.times=['2026-11-02T16:32:40.000Z', S.selected];
    client.catalog=async()=>['2026-11-02T16:32:40.000Z','2026-11-02T18:28:40.000Z'];
    client.history=async()=>['2026-11-02T15:30:07.000Z','2026-11-02T16:28:41.000Z'];
    client.frame=async(product,time)=>{window.fetchedTime=time;return {time};};
    displayFrame=frame=>{S.selected=frame.time;renderTime();};`);
  return h;
}
test('hour jumps leave live/playback mode and fetch older scans before background discovery finishes', async () => {
  for (const mode of ['live','playing']) for (const hours of [2,3]) {
    const h = timeJumpHarness(); h.run(`S.mode='${mode}'`);
    assert.equal(await h.run(`jumpHours(${hours})`), true);
    const expected = hours === 2 ? '2026-11-02T16:28:41.000Z' : '2026-11-02T15:30:07.000Z';
    assert.equal(h.context.fetchedTime, expected);
    assert.equal(h.run('S.selected'), expected); assert.equal(h.run('S.mode'),'paused');
  }
});
test('previewing the range does not rewrite its native value, and releasing it fetches that time', async () => {
  const h = timeJumpHarness(); let value=3600, writes=0;
  Object.defineProperty(h.element('timeSlider'),'value',{get:()=>value,set:n=>{value=n;writes++;}});
  h.run('previewSlider()');
  assert.equal(writes,0); assert.equal(value,3600);
  assert.equal(h.run('scrubTarget'),'2026-11-02T16:30:00.000Z');
  assert.equal(await h.run('commitSlider()'), true);
  assert.equal(h.context.fetchedTime,'2026-11-02T16:28:41.000Z');
});
test('a range change without an input event still requests the thumb position rather than the current frame', async () => {
  const h = timeJumpHarness(); h.element('timeSlider').value=0;
  assert.equal(await h.run('commitSlider()'), true);
  assert.equal(h.context.fetchedTime,'2026-11-02T15:30:07.000Z');
});
test('missing hour-jump data reports an error instead of silently clamping to the recent feed', async () => {
  const h = timeJumpHarness(); h.run('client.history=async()=>[];radarOverlay={};');
  assert.equal(await h.run('jumpHours(3)'), false);
  assert.equal(h.context.fetchedTime,undefined);
  assert.equal(h.run('S.selected'),'2026-11-02T18:28:40.000Z');
  assert.equal(h.run('scrubTarget'),null);
  assert.match(h.element('loopStatus').textContent,/No scan is available near the selected time/);
});
test('hour jumps in a dated window stay relative to that date', async () => {
  const h = timeJumpHarness();
  h.run(`S.windowEnd='2026-11-01T18:00:00.000Z';
    client.history=async()=>['2026-11-01T15:58:39.000Z','2026-11-01T17:58:40.000Z'];`);
  assert.equal(await h.run('jumpHours(2)'), true);
  assert.equal(h.context.fetchedTime,'2026-11-01T15:58:39.000Z');
  assert.equal(h.run('S.windowEnd'),'2026-11-01T18:00:00.000Z');
});
test('polarimetric selections use NOAA product parameters and all 33 MSL heights', () => {
  const h=harness();
  assert.equal(h.run('HEIGHTS.length'),33);
  const zdr=h.run("productInfo('zdr_00.75')"),rho=h.run("productInfo('rhohv_19.00')");
  assert.equal(zdr.archive,'MergedZdr_00.75'); assert.equal(zdr.heightMeters,750);
  assert.equal(zdr.category,9); assert.equal(zdr.parameter,4);
  assert.equal(rho.archive,'MergedRhoHV_19.00'); assert.equal(rho.heightMeters,19000);
  assert.equal(rho.category,9); assert.equal(rho.parameter,3);
  for(const invalid of ['zdr','zdr_00.00','rhohv_20.00','zdr_3.00','zdr_03.25','missing_03.00'])
    assert.throws(()=>h.run(`productInfo('${invalid}')`),/Unknown radar product or height/);
  assert.throws(()=>h.run("mapUrl('zdr_03.00','2026-11-02T18:25:41Z',[1,2,3,4])"),/not WMS/);
});
test('live polarimetric catalogs use the public three-hour archive and report empty heights', async () => {
  const h=harness();h.context.Date=class extends Date {static now(){return Date.parse('2026-11-02T18:30:00Z');}};
  h.run(`client.history=async(product,end,force)=>{window.catalogQuery={product,end,force};return ['${stamp}'];};`);
  assert.deepEqual([...await h.run("client.catalog('rhohv_03.00',true)")],[stamp]);
  assert.equal(h.context.catalogQuery.product,'rhohv_03.00');assert.equal(h.context.catalogQuery.force,true);
  h.run('client.history=async()=>[]');
  await assert.rejects(h.run("client.catalog('zdr_00.50')"),/No scans.*product and height/);
});
test('polarimetric frame downloads and cache entries stay isolated by variable and height', async () => {
  const calls=[],h=harness(async url=>{calls.push(url);return new Response(png());});
  h.run(`decodeArchive=async(blob,record,info)=>{window.decodedInfo=info;return blob;};`);
  for(const selection of ['zdr_03.00','zdr_04.00','rhohv_03.00']) {
    h.run(`client.archiveObjects.set('${selection}|${stamp}',{time:'${stamp}',key:'${selection}.grib2.gz'})`);
    const frame=()=>h.run(`client.frame('${selection}','${stamp}',${JSON.stringify(bbox)})`);
    assert.equal((await frame()).source,'archive');assert.equal((await frame()).cached,true);
    assert.equal(h.context.decodedInfo.id,selection);
  }
  assert.deepEqual(calls,['zdr_03.00','zdr_04.00','rhohv_03.00'].map(id=>'https://noaa-mrms-pds.s3.amazonaws.com/'+id+'.grib2.gz'));
  await assert.rejects(h.run(`client.frame('rhohv_04.00','${stamp}',${JSON.stringify(bbox)})`),/unavailable.*product and height/);
  assert.equal(calls.length,3);assert.equal(h.run('client.frames.size'),3);
});
test('five-minute dual-pol scans snap to a real prior observation without accepting a long gap', async () => {
  for(const [target,success] of [['2026-11-02T18:29:59.000Z',true],['2026-11-02T18:33:00.000Z',false]]) {
    const h=harness();h.context.Date=class extends Date {static now(){return Date.parse('2026-11-02T18:35:00Z');}};
    h.run(`S.product='zdr_03.00'; S.mode='paused'; radarOverlay={};
      client.catalog=client.history=async()=>['${stamp}'];
      client.frame=async(product,time)=>{window.polarScan=time;return {time};};
      displayFrame=frame=>{S.selected=frame.time;renderTime();};`);
    assert.equal(await h.run(`fetchImage(false,'${target}')`),success);
    assert.equal(h.context.polarScan,success?stamp:undefined);
  }
});
test('product changes expose MSL height, use the correct legend units, and preserve a historical date', () => {
  const h=harness();
  h.run("viewChanged=()=>{};S.windowEnd='2026-11-01T18:00:00.000Z'");
  h.element('productSelect').value='zdr';h.element('heightSelect').value='03.00';h.run('changeProduct()');
  assert.equal(h.run('S.product'),'zdr_03.00');assert.equal(h.run('S.windowEnd'),'2026-11-01T18:00:00.000Z');
  assert.equal(h.element('heightControls').hidden,false);assert.equal(h.element('productBadge').textContent,'ZDR · 3 km MSL');
  assert.match(h.element('legendBar').alt,/dB$/);assert.doesNotMatch(h.element('legendBar').alt,/dBZ/);
  h.element('productSelect').value='rhohv';h.element('heightSelect').value='04.00';h.run('changeProduct()');
  assert.equal(h.run('S.product'),'rhohv_04.00');assert.match(h.element('legendBar').alt,/unitless/);
  assert.match(decodeURIComponent(h.element('legendBar').src),/1\.00/);
  h.element('productSelect').value=product;h.run('changeProduct()');
  assert.equal(h.element('heightControls').hidden,true);assert.equal(h.run('S.height'),'04.00');
  assert.equal(h.run('S.product'),product);
});
test('switching variables or heights preserves the paused observation for comparison', () => {
  const h=harness();h.run(`viewChanged=time=>{window.comparisonTime=time;}; S.mode='paused'; S.selected='${stamp}';`);
  h.element('productSelect').value='zdr';h.element('heightSelect').value='03.00';h.run('changeProduct()');
  assert.equal(h.context.comparisonTime,stamp);assert.equal(h.run('S.mode'),'paused');
  h.run(`S.selected='${stamp}'`);h.element('heightSelect').value='04.00';h.run('changeProduct()');
  assert.equal(h.context.comparisonTime,stamp);assert.equal(h.run('S.product'),'zdr_04.00');
});
