import {chromium} from 'playwright';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';

const fixturePath=process.env.METASCIENCE_CLONE_PDF_FIXTURE;
if (!fixturePath) {
  console.log('Clone PDF acceptance: no generated fixture supplied; unmeasured');
  process.exit(0);
}
const fixture=JSON.parse(readFileSync(fixturePath,'utf8'));
assert.equal(fixture.code_unchanged,true);
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try {
  const page=await browser.newPage({viewport:{width:1100,height:800}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://clone-pdf.test/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path==='/paper.pdf')return route.fulfill({contentType:'application/pdf',body:readFileSync(fixture.pdf)});
    if(path==='/pdf.mjs')return route.fulfill({contentType:'text/javascript',body:readFileSync('node_modules/pdfjs-dist/build/pdf.mjs')});
    if(path==='/pdf.worker.min.mjs')return route.fulfill({contentType:'text/javascript',body:readFileSync('public/pdf.worker.min.mjs')});
    return route.fulfill({contentType:'text/html',body:'<div id="root" style="height:760px"></div>'});
  });
  await page.goto('http://clone-pdf.test/');
  await page.addStyleTag({content:readFileSync('app/globals.css','utf8')});
  await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
  await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
  await page.evaluate(async()=>window.modules={react:window.React,'pdfjs-dist':await import('http://clone-pdf.test/pdf.mjs')});
  for(const [name,file] of [
    ['@/lib/flipArrow','lib/flipArrow.ts'],
    ['./flipArrow.ts','lib/flipArrow.ts'],
    ['@/app/images/FlipArrow','app/images/FlipArrow.tsx'],
    ['./FlipArrow','app/images/FlipArrow.tsx'],
    ['@/lib/imagePdfBoxes','lib/imagePdfBoxes.ts'],['@/lib/pdfBoxes','lib/pdfBoxes.ts'],
    ['@/lib/severity','lib/severity.ts'],['@/lib/targets','lib/targets.ts'],
    ['./FindBar','app/project/[project]/review/[slug]/FindBar.tsx'],
    ['pdf','app/project/[project]/review/[slug]/PdfPane.tsx'],
  ]) {
    const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
    await page.addScriptTag({content:`(()=>{const exports={};const require=n=>window.modules[n];${code}\nwindow.modules[${JSON.stringify(name)}]=exports;})();`});
  }
  const projected=await page.evaluate(fixture=>{
    const boxes=window.modules['@/lib/imagePdfBoxes'].imagePdfBoxes(fixture.item,[fixture.size]);
    window.root=ReactDOM.createRoot(document.getElementById('root'));
    window.root.render(React.createElement(window.modules.pdf.PdfPane,{
      url:'http://clone-pdf.test/paper.pdf',imageBoxes:boxes,
      locator:{page:1,confidence:'bbox',targets:fixture.item.targets},label:'Matched regions A/B',zoom:.6,
    }));
    return boxes;
  },fixture);
  assert.equal(projected.length,2);
  for(let region=0;region<2;region++)for(let point=0;point<projected[region].points.length;point++)
    for(let axis=0;axis<2;axis++)assert.ok(Math.abs(projected[region].points[point][axis]-fixture.expected_pdf_polygons[region][point][axis])<.01);
  await page.locator('svg.pdf-duplication polygon:not([data-flip-arrow])').first().waitFor({timeout:30000});
  assert.equal(await page.locator('svg.pdf-duplication polygon:not([data-flip-arrow])').count(),2);
  assert.deepEqual(await page.locator('svg.pdf-duplication text').allTextContents(),['A','B']);
  const drawn=await page.locator('svg.pdf-duplication polygon:not([data-flip-arrow])').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('points')));
  assert.deepEqual(drawn,projected.map(box=>box.points.map(point=>point.join(',')).join(' ')));
  assert.equal(await page.locator('canvas').count()>0,true,'The real PDF must render');
  await page.screenshot({path:process.env.METASCIENCE_CLONE_PDF_SCREENSHOT || '/tmp/clone-pdf-viewer.png'});
  assert.deepEqual(errors,[]);
  console.log('Real PDF -> extracted pixels -> hybrid detector -> item feed -> rotated PDF viewer: both A/B polygons passed');
} finally {await browser.close();}
