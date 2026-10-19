import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const base=process.env.METASCIENCE_TEST_URL || 'http://localhost:3120';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1500,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
// METASCIENCE_TEST_SCENARIO=partial checks a paper whose only runs are partial
// pipelines (tools_only): its findings appear, labelled provisional, each with
// the tool that triggered it, and a finding's detail opens on ITS run. Set
// METASCIENCE_TEST_PARTIAL to "<project>/<paper dir>"; any corpus of tools_only
// runs serves (the 2026-10-18 check used the GRIM ground-truth verified_dev).
async function partialScenario(){
 const [project,...rest]=(process.env.METASCIENCE_TEST_PARTIAL||'').split('/');const dir=rest.join('/');
 assert.ok(project&&dir,'set METASCIENCE_TEST_PARTIAL=<project>/<paper dir>');
 const paper=await (await page.request.get(`${base}/api/paper?${new URLSearchParams({project,slug:dir,dir})}`)).json();
 const issues=paper.issues.issues;assert.ok(issues.length>0,'a partial-only paper shows its findings');
 assert.equal(paper.issues.source.partial_fallback,true);
 assert.match(paper.issues.source.pipeline.label,/provisional/);
 const details=[];page.on('response',r=>{if(r.url().includes('method=issue_detail'))details.push(r);});
 await page.goto(`${base}/project/${encodeURIComponent(project)}/review/${encodeURIComponent(dir)}?dir=${encodeURIComponent(dir)}`);
 await page.locator('[data-tool-badge]').first().waitFor({timeout:30000});
 const note=await page.locator('[data-partial-run]').innerText();
 assert.match(note,/no complete review/);assert.match(note,/tools only · provisional/);
 const shown=Math.min(issues.length,50);
 assert.equal(await page.locator('[data-tool-badge]').count(),shown,'every finding card carries a tool badge');
 const backed=issues.find(i=>i.tool_source==='tool_verdict');
 if(backed)assert.ok(await page.locator(`[data-tool-badge="tool_verdict"]`,{hasText:backed.tool}).count()>0);
 const options=await page.getByLabel('Version / run').locator('option').allInnerTexts();
 assert.ok(options.some(o=>o.includes('tools only · provisional')),options.join('\n'));
 await page.waitForTimeout(1500);
 assert.ok(details.length>0,'the focused finding loaded its detail');
 for(const r of details){assert.equal(r.status(),200,await r.text());assert.ok(new URL(r.url()).searchParams.get('run'),'detail names the run');}
 assert.equal(await page.getByText('Finding not in this project').count(),0);
 // An explicitly selected partial run behaves the same way.
 const other=paper.issues.run_options.find(o=>o.pipeline&&o.id!==paper.issues.latest_run);
 if(other){details.length=0;
  await page.goto(`${base}/project/${encodeURIComponent(project)}/review/${encodeURIComponent(dir)}?dir=${encodeURIComponent(dir)}&run=${other.id}`);
  await page.locator('[data-tool-badge]').first().waitFor({timeout:30000});await page.waitForTimeout(1500);
  assert.match(await page.locator('[data-partial-run]').innerText(),/^Partial run/);
  for(const r of details){assert.equal(r.status(),200,await r.text());assert.equal(new URL(r.url()).searchParams.get('run'),other.id);}
  assert.ok(details.length>0);console.log('explicit partial run',other.id,'detail loaded on its own run');}
 await page.goto(`${base}/project/${encodeURIComponent(project)}/review/${encodeURIComponent(dir)}?dir=${encodeURIComponent(dir)}`);
 await page.locator('[data-tool-badge]').first().waitFor({timeout:30000});await page.waitForTimeout(1000);
 await page.screenshot({path:process.env.METASCIENCE_TEST_SCREENSHOT||'/tmp/workbench-partial.png'});
 assert.deepEqual(errors,[]);console.log(`partial run: ${issues.length} findings, ${shown} tool badges, provisional label and detail on the finding's run`);
}
try{
 if(process.env.METASCIENCE_TEST_SCENARIO==='partial'){await partialScenario();await browser.close();process.exit(0);}
 const project='image_discovery_2026-09';const timings=[];
 for(let n=0;n<21;n++){
  const start=performance.now();const response=await page.request.get(`${base}/api/images?project=${project}&verdict=all`);
  assert.equal(response.status(),200);const raw=await response.body(),{feed}=JSON.parse(raw);
  assert.equal(feed.items.length,50);assert.ok(raw.length<250000);if(n)timings.push(performance.now()-start);
 }
 timings.sort((a,b)=>a-b);console.log('50-row HTTP p95_ms',Math.round(timings[Math.ceil(timings.length*.95)-1]));
 const {feed}=await (await page.request.get(`${base}/api/images?project=${project}&verdict=all`)).json();
 const first=feed.items.find(i=>i.panels?.length===2);assert.ok(first);
 const detailResponse=await page.request.get(`${base}/api/workbench?${new URLSearchParams({method:'item',project,run:first.run_id,item:first.id,component:'image_forensics'})}`);
 const detail=await detailResponse.json();assert.equal(detailResponse.status(),200,JSON.stringify(detail));
 assert.ok(detail.panels?.[0]);assert.ok(detail.measurements);
 await page.goto(`${base}/project/${project}`);await page.locator('tbody tr').first().waitFor();assert.equal(await page.locator('tbody tr').count(),50);
 await page.getByRole('button',{name:'Next 50',exact:true}).click();await page.waitForTimeout(300);
 await page.goto(`${base}/project/${project}/images/${encodeURIComponent(first.id)}?run=${first.run_id}`);
 await page.getByText('loading…',{exact:true}).waitFor({state:'hidden',timeout:30000});
 await page.waitForTimeout(1500);await page.screenshot({path:'/tmp/workbench-image.png'});
 const panel=detail.panels.find(p=>p.image);
 if(panel){const q=new URLSearchParams({project,dir:panel.paper_dir,f:panel.image});const response=await page.request.get(`${base}/api/media?${q}`);
  if(response.ok()){const bytes=await response.body();const range=await page.request.get(`${base}/api/media?${q}`,{headers:{Range:'bytes=-16'}});assert.equal(range.status(),206);assert.deepEqual(await range.body(),bytes.subarray(-16));
   const cached=await page.request.get(`${base}/api/media?${q}`,{headers:{'If-None-Match':response.headers().etag}});assert.equal(cached.status(),304);console.log('verified artifact byte ranges and ETag passed');
  } else {assert.equal(response.status(),404);console.log('artifact explicitly unavailable',await response.text());}}
 await page.goto(`${base}/project/cerebrolysin_papers/review/10.1039--d3na00760j?dir=10.1039--d3na00760j`);
 await page.getByText('Bbb grim 12 32 (BBB tests)',{exact:false}).first().waitFor({timeout:30000});
 await page.waitForTimeout(2000);await page.screenshot({path:'/tmp/workbench-paper.png'});
 assert.deepEqual(errors,[]);console.log('project pagination, image details, paper findings rendered without browser errors');
}finally{await browser.close();}
