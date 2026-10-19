import { chromium } from 'playwright';
import ts from 'typescript';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
try {
  const page = await browser.newPage({viewport:{width:1000,height:650}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://localhost/gif-test',route=>route.fulfill({contentType:'text/html',body:'<div style="width:900px;height:550px"><div id="root"></div></div>'}));
  await page.goto('http://localhost/gif-test');
  await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
  await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
  await page.evaluate(()=>window.modules={react:window.React});
  await page.addScriptTag({content:`(()=>{const exports={};const module={exports};${readFileSync('node_modules/gifenc/dist/gifenc.js','utf8')}\nwindow.modules.gifenc=module.exports;})();`});
  for(const [name,file] of [
    ['@/lib/affine','lib/affine.ts'],['@/lib/flipArrow','lib/flipArrow.ts'],
    ['./flipArrow.ts','lib/flipArrow.ts'],['@/lib/imagePdfBoxes','lib/imagePdfBoxes.ts'],
    ['comparator','app/project/[project]/images/[item]/Comparator.tsx'],
  ]) {
    const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
    await page.addScriptTag({content:`(()=>{const exports={};const require=n=>window.modules[n];${code}\nwindow.modules[${JSON.stringify(name)}]=exports;})();`});
  }
  await page.evaluate(async()=>{
    const image=async(color)=>{const c=document.createElement('canvas');c.width=160;c.height=100;
      const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,160,100);
      // The asymmetric right-hand patch tests reflection in the exported frame.
      ctx.fillStyle='blue';ctx.fillRect(120,0,40,100);
      const im=new Image();im.src=c.toDataURL();await im.decode();return im;};
    window.a=await image('red');window.b=await image('lime');
    window.root=ReactDOM.createRoot(document.getElementById('root'));
    window.show=(extra={})=>window.root.render(React.createElement(window.modules.comparator.Comparator,{
      imgA:window.a,imgB:window.b,srcA:window.a.src,srcB:window.b.src,
      affine:window.affine ||= [[1,0,0],[0,1,0]],flip:true,labelA:'Panel A',labelB:'Panel B',
      videoActions:React.createElement('button',{},'Generate video'),...extra}));
    window.show();
  });
  assert.equal(await page.getByRole('link',{name:'Download GIF'}).count(),0);
  await page.getByRole('button',{name:'blink',exact:true}).click();
  await page.getByRole('slider').fill('4');
  await page.getByRole('button',{name:'Generate GIF',exact:true}).click();
  const preview=page.getByRole('img',{name:'Generated blink comparison'});
  await preview.waitFor();
  const link=page.getByRole('link',{name:'Download GIF',exact:true});
  const url=await link.getAttribute('href');
  assert.equal(await preview.getAttribute('src'),url);
  await page.evaluate(()=>window.show({affine:[[1,0,0],[0,1,0]]}));
  assert.equal(await preview.getAttribute('src'),url, 'Equivalent refreshed geometry must preserve the GIF');
  const decoded=await page.evaluate(async(url)=>{
    const data=await (await fetch(url)).arrayBuffer();
    const decoder=new ImageDecoder({data,type:'image/gif'});await decoder.tracks.ready;
    const frames=[];
    for(let i=0;i<2;i++){
      const {image}=await decoder.decode({frameIndex:i});
      const c=document.createElement('canvas');c.width=image.displayWidth;c.height=image.displayHeight;
      const ctx=c.getContext('2d');ctx.drawImage(image,0,0);
      frames.push({duration:image.duration,left:Array.from(ctx.getImageData(20,50,1,1).data),right:Array.from(ctx.getImageData(90,50,1,1).data)});
      image.close();
    }
    return {header:String.fromCharCode(...new Uint8Array(data).slice(0,6)),count:decoder.tracks.selectedTrack.frameCount,
      repeat:decoder.tracks.selectedTrack.repetitionCount,frames};
  },url);
  assert.equal(decoded.header,'GIF89a');assert.equal(decoded.count,2);
  assert.equal(decoded.repeat,Infinity);
  assert.equal(decoded.frames[0].duration,250000);
  assert.deepEqual(decoded.frames[0].left,[255,0,0,255]);
  assert.deepEqual(decoded.frames[1].left,[0,0,255,255]);
  assert.deepEqual(decoded.frames[1].right,[0,255,0,255]);
  const downloadPromise=page.waitForEvent('download');await link.click();
  const download=await downloadPromise;
  assert.equal(download.suggestedFilename(),'blink-comparison.gif');assert.equal(await download.failure(),null);
  await page.getByRole('button',{name:'side',exact:true}).click();
  await page.getByRole('button',{name:'View GIF',exact:true}).click();await preview.waitFor();
  await page.screenshot({path:'/tmp/gif-comparison-test.png'});
  // Source changes discard exports, including their object URLs.
  await page.evaluate(()=>window.show({srcA:'different-source',imgB:null}));
  await page.waitForFunction(()=>!document.querySelector('a[download]'));
  assert.equal(await page.getByRole('button',{name:'Generate GIF',exact:true}).isDisabled(),true);
  assert.equal(await page.evaluate(async(url)=>{try{await fetch(url);return false;}catch{return true;}},url),true);
  // A failed encoder surfaces an error and can be retried.
  await page.evaluate(()=>{window.show();window.realGifenc=window.modules.gifenc;window.modules.gifenc={...window.realGifenc,GIFEncoder:()=>{throw Error('Encoding unavailable');}};});
  await page.getByRole('button',{name:'Generate GIF',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Encoding unavailable'}).waitFor();
  await page.evaluate(()=>window.modules.gifenc=window.realGifenc);
  await page.getByRole('button',{name:'Generate GIF',exact:true}).click();await preview.waitFor();
  assert.deepEqual(errors,[]);
  console.log('GIF: aligned/reflected frames, blink timing, looping, preview, download, cleanup and retry passed');
} finally {await browser.close();}
