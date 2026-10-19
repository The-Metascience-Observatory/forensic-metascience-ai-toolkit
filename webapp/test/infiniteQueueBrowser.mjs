import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base=process.env.METASCIENCE_TEST_URL || 'http://localhost:3199';
const project='image_discovery_2026-09_batch3';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1500,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try {
  await page.goto(`${base}/project/${project}/images`);
  await page.locator('tbody tr').first().waitFor();
  assert.equal(await page.locator('tbody tr').count(),50);
  assert.equal(await page.getByRole('button',{name:/Previous 50|Next 50/}).count(),0);
  assert.equal(await page.getByText(/in view · ranked by the shared triage rule/).count(),0);
  const first=await page.locator('tbody tr').evaluateAll(rows=>rows.map(row=>row.querySelector('a').getAttribute('href')));
  const scroll=page.locator('table').locator('..');
  let fail=true;
  await page.route('**/api/images?**',async route=>{
    if (new URL(route.request().url()).searchParams.get('offset')==='50' && fail) {
      fail=false;return route.fulfill({status:503,json:{error:'Simulated next-page outage'}});
    }
    return route.continue();
  });
  await scroll.evaluate(el=>el.scrollTop=el.scrollHeight);
  await page.getByRole('button',{name:'Retry loading',exact:true}).waitFor();
  assert.equal(await page.locator('tbody tr').count(),50,'Failed next page must preserve loaded rows');
  await page.getByRole('button',{name:'Retry loading',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('tbody tr').length>=100);
  const hrefs=await page.locator('tbody tr').evaluateAll(rows=>rows.map(row=>row.querySelector('a').getAttribute('href')));
  assert.deepEqual(hrefs.slice(0,50),first);
  assert.equal(new Set(hrefs).size,hrefs.length,'Infinite pages must not duplicate items');
  const row=page.locator('tbody tr').nth(75);
  await row.locator('td').first().click();
  await row.locator('a').first().focus();
  await page.keyboard.press('ArrowDown');
  assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('data-row-index')),'76');
  assert.equal(await page.locator('tr[aria-current="true"]').getAttribute('data-row-index'),'76');
  await page.keyboard.press('ArrowUp');
  assert.equal(await page.locator('tr[aria-current="true"]').getAttribute('data-row-index'),'75');
  await page.keyboard.press('j');await page.keyboard.press('k');
  assert.equal(await page.locator('tr[aria-current="true"]').getAttribute('data-row-index'),'75');
  const bounds=await row.evaluate(el=>{const r=el.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:innerHeight}});
  assert.ok(bounds.top>=0 && bounds.bottom<=bounds.height,'Arrow selection stays visible');
  await page.getByRole('checkbox',{name:'undecided only'}).focus();await page.keyboard.press('ArrowDown');
  assert.equal(await page.locator('tr[aria-current="true"]').getAttribute('data-row-index'),'75','Typing controls retain arrow behavior');
  await row.locator('td').first().click();
  const href=await row.locator('a').first().getAttribute('href');
  await page.keyboard.press('Enter');await page.waitForURL(url=>url.pathname===new URL(href,base).pathname);
  await page.goBack();
  await page.locator('tbody tr').nth(75).waitFor();
  await page.locator('tr[aria-current="true"][data-row-index="75"]').waitFor();
  assert.equal(await page.locator('tr[aria-current="true"]').getAttribute('data-row-index'),'75','Returning restores loaded pages and selection');
  await page.getByRole('combobox',{name:/^kind/}).selectOption('cross');
  await page.getByText(/saved results exist in this run selection/).waitFor();
  assert.equal(await page.locator('tbody tr').count(),0,'New filters cannot retain rows from old pages');
  await page.getByRole('button',{name:'Reset filters',exact:true}).click();
  await page.locator('tbody tr').first().waitFor();
  assert.deepEqual(errors,[]);
  console.log('Infinite scroll: append/order, failure retry, arrows, input isolation, Enter/back restoration, and filter reset passed');
} finally {await page.unrouteAll({behavior:'wait'});await browser.close();}
