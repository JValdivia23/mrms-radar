const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../index.html'),'utf8').split('<script>')[1].split('</script>')[0].replace(/\ninit\(\);/, '\n');
const png = Buffer.alloc(5000);
Buffer.from([137,80,78,71,13,10,26,10]).copy(png);
const ok = ()=>new Response(png.toString('base64'));
function harness(network=async()=>ok()){
  const elements = new Map();
  const element = id=>{
    if(!elements.has(id)) elements.set(id,{value:48,src:'',dataset:{},style:{},children:[{},{},{}],classList:{add(){},remove(){}},addEventListener(){},querySelector(){return {};}});
    return elements.get(id);
  };
  const timers = new Map(); let timerId=0;
  const context = {console,URL,URLSearchParams,Response,Headers,Blob,AbortController,Uint8Array,atob,
    navigator:{},fetch:network,location:{protocol:'file:',origin:'null'},
    localStorage:{getItem(){return null;},setItem(){}},
    document:{getElementById:element,addEventListener(){}},addEventListener(){},
    L:{tileLayer(){return {};}},
    createImageBitmap:async()=>({width:920,height:630,close(){}}),
    setTimeout:(fn,ms)=>{const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),
    setInterval:(fn,ms)=>{const id=++timerId;timers.set(id,{fn,ms});return id;},clearInterval:id=>timers.delete(id),
  };
  context.window=context; vm.createContext(context);
  vm.runInContext(source+`\ncategories=categoriesCatalog; S.categoryIdx=0; S.levelIdx=0;`,context);
  return {run:code=>vm.runInContext(code,context),context,element,timers};
}
const exact = '/api/radar?product=M3DL13&lat=40&lon=-104&zoom=7&time=2026-09-08T12:00:00Z';
test('exact history is fetched once and a blank is a 404, including cached misses',async()=>{
 let count=0;const h=harness(async()=>{count++;return new Response('');});
 assert.equal((await h.context.fetch(exact)).status,404);
 assert.equal((await h.context.fetch(exact)).status,404);assert.equal(count,1);
});
test('concurrent exact requests and later playback reuse the same image',async()=>{
 let count=0;const h=harness(async()=>{count++;return ok();});
 const results=await Promise.all([h.context.fetch(exact),h.context.fetch(exact)]);
 assert.equal(results[0].headers.get('X-MRMS-Timestamp'),'2026-09-08T12:00:00.000Z');
 assert.equal((await results[1].blob()).size,5000);
 await h.context.fetch(exact);assert.equal(count,1);
 await h.context.fetch(exact.replace('zoom=7','zoom=8'));assert.equal(count,2);
});
test('transport and non-image failures are not cached as unavailable',async()=>{
 let count=0;const h=harness(async()=>{count++;return new Response(Buffer.alloc(5000,65).toString('base64'));});
 assert.equal((await h.context.fetch(exact)).status,502);
 assert.equal((await h.context.fetch(exact)).status,502);assert.equal(count,2);
});
test('PNG decode failures are rejected',async()=>{
 const h=harness();h.context.createImageBitmap=async()=>{throw Error('Corrupt PNG');};
 assert.equal((await h.context.fetch(exact)).status,502);
});
test('five-minute and hourly latest searches step by product resolution',async()=>{
 for(const resolution of [5,60]){
  const seen=[];const h=harness(async url=>{seen.push(new URL(new URL(url).searchParams.get('url')).searchParams);return seen.length===1?new Response(''):ok();});
  const code=h.run(`categoriesCatalog.flatMap(c=>c.products).find(p=>p.min_res_minutes===${resolution}).code`);
  assert.equal((await h.context.fetch('/api/radar?product='+code)).status,200);
  const stamp=p=>Date.UTC(+p.get('year'),+p.get('month')-1,+p.get('day'),+p.get('hour'),+p.get('minute'));
  assert.equal(stamp(seen[0])-stamp(seen[1]),resolution*60000);
 }
});
test('unaligned history is rejected instead of silently rounded',async()=>{
 let count=0;const h=harness(async()=>{count++;return ok();});
 const code=h.run('categoriesCatalog.flatMap(c=>c.products).find(p=>p.min_res_minutes===5).code');
 assert.equal((await h.context.fetch('/api/radar?product='+code+'&time=2026-09-08T12:02')).status,400);assert.equal(count,0);
});
test('latest blank search is bounded to six renders',async()=>{
 let count=0;const h=harness(async()=>{count++;return new Response('');});
 assert.equal((await h.context.fetch('/api/radar?product=M3DL13')).status,404);assert.equal(count,6);
});
test('global render concurrency never exceeds three',async()=>{
 let active=0,max=0; const release=[];
 const h=harness(async()=>{active++;max=Math.max(max,active);await new Promise(r=>release.push(r));active--;return ok();});
 const jobs=Array.from({length:8},(_,i)=>h.context.fetch(exact.replace('zoom=7','zoom='+i)));
 for(let i=0;i<20;i++){await new Promise(setImmediate);release.splice(0).forEach(r=>r());}
 await Promise.all(jobs);assert.equal(max,3);
});
test('loop uses sorted unique frames, skips blanks and refreshes the full rolling window',async()=>{
 const h=harness();let anchor='2026-09-08T12:00:00Z';let renders=0;
 h.context.fetch=async url=>{
  const time=new URL(url,'https://example.test').searchParams.get('time')||anchor;
  renders++;
  if(time.includes('11:52')) return new Response('',{status:404});
  return new Response(png,{headers:{'X-MRMS-Timestamp':time}});
 };
 h.run("S.mode='playing'; updateRadarOverlay=()=>{};");
 await h.run('loadLoop(false)');
 let stamps=h.run('S.animCache.map(f=>f.ts)');
 assert.equal(stamps.length,17);assert.equal(new Set(stamps).size,17);
 assert.equal(stamps.at(-1),'2026-09-08T12:00:00.000Z');
 assert.ok(h.run('!!S.animTimer'));assert.equal(renders,18);
 anchor='2026-09-08T12:04:00Z';await h.run('loadLoop(true)');
 stamps=h.run('S.animCache.map(f=>f.ts)');assert.equal(stamps[0],'2026-09-08T10:56:00.000Z');
 assert.equal(stamps.at(-1),'2026-09-08T12:04:00.000Z');
});
test('stopping an in-flight loop prevents stale playback and historical work',async()=>{
 const h=harness();let release;let calls=0;
 h.context.fetch=async()=>{calls++;await new Promise(r=>release=r);return new Response(png,{headers:{'X-MRMS-Timestamp':'2026-09-08T12:00:00Z'}});};
 h.run("S.mode='playing'");const job=h.run('loadLoop(false)');
 h.run('stopAnimation()');release();await job;
 assert.equal(calls,1);assert.equal(h.run('S.animCache.length'),0);assert.equal(h.run('S.animTimer'),null);
});
test('two-minute live updates reuse the four-minute historical grid',()=>{
 const h=harness();
 const before=h.run("Array.from({length:17},(_,i)=>loopFrameDate(new Date('2026-09-08T12:02:00Z'),i+1).toISOString())");
 const after=h.run("Array.from({length:17},(_,i)=>loopFrameDate(new Date('2026-09-08T12:04:00Z'),i+1).toISOString())");
 assert.deepEqual([...before],[...after]);
});
test('negative cache expires so newly arriving frames can be discovered',async()=>{
 let count=0;const h=harness(async()=>++count===1?new Response(''):ok());
 assert.equal((await h.context.fetch(exact)).status,404);
 h.run('for(const value of radarFrames.values()) value.expires=0');
 assert.equal((await h.context.fetch(exact)).status,200);assert.equal(count,2);
});
test('playback starts before all historical frames finish',async()=>{
 const h=harness();let calls=0;const pending=[];
 h.context.fetch=async url=>{
  const time=new URL(url,'https://example.test').searchParams.get('time')||'2026-09-08T12:00:00Z';
  if(++calls>3) await new Promise(r=>pending.push(r));
  return new Response(png,{headers:{'X-MRMS-Timestamp':time}});
 };
 h.run("S.mode='playing'; updateRadarOverlay=()=>{}");const job=h.run('loadLoop(false)');
 await new Promise(setImmediate);
 assert.ok(h.run('!!S.animTimer'));assert.ok(h.run('S.animCache.length')>=3);assert.ok(calls<18);
 h.run('stopAnimation()');pending.forEach(r=>r());await job;
});
test('pausing and scrubbing the loop selects actual timestamps',async()=>{
 const h=harness();
 h.run("S.mode='playing'; S.timeline=['2026-09-08T11:52:00.000Z','2026-09-08T12:00:00.000Z']; S.selectedTime=S.timeline[1]");
 h.element('timeSlider').value=0;h.element('timeSlider').oninput();
 assert.equal(h.run('S.selectedTime'),'2026-09-08T11:52:00.000Z');
 h.element('timeSlider').value=1;h.element('timeSlider').oninput();
 assert.equal(h.run('S.selectedTime'),'2026-09-08T12:00:00.000Z');
 assert.match(h.run('radarUrl()'),/12%3A00%3A00/);
});
test('a warm live loop downloads only one new frame on the next two-minute update',async()=>{
 let count=0, now=Date.parse('2026-09-08T12:04:00Z');
 const h=harness(async()=>{count++;return ok();});
 h.context.Date=class extends Date {constructor(...args){super(...(args.length?args:[now]));}static now(){return now;}};
 h.run("S.mode='playing'; updateRadarOverlay=()=>{}");
 await h.run('loadLoop(false)');assert.equal(count,18);
 now+=120000;await h.run('loadLoop(true)');assert.equal(count,19);
});
test('a stalled proxy request times out and releases its render slot',async()=>{
 const h=harness((url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(Error('aborted')))));
 const job=h.context.fetch(exact);await new Promise(setImmediate);
 const timeout=[...h.timers.values()].find(t=>t.ms===20000);assert.ok(timeout);timeout.fn();
 assert.equal((await job).status,502);assert.equal(h.run('activeRenders'),0);
 assert.equal(h.run('radarFrames.size'),0);
});
test('scheduled refresh advances every image across three hours and midnight',async()=>{
 let now=Date.parse('2026-09-08T22:04:00Z');
 const h=harness(async url=>{
  const p=new URL(new URL(url).searchParams.get('url')).searchParams;
  const stamp=new Date(Date.UTC(+p.get('year'),+p.get('month')-1,+p.get('day'),+p.get('hour'),+p.get('minute'))).toISOString();
  const image=Buffer.from(png);image.write(stamp,32);
  return new Response(image.toString('base64'));
 });
 h.context.Date=class extends Date {constructor(...args){super(...(args.length?args:[now]));}static now(){return now;}};
 h.run("S.mode='playing'; updateRadarOverlay=()=>{}");
 await h.run('loadLoop(false)');
 const originalOldest=h.run('S.animCache[0].ts');
 for(let tick=1;tick<=90;tick++){
  now+=120000;
  const refresh=h.timers.get(h.run('S.animRefreshTimer'));
  assert.equal(refresh.ms,120000);
  await refresh.fn(); // Exercise the scheduled callback, not just the loop builder.
  const frames=h.run('S.animCache');
  const anchor=now-240000;
  const grid=Math.floor((anchor-1)/240000)*240000;
  const expected=Array.from({length:17},(_,i)=>new Date(grid-(16-i)*240000).toISOString());
  expected.push(new Date(anchor).toISOString());
  assert.deepEqual(Array.from(frames,f=>f.ts),expected,`complete window at refresh ${tick}`);
  for(const frame of frames){
   const bytes=Buffer.from(await frame.blob.arrayBuffer());
   assert.equal(bytes.subarray(32,56).toString(),frame.ts,'image bytes must match the timestamp');
  }
 }
 assert.equal(Date.parse(h.run('S.animCache[0].ts'))-Date.parse(originalOldest),180*60000);
});
