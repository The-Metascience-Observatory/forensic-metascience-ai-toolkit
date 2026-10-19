// Render the actual status and item hooks against a controlled transport.
import { chromium } from 'playwright';
import ts from 'typescript';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try {
 const page=await browser.newPage();
 page.on('pageerror',e=>console.error(e.message));
 page.setDefaultTimeout(10000);
 await page.setContent('<div id="root"></div>');
 await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
 await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
 for(const [name,path] of [['requestCache','lib/requestCache.ts'],['sync','lib/reviewSync.ts'],['status','app/CacheStatus.tsx'],['item','app/images/useFeed.ts']]) {
  const code=ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  await page.addScriptTag({content:`window.modules ||= {}; (()=>{const exports={};const require=n=>n==='next/navigation'?{usePathname:()=>window.testPath || '/project/project/papers'}:n==='react'?window.React:n==='@/lib/requestCache'?window.modules.requestCache:window.modules.sync;${code}\nwindow.modules[${JSON.stringify(name)}]=exports;})();`});
 }
 await page.evaluate(()=>{
  window.pending=0;window.statusReads=0;window.syncEvents=0;window.hasDecision=false;
  window.fetch=async url=>{
   if(String(url).includes('method=status')){window.statusReads++;return {ok:true,json:async()=>({ready:true,pending_writes:window.pending})};}
   return {ok:true,json:async()=>({reviews:{reviewers:window.hasDecision?[{reviewer:'Test',decision:'confirmed',pending:!!window.pending}]:[]}})};
  };
  window.addEventListener('workbench-review-synced',()=>{window.syncEvents++;window.notified=performance.now();});
  const {CacheStatus,ReviewJudgments}=window.modules.status;
  function Harness(){const {item}=window.modules.item.useItem('project','run','image','item');return React.createElement(React.Fragment,null,React.createElement(CacheStatus),React.createElement(ReviewJudgments,{reviews:item?.reviews}));}
  window.root=ReactDOM.createRoot(document.getElementById('root'));window.root.render(React.createElement(Harness));
 });
 await page.waitForFunction(()=>window.statusReads>0);
 await page.evaluate(()=>{window.hasDecision=true;window.pending=1;window.dispatchEvent(new Event('workbench-review'));});
 await page.waitForFunction(()=>document.getElementById('root').textContent.includes('pending sync'));
 console.log('rendered pending:',await page.locator('#root').innerText());
 await page.evaluate(()=>{window.pending=0;window.acknowledged=performance.now();});
 await page.waitForFunction(()=>window.syncEvents===1 && !document.getElementById('root').textContent.includes('pending sync'));
 const delay=await page.evaluate(()=>window.notified-window.acknowledged);
 console.log('controlled database acknowledgment to browser refresh:',Math.round(delay),'ms');
 // Pending reviews use the five-second interval introduced by the workbench
 // efficiency changes; allow scheduling overhead in the concurrent test stack.
 assert.ok(delay<6500,`Expected acknowledgment within one pending polling interval, got ${delay}ms`);
 console.log('rendered synchronized:',await page.locator('#root').innerText());
 await page.evaluate(()=>window.dispatchEvent(new Event('workbench-review')));
 await page.waitForFunction(()=>window.syncEvents===2);
 await page.evaluate(()=>window.root.unmount());
 const reads=await page.evaluate(()=>window.statusReads);
 await page.waitForTimeout(600);
 assert.equal(await page.evaluate(()=>window.statusReads),reads);
 console.log('rendered review sync: delayed/immediate acknowledgment and unmount passed');
 await page.evaluate(()=>{
  window.testPath='/project/project/images/item';window.imageReads=0;window.sharedWrites=0;
  window.fetch=async (url,options)=>{
   if(options?.method==='POST')window.sharedWrites++;
   if(String(url).includes('method=image_status'))window.imageReads++;
   return {ok:true,json:async()=>({ready:true,local:true,pending_writes:0})};
  };
  window.root=ReactDOM.createRoot(document.getElementById('root'));
  window.root.render(React.createElement(window.modules.status.CacheStatus));
 });
 await page.waitForFunction(()=>document.getElementById('root').textContent.includes('Saved on this computer'));
 const before=await page.evaluate(()=>window.imageReads);
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await page.waitForFunction(n=>window.imageReads>n,before);
 assert.equal(await page.evaluate(()=>window.sharedWrites),0);
 await page.evaluate(()=>window.root.unmount());
 console.log('local image status and focus never synchronize shared storage');
} finally {await browser.close();}
