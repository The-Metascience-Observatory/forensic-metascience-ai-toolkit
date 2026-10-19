import {chromium} from 'playwright';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';

// Render the real queue with its compact API shape, not a full detail fixture.
const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
try {
  const page = await browser.newPage({viewport:{width:1500,height:1100}});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://queue.test/',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
  await page.route('http://queue.test/api/media?**',route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80"><rect width="100" height="80" fill="gray"/></svg>'}));
  await page.goto('http://queue.test/');
  await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
  await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
  await page.evaluate(()=>{
    const noop=()=>{};
    window.modules={react:React,
      'next/link':{__esModule:true,default:({prefetch,...props})=>React.createElement('a',props)},
      'next/navigation':{useSearchParams:()=>new URLSearchParams(),useRouter:()=>({push:noop})},
      '@/app/ReviewerChip':{readReviewer:()=>''},
      '@/app/RunSelector':{RunSelector:()=>null},
      '@/app/images/useInfiniteFeed':{useInfiniteFeed:(_p,_r,_f,enabled)=>({
        feed:enabled?window.feed:null,loading:false,loadMore:noop,refresh:noop})},
      '@/app/images/HoverPreview':{HoverPreview:()=>null},
    };
    const panel={uid:'a',paper_dir:'paper',image:'panel.png',figure_label:'Figure 1'};
    window.items=['omitted','null','empty','pair','mirrored-b','clone'].map((id,i)=>({
      id,run_id:'exact-run',kind:i===4?'cross':'within',detector_kind:i===5?'intra_panel_clone':'transformed_match',
      paper:{dir:'paper'},papers:[{dir:'paper'}],panels:[panel],figure_labels:['Figure 1'],
      rank:{score:6-i,reasons:[]},adjudication:null,decision:null,
    }));
    window.items[1].measurements=null;
    window.items[2].measurements={};
    window.items[3].measurements={panel_px_a:[100,80],inlier_box_a:[10,20,50,70]};
    window.items[4].panels=[{...panel,image:null},{...panel,uid:'b'}];
    window.items[4].measurements={panel_px_b:[100,80],inlier_box_b:[10,20,50,70],flip:true};
    window.items[5].measurements={panel_px_a:[100,80],regions:[{bbox:[1,2,30,40]},{bbox:[45,6,70,50]}]};
    window.feed={items:window.items,counts:{items:6,papers:1},notes:[],runs:[],pagination:{total:6,next_offset:null}};
  });
  const modules=[
    ['./affine.ts','lib/affine.ts'],['@/lib/imagePreview','lib/imagePreview.ts'],
    ['@/lib/flipArrow','lib/flipArrow.ts'],['@/app/images/FlipArrow','app/images/FlipArrow.tsx'],
    ['@/app/images/lib','app/images/lib.ts'],['queue','app/project/[project]/images/ImageQueue.tsx'],
  ];
  for(const [name,file] of modules){
    const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
    await page.addScriptTag({content:`(()=>{const exports={};const require=n=>window.modules[n];${code}\nwindow.modules[${JSON.stringify(name)}]=exports;})();`});
  }
  await page.evaluate(()=>{
    ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(window.modules.queue.ImageQueue,{project:'fixture',projectName:'Queue fixture'}));
  });
  await page.waitForFunction(()=>document.querySelectorAll('tbody tr').length===6, null, {timeout:5000}).catch(error=>{
    assert.deepEqual(errors,[], 'Compact queue rows must not crash the page');
    throw error;
  });
  assert.deepEqual(errors,[], 'Compact queue rows must not crash the page');
  assert.equal(await page.locator('tbody tr').count(),6);
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('tbody img')).every(img=>img.naturalWidth>0));
  const rects=await page.locator('tbody tr').evaluateAll(rows=>rows.map(row=>Array.from(row.querySelectorAll('svg rect')).map(rect=>['x','y','width','height'].map(k=>Number(rect.getAttribute(k))))));
  assert.deepEqual(rects,[[],[],[],[[10,20,40,50]],[[50,20,40,50]],[[1,2,29,38],[45,6,25,44]]]);
  assert.equal(await page.locator('tbody tr').first().locator('a').first().getAttribute('href'),'/project/fixture/images/omitted?run=latest');
  assert.deepEqual(errors,[]);
  console.log('Real image queue: omitted/null/empty measurements render; recorded A/B, mirrored and clone outlines remain correct.');
} finally {await browser.close();}
