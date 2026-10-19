import assert from 'node:assert/strict';
import { advanceTarget, decidedKey, DecisionOutbox, newEventId, sendDecision } from '../lib/decisionQueue.ts';
const r=(id)=>({id,run_id:'run'});
// Navigation known: the first undecided item not decided in this session.
const nav={next_undecided:r('b'),upcoming:[r('b'),r('c'),r('d')]};
assert.deepEqual(advanceTarget(r('a'),nav,null,new Set()),r('b'));
assert.deepEqual(advanceTarget(r('a'),nav,null,new Set([decidedKey(r('b'))])),r('c'));
// Short list exhausted: nothing left. Full list exhausted: not yet known.
assert.equal(advanceTarget(r('a'),nav,null,new Set(['b','c','d'].map(x=>decidedKey(r(x))))),null);
const full={next_undecided:r('b'),upcoming:['b','c','d','e','f'].map(r)};
assert.equal(advanceTarget(r('a'),full,null,new Set(['b','c','d','e','f'].map(x=>decidedKey(r(x))))),undefined);
// Navigation not loaded: the previous item's list for THIS item, else wait.
assert.deepEqual(advanceTarget(r('b'),null,{from:r('b'),upcoming:[r('c'),r('d')]},new Set()),r('c'));
assert.equal(advanceTarget(r('x'),null,{from:r('b'),upcoming:[r('c')]},new Set()),undefined);
assert.equal(advanceTarget(r('b'),null,null,new Set()),undefined);
// A lost response is retried with the SAME event id.
const seen=[];let fail=2;
const fetcher=async(url,init)=>{const body=JSON.parse(init.body);seen.push(body.event_id);
  if(fail-->0)throw new Error('network');return {ok:true,status:200,json:async()=>({ok:true,decision:{event_id:body.event_id}})};};
const id=newEventId();assert.match(id,/^rv_[0-9a-f]{32}$/);
const saved=await sendDecision({project:'p',run:'run',item:'a',decision:'unsure',reviewer:'R',event_id:id},fetcher,3,async()=>{});
assert.equal(saved.event_id,id);assert.deepEqual(seen,[id,id,id]);
// The outbox marks an item decided at once, and un-marks and reports a failure.
const box=new DecisionOutbox(async body=>{if(body.item==='bad')throw new Error('refused');return body;});
const ok=box.submit({project:'p',run:'run',item:'a',decision:'unsure',reviewer:'R',event_id:'1'});
assert.ok(box.decided.has(decidedKey(r('a'))));assert.equal(box.pending.size,1);
await ok;assert.equal(box.pending.size,0);
await assert.rejects(box.submit({project:'p',run:'run',item:'bad',decision:'unsure',reviewer:'R',event_id:'2'}),/refused/);
assert.ok(!box.decided.has(decidedKey(r('bad'))));
assert.equal(box.failures.length,1);assert.equal(box.failures[0].error,'refused');
console.log('decision queue: advance targets, same-id retries, outbox failures passed');
