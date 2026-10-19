import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base=process.env.METASCIENCE_TEST_URL || 'http://localhost:3199';
const project='image_discovery_2026-09_batch3';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const page=await browser.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try {
  await page.addInitScript(project=>{
    localStorage.setItem(`metascience.images.filter.v4.${project}.latest`,JSON.stringify({
      verdict:'all',kind:'all',undecided:false,adjudicator:'Saved AI judgment: issue · low',judgments:['issue','unresolved'],
    }));
  },project);
  const requests=[];page.on('request',r=>{if(r.url().includes('/api/images?'))requests.push(new URL(r.url()));});
  await page.goto(`${base}/project/${project}/images`);
  await page.locator('tbody tr').first().waitFor();
  assert.equal(await page.locator('tbody tr').count(),50);
  assert.ok(requests.length>0);
  assert.ok(requests.every(url=>!url.searchParams.has('adjudicator')),'Removed control must not send hidden filters');
  assert.ok(requests.every(url=>url.searchParams.get('judgments')==='["issue","unresolved"]'),'Restore preferences before first feed request');
  await page.getByText('Adjudicator output: Issue, Unresolved',{exact:true}).click();
  await page.getByRole('checkbox',{name:/^Issue \(/}).uncheck();
  await page.getByRole('checkbox',{name:/^Unresolved \(/}).uncheck();
  await page.getByText(/saved results exist in this run selection/).waitFor();
  assert.equal(await page.locator('tbody tr').count(),0);
  await page.getByRole('button',{name:'Reset filters',exact:true}).click();
  await page.locator('tbody tr').first().waitFor();
  assert.equal(await page.locator('tbody tr').count(),50);
  assert.equal(await page.getByText('Saved candidates are available for review; viewing them does not publish them.',{exact:false}).count(),0);
  const kind=page.locator('tbody tr').first().locator('td').nth(5);
  assert.match(await kind.innerText(),/transformed_match\s+v[\d.]+/);
  assert.doesNotMatch(await kind.innerText(),/ar_/);
  assert.equal(await kind.locator('div').count(),0);
  await page.screenshot({path:'/tmp/workbench-fast-queue.png'});
  assert.deepEqual(errors,[]);
  console.log('Saved obsolete filter, initial restored query, truthful empty state, and reset recovery: passed');
} finally {await browser.close();}
