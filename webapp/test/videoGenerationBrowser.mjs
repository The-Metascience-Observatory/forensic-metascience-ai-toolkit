import { chromium } from 'playwright';
import ts from 'typescript';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try {
 const page=await browser.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<div id="root"></div>');
 await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
 await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
 const code=ts.transpileModule(readFileSync('app/project/[project]/images/[item]/VideoGeneration.tsx','utf8'),{
   compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 await page.addScriptTag({content:`(()=>{const exports={};const require=()=>window.React;${code}\nwindow.videoModule=exports;})();`});
 await page.evaluate(()=>{
   window.mode='failure';window.phase='idle';window.calls=[];
   window.fetch=async (url,options={})=>{
     window.calls.push({url,body:options.body});
     if(options.method==='POST') {
       if(window.mode==='failure')return {ok:false,json:async()=>({error:'Panel source unavailable'})};
       if(window.mode==='timeout'){window.phase='ready';window.failReads=1;return {ok:false,status:504,json:async()=>({error:'Error: Workbench request timed out'})};}
       window.phase='running';setTimeout(()=>window.phase='ready',100);
       return {ok:true,json:async()=>({status:'queued',can_generate:true})};
     }
     if(window.failReads>0){window.failReads--;throw new TypeError('Network interrupted');}
     return {ok:true,json:async()=>window.mode==='unsupported'
       ? {status:'idle',can_generate:false,reason:'No usable recorded transformation is available.'}
       : {status:window.phase,can_generate:true,video:window.phase==='ready'?'__videos/job/hash.mp4':null,thumbnail:window.phase==='ready'?'__videos/job/titlehash.png':null}};
   };
   window.root=ReactDOM.createRoot(document.getElementById('root'));
   window.item={id:'within:p:IMGDUP-1',run_id:'r_old',record_revision:'one',paper:{dir:'paper'},
     video_generation:{status:'idle',can_generate:true}};
   function Harness(){const s=window.videoModule.useVideoGeneration('project',window.item);
     return React.createElement(window.videoModule.VideoGeneration,{state:s});}
   window.show=()=>window.root.render(React.createElement(Harness));window.show();
 });
 // Embedded idle status avoids a second item/status fetch.
 await page.evaluate(()=>{window.item={...window.item,id:'embedded-status',record_revision:'embedded',video_generation:{status:'idle',can_generate:true}};window.calls=[];window.show();});
 await page.getByRole('button',{name:'Generate video',exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>window.calls.length),0);
 await page.evaluate(()=>{delete window.item.video_generation;window.item={...window.item,id:'within:p:IMGDUP-1',record_revision:'one'};window.show();});
 await page.getByRole('button',{name:'Generate video',exact:true}).click();
 await page.getByRole('button',{name:'Retry video',exact:true}).waitFor();
 assert.match(await page.locator('[role=status]').innerText(),/Panel source unavailable/);
 const sent=await page.evaluate(()=>JSON.parse(window.calls.find(c=>c.body).body));
 assert.equal(sent.run,'r_old');assert.equal(sent.item,'within:p:IMGDUP-1');
 await page.evaluate(()=>window.mode='success');
 await page.getByRole('button',{name:'Retry video',exact:true}).click();
 await page.getByRole('button',{name:/Queued|Generating/}).waitFor();
 await page.getByText('Saved on this computer').waitFor();
 const thumbnail=page.getByRole('link',{name:'Download thumbnail',exact:true});
 await thumbnail.waitFor();
 const params=new URL(await thumbnail.getAttribute('href'),'http://localhost').searchParams;
 assert.equal(params.get('f'),'__videos/job/titlehash.png');
 assert.equal(params.get('dir'),'paper');assert.equal(params.get('project'),'project');
 assert.equal(params.get('download'),'1');
 assert.notEqual(await thumbnail.getAttribute('download'),null);
 // Media availability changes without changing the scientific record. A
 // refreshed failure must replace local ready state and expose regeneration.
 await page.evaluate(()=>{
   window.item={...window.item,video_generation:{status:'failed',can_generate:true,
     revision:'missing-file',error:'Saved video is unavailable or changed'}};
   window.show();
 });
 await page.getByRole('button',{name:'Retry video',exact:true}).waitFor();
 assert.equal(await page.getByText('Saved on this computer').count(),0);
 await page.getByRole('button',{name:'Retry video',exact:true}).click();
 await page.getByText('Saved on this computer').waitFor();
 // A late response from an older job snapshot cannot overwrite newer props.
 await page.evaluate(()=>{
   window.originalFetch=window.fetch;
   window.fetch=()=>new Promise(resolve=>{window.finishOldRead=resolve;});
   window.item={...window.item,video_generation:{status:'queued',can_generate:true,revision:'queued-snapshot'}};
   window.show();
 });
 await page.waitForFunction(()=>!!window.finishOldRead);
 await page.evaluate(()=>{
   window.item={...window.item,video_generation:{status:'failed',can_generate:true,revision:'new-failure',error:'Newer failure'}};
   window.show();
 });
 await page.getByRole('button',{name:'Retry video',exact:true}).waitFor();
 await page.evaluate(async()=>{
   window.finishOldRead({ok:true,json:async()=>({status:'ready',can_generate:true,video:'stale.mp4'})});
   await new Promise(resolve=>setTimeout(resolve,50));
   window.fetch=window.originalFetch;
 });
 assert.equal(await page.getByText('Saved on this computer').count(),0);
 assert.match(await page.locator('[role=status]').innerText(),/Newer failure/);
 await page.evaluate(()=>{delete window.item.video_generation;});
 // A timed-out POST may already have completed. Recover through GET, even
 // when the first reconciliation request also fails, without another POST.
 await page.evaluate(()=>{window.mode='timeout';window.phase='idle';window.item={...window.item,id:'timeout-item',record_revision:'timeout'};window.show();});
 await page.getByRole('button',{name:'Generate video',exact:true}).click();
 await page.getByText('Connection interrupted; checking video status…').waitFor();
 await page.getByRole('link',{name:'Download thumbnail',exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>window.calls.filter(c=>c.body&&JSON.parse(c.body).item==='timeout-item').length),1);
 assert.equal(await page.getByText('Saved on this computer').count(),1);
 // Initial status failures must also recover rather than remaining blank.
 await page.evaluate(()=>{window.failReads=1;window.item={...window.item,id:'initial-read-failure',record_revision:'read-failure'};window.show();});
 await page.getByText('Connection interrupted; checking video status…').waitFor();
 await page.getByRole('link',{name:'Download thumbnail',exact:true}).waitFor();
 await page.evaluate(()=>{window.mode='unsupported';window.item={...window.item,id:'another',record_revision:'two'};window.show();});
 await page.getByText('No usable recorded transformation is available.').waitFor();
 assert.equal(await page.getByRole('button',{name:'Generate video',exact:true}).isDisabled(),true);
 await page.evaluate(()=>window.root.unmount());
 assert.deepEqual(errors,[]);
 console.log('Video controls: exact run, source failure, retry, queued-to-ready, navigation and unsupported state passed');
} finally {await browser.close();}
