const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const zlib = require('node:zlib');
const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const app = html.match(/<script id="radar-app">([\s\S]*?)<\/script>/)[1];
const source = app.slice(app.indexOf('function archiveWorker()'), app.indexOf('function utcDay('));
const scales = vm.runInNewContext(app.slice(app.indexOf('const ARCHIVE_PALETTE'), app.indexOf('// Source-specific MRMS')) + '\nARCHIVE_SCALES;');
const crcTable = Uint32Array.from({length:256},(_, n) => {
  for(let i=0;i<8;i++) n=n&1?0xedb88320^(n>>>1):n>>>1;
  return n>>>0;
});
function crc(data) {let c=0xffffffff;for(const n of data)c=crcTable[(c^n)&255]^(c>>>8);return(c^0xffffffff)>>>0;}
function chunk(name, data) {
  const out=Buffer.alloc(data.length+12);out.writeUInt32BE(data.length);out.write(name,4);data.copy(out,8);
  out.writeUInt32BE(crc(out.subarray(4,-4)),out.length-4);return out;
}
function paeth(a,b,c) {const p=a+b-c,da=Math.abs(p-a),db=Math.abs(p-b),dc=Math.abs(p-c);return da<=db&&da<=dc?a:db<=dc?b:c;}
const fixtures = new Map();
function archive({bits=16,category=11,parameter=0,heightMeters=500,reference=-9990,decimal=1,samples=[0,10190,10440]}={}) {
  const key=JSON.stringify([...arguments]);
  if(fixtures.has(key))return Buffer.from(fixtures.get(key));
  const width=7000,height=3500,bpp=bits===24?3:2,stride=width*bpp,row=Buffer.alloc(stride);
  for(let x=0;x<width;x++) row.writeUIntBE(samples[x<2333?0:x<4666?1:2],x*bpp,bpp);
  const raw=Buffer.alloc((stride+1)*height);
  for(let y=0;y<height;y++) {
    const filter=y%5,start=y*(stride+1);raw[start]=filter;
    for(let x=0;x<stride;x++) {
      const a=x>=bpp?row[x-bpp]:0,b=y?row[x]:0,c=y&&x>=bpp?row[x-bpp]:0;
      const predict=filter===0?0:filter===1?a:filter===2?b:filter===3?Math.floor((a+b)/2):paeth(a,b,c);
      raw[start+x+1]=(row[x]-predict)&255;
    }
  }
  const ihdr=Buffer.alloc(13);ihdr.writeUInt32BE(width);ihdr.writeUInt32BE(height,4);ihdr[8]=bits===24?8:16;ihdr[9]=bits===24?2:0;
  const png=Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',ihdr),chunk('IDAT',zlib.deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);
  const section=(number,length)=>{const b=Buffer.alloc(length);b.writeUInt32BE(length);b[4]=number;return b;};
  const header=Buffer.alloc(16);header.write('GRIB');header[6]=209;header[7]=2;
  const id=section(1,21);id.writeUInt16BE(161,5);id[11]=3;id.writeUInt16BE(2026,12);id[14]=11;id[15]=1;id[18]=4;
  const grid=section(3,72);grid[14]=2;grid.writeUInt32BE(width,30);grid.writeUInt32BE(height,34);grid.writeUInt32BE(0xffffffff,42);
  grid.writeUInt32BE(54995000,46);grid.writeUInt32BE(230005000,50);grid.writeUInt32BE(10000,63);grid.writeUInt32BE(10000,67);
  const product=section(4,34);product[9]=category;product[10]=parameter;product[22]=102;product.writeUInt32BE(heightMeters,24);
  const packing=section(5,21);packing.writeUInt32BE(width*height,5);packing.writeUInt16BE(41,9);packing.writeFloatBE(reference,11);packing.writeUInt16BE(decimal,17);packing[19]=bits;
  const bitmap=section(6,6);bitmap[5]=255;
  const data=section(7,png.length+5);png.copy(data,5);
  const fixture=Buffer.concat([header,id,grid,product,packing,bitmap,data,Buffer.from('7777')]);fixture.writeUInt32BE(fixture.length,12);
  fixtures.set(key,fixture);
  return Buffer.from(fixture);
}
async function decode(bytes, overrides={}) {
  const radius=6378137, radians=Math.PI/180, merc=lat=>radius*Math.log(Math.tan(Math.PI/4+lat*radians/2));
  let result;
  const context={Blob,DecompressionStream,self:{postMessage(value){result=value;}}};
  vm.createContext(context);vm.runInContext(source+'\narchiveWorker();',context);
  await context.self.onmessage({data:{bytes:zlib.gzipSync(bytes),time:'2026-11-01T00:00:04.000Z',
    category:11,parameter:0,heightMeters:500,width:5,height:1,scale:scales.reflectivity,
    bbox:[-150*radius*radians,merc(15),-40*radius*radians,merc(60)],...overrides}});
  return result;
}
test('archive decoding preserves 16-bit values, all five PNG filters, transparency, colors, and geographic placement', async () => {
  const result=await decode(archive());assert.equal(result.error,undefined);
  assert.deepEqual([...new Uint8Array(result.rgba)],
    [0,0,0,0, 0,0,0,0, 0,255,0,255, 255,144,0,255, 0,0,0,0]);
});
test('archive decoding rejects incorrect dates, products, grids, and corrupt image checksums', async () => {
  assert.match((await decode(archive(),{time:'2026-11-02T00:00:04.000Z'})).error,/observation time/);
  assert.match((await decode(archive(),{category:10})).error,/product/);
  const badGrid=archive();badGrid.writeUInt32BE(6000,16+21+30);
  assert.match((await decode(badGrid)).error,/map grid/);
  const corrupt=archive();const png=corrupt.indexOf(Buffer.from([137,80,78,71,13,10,26,10]));corrupt[png+20]^=1;
  assert.match((await decode(corrupt)).error,/checksum/);
});
test('ZDR preserves negative and fractional dB values and validates parameter and height', async () => {
  const bytes=archive({category:9,parameter:4,heightMeters:3000,samples:[9970,9996,10020]});
  const job={category:9,parameter:4,heightMeters:3000,scale:scales.zdr};
  const result=await decode(bytes,job); assert.equal(result.error,undefined);
  assert.deepEqual([...new Uint8Array(result.rgba)],
    [0,0,0,0, 156,156,156,255, 35,152,211,255, 218,0,0,255, 0,0,0,0]);
  assert.match((await decode(bytes,{...job,parameter:3})).error,/product or height/);
  assert.match((await decode(bytes,{...job,heightMeters:500})).error,/product or height/);
});
test('24-bit RGB correlation samples retain all bytes and all five PNG row filters', async () => {
  const bytes=archive({bits:24,category:9,parameter:3,heightMeters:750,reference:-99900,decimal:2,samples:[0,99995,100000]});
  const result=await decode(bytes,{category:9,parameter:3,heightMeters:750,scale:scales.rhohv});
  assert.equal(result.error,undefined);
  assert.deepEqual([...new Uint8Array(result.rgba)],
    [0,0,0,0, 0,0,0,0, 255,137,3,255, 250,172,209,255, 0,0,0,0]);
});
test('correlation missing values remain transparent while zero and values above unity retain their colors', async () => {
  const bytes=archive({bits:24,category:9,parameter:3,reference:-99900,decimal:2,samples:[90000,99900,100005]});
  const result=await decode(bytes,{category:9,parameter:3,scale:scales.rhohv});
  assert.equal(result.error,undefined);
  assert.deepEqual([...new Uint8Array(result.rgba)],
    [0,0,0,0, 0,0,0,0, 149,148,156,255, 119,0,125,255, 0,0,0,0]);
});
