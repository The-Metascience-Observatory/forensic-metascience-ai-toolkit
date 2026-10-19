import assert from 'node:assert/strict';
import { imagePdfBoxes, projectImageBox } from '../lib/imagePdfBoxes.ts';
const placement = {page:2, document_path:'supplement.pdf', bbox_kind:'crop_exact',
  parent_size:[1000,500], transform:[400,0,0,200,50,70], page_size:[600,800], page_rotation:0};
const panel = {paper_dir:'paper',crop_box:[100,200,300,600],placements:[placement]};
// A resized 200x100 crop covers parent x=200..600, y=100..300.
// Its central half lands at PDF x=170..250, y=130..170.
assert.deepEqual(projectImageBox(panel,placement,[200,100],[50,25,150,75]),
  [[170,130],[250,130],[250,170],[170,170]]);
assert.deepEqual(projectImageBox(panel,{...placement,page_rotation:90},[200,100],[50,25,150,75]),
  [[670,170],[670,250],[630,250],[630,170]]);
// A rotated stream retains its quadrilateral instead of an enclosing rectangle.
assert.deepEqual(projectImageBox({...panel,crop_box:null},{...placement,bbox_kind:'stream_exact',transform:[0,400,-200,0,250,70]},[1000,500],[0,0,500,250]),
  [[250,70],[250,270],[150,270],[150,70]]);
for(const bad of [{bbox_kind:'parent_approximate'},{transform:undefined},{geometry_gap:'missing stream'}, {parent_size:[0,500]}]) {
  assert.equal(projectImageBox(panel,{...placement,...bad},[200,100],[50,25,150,75]),null);
}
const item={id:'pair',panels:[panel,panel],measurements:{inlier_box_a:[0,0,50,50],inlier_box_b:[0,0,50,50],flip:true}};
const boxes=imagePdfBoxes(item,[[200,100],[200,100]]);
assert.equal(boxes.length,2);
assert.equal(boxes[0].color,boxes[1].color);
assert.equal(boxes[0].documentPath,'supplement.pdf');
assert.equal(boxes[0].tid,'pair:a:0');
assert.equal(boxes[1].tid,'pair:b:0');
assert.equal(boxes[0].points[0][0],130);
assert.equal(boxes[1].points[0][0],250); // B unmirrored before PDF mapping
assert.deepEqual(imagePdfBoxes(item,[null,null]),[]);
for (const measurements of [undefined,null,{}]) {
  assert.deepEqual(imagePdfBoxes({...item,measurements},[[200,100],[200,100]]),[]);
}
const clone=imagePdfBoxes({...item,detector_kind:'intra_panel_clone',measurements:{regions:[{bbox:[0,0,50,50]},{bbox:[100,0,150,50]}]}},[[200,100],[200,100]]);
assert.equal(clone.length,2);
assert.equal(clone[0].tid,clone[1].tid);
assert.deepEqual(clone.map(box=>box.regionLabel),['A','B']);
console.log('PDF duplication geometry: crops, resize, mirror, rotation, clone and missing geometry passed');
const archivedPanel={...panel,document:{id:'source-id',path:'__runs/run/pdf'},
  placements:[{...placement,document_id:'source-id'}]};
assert.equal(imagePdfBoxes({...item,panels:[archivedPanel]},[[200,100]])[0].documentPath,'__runs/run/pdf');
const differentDocument={...archivedPanel,placements:[{...placement,document_id:'different-id'}]};
assert.equal(imagePdfBoxes({...item,panels:[differentDocument]},[[200,100]])[0].documentPath,'supplement.pdf');

assert.equal(projectImageBox({...panel,crop_box:null},placement,[200,100],[50,25,150,75]),null);

const polygonClone = imagePdfBoxes({...item, panels: [panel], detector_kind:'intra_panel_clone',
  measurements:{regions:[{bbox:[0,0,100,50],polygon:[[0,0],[100,0],[50,50]]}]}}, [[200,100]]);
assert.equal(polygonClone[0].points.length, 3);
assert.deepEqual(polygonClone[0].points, [[130,110],[210,110],[170,150]]);

const stalePanel={...panel,document:{id:'main-id',path:'/expired/work/main.pdf',role:'main'},
 placements:[{...placement,document_id:'main-id',document_path:'/expired/work/main.pdf'}]};
assert.equal(imagePdfBoxes({...item,panels:[stalePanel],papers:[{dir:'paper',pdf:'__runs/exact/main'}]},[[200,100]])[0].documentPath,'__runs/exact/main');
assert.deepEqual(imagePdfBoxes({...item,panels:[stalePanel],papers:[{dir:'paper',pdf:null}]},[[200,100]]),[]);
