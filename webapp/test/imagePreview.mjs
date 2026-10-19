import assert from 'node:assert/strict';
import {previewBoxes} from '../lib/imagePreview.ts';
const ms = {inlier_box_a:[10,20,50,70],inlier_box_b:[10,5,40,35],flip:true};
assert.deepEqual(previewBoxes(ms,0,[100,80]),[[10,20,50,70]]);
assert.deepEqual(previewBoxes(ms,1,[200,60]),[[160,5,190,35]]);
assert.deepEqual(previewBoxes({regions:[{bbox:[1,2,30,40]},{bbox:[45,6,70,50]}],flip:true},0,[100,80],true),[[1,2,30,40],[45,6,70,50]]);
assert.deepEqual(previewBoxes(ms,2,[100,80]),[]);
for (const raw of [null,[],[1,2,3],[1,2,NaN,5],['1',2,3,5],[5,2,1,8],[0,0,0,2]]) {
  assert.deepEqual(previewBoxes({inlier_box_a:raw},0,[100,80]),[]);
}
assert.deepEqual(previewBoxes({inlier_box_a:[-5,10,120,90]},0,[100,80]),[[0,10,100,80]]);
assert.deepEqual(previewBoxes({inlier_box_a:[120,0,150,20]},0,[100,80]),[]);
assert.deepEqual(previewBoxes({},0,[100,80]),[]);
console.log('Hover preview boxes: native coordinates, mirrored B, clone, clipping and missing/invalid regions passed');
