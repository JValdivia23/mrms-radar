const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const zlib = require('node:zlib');
const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const app = html.match(/<script id="radar-app">([\s\S]*?)<\/script>/)[1];
const source = app.slice(app.indexOf('function archiveWorker()'), app.indexOf('function utcDay('));
const palette = [[221,254,255],[216,210,233],[208,175,212],[163,127,167],[115,74,119],[214,212,173],
  [169,168,125],[119,119,119],[0,236,236],[1,160,246],[0,0,246],[0,255,0],[0,200,0],[0,144,0],
  [255,255,0],[231,192,0],[255,144,0],[255,0,0],[220,0,0],[192,0,0],[255,0,255],[153,85,201]];
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
let fixture;
function archive() {
  if(fixture)return Buffer.from(fixture);
  const width=7000,height=3500,stride=width*2,row=Buffer.alloc(stride);
  for(let x=0;x<width;x++) row.writeUInt16BE(x<2333?0:x<4666?10190:10440,x*2);
  const raw=Buffer.alloc((stride+1)*height);
  for(let y=0;y<height;y++) {
    const filter=y%5,start=y*(stride+1);raw[start]=filter;
    for(let x=0;x<stride;x++) {
      const a=x>=2?row[x-2]:0,b=y?row[x]:0,c=y&&x>=2?row[x-2]:0;
      const predict=filter===0?0:filter===1?a:filter===2?b:filter===3?Math.floor((a+b)/2):paeth(a,b,c);
      raw[start+x+1]=(row[x]-predict)&255;
    }
  }
  const ihdr=Buffer.alloc(13);ihdr.writeUInt32BE(width);ihdr.writeUInt32BE(height,4);ihdr[8]=16;
  const png=Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',ihdr),chunk('IDAT',zlib.deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);
  const section=(number,length)=>{const b=Buffer.alloc(length);b.writeUInt32BE(length);b[4]=number;return b;};
  const header=Buffer.alloc(16);header.write('GRIB');header[6]=209;header[7]=2;
  const id=section(1,21);id.writeUInt16BE(161,5);id[11]=3;id.writeUInt16BE(2026,12);id[14]=11;id[15]=1;id[18]=4;
  const grid=section(3,72);grid[14]=2;grid.writeUInt32BE(width,30);grid.writeUInt32BE(height,34);grid.writeUInt32BE(0xffffffff,42);
  grid.writeUInt32BE(54995000,46);grid.writeUInt32BE(230005000,50);grid.writeUInt32BE(10000,63);grid.writeUInt32BE(10000,67);
  const product=section(4,34);product[9]=11;product[22]=102;product.writeUInt32BE(500,24);
  const packing=section(5,21);packing.writeUInt32BE(width*height,5);packing.writeUInt16BE(41,9);packing.writeFloatBE(-9990,11);packing.writeUInt16BE(1,17);packing[19]=16;
  const bitmap=section(6,6);bitmap[5]=255;
  const data=section(7,png.length+5);png.copy(data,5);
  fixture=Buffer.concat([header,id,grid,product,packing,bitmap,data,Buffer.from('7777')]);fixture.writeUInt32BE(fixture.length,12);
  return Buffer.from(fixture);
}
async function decode(bytes, overrides={}) {
  const radius=6378137, radians=Math.PI/180, merc=lat=>radius*Math.log(Math.tan(Math.PI/4+lat*radians/2));
  let result;
  const context={Blob,DecompressionStream,self:{postMessage(value){result=value;}}};
  vm.createContext(context);vm.runInContext(source+'\narchiveWorker();',context);
  await context.self.onmessage({data:{bytes:zlib.gzipSync(bytes),time:'2026-11-01T00:00:04.000Z',
    category:11,width:5,height:1,palette,bbox:[-150*radius*radians,merc(15),-40*radius*radians,merc(60)],...overrides}});
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
