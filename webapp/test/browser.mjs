import { chromium } from 'playwright';
import assert from 'node:assert/strict';
const browser = await chromium.launch({headless:true, executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
const page = await browser.newPage({viewport:{width:1500,height:1000}});
try {
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>{ localStorage.setItem('metascience.reviewer','Browser test (requests mocked)'); });
const documents=[];page.on('request',r=>{if(r.resourceType()==='document')documents.push(r.url())});
const project=process.env.METASCIENCE_TEST_PROJECT || 'image_discovery_2026-09';
const base=process.env.METASCIENCE_TEST_URL || 'http://localhost:3100';
let t=performance.now();const resp=await page.request.get(`${base}/api/images?project=${project}`);assert.equal(resp.status(),200);const {feed}=await resp.json();
console.log('feed_http_ms',Math.round(performance.now()-t),'items',feed.items.length,'refresh',feed.refresh_needed);
assert.ok(feed.items.length >= 2,'Browser fixture requires two published image items');
const first=feed.items[0];const panel=first.panels[0];const q=new URLSearchParams({project,dir:panel.paper_dir,f:panel.image});
const full=await page.request.get(`${base}/api/media?${q}`);const bytes=await full.body();
const suffix=await page.request.get(`${base}/api/media?${q}`,{headers:{Range:'bytes=-16'}});assert.equal(suffix.status(),206);assert.deepEqual(await suffix.body(),bytes.subarray(-16));
const fresh=await page.request.get(`${base}/api/media?${q}`,{headers:{'If-None-Match':full.headers().etag}});assert.equal(fresh.status(),304);
console.log('media_suffix_and_revalidation','passed');
await page.goto(`${base}/project/${project}/images`);await page.locator('tbody tr').first().waitFor();
const kindOptions=await page.locator('label:has-text("kind") select option').allTextContents();
assert.ok(kindOptions.length>=2,'kind dropdown must list all and at least one detector kind');
for(const label of kindOptions){
  assert.match(label,/\(\d[\d,]*\)$/,`kind option must show a count: ${JSON.stringify(label)}`);
}
const nDocs=documents.length;t=performance.now();await page.locator('tbody tr').first().locator('a').first().click();
await page.locator('.pdf-finding').first().waitFor();
const target=first.targets[0].page;
await page.waitForFunction(p=>{const cv=document.querySelector(`[data-page="${p}"] canvas`);return cv && cv.dataset.rendered === "true"},target);
console.log('first_target_pdf_ready_ms',Math.round(performance.now()-t),'new_documents',documents.length-nDocs);
assert.equal(documents.length,nDocs);
await page.screenshot({path:process.env.METASCIENCE_TEST_SCREENSHOT || '/tmp/webapp-image-review.png'});
console.log('pdf_canvases',await page.locator('.pdf-scroll canvas').evaluateAll(xs=>({slots:xs.length,allocated:xs.filter(x=>x.width>0).length})));
// Search remains available independently of page rasterization.
await page.keyboard.press('Control+f');
const search = page.getByRole('textbox', {name:'Find in PDF'});
await search.waitFor();
await page.waitForFunction(() => [...document.querySelectorAll('.pdf-text-layer span')].some(x=>/[A-Za-z]{5,}/.test(x.textContent)));
const word = await page.locator('.pdf-text-layer span').evaluateAll(xs =>
  xs.map(x=>x.textContent.match(/[A-Za-z]{5,}/)?.[0]).find(Boolean));
assert.ok(word, 'visible PDF text must be selectable/searchable');
await search.fill(word);
await page.locator('.pdf-hit').first().waitFor();
await page.getByTitle('Close (Esc)').click();
// Zoom and split-pane refit must reuse the PDF document, not fetch it again.
let pdfRequests=0;
const countPdf = r => { if (new URL(r.url()).searchParams.get('f')?.endsWith('.pdf')) pdfRequests++; };
page.on('request',countPdf);
const zoom=page.getByRole('group',{name:'Zoom'});
await zoom.waitFor();
const pageWidth=()=>page.locator(`[data-page="${target}"] canvas`).evaluate(cv=>cv.getBoundingClientRect().width);
const widthBefore=await pageWidth();
await zoom.getByRole('button',{name:'Zoom in'}).click();
await page.waitForFunction(({p,w})=>{
  const cv=document.querySelector(`[data-page="${p}"] canvas`);
  return cv && cv.dataset.rendered==="true" && cv.getBoundingClientRect().width>w;
},{p:target,w:widthBefore});
const widthIn=await pageWidth();
assert.ok(widthIn>widthBefore,'zoom in must widen the page');
await zoom.getByRole('button',{name:'Zoom out'}).click();
await page.waitForFunction(({p,w})=>{
  const cv=document.querySelector(`[data-page="${p}"] canvas`);
  return cv && cv.dataset.rendered==="true" && cv.getBoundingClientRect().width<w;
},{p:target,w:widthIn});
const gutter = page.getByRole('separator', {name:'Resize the notes and evidence panes'});
await gutter.focus(); await page.keyboard.press('ArrowRight');
await page.waitForFunction(p=>{const cv=document.querySelector(`[data-page="${p}"] canvas`);return cv && cv.dataset.rendered === "true"},target);
assert.equal(pdfRequests,0,'zoom and refitting must reuse the loaded PDF');
page.off('request',countPdf);
let saves=0;
await page.route('**/api/images', async route => {
  if (route.request().method() !== 'POST') return route.continue();
  saves++;
  const body=route.request().postDataJSON();
  await new Promise(resolve=>setTimeout(resolve,150));
  await route.fulfill({json:{ok:true,decision:{item:body.item,decision:body.decision,reviewer:body.reviewer,note:body.note}}});
});
await page.keyboard.press('1'); await page.keyboard.press('1');
await page.waitForFunction(()=>!document.querySelector('aside button')?.disabled);
assert.equal(saves,1,'repeat decision hotkeys must coalesce');
t=performance.now();await page.getByRole('button',{name:'next ›',exact:true}).click();
await page.waitForURL(u=>u.pathname.includes(encodeURIComponent(feed.items[1].id)));
await page.waitForFunction(id => document.body.textContent.includes(id),feed.items[1].id);
await page.waitForFunction(p=>{const cv=document.querySelector(`[data-page="${p}"] canvas`); return cv && cv.dataset.rendered === "true"},feed.items[1].targets[0].page);
console.log('next_target_pdf_ready_ms',Math.round(performance.now()-t),'new_documents',documents.length-nDocs);
assert.equal(documents.length,nDocs);
await page.getByRole('link',{name:'← queue',exact:true}).click();await page.waitForURL(`${base}/project/${project}/images`);await page.locator('tbody tr').first().waitFor();
assert.equal(await page.locator('tbody tr').count(),feed.items.length);
assert.deepEqual(errors,[]);console.log('page_errors',errors);
} finally { await browser.close(); }
