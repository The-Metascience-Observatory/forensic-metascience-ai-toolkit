import { chromium } from 'playwright';
import ts from 'typescript';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
try {
  const page = await browser.newPage({viewport:{width:900,height:700}});
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<div id="root" style="height:650px"></div>');
  await page.addStyleTag({content:readFileSync('app/globals.css','utf8')});
  // Use Next's actual renderer: its innerHTML prop handling differs from the
  // standalone React UMD build and used to discard overlays on navigation.
  await page.evaluate(()=>window.modules={});
  for(const [name,file] of [
    ['next/dist/compiled/react','react/cjs/react.development.js'],
    ['next/dist/compiled/scheduler','scheduler/cjs/scheduler.development.js'],
    ['next/dist/compiled/react-dom','react-dom/cjs/react-dom.development.js'],
  ]) {
    const code=readFileSync(`node_modules/next/dist/compiled/${file}`,'utf8');
    await page.addScriptTag({content:`(()=>{const exports={};const module={exports};const process={env:{NODE_ENV:'development'}};const require=n=>window.modules[n];${code}\nwindow.modules[${JSON.stringify(name)}]=module.exports;})();`});
  }
  await page.evaluate(()=>{
    window.React=window.modules.react=window.modules['next/dist/compiled/react'];
    window.ReactDOM=window.modules['next/dist/compiled/react-dom'];
  });
  const modules=[
    ['@/lib/flipArrow','lib/flipArrow.ts'],
    ['./flipArrow.ts','lib/flipArrow.ts'],
    ['@/app/images/FlipArrow','app/images/FlipArrow.tsx'],
    ['./FlipArrow','app/images/FlipArrow.tsx'],
    ['@/lib/requestCache','lib/requestCache.ts'],
    ['@/lib/haystack','lib/haystack.ts'],['@/lib/severity','lib/severity.ts'],
    ['./FindBar','app/project/[project]/review/[slug]/FindBar.tsx'],
    ['@/lib/xmlFigures','lib/xmlFigures.ts'],
    ['@/lib/imageXmlBoxes','lib/imageXmlBoxes.ts'],
    ['@/lib/xmlImageOverlays','lib/xmlImageOverlays.ts'],
    ['../../review/[slug]/HtmlArticlePane','app/project/[project]/review/[slug]/HtmlArticlePane.tsx'],
    ['@/app/images/lib','app/images/lib.ts'],
    ['./NativeImagePane','app/project/[project]/images/[item]/NativeImagePane.tsx'],
    ['xml','app/project/[project]/images/[item]/XmlPaperPane.tsx'],
  ];
  for(const [name,file] of modules){
    const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
    await page.addScriptTag({content:`(()=>{const exports={};const require=n=>window.modules[{'./imageXmlBoxes.ts':'@/lib/imageXmlBoxes','./xmlFigures.ts':'@/lib/xmlFigures'}[n]||n];${code}\nwindow.modules[${JSON.stringify(name)}]=exports;})();`});
  }
  await page.evaluate(()=>{
    window.calls=[];window.pending={};
    const figures=[{id:'F1',anchor:'xml-figure-1',label:'Figure 1',graphics:[{reference:'main.jpg',relpath:'main.jpg'}]},
      {id:'F5',anchor:'xml-figure-2',label:'Extended Data Figure 1',graphics:[{reference:'extended.jpg',relpath:'extended.jpg'}]}];
    window.source={article:{mode:'xml',warning:'Preserved XML source.',figures,
      html:'<h1>XML-only paper</h1><p>Full article text.</p><div style="height:700px"></div>'+
      '<figure id="xml-figure-1"><figcaption>Figure 1. Main caption</figcaption></figure><div style="height:700px"></div>'+
      '<figure id="xml-figure-2"><figcaption>Extended Data Figure 1. Complete extended caption</figcaption></figure><div style="height:650px"></div>'}};
    window.fetch=(url,options)=>{
      window.calls.push(url);
      const dir=new URL(url,'http://test').searchParams.get('dir');
      if(dir==='slow') return new Promise(resolve=>window.pending.slow=()=>resolve({ok:true,json:async()=>({article:{mode:'xml',html:'WRONG OLD PAPER'}})}));
      if(dir==='missing')return Promise.resolve({ok:false,json:async()=>({error:'Historical source unavailable'})});
      return Promise.resolve({ok:true,json:async()=>window.source});
    };
    window.root=ReactDOM.createRoot(document.getElementById('root'));
    window.panel={uid:'pmc:extended.jpg-seg1',paper_dir:'paper',image:null,parent_image:null,figure_label:'Figure 1',document:{role:'pmc_render'},placements:[]};
    window.show=(panel=window.panel,item)=>window.root.render(React.createElement(window.modules.xml.XmlPaperPane,{project:'project',panel,item,run:'exact-run',component:'image_forensics',reason:'No PDF location'}));
    window.show();
  });
  await page.getByRole('combobox',{name:'Article figure'}).waitFor();
  assert.equal(await page.getByRole('combobox').inputValue(),'xml-figure-2');
  assert.equal(await page.evaluate(()=>new URL(window.calls[0],'http://test').searchParams.get('run')),'exact-run');
  await page.waitForFunction(()=>document.querySelector('.xml-article').scrollTop>1000);
  await page.getByRole('button',{name:'Back to top'}).click();
  assert.equal(await page.locator('.xml-article').evaluate(el=>el.scrollTop),0);
  await page.evaluate(()=>window.show({...window.panel,uid:'pmc:main.jpg-seg1'}));
  await page.waitForFunction(()=>document.querySelector('select').value==='xml-figure-1');
  await page.waitForFunction(()=>document.querySelector('.xml-article').scrollTop>500);
  assert.equal(await page.evaluate(()=>window.calls.length),1, 'Same-paper panel navigation reuses source');
  await page.keyboard.press('Control+f');
  await page.getByRole('textbox').fill('Complete extended caption');
  await page.locator('mark.html-hit').waitFor();
  await page.getByTitle('Close (Esc)').click();
  await page.getByRole('button',{name:'Show native image'}).click();
  await page.getByText(/No native image is available/).waitFor();
  await page.getByRole('button',{name:'Show article'}).click();
  await page.evaluate(()=>window.show({...window.panel,paper_dir:'slow'}));
  await page.getByText('Loading paper…').waitFor();
  await page.evaluate(()=>window.show({...window.panel,paper_dir:'other'}));
  await page.getByRole('combobox').waitFor();
  await page.evaluate(()=>window.pending.slow());
  assert.equal(await page.getByText('WRONG OLD PAPER').count(),0);
  await page.evaluate(()=>window.show({...window.panel,paper_dir:'missing'}));
  await page.getByText('Historical source unavailable',{exact:false}).waitFor();
  await page.getByText(/No native image is available/).waitFor();
  // Exercise the actual React pane, lazy image events and responsive SVG layout.
  let releaseImage, imageRequested;
  const released=new Promise(resolve=>releaseImage=resolve);
  const requested=new Promise(resolve=>imageRequested=resolve);
  await page.route('http://overlay.test/**',async route=>{
    imageRequested(); await released;
    await route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="742" height="1025"><rect width="742" height="1025" fill="white"/></svg>'});
  });
  await page.evaluate(()=>{
    const name='figure.jpg';
    window.overlayPanel={...window.panel,paper_dir:'overlay',uid:`pmc_figures:pmc:${name}-seg1`,crop_box:[123,26,212,138]};
    window.overlayItem={id:'match',panels:[window.overlayPanel,{...window.overlayPanel,uid:`pmc_figures:pmc:${name}-seg2`,crop_box:[123,142,212,252]}],
      detector_kind:'transformed_match',measurements:{panel_px_a:[112,89],panel_px_b:[110,89],inlier_box_a:[77.4,7.4,108.4,70],inlier_box_b:[3.2,20.5,34.2,82.9]}};
    window.source={article:{mode:'xml',figures:[{id:'F1',anchor:'xml-figure-1',label:'Figure 1',
      graphics:[{reference:name,relpath:'pmc_figures/figure.jpg',status:'local_current'}]}],
      html:'<h1>Paper</h1><figure class="xml-figure" id="xml-figure-1"><a href="http://overlay.test/full"><img loading="lazy" src="http://overlay.test/media?f=pmc_figures%2Ffigure.jpg" alt="Figure 1"/></a><figcaption>Caption text</figcaption></figure>'}};
    window.show(window.overlayPanel,window.overlayItem);
  });
  await page.getByRole('checkbox',{name:'Show boxes'}).waitFor();
  await requested;
  assert.equal(await page.locator('.xml-image-overlay').count(),0,'no overlay before image decode');
  releaseImage();
  await page.locator('.xml-image-overlay g').first().waitFor();
  assert.equal(await page.locator('.xml-image-overlay g').count(),2);
  const rectangles=await page.locator('.xml-image-overlay g rect:first-of-type').evaluateAll(els=>els.map(el=>['x','y','width','height'].map(k=>Number(el.getAttribute(k)))));
  for(const [i,expected] of [[0,[103.4,130.4,31,62.6]],[1,[145.2,143.5,31,62.4]]]) expected.forEach((v,k)=>assert.ok(Math.abs(rectangles[i][k]-v)<1e-7));
  const checkLayout=async()=>{
    const layout=await page.locator('.xml-image-overlay').evaluate(el=>{
      const im=el.querySelector('img').getBoundingClientRect(),svg=el.querySelector('svg').getBoundingClientRect();
      return {iw:im.width,ih:im.height,sw:svg.width,sh:svg.height,dx:im.x-svg.x,dy:im.y-svg.y};
    });
    for(const delta of [layout.iw-layout.sw,layout.ih-layout.sh,layout.dx,layout.dy])assert.ok(Math.abs(delta)<1,'SVG and image must share the displayed frame');
    return layout.iw;
  };
  const wide=await checkLayout();
  await page.setViewportSize({width:420,height:700});
  assert.ok(await checkLayout()<wide,'overlay follows responsive image size');
  await page.getByRole('checkbox',{name:'Show boxes'}).uncheck();
  assert.equal(await page.locator('.xml-image-overlay').count(),0);
  assert.equal(await page.locator('.xml-article img').count(),1,'toggle preserves image');
  await page.getByRole('checkbox',{name:'Show boxes'}).check();
  await page.locator('.xml-image-overlay').waitFor();
  await page.getByRole('button',{name:'Back to top'}).click();
  assert.equal(await page.locator('.xml-image-overlay g').count(),2,'parent navigation must not replace the augmented article DOM');
  await page.getByRole('combobox',{name:'Article figure'}).selectOption('xml-figure-1');
  assert.equal(await page.locator('.xml-image-overlay g').count(),2,'figure navigation preserves overlays');
  await page.keyboard.press('Control+f');
  await page.getByRole('textbox').fill('Matched region');
  assert.equal(await page.locator('mark.html-hit').count(),0,'find ignores overlay metadata');
  await page.getByRole('textbox').fill('Caption text');
  await page.locator('mark.html-hit').waitFor();
  assert.equal(await page.locator('.xml-image-overlay g').count(),2,'find preserves boxes');
  await page.getByTitle('Close (Esc)').click();
  await page.evaluate(()=>window.show(window.overlayPanel,{...window.overlayItem,id:'new-match',measurements:{}}));
  await page.waitForFunction(()=>document.querySelectorAll('[data-box-kind="panel"]').length===2);
  assert.equal(await page.locator('[data-box-kind="match"]').count(),0,'item change clears old matches');
  await page.getByRole('button',{name:'Show native image'}).click();
  assert.equal(await page.locator('.xml-image-overlay').count(),0);
  await page.getByRole('button',{name:'Show article'}).click();
  await page.locator('.xml-image-overlay').waitFor();
  assert.equal(await page.locator('.xml-image-overlay .xml-image-overlay').count(),0,'no nested wrappers after remount');
  await page.evaluate(()=>document.querySelector('.xml-article img').dispatchEvent(new Event('error')));
  assert.equal(await page.locator('.xml-image-overlay').count(),0,'decode error clears overlay');
  await page.getByText('Figure 1: image unavailable or could not be decoded.').waitFor();
  await page.setViewportSize({width:900,height:700});
  if (process.env.METASCIENCE_XML_BROWSER_FIXTURE) {
    const fixture=JSON.parse(readFileSync(process.env.METASCIENCE_XML_BROWSER_FIXTURE,'utf8'));
    await page.route('http://xml-reader.test/**', async route=>{
      const file=new URL(route.request().url()).searchParams.get('f');
      const asset=fixture.media[file];
      if(asset) await route.fulfill({path:asset}); else await route.abort();
    });
    await page.evaluate(fixture=>{
      const base=document.createElement('base');base.href='http://xml-reader.test/';document.head.append(base);
      window.source=fixture.source;
      window.show({...window.panel,paper_dir:'real-fixture',uid:'pmc_figures:pmc:nihms863503f13.jpg-seg1'});
    },fixture);
    await page.getByRole('combobox').waitFor();
    assert.equal(await page.getByRole('combobox').inputValue(),'xml-figure-9');
    await page.waitForFunction(()=>{
      const image=document.querySelector('#xml-figure-9 img');return image?.naturalWidth>0;
    });
    assert.equal(await page.locator('.xml-article img').count(),14);
    assert.match(await page.locator('#xml-figure-9 figcaption').innerText(),/Extended Data Figure 9/);
    await page.screenshot({path:process.env.METASCIENCE_XML_BROWSER_SCREENSHOT || '/tmp/xml-paper-review.png'});
    console.log('Real Nature paper: 14 images, selected Extended Data Figure 9 decoded, complete XML caption rendered');
  }
  assert.deepEqual(errors,[]);
  console.log('XML paper: figure navigation, search, lazy overlays, resize, toggling, item updates, native fallback and errors passed');
} finally {await browser.close();}
