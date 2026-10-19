import {chromium} from 'playwright';
import assert from 'node:assert/strict';
const base=process.env.METASCIENCE_TEST_URL||'http://localhost:3100';
const project=process.env.METASCIENCE_TEST_PROJECT||'masliah_papers';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try {
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>localStorage.setItem('metascience.reviewer','History browser test (writes mocked)'));
 async function feed(run){const r=await page.request.get(`${base}/api/images?${new URLSearchParams({project,run})}`);assert.equal(r.status(),200);return(await r.json()).feed;}
 const mixed=await feed('latest'),choices=mixed.runs.filter(r=>r.n_items>0&&r.version!=='unknown');
 assert.ok(choices.length>=2);const selection=choices[0].id,older=choices[1].id,selected=await feed(selection);
 const item=selected.items.find(i=>i.panels?.[0]?.image&&i.targets?.length&&i.paper?.pdf);assert.ok(item);
 const media=`${base}/api/media?${new URLSearchParams({project,dir:item.panels[0].paper_dir,f:item.panels[0].image})}`;
 const whole=await page.request.get(media),bytes=await whole.body();assert.equal(whole.status(),200);
 const range=await page.request.get(media,{headers:{Range:'bytes=-16'}});assert.equal(range.status(),206);assert.deepEqual(await range.body(),bytes.subarray(-16));
 assert.equal((await page.request.get(media,{headers:{'If-None-Match':whole.headers().etag}})).status(),304);
 const missing=await page.request.get(`${base}/api/media?${new URLSearchParams({project,dir:item.paper.dir,f:`__runs/${item.run_id}/missing`})}`);assert.ok(missing.status()>=400);
 const csv=await page.request.get(`${base}/api/images?${new URLSearchParams({project,run:selection,format:'csv'})}`),exported=await csv.text();
 assert.ok(exported.startsWith('run_id,id,publication_status,detector_kind,sentence,decision,reviewer'));assert.ok(exported.includes(item.run_id));
 await page.goto(`${base}/project/${project}/images?run=latest`);await page.waitForFunction(n=>document.querySelectorAll('tbody tr').length===n,mixed.items.length);
 await page.route('**/api/images?*',async route=>{if(new URL(route.request().url()).searchParams.get('run')===older)await new Promise(r=>setTimeout(r,800));await route.continue();});
 const picker=page.getByRole('combobox',{name:'Version / run'});await picker.selectOption(older);await picker.selectOption(selection);
 await page.waitForFunction(n=>document.querySelectorAll('tbody tr').length===n,selected.items.length);
 await page.waitForTimeout(1200);assert.equal(await picker.inputValue(),selection);assert.equal(await page.locator('tbody tr').count(),selected.items.length);
 await page.goto(`${base}/project/${project}/images/${encodeURIComponent(item.id)}?run=${selection}`);await page.getByText('← queue',{exact:true}).waitFor();
 await page.waitForFunction(()=>[...document.querySelectorAll('.pdf-scroll canvas')].some(c=>c.dataset.rendered==='true'));
 await page.screenshot({path:'/tmp/history-verified-comparison.png'});
 let posted;await page.route('**/api/images',async route=>{if(route.request().method()!=='POST')return route.continue();posted=route.request().postDataJSON();await route.fulfill({json:{ok:true,decision:{...posted,db_mirror:{state:'synced'}}}});});
 await page.keyboard.press('1');await page.waitForTimeout(500);assert.equal(posted.run,item.run_id);assert.notEqual(posted.run,selection);
 const summary=await page.request.get(`${base}/api/images/summary?${new URLSearchParams({project,run:item.run_id,item:item.id})}`);assert.equal(summary.status(),200);assert.match(summary.headers()['content-type'],/image\/png/);
 await page.getByText('← queue',{exact:true}).click();await page.waitForURL(u=>u.searchParams.get('run')===selection&&u.pathname.endsWith('/images'));
 await page.reload();await page.waitForFunction(n=>document.querySelectorAll('tbody tr').length===n,selected.items.length);
 await picker.selectOption(older);await page.waitForURL(u=>u.searchParams.get('run')===older);await page.goBack();await page.waitForURL(u=>u.searchParams.get('run')===selection);assert.equal(await picker.inputValue(),selection);
 await page.goto(`${base}/project/${project}/copypaste?run=latest`);await page.getByRole('heading',{name:'Copy/paste review'}).waitFor();
 assert.deepEqual(errors,[]);console.log(JSON.stringify({mixed_items:mixed.items.length,selected_items:selected.items.length,selection,owning_run:item.run_id,media_range:true,csv_provenance:true,pdf_rendered:true,summary_export:true,selection_navigation:true,page_errors:errors}));
}finally{await browser.close();}
