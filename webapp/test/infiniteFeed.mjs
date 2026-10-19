import assert from 'node:assert/strict';
import { queuePages } from '../lib/infiniteFeed.ts';
const page=(offset, revision='one', total=123)=>({revision,items:Array.from({length:Math.min(50,total-offset)},(_,n)=>({id:String(offset+n)})),pagination:{offset,limit:50,total,next_offset:offset+50<total?offset+50:null}});
let calls=[];
const fetchPage=async offset=>{calls.push(offset);return page(offset)};
let pages=await queuePages([],'refresh',fetchPage);
assert.deepEqual(calls,[0]);
pages=await queuePages(pages,'more',fetchPage);
assert.deepEqual(pages.flatMap(p=>p.items).map(i=>i.id),Array.from({length:100},(_,i)=>String(i)));
pages=await queuePages(pages,'more',fetchPage);
assert.equal(pages.flatMap(p=>p.items).length,123);
calls=[];assert.equal(await queuePages(pages,'more',fetchPage),pages);assert.deepEqual(calls,[]);
calls=[];pages=await queuePages(pages,'refresh',fetchPage);assert.deepEqual(calls,[0]);
// Reviews/filtering can reorder every page: replace the set atomically.
calls=[];pages=await queuePages(pages,'refresh',async offset=>{calls.push(offset);return page(offset,'two',110)});
assert.deepEqual(calls,[0,50,100]);assert.ok(pages.every(p=>p.revision==='two'));
const before=pages;
// A revision that changes DURING pagination is retaken, not an error: every
// saved review bumps the revision, and a reviewer saving in bulk was shown
// "Results changed while loading" in the middle of their own work.
calls=[];let settle=0;
pages=await queuePages(pages,'refresh',async offset=>{
  calls.push(offset);
  // First attempt: page 0 is 'five' and the rest 'six' (a write landed).
  // Second attempt: one consistent snapshot.
  if(settle===0&&offset>0){settle=1;return page(offset,'six',110)}
  return page(offset,settle?'six':'five',110)});
assert.ok(pages.every(p=>p.revision==='six'),'the retaken snapshot is consistent');
assert.equal(pages.flatMap(p=>p.items).length,110);
assert.ok(calls.length>3,'it paginated again rather than erroring');
// Still refuses when the queue never settles.
await assert.rejects(queuePages(pages,'refresh',async offset=>page(offset,offset?'four':'three')),/Results changed/);
assert.equal(pages.flatMap(p=>p.items).length,110);
void before;
// A next-page response from a new snapshot must never be appended to old rows.
calls=[];pages=await queuePages([page(0)],'more',async offset=>{calls.push(offset);return page(offset,'two')});
assert.deepEqual(calls,[50,0,50]);assert.ok(pages.every(p=>p.revision==='two'));
console.log('infinite queue: ordering, final page, refresh, snapshot changes and stale-page refusal passed');
