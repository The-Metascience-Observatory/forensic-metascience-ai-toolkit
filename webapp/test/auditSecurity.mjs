import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {Readable} from 'node:stream';
import vm from 'node:vm';
import ts from 'typescript';
import {chromium} from 'playwright';
import {rejectCrossOrigin} from '../lib/mutation.ts';
import {mediaType,mediaDisposition,cacheControl} from '../lib/media.ts';
import {byteRange} from '../lib/byteRange.ts';
function endpoint(file,modules={}) {
 const exports={};
 const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 vm.runInNewContext(code,{exports,URL,Response,ReadableStream,TextEncoder,process,require:name=>({
  'next/server':{NextResponse:Response},'@/lib/mutation':{rejectCrossOrigin},...modules,
 }[name] || new Proxy({}, {get:()=>()=>{throw Error(`Unexpected side effect: ${name}`);}}))});
 return exports;
}
for(const route of ['settings','draft','metadata','index','stats','viewed','reveal','images','images/bulk','images/missed','review','workbench']) {
 const api=endpoint(`app/api/${route}/route.ts`);
 for(const headers of [{origin:'https://unrelated.invalid'},{origin:'null'},{'sec-fetch-site':'cross-site'}]) {
  const req=new Request(`http://localhost:3100/api/${route}`,{method:'POST',headers,body:'invalid JSON'});
  req.json=()=>{throw Error('Untrusted request parsed before rejection');};
  assert.equal((await api.POST(req)).status,403,route);
 }
}
for(const headers of [{},{origin:'http://localhost:3100'},{'sec-fetch-site':'same-origin'}])
 assert.equal(rejectCrossOrigin(new Request('http://localhost:3100/api/settings',{headers})),null);
const root=mkdtempSync(path.join(tmpdir(),'audit-media-'));let browser;
try {
 const file=path.join(root,'evidence.html');
 writeFileSync(file,`<body>Evidence<script>window.ran=true;fetch('/api/settings').then(()=>window.read=true).catch(()=>window.blocked=true);try{window.storage=localStorage.length}catch{window.isolated=true}</script>`);
 const api=endpoint('app/api/media/route.ts',{
  'node:fs':{default:fs},'node:fs/promises':{default:fsp},'node:stream':{Readable},
  '@/lib/err':{errMsg:e=>e.message},'@/lib/media':{mediaType,mediaDisposition,cacheControl},'@/lib/byteRange':{byteRange},
  '@/lib/workbench':{workbenchTimed:async()=>({value:{path:file,record:{name:'evidence.html'}},timings:{}}),serverTiming:()=>''},
 });
 const url='http://localhost:3100/api/media?project=fixture&dir=paper&f=evidence.html';
 const response=await api.GET(new Request(url));assert.equal(response.status,200);
 assert.equal(response.headers.get('x-content-type-options'),'nosniff');
 const headers=Object.fromEntries(response.headers),body=await response.text();
 browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage();let apiCalls=0;
 await page.route('**/*',async route=>{
  if(route.request().url()===url)await route.fulfill({status:200,headers,body});
  else {apiCalls++;await route.fulfill({status:200,body:'{}'});}
 });
 await page.goto(url);await page.waitForFunction(()=>window.ran && window.blocked && window.isolated);
 assert.equal(apiCalls,0,'HTML evidence must not call workbench APIs');
 assert.equal(await page.locator('body').innerText(),'Evidence');
 const range=await api.GET(new Request(url,{headers:{Range:'bytes=0-4'}}));
 assert.equal(range.status,206);assert.equal(await range.text(),'<body');
 const cached=await api.GET(new Request(url,{headers:{'If-None-Match':headers.etag}}));
 assert.equal(cached.status,304);assert.equal(cached.headers.get('content-security-policy'),headers['content-security-policy']);
 console.log('auditSecurity: all mutation guards, rendered HTML isolation, ranges and cache headers passed');
} finally {await browser?.close();rmSync(root,{recursive:true,force:true});}
