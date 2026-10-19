import {chromium} from 'playwright';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
// Imported image results must reach the landing page: every catalog project
// gets its image-review counts joined, and image projects the catalog does
// not list yet are appended rather than hidden (Yadong Huang's, 2026-09-30).
const home=readFileSync('app/page.tsx','utf8');
assert.match(home, /<ProjectsTable\s+projects=\{withImageReviews\(listed,\s*counts\)\}/);
assert.match(home, /const listed\s*=\s*\[\.\.\.index\.projects,\s*\.\.\.imageOnlyProjects\(index\.projects,\s*counts\)\]/);
const fields=['n_papers','n_pdf','n_xml','n_image_run','n_text_run','n_human_reviewed'];
const labels=['Papers','With PDF','With XML','Image track','Text track','Human reviewed'];
const rows=[2,10,0,null].map((value,i)=>({name:['two','ten','zero','unknown'][i],
  ...Object.fromEntries(fields.map(f=>[f,value])),n_not_fetched:0,n_in_progress:0}));
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try {
 const page=await browser.newPage();
 await page.setContent('<div id="root"></div>');
 await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
 await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
 const code=ts.transpileModule(readFileSync('app/ProjectsTable.tsx','utf8'),{
   compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 await page.addScriptTag({content:`(()=>{const exports={};const require=()=>React;${code}\nwindow.ProjectsTable=exports.ProjectsTable;})();`});
 await page.evaluate(rows=>ReactDOM.render(React.createElement(window.ProjectsTable,{projects:rows}),document.getElementById('root')),rows);
 const names=()=>page.locator('tbody tr td:first-child a').allTextContents();
 for(const label of labels){
   const button=page.getByRole('button',{name:new RegExp('^'+label+' ')});
   await button.click();
   assert.deepEqual(await names(),['ten','two','zero','unknown']);
   assert.equal(await page.locator('th[aria-sort="descending"]').count(),1);
   await button.click();
   assert.deepEqual(await names(),['zero','two','ten','unknown']);
   assert.equal(await page.locator('th[aria-sort="ascending"]').count(),1);
 }
 assert.equal(await page.getByRole('link',{name:'two',exact:true}).getAttribute('href'),'/project/two');
 console.log('Projects table: all six numeric columns sort both ways; missing counts remain last.');
} finally {await browser.close();}
