import assert from 'node:assert/strict';
import { watchReviewSync } from '../lib/reviewSync.ts';

const original = {setTimeout, clearTimeout, now:Date.now};
let now=0, timerId=0, timers=new Map();
globalThis.setTimeout=(fn,delay)=>{const id=++timerId;timers.set(id,{fn,at:now+delay});return id;};
globalThis.clearTimeout=id=>timers.delete(id);
Date.now=()=>now;
const flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve();};
const tick=async(ms)=>{now+=ms;for(const [id,t] of [...timers])if(t.at<=now){timers.delete(id);t.fn();}await flush();};
let pending=0, failed=false, completed=0, reads=0, resolveRead, held=false, state;
const watcher=watchReviewSync({
 read:async()=>{reads++;if(held)return new Promise(r=>resolveRead=r);if(failed)throw Error('offline');return {pending_writes:pending};},
 update:s=>state=s, completed:()=>completed++, visible:()=>true,
});
try {
 await flush();
 // Already synchronized before the first post-save status response.
 watcher.saved();await flush();assert.equal(completed,1);
 pending=1;watcher.saved();await flush();
 const start=now;pending=0;await tick(4999);assert.equal(completed,1);
 await tick(1);assert.equal(completed,2);
 console.log('simulated acknowledgment-to-refresh delay:',now-start,'ms');
 assert.equal([...timers.values()][0].at-now,30000);
 // Saves arriving during a request force one fresh read, never overlapping reads.
 held=true;watcher.refresh();const before=reads;
 watcher.saved();watcher.saved();assert.equal(reads,before);
 resolveRead({pending_writes:0});await flush();assert.equal(completed,2);
 held=false;await tick(0);assert.equal(reads,before+1);assert.equal(completed,3);
 // Partial batch completion refreshes judgments even with another event pending.
 pending=2;watcher.saved();await flush();pending=1;await tick(5000);assert.equal(completed,4);
 failed=true;await tick(5000);assert.match(state.error,/unavailable/);
 assert.equal([...timers.values()][0].at-now,5000);
 failed=false;pending=0;await tick(5000);assert.equal(completed,5);
 // Pending writes keep the five-second cadence.
 pending=1;watcher.saved();await flush();await tick(30000);
 assert.equal([...timers.values()][0].at-now,5000);
 held=true;watcher.refresh();watcher.stop();resolveRead({pending_writes:0});await flush();
 assert.equal(timers.size,0);assert.equal(completed,5);
 console.log('review sync: immediate/delayed completion, concurrent saves, partial batches, offline recovery, backoff and cleanup passed');
} finally {
 watcher.stop();globalThis.setTimeout=original.setTimeout;globalThis.clearTimeout=original.clearTimeout;Date.now=original.now;
}
