import {test} from 'node:test';
import assert from 'node:assert/strict';
import {isAllowedApiRoute,readJsonBody} from '../lib/api-proxy.mjs';

test('proxy accepts only documented routes and methods',()=>{
 assert.equal(isAllowedApiRoute('GET',['v1','observations']),true);
 assert.equal(isAllowedApiRoute('POST',['v1','parcels','assess']),true);
 for(const path of [['..','secret'],['v1','..','status'],['https:','','evil'],['v1','openapi.json']])assert.equal(isAllowedApiRoute('GET',path),false);
 assert.equal(isAllowedApiRoute('POST',['v1','status']),false);
});
test('streamed limit counts UTF-8 bytes rather than JS characters',async()=>{
 const req=new Request('https://local.invalid',{method:'POST',headers:{'Content-Type':'application/json'},body:'กกก'});
 await assert.rejects(()=>readJsonBody(req,8),e=>e.status===413);
});
test('declared oversize and invalid media type rejected',async()=>{
 const req=new Request('https://local.invalid',{method:'POST',headers:{'Content-Type':'application/json','Content-Length':'70000'},body:'{}'});
 await assert.rejects(()=>readJsonBody(req),e=>e.status===413);
 const plain=new Request('https://local.invalid',{method:'POST',body:'{}'});
 await assert.rejects(()=>readJsonBody(plain),e=>e.status===415);
});
test('valid JSON text is forwarded unchanged and invalid UTF-8 rejected',async()=>{
 const req=new Request('https://local.invalid',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"lat":13,"lon":100}'});
 assert.equal(await readJsonBody(req),'{"lat":13,"lon":100}');
 const bad=new Request('https://local.invalid',{method:'POST',headers:{'Content-Type':'application/json'},body:new Uint8Array([255])});
 await assert.rejects(()=>readJsonBody(bad),e=>e.status===400);
});
test('body read has a total deadline',async()=>{
 const req=new Request('https://local.invalid',{method:'POST',headers:{'Content-Type':'application/json'},body:new ReadableStream({start(){}}),duplex:'half'});
 await assert.rejects(()=>readJsonBody(req,64000,10),e=>e.status===408);
});
