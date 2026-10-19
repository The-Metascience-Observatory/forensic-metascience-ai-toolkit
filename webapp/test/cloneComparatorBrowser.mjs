import {chromium} from 'playwright';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
try {
  const page = await browser.newPage({viewport:{width:1000,height:650}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<div style="width:900px;height:550px"><div id="root"></div></div>');
  await page.addScriptTag({path:'node_modules/react/umd/react.development.js'});
  await page.addScriptTag({path:'node_modules/react-dom/umd/react-dom.development.js'});
  await page.evaluate(()=>window.modules={react:window.React});
  for(const [name,file] of [
    ['@/lib/affine','lib/affine.ts'],['@/lib/flipArrow','lib/flipArrow.ts'],
    ['./flipArrow.ts','lib/flipArrow.ts'],
    ['@/app/images/FlipArrow','app/images/FlipArrow.tsx'],
    ['./FlipArrow','app/images/FlipArrow.tsx'],
    ['@/lib/imagePdfBoxes','lib/imagePdfBoxes.ts'],
    ['comparator','app/project/[project]/images/[item]/Comparator.tsx'],
  ]) {
    const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
    await page.addScriptTag({content:`(()=>{const exports={};const require=n=>window.modules[n];${code}\nwindow.modules[${JSON.stringify(name)}]=exports;})();`});
  }
  for (const transformCase of [
    {angle:90,scale:1,flip:false},
    {angle:37,scale:1.5,flip:true},
    {angle:173,scale:.5,flip:false},
  ]) {
  await page.evaluate(async({angle,scale,flip})=>{
    const source=document.createElement('canvas');source.width=300;source.height=200;
    const ctx=source.getContext('2d');ctx.fillStyle='#888';ctx.fillRect(0,0,300,200);
    for(let y=40;y<90;y++)for(let x=30;x<80;x++) {
      ctx.fillStyle=`rgb(${x*3},${y*2},${(x+y)%255})`;ctx.fillRect(x,y,1,1);
    }
    const original=new Image();original.src=source.toDataURL();await original.decode();
    const radians=angle*Math.PI/180;
    const a=Math.cos(radians)*scale*(flip?-1:1), b=Math.sin(radians)*scale*(flip?-1:1);
    const c=-Math.sin(radians)*scale, d=Math.cos(radians)*scale;
    const e=210-a*55-c*65, f=110-b*55-d*65;
    ctx.save();ctx.setTransform(a,b,c,d,e,f);ctx.drawImage(original,30,40,50,50,30,40,50,50);ctx.restore();
    const image=new Image();image.src=source.toDataURL();await image.decode();
    const corners=[[30,40],[80,40],[80,90],[30,90]];
    const polygon=corners.map(([x,y])=>[a*x+c*y+e,b*x+d*y+f]);
    const xs=polygon.map(p=>p[0]),ys=polygon.map(p=>p[1]);
    window.cloneTestRoot ||= ReactDOM.createRoot(document.getElementById('root'));
    window.cloneTestRoot.render(React.createElement(window.modules.comparator.Comparator,{
      imgA:image,imgB:null,srcA:image.src,srcB:null,labelA:'Panel',labelB:'Region B',
      affine:[[a,c,e],[b,d,f]],flip,regions:[
        {role:'A',bbox:[30,40,80,90],polygon:corners},
        {role:'B',bbox:[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)],polygon},
      ],transformNote:`rotation ${angle}°, scale ${scale}, reflection ${flip}`,
    }));
  },transformCase);
  await page.getByRole('button',{name:'overlay',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('canvas')?.width>0);
  await page.getByText(/copying direction is unknown/).waitFor();
  // Changing overlay opacity must not move the rotated region or substitute
  // a rectangle-derived translation. Compare an interior area, away from labels.
  async function pixels() {
    return page.locator('canvas').first().evaluate(c=>{
      const scale=c.width/300, ctx=c.getContext('2d');
      return Array.from(ctx.getImageData(Math.round(50*scale),Math.round(60*scale),5,5).data);
    });
  }
  const slider=page.getByRole('slider');
  await slider.fill('0');await page.waitForTimeout(40);const a=await pixels();
  await slider.fill('1');await page.waitForTimeout(40);const b=await pixels();
  assert.ok(a.every((n,i)=>Math.abs(n-b[i])<=6),`Recorded transform must align region B with A: ${JSON.stringify(transformCase)}`);
  }
  assert.deepEqual(errors,[]);
  console.log('Clone viewer: A/B polygons, right/arbitrary rotations, resizing and combined reflection alignment passed');
} finally {await browser.close();}
