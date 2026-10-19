import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base=process.env.METASCIENCE_TEST_URL || 'http://localhost:3199';
const project='image_discovery_2026-09_batch3';
const queue=`${base}/project/${project}/images?run=latest`;
const item='within:10.1038--onc.2017.172:IMGDUP-1';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1500,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try {
  for(const phase of ['fresh browser','warm reload']) {
    const start=performance.now();
    await page.goto(queue,{waitUntil:'domcontentloaded',timeout:60000});
    await page.locator('tbody tr').first().waitFor({timeout:60000});
    const rowsMs=Math.round(performance.now()-start);
    await page.waitForFunction(()=>{
      const visible=[...document.querySelectorAll('tbody img')].filter(i=>{const r=i.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight});
      return visible.length>=5&&visible.every(i=>i.complete&&i.naturalWidth>0);
    },{},{timeout:60000});
    const report=await page.evaluate(()=>{
      const images=[...document.querySelectorAll('tbody img')];
      const visible=images.filter(i=>{const r=i.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight});
      const media=performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/media'));
      return {rows:document.querySelectorAll('tbody tr').length,visible:visible.length,loaded:visible.filter(i=>i.complete&&i.naturalWidth).length,
        dimensions:visible.map(i=>[i.naturalWidth,i.naturalHeight]),imageRequests:media.length,imageBytes:media.reduce((sum,r)=>sum+r.encodedBodySize,0)};
    });
    assert.equal(report.rows,50);assert.ok(report.dimensions.every(([w,h])=>w<=260&&h<=120));
    console.log(JSON.stringify({phase,rowsMs,visibleReadyMs:Math.round(performance.now()-start),...report}));
  }
  const thumb=page.locator('tbody img').first();await thumb.hover();
  await page.waitForFunction(()=>[...document.images].some(i=>i.naturalWidth>260&&i.complete&&!i.src.includes('variant=thumbnail')),{},{timeout:30000});
  console.log('hover original image loaded');
  await page.mouse.move(1450,0);
  await page.route('**/api/images?**',async route=>{await new Promise(r=>setTimeout(r,2000));await route.continue();});
  const t=performance.now();
  await page.goto(`${base}/project/${project}/images/${encodeURIComponent(item)}?run=latest`);
  await page.getByRole('button',{name:'Show transform boxes',exact:true}).waitFor({timeout:60000});
  console.log('item controls visible with delayed queue_ms',Math.round(performance.now()-t));
  await page.locator('.pdf-duplication').first().waitFor({timeout:60000});
  await page.waitForFunction(()=>document.querySelector('[data-page="5"] canvas')?.dataset.rendered==='true',{},{timeout:60000});
  assert.equal(await page.locator('.pdf-duplication polygon').count(),2);
  const polygon=page.locator('.pdf-duplication polygon').first();assert.equal(await polygon.getAttribute('stroke'),'#00FFDD');
  await page.screenshot({path:process.env.METASCIENCE_TEST_SCREENSHOT || '/tmp/workbench-fast-review.png'});
  await page.unrouteAll({behavior:'wait'});
  await page.getByRole('link',{name:'← queue',exact:true}).click();
  await page.locator('tbody tr').first().waitFor();
  const params=new URLSearchParams({project,run:'latest',component:'image_forensics',verdict:'all',kind:'all',undecided:'false',judgments:JSON.stringify(['issue','unresolved']),offset:'0'});
  const feed=(await (await page.request.get(`${base}/api/images?${params}`)).json()).feed;
  const rel=feed.items[0].exhibit || feed.items[0].panels[0].image;
  const dir=feed.items[0].exhibit?feed.items[0].paper.dir:feed.items[0].panels[0].paper_dir;
  const media=`${base}/api/media?${new URLSearchParams({project,dir,f:rel,variant:'thumbnail'})}`;
  const endpoints={feed:`${base}/api/images?${params}`,item:`${base}/api/workbench?${new URLSearchParams({method:'item',project,run:'latest',component:'image_forensics',item})}`,thumbnail:media,status:`${base}/api/workbench?method=status`};
  for(const [name,url] of Object.entries(endpoints)) {
    const samples=[];let header;
    for(let i=0;i<21;i++){
      const start=performance.now();const response=await page.request.get(url);await response.body();
      assert.equal(response.status(),200,await response.text());if(i)samples.push(performance.now()-start);header=response.headers()['server-timing'];
    }
    samples.sort((a,b)=>a-b);console.log(JSON.stringify({endpoint:name,n:samples.length,p95_ms:Math.round(samples[Math.ceil(samples.length*.95)-1]),timings:header}));
  }
  const originalUrl=media.replace('&variant=thumbnail','');
  const original=await page.request.get(originalUrl);assert.equal(original.status(),200);const bytes=await original.body();
  const range=await page.request.get(originalUrl,{headers:{Range:'bytes=-16'}});assert.equal(range.status(),206);assert.deepEqual(await range.body(),bytes.subarray(-16));
  const unchanged=await page.request.get(originalUrl,{headers:{'If-None-Match':original.headers().etag}});assert.equal(unchanged.status(),304);
  assert.deepEqual(errors,[]);console.log('PDF boxes, navigation, byte ranges, ETag, and browser errors: passed');
} finally {await browser.close();}
