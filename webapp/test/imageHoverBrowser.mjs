import {chromium} from 'playwright';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
try {
  const page = await browser.newPage({viewport:{width:1500,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<button id="hover">Hover panel</button><div id="root"></div>');
  await page.addStyleTag({content:readFileSync('app/globals.css','utf8')});
  await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
  await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
  await page.evaluate(()=>window.modules={react:window.React});
  const modules=[
    ['./affine.ts','lib/affine.ts'],['@/lib/imagePreview','lib/imagePreview.ts'],
    ['@/lib/flipArrow','lib/flipArrow.ts'],
    ['./flipArrow.ts','lib/flipArrow.ts'],
    ['@/app/images/FlipArrow','app/images/FlipArrow.tsx'],
    ['./FlipArrow','app/images/FlipArrow.tsx'],
    ['@/lib/imagePdfBoxes','lib/imagePdfBoxes.ts'],['@/lib/requestCache','lib/requestCache.ts'],
    ['./lib','app/images/lib.ts'],['./useFeed','app/images/useFeed.ts'],
    ['./PanelPreview','app/images/PanelPreview.tsx'],['hover','app/images/HoverPreview.tsx'],
  ];
  for(const [name,file] of modules){
    const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
    await page.addScriptTag({content:`(()=>{const exports={};const require=n=>window.modules[n];${code}\nwindow.modules[${JSON.stringify(name)}]=exports;})();`});
  }
  await page.route('**/api/media?**', route=>{
    const side=new URL(route.request().url()).searchParams.get('f');
    assert.notEqual(side,'old-text-exhibit.png','Hover must show panels, not the old text-heavy exhibit');
    const [w,h]=side==='b.png'?[200,60]:[100,80];
    return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="100%" height="100%" fill="#647985"/><path d="M0 0 L${w} ${h} M${w} 0 L0 ${h}" stroke="#eee" stroke-width="2"/></svg>`});
  });
  await page.evaluate(()=>{
    const base=document.createElement('base');base.href='http://hover.test/';document.head.append(base);
    window.calls=[];window.mode='pair';
    window.item={id:'pair',run_id:'historical-run',detector_kind:'transformed_match',exhibit:'old-text-exhibit.png',
      paper:{dir:'paper'},figure_labels:['Figure 1','Figure 2'],measurements:{},
      panels:[{uid:'a',paper_dir:'paper',image:'a.png',figure_label:'Figure 1'},
              {uid:'b',paper_dir:'other-paper',image:'b.png',figure_label:'Figure 2'}]};
    window.fetch=async url=>{
      window.calls.push(url);
      await new Promise(resolve=>setTimeout(resolve,120));
      if(window.mode==='error')return {ok:false,json:async()=>({error:'Detail unavailable'})};
      return {ok:true,json:async()=>({...window.item,measurements:window.mode==='empty'?{}:window.mode==='clone'
        ?{regions:[{bbox:[10,10,40,40]},{bbox:[50,20,80,60]}]}
        :{inlier_box_a:[10,20,50,70],inlier_box_b:[10,5,40,35],flip:true}})};
    };
    window.root=ReactDOM.createRoot(document.getElementById('root'));
    document.getElementById('hover').onmouseenter=()=>window.root.render(React.createElement(window.modules.hover.HoverPreview,
      {project:'project',it:window.item,x:100,y:200,key:window.item.id}));
    document.getElementById('hover').onmouseleave=()=>window.root.render(null);
  });
  await page.locator('#hover').hover();
  await page.getByText('Loading match regions…').waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('[data-preview-box]').length===2);
  const request=new URL(await page.evaluate(()=>window.calls[0]),'http://hover.test');
  assert.equal(request.searchParams.get('run'),'historical-run');
  assert.equal(request.searchParams.get('item'),'pair');
  const rects=await page.locator('[data-preview-box]').evaluateAll(xs=>xs.map(x=>['x','y','width','height'].map(k=>Number(x.getAttribute(k)))));
  assert.deepEqual(rects,[[10,20,40,50],[160,5,30,30]]);
  assert.deepEqual(await page.locator('[data-flip-arrow]').evaluateAll(xs=>xs.map(x=>x.getAttribute('data-flip-arrow'))),['1','-1']);
  await page.screenshot({path:'/tmp/flip-hover.png'});
  // SVG and image use the same contain transform, even when height-limited.
  async function checkAlignment() {
    return page.locator('[data-preview-box]').evaluateAll(xs=>xs.map(rect=>{
      const svg=rect.ownerSVGElement,img=svg.parentElement.querySelector('img'),r=img.getBoundingClientRect();
      const scale=Math.min(r.width/img.naturalWidth,r.height/img.naturalHeight);
      const x=r.x+(r.width-img.naturalWidth*scale)/2+Number(rect.getAttribute('x'))*scale;
      const y=r.y+(r.height-img.naturalHeight*scale)/2+Number(rect.getAttribute('y'))*scale;
      const actual=rect.getBoundingClientRect();
      return Math.max(Math.abs(x-actual.x),Math.abs(y-actual.y),Math.abs(actual.width-Number(rect.getAttribute('width'))*scale));
    }));
  }
  assert.ok((await checkAlignment()).every(n=>n<1));
  await page.setViewportSize({width:800,height:600});
  await page.mouse.move(50,20); // update viewport bounds without leaving the trigger
  assert.ok((await checkAlignment()).every(n=>n<1));
  await page.mouse.move(790,590);
  assert.equal(await page.getByRole('tooltip').count(),0);
  await page.evaluate(()=>{window.mode='empty';window.item={...window.item,id:'empty'};});
  await page.locator('#hover').hover();
  await page.getByText('No saved region coordinates').first().waitFor();
  assert.equal(await page.locator('[data-preview-box]').count(),0);
  await page.mouse.move(790,590);
  await page.evaluate(()=>{window.mode='clone';window.item={...window.item,id:'clone',detector_kind:'intra_panel_clone',panels:window.item.panels.slice(0,1)};});
  await page.locator('#hover').hover();
  await page.waitForFunction(()=>document.querySelectorAll('[data-preview-box]').length===2);
  assert.equal(await page.getByRole('tooltip').locator('img').count(),1);
  await page.mouse.move(790,590);
  await page.evaluate(()=>{window.mode='error';window.item={...window.item,id:'error'};});
  await page.locator('#hover').hover();
  await page.getByText('Match regions unavailable').waitFor();
  assert.equal(await page.locator('[data-preview-box]').count(),0);
  assert.deepEqual(errors,[]);
  console.log('Hover UI: lazy exact-run details, original images, mirrored boxes, responsive alignment, clone regions, missing geometry and failure states passed');
} finally {await browser.close();}
