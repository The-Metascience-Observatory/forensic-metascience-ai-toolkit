import {chromium} from 'playwright';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try {
 const page=await browser.newPage({viewport:{width:900,height:800}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<div id="root"></div>');
 await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
 await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
 await page.evaluate(()=>window.modules={'react':window.React,'@/app/images/lib':{mediaUrl:(p,d,image)=>image}});
 const code=ts.transpileModule(readFileSync('app/project/[project]/images/[item]/TextSupport.tsx','utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 await page.addScriptTag({content:`(()=>{const exports={};const require=n=>window.modules[n];${code}\nwindow.TextSupport=exports.TextSupport})();`});
 const loc={status:'measured',reason:'text_localized',boxes:[{box:[10,20,100,40],text:'MDA-MB-231',confidence:95}],size:[200,200],mask_fraction:.045};
 let value={status:'measured',reason:'text_label_only',policy:'diagnostic',would_demote:true,demote:false,n_inliers:62,text_inliers_both:61,nontext_inliers:1,inlier_floor:15,uid_a:'a',uid_b:'b',a:loc,b:loc};
 let item={panels:[{uid:'a',paper_dir:'paper',image:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><text x="10" y="35">MDA-MB-231</text></svg>'},{uid:'b',paper_dir:'paper',image:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"/>'}]};
 async function render(v){await page.evaluate(({value,item})=>ReactDOM.render(React.createElement(window.TextSupport,{value,item,project:'test'}),document.getElementById('root')),{value:v,item});}
 await render(value);
 assert.match(await page.textContent('body'),/Diagnostic only/);
 assert.match(await page.textContent('body'),/61 of 62/);
 assert.equal(await page.locator('svg rect').count(),0);
 await page.getByRole('switch',{name:'Show excluded text regions'}).check();
 assert.equal(await page.locator('svg rect').count(),2);
 await page.getByRole('switch').uncheck();
 assert.equal(await page.locator('svg rect').count(),0);
 await page.getByRole('switch').check();
 assert.equal(await page.locator('svg rect').first().getAttribute('x'),'10');
 await render({...value,demote:true});
 assert.match(await page.textContent('body'),/Retained as text-label context/);
 await render({status:'abstained',reason:'ocr_unavailable'});
 assert.match(await page.textContent('body'),/not measured reliably/);
 assert.equal(await page.locator('svg').count(),0);
 await render(null);assert.match(await page.textContent('body'),/not measured/);
 // Optional real archived replay for visual QA, without touching the workbench DB.
 if(process.env.TEXT_SUPPORT_REPLAY) {
   const replay=JSON.parse(readFileSync(process.env.TEXT_SUPPORT_REPLAY,'utf8'));
   const rows=Array.isArray(replay)?replay:replay.rows;
   const reviews=JSON.parse(readFileSync(process.env.TEXT_SUPPORT_REVIEWS,'utf8')).rows;
   const row=rows.find(r=>r.item.includes('acc4eb'));
   const reviewed=reviews.find(r=>r.issue_key===row.item);
   value=row.result.match_stats.text_support;
   item={panels:reviewed.panels.map(p=>({uid:p.uid,paper_dir:'paper',image:'data:image/png;base64,'+readFileSync(p.path).toString('base64')}))};
   await render(value);
   if(process.env.TEXT_SUPPORT_SCREENSHOT) await page.screenshot({path:process.env.TEXT_SUPPORT_SCREENSHOT,fullPage:true});
 }
 assert.deepEqual(errors,[]);
 console.log('Text support: diagnostic/context/abstention states and native-coordinate overlays rendered correctly');
}finally{await browser.close();}
