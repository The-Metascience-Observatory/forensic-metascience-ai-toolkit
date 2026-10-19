import assert from 'node:assert/strict';
import {DEFAULT_FILTER, restoreFilter, matchRegionKind, matchRegionLabel} from '../app/images/lib.ts';
// The filter itself runs in the service: tests/test_workbench_match_region_filter.py.

const base = {id:'pair',kind:'within',detector_kind:'transformed_match',paper:{dir:'paper'},
  panels:[{uid:'a'},{uid:'b'}],screening:{decision:'issue'},region_coverage:{a:.21,b:.235}};
const filter = {...DEFAULT_FILTER, match_region:'partial_both',region_max_percent:80};
assert.equal(matchRegionKind(base), 'partial_both');
assert.equal(matchRegionLabel(base), 'Match boxes: A 21.0% · B 23.5%');
assert.equal(matchRegionKind({...base,region_coverage:{a:.2,b:.9}}), 'partial_one');
assert.equal(matchRegionKind({...base,region_coverage:{a:.9,b:.2}}), 'partial_one');
assert.equal(matchRegionKind({...base,region_coverage:{a:.8,b:.8}}), 'partial_both');
assert.equal(matchRegionKind({...base,region_coverage:{a:.81,b:.85}}), 'large_both');
assert.equal(matchRegionKind(base,20), 'large_both');
for (const coverage of [undefined,null,{a:0,b:.2},{a:NaN,b:.2},{a:.2,b:1.01}]) {
  const it = {...base,region_coverage:coverage};
  assert.equal(matchRegionKind(it),'unknown');
}
assert.deepEqual(restoreFilter(filter), filter);
assert.equal(restoreFilter({...filter,region_max_percent:0}).region_max_percent,80);
assert.equal(restoreFilter({...filter,match_region:'retired'}).match_region,'all');
assert.equal(restoreFilter({}).match_region,'all');
console.log('match region: both denominators, cutoff, unknowns and persistence passed');
