// Explicit live QA: use a disposable catalog seeded by test_workbench_videos.py.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const base = process.env.VIDEO_QA_BASE;
const database = process.env.VIDEO_QA_DB;
if (!base && !database) {
  console.log('SKIP: live video QA requires disposable VIDEO_QA_BASE and VIDEO_QA_DB');
  process.exit(0);
}
if (!base || !database?.startsWith('/tmp/')) throw new Error('Disposable VIDEO_QA_BASE and VIDEO_QA_DB required');
const browser = await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
try {
  const page = await browser.newPage({viewport:{width:1600,height:1000}});
  page.setDefaultTimeout(20000);
  const errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  await page.goto(`${base}/project/project/images/within%3Apaper%3AIMGDUP-1?run=r1`);
  const started=Date.now();
  const status=await (await page.request.get(`${base}/api/workbench?method=video_status&project=project&run=r1&item=within%3Apaper%3AIMGDUP-1`)).json();
  if(status.status!=='ready') {
    const generate=page.getByRole('button',{name:/^(Generate video|Retry video)$/});
    await generate.waitFor();
    await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>/^(Generate video|Retry video)$/.test(b.textContent)&&!b.disabled));
    await generate.click();
    await page.getByRole('button',{name:/Queuing|Queued|Generating/}).waitFor();
    await page.reload();
  }
  await page.getByRole('button',{name:/View video/}).waitFor({timeout:180000});
  const elapsed=(Date.now()-started)/1000;
  await page.getByRole('button',{name:/View video/}).click();
  const video=page.locator('video');
  await video.waitFor();
  await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2);
  const src=await video.getAttribute('src');
  assert.ok(src.includes('__videos'));
  const range=await page.request.get(new URL(src,base).href,{headers:{Range:'bytes=0-99'}});
  assert.equal(range.status(),206);
  assert.equal((await range.body()).length,100);
  await video.evaluate(v=>new Promise((resolve,reject)=>{
    v.pause(); v.addEventListener('seeked',()=>resolve(),{once:true});
    v.addEventListener('error',()=>reject(new Error('video decode failed')),{once:true});
    v.currentTime=20;
  }));
  assert.ok(Math.abs(await video.evaluate(v=>v.currentTime)-20)<1);
  await page.screenshot({path:'/tmp/on-demand-video-ready.png'});
  let stopped=0;
  for(const pid of readdirSync('/proc').filter(p=>/^\d+$/.test(p))) {
    try {
      const env=readFileSync(`/proc/${pid}/environ`,'utf8').split('\0');
      const cmd=readFileSync(`/proc/${pid}/cmdline`,'utf8');
      if(env.includes(`METASCIENCE_WORKBENCH_DB=${database}`)&&cmd.includes('metascience_agent.workbench.service')) {
        process.kill(Number(pid),'SIGTERM'); stopped++;
      }
    } catch { /* process exited */ }
  }
  assert.equal(stopped,1);
  await page.waitForTimeout(500);
  await page.reload();
  await page.getByRole('button',{name:/View video/}).waitFor();
  await page.getByRole('button',{name:/View video/}).click();
  assert.equal(await page.locator('video').getAttribute('src'),src);
  assert.deepEqual(errors,[]);
  const head=await page.request.head(new URL(src,base).href);
  console.log(JSON.stringify({elapsed_seconds:elapsed,bytes:Number(head.headers()['content-length']),
    seeking:true,persistent_after_service_restart:true,src}));
} finally { await browser.close(); }
