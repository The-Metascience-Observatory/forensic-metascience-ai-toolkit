import assert from 'node:assert/strict';
import { imageXmlBoxes, projectXmlImageBox } from '../lib/imageXmlBoxes.ts';

// Retained embargoed-corpus example: crops and inlier coordinates are in different frames.
const name = 'oncotarget-08-111295-g002.jpg';
const figures = [{anchor:'xml-figure-2', label:'Figure 2', graphics:[{
  reference:name, relpath:`pmc_figures/${name}`, status:'local_current',
}]}];
const panel = (crop, segment) => ({uid:`pmc_figures:pmc:${name}-seg${segment}`,
  paper_dir:'paper', image:`__runs/run/crop${segment}`, parent_image:'/old/work/parent.png',
  crop_box:crop, figure_label:'Figure 2'});
const item = {id:'pair', detector_kind:'transformed_match', panels:[
  panel([123,26,212,138],1), panel([123,142,212,252],13),
], measurements:{panel_px_a:[112,89],panel_px_b:[110,89],
  inlier_box_a:[77.4,7.4,108.4,70],inlier_box_b:[3.2,20.5,34.2,82.9],flip:false}};
const boxes = imageXmlBoxes(item,'paper',figures,[[224,178],[220,178]]);
assert.equal(boxes.length,2);
assert.deepEqual(boxes.map(b=>b.label),['A','B']);
const close = (actual,expected) => expected.forEach((v,i)=>assert.ok(Math.abs(actual[i]-v)<1e-8));
close(projectXmlImageBox(boxes[0],[742,1025]),[103.4,130.4,134.4,193]);
close(projectXmlImageBox(boxes[1],[742,1025]),[145.2,143.5,176.2,205.9]);
assert.deepEqual(boxes[0].size,[112,89],'recorded detector size wins over preview size');
const flipped=imageXmlBoxes({...item,measurements:{...item.measurements,flip:true}},'paper',figures);
close(projectXmlImageBox(flipped[1],[742,1025]),[217.8,143.5,248.8,205.9]);

// Same label is insufficient, as are two ambiguous file matches or another paper.
assert.deepEqual(imageXmlBoxes(item,'another',figures),[]);
assert.deepEqual(imageXmlBoxes(item,'paper',[...figures,...figures]),[]);
const otherImage=[{...figures[0],graphics:[{reference:name,relpath:'publisher_figures/other.jpg',status:'available'}]}];
assert.deepEqual(imageXmlBoxes(item,'paper',otherImage),[]);
const sameNameOtherSource=[{...figures[0],graphics:[{reference:name,relpath:`publisher_figures/${name}`,status:'available'}]}];
assert.deepEqual(imageXmlBoxes(item,'paper',sameNameOtherSource),[],'same filename in another rendition channel is not the same frame');
const extensionless=[{...figures[0],graphics:[{...figures[0].graphics[0],reference:name.replace('.jpg','')}]}];
assert.equal(imageXmlBoxes(item,'paper',extensionless).length,2,'the source service has already resolved extensionless XML references');
const pdf={...item,panels:[{...item.panels[0],uid:'paper.pdf:xref1'}]};
assert.deepEqual(imageXmlBoxes(pdf,'paper',figures),[],'PDF geometry does not imply XML image geometry');
const archive=[{...figures[0],graphics:[{reference:name,relpath:'__runs/run/figure',status:'verified'}]}];
assert.equal(imageXmlBoxes(item,'paper',archive)[0].relpath,'__runs/run/figure');
const direct={...pdf,panels:[{...pdf.panels[0],parent_image:`pmc_figures/${name}`}]};
assert.equal(imageXmlBoxes(direct,'paper',figures).length,1,'exact source image path licenses the frame');

const whole={...item,panels:[{...item.panels[0],uid:`pmc_figures:pmc:${name}`,crop_box:null}],
  measurements:{panel_px_a:[371,512.5],inlier_box_a:[10,20,30,40]}};
close(projectXmlImageBox(imageXmlBoxes(whole,'paper',figures)[0],[742,1025]),[20,40,60,80]);
const missingSize={...item,measurements:{inlier_box_a:[0,0,10,10]}};
assert.equal(imageXmlBoxes(missingSize,'paper',figures).filter(b=>b.kind==='match').length,0);
assert.equal(imageXmlBoxes(missingSize,'paper',figures,[[112,89]]).filter(b=>b.kind==='match').length,1);
const unlocalized=imageXmlBoxes({...item,measurements:{}},'paper',figures);
for (const measurements of [undefined,null]) {
  assert.deepEqual(imageXmlBoxes({...item,measurements},'paper',figures),unlocalized,
    'Missing geometry may locate a known panel but must not invent a match');
}
assert.deepEqual(unlocalized.map(b=>b.kind),['panel','panel']);
close(projectXmlImageBox(unlocalized[0],[742,1025]),[26,123,138,212]);
const clone=imageXmlBoxes({...item,detector_kind:'intra_panel_clone',measurements:{panel_px_a:[112,89],
  regions:[{bbox:[1,2,10,20]},{bbox:[30,40,50,60]}]}},'paper',figures);
assert.deepEqual(clone.map(b=>b.label),['A1','A2']);
close(projectXmlImageBox(clone[1],[742,1025]),[56,163,76,183]);

// Invalid geometry must never leave a plausible but wrong rectangle.
for(const region of [[0,0,200,10],[NaN,0,1,1],[-1,0,3,3],[3,0,1,4]]) {
  assert.equal(projectXmlImageBox({...boxes[0],region},[742,1025]),null);
  assert.equal(imageXmlBoxes({...item,panels:[item.panels[0]],measurements:{panel_px_a:[112,89],inlier_box_a:region}},'paper',figures).length,0);
}
assert.equal(projectXmlImageBox(boxes[0],[100,100]),null,'crop outside image is refused');
assert.equal(projectXmlImageBox({...boxes[0],size:[0,89]},[742,1025]),null);
assert.equal(projectXmlImageBox({...boxes[0],crop:[5,2,4,9]},[742,1025]),null);
console.log('XML image boxes: embargoed-corpus crop mapping, source identity, scaling, mirrors, clones and invalid geometry passed');
