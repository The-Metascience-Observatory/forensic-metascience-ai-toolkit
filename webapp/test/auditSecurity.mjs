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
import {asRecord, errMsg, jsonError} from '../lib/err.ts';
import {mediaType,mediaDisposition,cacheControl} from '../lib/media.ts';
import {byteRange} from '../lib/byteRange.ts';
function endpoint(file,modules={}) {
 const exports={};
 const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 vm.runInNewContext(code,{exports,URL,Response,ReadableStream,TextEncoder,process,require:name=>({
  'next/server':{NextResponse:Response},'@/lib/mutation':{rejectCrossOrigin},'@/lib/err':{asRecord,errMsg,jsonError},...modules,
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
for(const headers of [{},{origin:'http://localhost:3100'},{'sec-fetch-site':'same-origin'},
  // serve.mjs prints 127.0.0.1 while Next reports localhost in req.url.
  {origin:'http://127.0.0.1:3100'},{origin:'http://[::1]:3100'}])
 assert.equal(rejectCrossOrigin(new Request('http://localhost:3100/api/settings',{headers})),null,JSON.stringify(headers));
// Loopback aliases only: another port or scheme, or a rebinding name, stays refused.
for(const origin of ['http://127.0.0.1:3101','https://127.0.0.1:3100','http://rebind.invalid:3100','http://127.0.0.2:3100','not a url'])
 assert.equal(rejectCrossOrigin(new Request('http://localhost:3100/api/settings',{headers:{origin,host:'rebind.invalid:3100'}}))?.status,403,origin);
// Hosted mode (lib/accessToken.ts): routes trust only the identity header
// the proxy sets after verifying the Cloudflare Access token. The real
// routeGuard runs against a fixed directory (an email it does not list has
// no identity); the workbench is a recorder; no project sources are set.
{
 const saved={...process.env};
 process.env.METASCIENCE_ACCESS_TEAM='audit-team';process.env.METASCIENCE_ACCESS_AUD='a'.repeat(64);
 process.env.METASCIENCE_PUBLIC_ORIGIN='https://review.example.org';
 const {hostedMode}=await import('../lib/accessToken.ts');
 const DIRECTORY=[{email:'dan@example.org',name:'Dan Elton',role:'admin',projects:[]},{email:'rev@example.org',name:'Second Reviewer',role:'reviewer',projects:['p']}];
 const signedInEmail=req=>{const e=req.headers.get('x-ms-reviewer-email');return hostedMode()&&e?e:null;};
 const identity=req=>{const e=signedInEmail(req);return e?DIRECTORY.find(r=>r.email===e)||null:null;};
 const mayOpenProject=(who,p)=>who.role==='admin'||who.projects.includes(p);
 const auth={hostedMode,identity,signedInEmail,mayOpenProject,NOT_SET_UP:'not set up',withReviewer:(req,body,field='reviewer')=>{const who=identity(req);return who?{...body,[field]:who.name}:body;}};
 const routeGuard=endpoint('lib/routeGuard.ts',{'./auth.ts':auth,'./projectSources.ts':{sourceView:async()=>null},'server-only':{}});
 const calls=[];
 const mods={'@/lib/routeGuard':routeGuard,'@/lib/auth':auth,'node:path':{default:path},'node:fs':{default:fs},
  '@/lib/workbench':{workbench:async(method,params)=>{calls.push({method,params});return {ok:true,issues:{review:{}},pending:0};},workbenchTimed:async()=>({value:{},timings:{}}),serverTiming:()=>''},
  '@/lib/settings':{hostPath:p=>p,saveSettings:()=>{throw Error('settings saved');},loadSettings:()=>({python_bin:'/opt/python',papers_root:'/srv/papers',known_reviewers:['Dan Elton','Second Reviewer'],reviewers:DIRECTORY})}};
 const as=(email,route,{headers={},body='{}',method='POST'}={})=>new Request(`http://review.example.org/api/${route}`,{method,body:method==='GET'?undefined:body,
  headers:{origin:'https://review.example.org','x-forwarded-proto':'https','content-type':'application/json',...(email?{'x-ms-reviewer-email':email}:{}),...headers}});
 const MUTATIONS=['settings','draft','metadata','index','stats','viewed','reveal','images','images/bulk','images/missed','images/viewed','images/sync','images/reference','projects','review','workbench'];
 const api=Object.fromEntries(MUTATIONS.map(r=>[r,endpoint(`app/api/${r}/route.ts`,mods)]));
 // No token (so no identity header from the proxy): 401 everywhere, body unread.
 for(const route of MUTATIONS){const req=as(null,route);req.json=()=>{throw Error('parsed before 401');};assert.equal((await api[route].POST(req)).status,401,`${route} anonymous`);}
 // The public origin is same-origin through the tunnel; a foreign one is still refused first.
 for(const route of MUTATIONS){const req=as('dan@example.org',route,{headers:{origin:'https://evil.example.org'}});req.json=()=>{throw Error('parsed before 403');};assert.equal((await api[route].POST(req)).status,403,`${route} foreign origin`);}
 assert.equal(rejectCrossOrigin(as('dan@example.org','review')),null,'public origin with x-forwarded-proto accepted');
 // Admin routes: 403 for a reviewer and for an email outside the directory; the admin gets past the guard.
 for(const route of ['settings','draft','metadata','index','stats','images/reference','images/sync','projects']){
  for(const who of ['rev@example.org','stranger@example.org'])assert.equal((await api[route].POST(as(who,route))).status,403,`${route} ${who}`);
  const r=await api[route].POST(as('dan@example.org',route));assert.ok(![401,403].includes(r.status),`${route} admin got ${r.status}`);
 }
 for(const who of ['rev@example.org','dan@example.org'])assert.equal((await api.reveal.POST(as(who,'reveal',{body:JSON.stringify({project:'p',dir:'d'})}))).status,403,`reveal ${who}`);
 for(const [m,expected] of [['register_root',403],['map_paper',403],['register_file',403],['sync',403],['review',200]]){
  assert.equal((await api.workbench.POST(as('rev@example.org','workbench',{body:JSON.stringify({method:m,project:'p',reviewer:'Mallory'})}))).status,expected,`workbench ${m} reviewer`);
  assert.equal((await api.workbench.POST(as('dan@example.org','workbench',{body:JSON.stringify({method:m})}))).status,200,`workbench ${m} admin`);
 }
 // The body's reviewer is ignored: the recorded name is the directory's display name, or the address for an unlisted email.
 calls.length=0;
 assert.equal((await api.review.POST(as('rev@example.org','review',{body:JSON.stringify({project:'p',slug:'s',reviewer:'Mallory',patch:{issue_id:'i',decision:'true_issue'}})}))).status,200);
 assert.equal(calls[0].params.reviewer,'Second Reviewer','review');
 // An email the directory does not list may do nothing, and another project is refused.
 const before=calls.length;
 assert.equal((await api.images.POST(as('stranger@example.org','images',{body:JSON.stringify({project:'p',run:'r',item:'i',decision:'false_positive',reviewer:'Mallory'})}))).status,403);
 assert.equal((await api.images.POST(as('rev@example.org','images',{body:JSON.stringify({project:'other',run:'r',item:'i',decision:'false_positive'})}))).status,403);
 assert.equal((await api.review.POST(as('rev@example.org','review',{body:JSON.stringify({project:'other',slug:'s',patch:{issue_id:'i',decision:'true_issue'}})}))).status,403);
 assert.equal(calls.length,before,'nothing reached the service');
 for(const [route,field] of [['images/bulk','reviewer'],['images/missed','reviewer'],['images/viewed','viewer'],['viewed','viewer']]){
  assert.equal((await api[route].POST(as('rev@example.org',route,{body:JSON.stringify({project:'p',decision:'false_positive',reviewer:'Mallory',viewer:'Mallory'})}))).status,200,route);
  assert.equal(calls.at(-1).params[field],'Second Reviewer',route);
 }
 assert.equal((await api.workbench.POST(as('rev@example.org','workbench',{body:JSON.stringify({method:'review',project:'p',reviewer:'Mallory'})}))).status,200);
 assert.equal(calls.at(-1).params.reviewer,'Second Reviewer','workbench review');
 // GET /api/settings: names only for a reviewer, the whole file for the admin, 401 without identity.
 const names=await(await api.settings.GET(as('rev@example.org','settings',{method:'GET'}))).json();
 assert.deepEqual(names,{known_reviewers:['Dan Elton','Second Reviewer']});
 const full=await(await api.settings.GET(as('dan@example.org','settings',{method:'GET'}))).json();
 assert.equal(full.papers_root,'/srv/papers');assert.equal(full.python_bin,'/opt/python');
 assert.equal((await api.settings.GET(as(null,'settings',{method:'GET'}))).status,401);
 for(const k of Object.keys(process.env))if(!(k in saved))delete process.env[k];Object.assign(process.env,saved);
 // Back in local mode the same requests need no identity.
 assert.equal((await api.viewed.POST(new Request('http://localhost:3100/api/viewed',{method:'POST',body:'{"viewer":"Typed"}'}))).status,200);
 assert.equal(calls.at(-1).params.viewer,'Typed','local mode keeps the body\'s name');
}
const root=mkdtempSync(path.join(tmpdir(),'audit-media-'));let browser;
try {
 const file=path.join(root,'evidence.html');
 writeFileSync(file,`<body>Evidence<script>window.ran=true;fetch('/api/settings').then(()=>window.read=true).catch(()=>window.blocked=true);try{window.storage=localStorage.length}catch{window.isolated=true}</script>`);
 const api=endpoint('app/api/media/route.ts',{
  'node:fs':{default:fs},'node:fs/promises':{default:fsp},'node:stream':{Readable},
  '@/lib/err':{errMsg:e=>e.message},'@/lib/media':{mediaType,mediaDisposition,cacheControl},'@/lib/byteRange':{byteRange},'@/lib/routeGuard':{guard:async()=>null},
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
 console.log('auditSecurity: all mutation guards, hosted-mode identity and role gating, rendered HTML isolation, ranges and cache headers passed');
} finally {await browser?.close();rmSync(root,{recursive:true,force:true});}
