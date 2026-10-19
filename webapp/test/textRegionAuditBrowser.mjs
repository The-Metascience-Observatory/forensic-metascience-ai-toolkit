import {chromium} from 'playwright';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {deflateSync} from 'node:zlib';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try {
 const page=await browser.newPage({viewport:{width:1000,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('http://audit.test/**',route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80"><rect width="100" height="80" fill="white"/><text x="10" y="23" font-size="12">Label</text><circle cx="60" cy="50" r="15" fill="#78967a"/></svg>'}));
 await page.setContent('<div id="root"></div>');
 await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
 await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
 const packed=Buffer.alloc(1000);
 for(let y=10;y<=25;y++)for(let x=8;x<=44;x++){const i=y*100+x;packed[i>>3]|=128>>(i&7);}
 const loc={provenance:{device:'cuda:0',execution:{runtime:{hardware:{name:'Fixture accelerator'}}}},status:'measured',reason:'synthetic localization fixture',size:[100,80],polygons:[[[8,10],[44,10],[44,25],[8,25]]],mask_bits:deflateSync(packed).toString('base64'),mask_fraction:16*37/8000};
 await page.evaluate(loc=>{
   window.modules={'react':React,'@/app/images/lib':{mediaUrl:()=> 'http://audit.test/image.svg?record=fixture'}};
   window.requests=[];
   const panel={uid:'panel-with-no-findings',paper:'fixture-paper',run:'exact-run',image:'saved.png',status:'measured',policy:'diagnostic',consumers:[{consumer:'transformed',status:'measured',policy:'diagnostic',applied:false,excluded_features:0,remaining_features:42},{consumer:'clones',stage:'verification_centers',status:'measured',policy:'enforce',applied:true,sample_type:'grid_centers',size:loc.size,mask_bits:loc.mask_bits,mask_fraction:loc.mask_fraction,excluded_samples:592,remaining_samples:7408}]};
   panel.consumers.push({...panel.consumers[1],stage:'cropped_grid',analysis_size:[100,80],to_analysis:[[.5,0,10],[0,.5,20]]});
   window.fetch=async url=>{
    const p=new URL(url,'http://audit.test').searchParams;window.requests.push(String(url));
    const body=p.get('summary_only')==='true' ? {status:'recorded',panel} : p.has('uid') ? {status:'measured',localization:loc,usage:p.has('consumer')?{...panel.consumers[Number(p.get('consumer'))],excluded_feature_footprints:[]}:null} : {status:'recorded',panels:[panel],total:1,pagination:{next_offset:null}};
    return {ok:true,json:async()=>body};
   };
 },loc);
 const code=ts.transpileModule(readFileSync('app/project/[project]/images/text-regions/TextRegionAudit.tsx','utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 await page.addScriptTag({content:`(()=>{const exports={};const require=n=>window.modules[n];${code}\nwindow.Audit=exports.TextRegionAudit;window.FindingAudit=exports.FindingRegionAudit;window.AuditPanel=exports.AuditPanel})();`});
 await page.evaluate(()=>ReactDOM.render(React.createElement(window.Audit,{project:'fixture',initialRun:'exact-run'}),document.getElementById('root')));
 await page.getByRole('heading',{name:'fixture-paper · panel-with-no-findings'}).waitFor();
 assert.equal(await page.locator('canvas').count(),0);
 assert.equal((await page.evaluate(()=>window.requests)).length,1);
 await page.getByRole('switch',{name:'Show excluded text regions'}).check();
 await page.waitForFunction(()=>document.querySelector('canvas')?.getContext('2d').getImageData(8,10,1,1).data[3]===115);
 await page.getByText('Localization backend: cuda:0 · Fixture accelerator',{exact:true}).waitFor();
 assert.equal(await page.locator('polygon').getAttribute('points'),'8,10 44,10 44,25 8,25');
 assert.equal(await page.locator('polygon').getAttribute('stroke-dasharray'),'5 3');
 const count=await page.evaluate(()=>{const d=document.querySelector('canvas').getContext('2d').getImageData(0,0,100,80).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n;});
 assert.equal(count,16*37);
 await page.getByRole('combobox').selectOption('0');
 await page.getByText('0 features excluded',{exact:false}).waitFor();
 await page.getByRole('combobox').selectOption('1');
 await page.getByText('592 grid centers excluded',{exact:false}).waitFor();
 await page.waitForFunction(()=>document.querySelector('canvas[aria-label="Effective sampling exclusions"]')?.getContext('2d').getImageData(8,10,1,1).data[3]===100);
 assert.equal(await page.locator('polygon').getAttribute('stroke-dasharray'),null);
 await page.getByRole('combobox').selectOption('2');
 await page.waitForFunction(()=>{const c=document.querySelector('canvas[aria-label="Effective sampling exclusions"]');return c?.getContext('2d').getImageData(14,25,1,1).data[3]===100 && c.getContext('2d').getImageData(8,10,1,1).data[3]===0;});
 if(process.env.TEXT_AUDIT_SCREENSHOT)await page.screenshot({path:process.env.TEXT_AUDIT_SCREENSHOT,fullPage:true});
 await page.getByRole('switch').uncheck();
 assert.equal(await page.locator('canvas').count(),0);
 await page.evaluate(()=>ReactDOM.render(React.createElement(window.FindingAudit,{project:'fixture',run:'exact-run',panels:[{uid:'panel-with-no-findings',paper_dir:'fixture-paper'}]}),document.getElementById('root')));
 const before=await page.evaluate(()=>window.requests.length);
 await page.locator('summary').filter({hasText:'Audit retained text exclusions for this finding'}).click();
 await page.getByRole('switch',{name:'Show excluded text regions'}).waitFor();
 assert.equal(await page.evaluate(()=>window.requests.length),before+1);
 assert.match(await page.evaluate(()=>window.requests.at(-1)),/summary_only=true/);
 assert.equal(await page.locator('canvas').count(),0);
 await page.getByRole('switch').check();
 await page.waitForFunction(()=>document.querySelector('canvas')?.getContext('2d').getImageData(8,10,1,1).data[3]===115);
 assert.match(await page.getByRole('link',{name:'Audit every panel in this exact run'}).getAttribute('href'),/run=exact-run/);
 if(process.env.TEXT_AUDIT_REAL_FIXTURE) {
   const fixture=JSON.parse(readFileSync(process.env.TEXT_AUDIT_REAL_FIXTURE,'utf8'));
   const image='data:image/png;base64,'+readFileSync(fixture.image.path).toString('base64');
   await page.evaluate(({fixture,image})=>{
     window.modules['@/app/images/lib'].mediaUrl=()=>image;
     const panel={uid:fixture.image.id,paper:'Embargoed-corpus frozen evaluation',run:'cpu-localization-validation',image:'retained-analysis.png',status:'measured',policy:'diagnostic',provenance:fixture.localization.provenance};
     window.fetch=async()=>({ok:true,json:async()=>({panel,localization:fixture.localization,status:'measured'})});
     ReactDOM.render(React.createElement(window.AuditPanel,{project:'validation',panel}),document.getElementById('root'));
   },{fixture,image});
   await page.getByRole('switch').check();
   await page.waitForFunction(()=>document.querySelector('canvas')?.width>100);
   await page.screenshot({path:process.env.TEXT_AUDIT_REAL_SCREENSHOT,fullPage:true});
 }
 assert.deepEqual(errors,[]);
 console.log('Panel audit: no-finding panel, lazy exact mask, alignment, selector and toggle passed');
}finally{await browser.close();}
