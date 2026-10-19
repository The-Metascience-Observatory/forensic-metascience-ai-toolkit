// Render the real item page against controlled read-only transport.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';

const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
try {
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  let item = {
    id:'within:paper:IMGDUP-1',run_id:'run',execution_id:'execution',kind:'within',
    source_id:'IMGDUP-1',detector_kind:'transformed_match',paper:{dir:'paper',title:'Context regression'},
    papers:[{dir:'paper',title:'Context regression'}],panels:[],targets:[],captions:{},measurements:{},
    rank:{score:1,reasons:['Detector match awaits contextual review.']},figure_labels:[],
    sentence:'Candidate comparison',cleared:false,adjudication:null,decision:null,
    publication_status:'unscreened',screening_status:'failed',scientific_disposition:null,
    screening:{decision:'unresolved',confidence:'low',validated:false,policy:'image-screen-v6',
      explanation:'The model recognized an overview and its detail, but context validation failed.',
      validation_errors:['Caption context unavailable.']},
  };
  await page.route('**/api/**',async route=>{
    const url=new URL(route.request().url());
    let body={};
    if(url.pathname==='/api/images') body={feed:{project:'test',items:[item],counts:{items:1},notes:[],runs:[],built_at:'now'}};
    else if(url.searchParams.get('method')==='item') body=item;
    else if(url.searchParams.get('method')==='status') body={ready:true,pending_writes:0};
    else if(url.searchParams.get('method')==='runs') body={runs:[]};
    await route.fulfill({json:body});
  });
  await page.goto(`${process.env.TEST_BASE_URL || 'http://localhost:3124'}/project/test/images/within%3Apaper%3AIMGDUP-1?run=latest`);
  await page.getByText('Screening failed — no validated scientific decision.').waitFor();
  assert.equal(await page.getByText('Cleared detector candidate',{exact:true}).count(),0);
  await page.getByText('Caption context unavailable.',{exact:true}).waitFor();
  if(process.env.TEST_SCREENSHOT) await page.screenshot({path:process.env.TEST_SCREENSHOT});
  item={...item,publication_status:'cleared',screening_status:'completed',scientific_disposition:'innocuous',
    screening:{...item.screening,decision:'innocuous',confidence:'high',validated:true,
      explanation:'The caption identifies Q as the magnified views of the same patients.',
      evidence_quote:'(Q) Magnified images show colocalization.',validation_errors:[]}};
  await page.reload();
  await page.getByText('Cleared detector candidate',{exact:true}).waitFor();
  await page.getByText('Validated scientific disposition: innocuous',{exact:true}).waitFor();
  await page.getByText('(Q) Magnified images show colocalization.',{exact:true}).waitFor();
  console.log('Actual item page distinguishes invalid screening from supported innocuous decisions and renders explanations/quotes.');
} finally {await browser.close();}
