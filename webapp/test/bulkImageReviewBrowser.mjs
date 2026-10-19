import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
const page = await browser.newPage({viewport:{width:1500,height:1000}});
const requests = [], errors = [];
page.on('pageerror', e => errors.push(e.message));
const items = Array.from({length:3}, (_, i) => ({
  id:`item-${i}`, run_id:`run-${i}`, kind:'within', paper:{dir:`paper-${i}`},
  papers:[], panels:[], figure_labels:['Fig. 1'], detector_kind:'exact',
  rank:{score:10,reasons:[]}, decision:null, adjudication:null,
}));
let fail = true;
try {
  await page.addInitScript(() => localStorage.setItem('metascience.reviewer','Bulk test'));
  // The bulk save is a background job: POST starts it, GET ?job= polls it.
  const jobs = new Map();
  await page.route('**/api/images/bulk**', async route => {
    const request = route.request();
    if (request.method() === 'POST') {
      const body = request.postDataJSON(); requests.push(body);
      const id = `job-${jobs.size}`;
      const failed = [], saved = [];
      for (const target of body.items) {
        if (target.id === 'item-1' && fail) { fail = false; failed.push({id:target.id,run:target.run,error:'Simulated save failure'}); continue; }
        const item = items.find(it => it.id === target.id && it.run_id === target.run);
        item.decision = {decision:body.decision,reviewer:body.reviewer};
        saved.push(target.id);
      }
      jobs.set(id, {polls:0,result:{matched:body.items.length,saved:saved.length,failed,skipped_already_decided:0}});
      return route.fulfill({json:{ok:true,job:{id,state:'running',progress:{}}}});
    }
    const job = jobs.get(new URL(request.url()).searchParams.get('job'));
    // One poll still running, with progress, before the answer.
    if (job.polls++ === 0) return route.fulfill({json:{ok:true,job:{state:'running',progress:{to_save:job.result.matched,processed:0,saved:0}}}});
    return route.fulfill({json:{ok:true,job:{state:'done',progress:{},result:job.result}}});
  });
  await page.route(/\/api\/images(\?|$)/, async route => {
    return route.fulfill({json:{feed:{
      items,counts:{items:3,papers:3},notes:[],runs:[],built_at:'test',
      pagination:{offset:0,limit:50,total:3,next_offset:null},
    }}});
  });
  // Keep verification isolated from shared review writes and sync.
  await page.route('**/api/workbench**', route => route.fulfill({json:{ready:true,pending_writes:0}}));
  await page.goto((process.env.METASCIENCE_TEST_URL || 'http://localhost:3100') +
    '/project/image_discovery_2026-09_batch3/images');
  const all = page.getByRole('checkbox',{name:'Select all loaded rows',exact:true});
  const first = page.getByRole('checkbox',{name:'Select row 1',exact:true});
  await first.check();
  assert.equal(await all.evaluate(el => el.indeterminate),true);
  await all.check();
  assert.equal(await page.locator('tbody input:checked').count(),3);
  await all.uncheck();
  assert.equal(await page.locator('tbody input:checked').count(),0);
  await page.getByRole('button',{name:'Select all loaded rows',exact:true}).click();
  await page.getByRole('button',{name:'Mark selection as False positive',exact:true}).click();
  await page.getByText(/2 of 3 saved locally as False positive/).waitFor();
  assert.equal(await page.locator('tbody input:checked').count(),1);
  assert.equal(await page.getByRole('checkbox',{name:'Select row 2',exact:true}).isChecked(),true);
  assert.deepEqual(requests[0].items, items.map(it => ({id:it.id,run:it.run_id})));
  assert.deepEqual([requests[0].decision,requests[0].reviewer],['false_positive','Bulk test']);
  await page.getByRole('button',{name:'Mark selection as False positive',exact:true}).click();
  await page.getByText(/1 of 1 saved locally as False positive/).waitFor();
  assert.equal(await page.locator('tbody input:checked').count(),0);
  await page.waitForFunction(() => [...document.querySelectorAll('tbody tr')].every(row =>
    row.lastElementChild.textContent.includes('False positive')));
  await first.check();
  await page.getByRole('checkbox',{name:'undecided only'}).check();
  assert.equal(await page.locator('tbody input:checked').count(),0);
  assert.deepEqual(errors,[]);
  console.log('Bulk review passed: row selection, indeterminate/select-all toggle, exact run ownership, generic verdict, partial failure/retry, background job polling, rendered decisions, filter reset.');
} finally { await browser.close(); }
